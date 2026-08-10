from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from .quality import profile_dataset, discover_cohort, evaluate_protocol

app = FastAPI(title="ClinicalPilot AI API", version="0.1.0")
SAMPLE_DATASET = Path(__file__).resolve().parents[2] / "sample_data" / "cardiovascular_phase_ii.csv"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "clinicalpilot-ai"}


def load_sample_dataset() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DATASET)


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
    return profile_dataset(frame)


@app.get("/datasets/demo-profile")
def demo_profile() -> dict:
    frame = load_sample_dataset()
    return profile_dataset(frame)


@app.post("/cohorts/discover")
def cohort_discovery(filters: dict) -> dict:
    return discover_cohort(filters, load_sample_dataset())


@app.post("/protocols/check")
def protocol_check(payload: dict) -> dict:
    return evaluate_protocol(payload.get("criteria", ""), load_sample_dataset())


@app.post("/papers/analyze")
async def analyze_paper(file: UploadFile = File(...)) -> dict:
    return {
        "filename": file.filename,
        "study_objective": "Evaluate treatment efficacy and safety against standard of care.",
        "population": "Adult participants across multi-site clinical settings.",
        "methods": "Randomized controlled trial with longitudinal follow-up.",
        "results": "Primary outcome improved with no material increase in serious adverse events.",
        "limitations": "Older adults and severe renal impairment groups were under-represented.",
    }


@app.post("/chat")
def chat_with_dataset(payload: dict) -> dict:
    question = payload.get("question", "")
    frame = load_sample_dataset()
    if "PatientID" in frame.columns:
        frame = frame.drop_duplicates(subset=["PatientID"], keep="first")
    diabetic = frame[frame["DiabetesType2"] == True]
    overlap = diabetic[diabetic["Hypertension"] == True]
    percent = round((len(overlap) / len(diabetic)) * 100) if len(diabetic) else 0
    return {
        "question": question,
        "answer": f"{percent}% of diabetic patients also have hypertension in the packaged cardiovascular dataset.",
        "sources": ["Cardiovascular_Phase_II.csv", "sample_data/cardiovascular_phase_ii.csv"],
    }
