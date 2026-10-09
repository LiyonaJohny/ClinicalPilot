import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anthropic
import pandas as pd
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import agent, llm, rag
from .cda import CdaError, ingest_document, reject_document
from .fhir import BundleError, ingest_bundle
from .persistence import (
    PatientRecord,
    init_db,
    patient_to_dict,
    save_analysis_history,
    save_cohort,
    save_dataset_profile,
    save_generated_report,
    session_scope,
    storage_summary,
)
from .quality import profile_dataset, discover_cohort, evaluate_protocol

app = FastAPI(title="ClinicalPilot AI API", version="0.2.0")
SAMPLE_DATASET = Path(__file__).resolve().parents[2] / "sample_data" / "cardiovascular_phase_ii.csv"
LLM_ERRORS = (llm.LLMNotConfigured, llm.LLMError, anthropic.APIError)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "clinicalpilot-ai"}


def load_sample_dataset() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DATASET)


def llm_http_exception(error: Exception) -> HTTPException:
    status, detail = llm.http_error(error)
    return HTTPException(status_code=status, detail=detail)


@app.get("/datasets")
def list_datasets() -> dict:
    frame = load_sample_dataset()
    return {
        "datasets": [
            {
                "name": "Cardiovascular_Phase_II.csv",
                "path": str(SAMPLE_DATASET),
                "rows": len(frame),
                "columns": list(frame.columns),
            }
        ]
    }


@app.post("/datasets/profile")
async def upload_dataset(file: UploadFile = File(...)) -> dict:
    if file.filename and file.filename.endswith((".xlsx", ".xls")):
        frame = pd.read_excel(file.file)
    else:
        frame = pd.read_csv(file.file)
    profile = profile_dataset(frame)
    with session_scope() as session:
        save_dataset_profile(session, file.filename or "uploaded_dataset", profile)
        save_analysis_history(session, "dataset_profile", file.filename or "uploaded_dataset", profile)
    return profile


@app.get("/datasets/demo-profile")
def demo_profile() -> dict:
    frame = load_sample_dataset()
    return profile_dataset(frame)


@app.post("/ingest/fhir")
def ingest_fhir(bundle: Any = Body(...)) -> dict:
    """Validate a FHIR R4 Bundle and load its Patient, Condition and Observation resources."""
    failure = None
    with session_scope() as session:
        try:
            result = ingest_bundle(bundle, session).model_dump()
        except BundleError as error:
            # Leave the scope normally so the rejected bundle is still recorded.
            failure = str(error)
        else:
            summary = {key: value for key, value in result.items() if key != "patients"}
            save_analysis_history(session, "fhir_ingestion", f"Bundle with {result['patients_ingested']} patients", summary)
    if failure is not None:
        raise HTTPException(status_code=422, detail=f"Not a valid FHIR Bundle: {failure}")
    return result


@app.post("/ingest/cda")
async def ingest_cda(file: UploadFile = File(...)) -> dict:
    """Parse a C-CDA XML document and load its patient, problems and vital signs."""
    data = await file.read()
    failure = None
    with session_scope() as session:
        try:
            result = ingest_document(data, session).model_dump()
        except CdaError as error:
            failure = str(error)
            reject_document(session, failure, data)
        else:
            summary = {key: value for key, value in result.items() if key != "patients"}
            save_analysis_history(session, "cda_ingestion", file.filename or "uploaded_document", summary)
    if failure is not None:
        raise HTTPException(status_code=422, detail=f"Not a valid C-CDA document: {failure}")
    return result


@app.get("/patients")
def list_patients(limit: int = 100, offset: int = 0) -> dict:
    """Patients loaded through FHIR and CDA ingestion."""
    limit = max(1, min(limit, 500))
    with session_scope() as session:
        total = session.query(PatientRecord).count()
        records = session.query(PatientRecord).order_by(PatientRecord.id).offset(max(0, offset)).limit(limit).all()
        return {"total": total, "patients": [patient_to_dict(record) for record in records]}


@app.post("/cohorts/discover")
def cohort_discovery(filters: dict) -> dict:
    result = discover_cohort(filters, load_sample_dataset())
    with session_scope() as session:
        save_cohort(session, str(filters.get("name", "Cohort Discovery")), filters, result)
        save_analysis_history(session, "cohort_discovery", str(filters), result)
    return result


@app.post("/protocols/check")
def protocol_check(payload: dict) -> dict:
    criteria = payload.get("criteria", "")
    result = evaluate_protocol(criteria, load_sample_dataset())
    with session_scope() as session:
        save_analysis_history(session, "protocol_check", criteria, result)
    return result


@app.post("/papers/analyze")
async def analyze_paper(file: UploadFile = File(...)) -> dict:
    """Index an uploaded paper for retrieval and summarize it from the retrieved chunks."""
    filename = file.filename or "uploaded_paper"
    data = await file.read()
    try:
        text = rag.extract_text(filename, data)
    except rag.UnsupportedDocument as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    try:
        client = llm.get_client()
        with session_scope() as session:
            paper = rag.index_paper(session, filename, text)
            result = rag.summarize_paper(session, paper, client)
            save_analysis_history(session, "paper_analysis", filename, result)
    except LLM_ERRORS as error:
        raise llm_http_exception(error) from error
    return result


@app.get("/papers/search")
def paper_search(query: str, top_k: int = 5) -> dict:
    """Retrieve the paper chunks most similar to a query, without calling the LLM."""
    if not query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    with session_scope() as session:
        chunks = rag.search_papers(session, query, top_k=max(1, min(top_k, 10)))
    return {"query": query, "results": [rag.source_entry(chunk) for chunk in chunks]}


def _question(payload: dict) -> str:
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=422, detail="question must be a non-empty string")
    return question.strip()


def _save_chat(result: dict) -> None:
    with session_scope() as session:
        save_analysis_history(session, "dataset_chat", result["question"], result)


@app.post("/chat")
def chat_with_dataset(payload: dict) -> dict:
    """Answer a question with tool calling and return the complete answer."""
    question = _question(payload)
    try:
        result = agent.answer_question(question, llm.get_client())
    except LLM_ERRORS as error:
        raise llm_http_exception(error) from error
    _save_chat(result)
    return result


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.post("/chat/stream")
def chat_stream(payload: dict) -> StreamingResponse:
    """Answer a question as server-sent events: token, tool_call, tool_result, then done or error."""
    question = _question(payload)
    try:
        client = llm.get_client()
    except llm.LLMNotConfigured as error:
        raise llm_http_exception(error) from error

    def events() -> Iterator[str]:
        try:
            for event in agent.run_agent(question, client):
                kind = event.pop("type")
                if kind == "done":
                    _save_chat(event)
                yield _sse(kind, event)
        except LLM_ERRORS as error:
            _, detail = llm.http_error(error)
            yield _sse("error", {"detail": detail})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/reports")
def save_report(payload: dict) -> dict:
    title = payload.get("title", "Untitled Study Report")
    dataset_name = payload.get("dataset_name", "Unknown Dataset")
    content = payload.get("content", "")
    metadata = payload.get("metadata", {})
    result = {
        "title": title,
        "dataset_name": dataset_name,
        "content_length": len(content),
        "metadata": metadata,
    }
    with session_scope() as session:
        report = save_generated_report(session, title, dataset_name, content, metadata)
        save_analysis_history(session, "generated_report", title, result)
        report_id = report.id
    return {"id": report_id, "status": "saved", **result}


@app.get("/storage/summary")
def get_storage_summary() -> dict[str, int]:
    with session_scope() as session:
        return storage_summary(session)
