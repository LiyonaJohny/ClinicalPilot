import os
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi.encoders import jsonable_encoder
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Select, String, Text, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

EMBEDDING_DIM = 384


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./clinicalpilot.db")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _connect_args(url: str) -> dict[str, Any]:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


class Base(DeclarativeBase):
    pass


class DatasetRecord(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    columns: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class CohortRecord(Base):
    __tablename__ = "cohorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    matching_patients: Mapped[int] = mapped_column(Integer, nullable=False)
    population_share: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_type: Mapped[str] = mapped_column(String(80), nullable=False)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class PatientRecord(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    race: Mapped[str | None] = mapped_column(String(128), nullable=True)
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    systolic_bp: Mapped[float | None] = mapped_column(Float, nullable=True)
    diastolic_bp: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lab_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    diabetes_type2: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hypertension: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kidney_disease: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)


class IngestionReject(Base):
    __tablename__ = "ingestion_rejects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class PaperRecord(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class PaperChunk(Base):
    __tablename__ = "paper_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    paper_id: Mapped[int] = mapped_column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector column on PostgreSQL; a JSON list of floats on SQLite (local dev and tests).
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite"), nullable=False)


engine = create_engine(_database_url(), connect_args=_connect_args(_database_url()))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Any:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_dataset_profile(session: Session, name: str, profile: dict[str, Any]) -> DatasetRecord:
    profile = jsonable_encoder(profile)
    record = DatasetRecord(
        name=name,
        row_count=int(profile["rows"]),
        columns=list(profile["columns"]),
        profile=profile,
    )
    session.add(record)
    session.flush()
    return record


def save_generated_report(session: Session, title: str, dataset_name: str, content: str, metadata: dict[str, Any]) -> GeneratedReport:
    metadata = jsonable_encoder(metadata)
    record = GeneratedReport(
        title=title,
        dataset_name=dataset_name,
        content=content,
        metadata_json=metadata,
    )
    session.add(record)
    session.flush()
    return record


def save_cohort(session: Session, name: str, filters: dict[str, Any], result: dict[str, Any]) -> CohortRecord:
    filters = jsonable_encoder(filters)
    result = jsonable_encoder(result)
    record = CohortRecord(
        name=name,
        filters=filters,
        result=result,
        matching_patients=int(result["matching_patients"]),
        population_share=float(result["population_share"]),
    )
    session.add(record)
    session.flush()
    return record


def save_analysis_history(session: Session, analysis_type: str, input_summary: str, result: dict[str, Any]) -> AnalysisHistory:
    result = jsonable_encoder(result)
    record = AnalysisHistory(
        analysis_type=analysis_type,
        input_summary=input_summary,
        result=result,
    )
    session.add(record)
    session.flush()
    return record


PATIENT_FIELDS = (
    "source",
    "birth_date",
    "age",
    "gender",
    "race",
    "diagnosis",
    "systolic_bp",
    "diastolic_bp",
    "last_lab_date",
    "diabetes_type2",
    "hypertension",
    "kidney_disease",
    "conditions",
)


def upsert_patient(session: Session, row: dict[str, Any]) -> PatientRecord:
    record = session.query(PatientRecord).filter(PatientRecord.patient_id == row["patient_id"]).one_or_none()
    if record is None:
        record = PatientRecord(patient_id=row["patient_id"])
        session.add(record)
    for field in PATIENT_FIELDS:
        setattr(record, field, row[field])
    session.flush()
    return record


def save_ingestion_reject(
    session: Session,
    source: str,
    resource_type: str,
    resource_id: str | None,
    reason: str,
    payload: Any,
) -> IngestionReject:
    record = IngestionReject(
        source=source,
        resource_type=resource_type,
        resource_id=resource_id,
        reason=reason,
        payload=jsonable_encoder(payload),
    )
    session.add(record)
    session.flush()
    return record


def patient_to_dict(record: PatientRecord) -> dict[str, Any]:
    return {
        "PatientID": record.patient_id,
        "Source": record.source,
        "Age": record.age,
        "Gender": record.gender,
        "Race": record.race,
        "Diagnosis": record.diagnosis,
        "SystolicBP": record.systolic_bp,
        "DiastolicBP": record.diastolic_bp,
        "LastLabDate": record.last_lab_date.isoformat() if record.last_lab_date else None,
        "DiabetesType2": record.diabetes_type2,
        "Hypertension": record.hypertension,
        "KidneyDisease": record.kidney_disease,
    }


PATIENT_FRAME_COLUMNS = [
    "PatientID",
    "Source",
    "Age",
    "Gender",
    "Race",
    "Diagnosis",
    "SystolicBP",
    "DiastolicBP",
    "LastLabDate",
    "DiabetesType2",
    "Hypertension",
    "KidneyDisease",
]


def patients_frame(session: Session) -> pd.DataFrame:
    """Ingested FHIR and CDA patients in the same column layout as the sample CSV."""
    records = session.query(PatientRecord).order_by(PatientRecord.id).all()
    frame = pd.DataFrame([patient_to_dict(record) for record in records], columns=PATIENT_FRAME_COLUMNS)
    for column in ("Age", "SystolicBP", "DiastolicBP"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("DiabetesType2", "Hypertension", "KidneyDisease"):
        frame[column] = frame[column].astype(bool)
    return frame


def save_paper(session: Session, filename: str, char_count: int, chunks: list[str], embeddings: list[list[float]]) -> PaperRecord:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    paper = PaperRecord(filename=filename, char_count=char_count, chunk_count=len(chunks))
    session.add(paper)
    session.flush()
    for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(f"embedding has {len(embedding)} dimensions, expected {EMBEDDING_DIM}")
        session.add(PaperChunk(paper_id=paper.id, chunk_index=index, content=content, embedding=[float(value) for value in embedding]))
    session.flush()
    return paper


def pgvector_search_statement(query_embedding: list[float], top_k: int, paper_id: int | None) -> Select:
    """Nearest chunks by pgvector cosine distance (the <=> operator)."""
    distance = PaperChunk.embedding.cosine_distance(query_embedding)
    statement = select(PaperChunk, PaperRecord.filename, distance.label("distance")).join(PaperRecord, PaperRecord.id == PaperChunk.paper_id)
    if paper_id is not None:
        statement = statement.where(PaperChunk.paper_id == paper_id)
    return statement.order_by(distance).limit(top_k)


def search_chunks(session: Session, query_embedding: list[float], top_k: int = 5, paper_id: int | None = None) -> list[dict[str, Any]]:
    """Top matching chunks by cosine similarity, best first."""
    query_embedding = [float(value) for value in query_embedding]
    if session.get_bind().dialect.name == "postgresql":
        rows = session.execute(pgvector_search_statement(query_embedding, top_k, paper_id)).all()
        scored = [(chunk, filename, 1.0 - float(found)) for chunk, filename, found in rows]
    else:
        query = session.query(PaperChunk, PaperRecord.filename).join(PaperRecord, PaperRecord.id == PaperChunk.paper_id)
        if paper_id is not None:
            query = query.filter(PaperChunk.paper_id == paper_id)
        target = np.asarray(query_embedding, dtype=float)
        target_norm = float(np.linalg.norm(target))
        scored = []
        for chunk, filename in query.all():
            vector = np.asarray(chunk.embedding, dtype=float)
            denominator = float(np.linalg.norm(vector)) * target_norm
            scored.append((chunk, filename, float(vector @ target) / denominator if denominator else 0.0))
        scored.sort(key=lambda item: (-item[2], item[0].id))
        scored = scored[:top_k]
    return [
        {
            "chunk_id": chunk.id,
            "paper_id": chunk.paper_id,
            "paper": filename,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "score": round(score, 4),
        }
        for chunk, filename, score in scored
    ]


def storage_summary(session: Session) -> dict[str, int]:
    return {
        "datasets": session.query(DatasetRecord).count(),
        "generated_reports": session.query(GeneratedReport).count(),
        "cohorts": session.query(CohortRecord).count(),
        "analysis_history": session.query(AnalysisHistory).count(),
        "patients": session.query(PatientRecord).count(),
        "ingestion_rejects": session.query(IngestionReject).count(),
        "papers": session.query(PaperRecord).count(),
        "paper_chunks": session.query(PaperChunk).count(),
    }
