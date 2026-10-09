"""Retrieval-augmented paper analysis: chunk, embed, store, retrieve, and summarize from sources."""

import io
import os
import re
import zipfile
from typing import Any, Protocol

from lxml import etree
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .llm import BACKEND_DIR, LLMError, request_options
from .persistence import EMBEDDING_DIM, PaperRecord, save_paper, search_chunks

EMBEDDING_MODEL = os.getenv("CLINICALPILOT_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
SUMMARY_TOP_K = 3
SUMMARY_MAX_CHUNKS = 10
SUMMARY_MAX_TOKENS = 16000
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NOT_STATED = "Not stated in the retrieved excerpts."

# One retrieval query per summary field, so each field is grounded in its own best matches.
FIELD_QUERIES = {
    "study_objective": "study objective, aim, hypothesis, primary research question",
    "population": "study population, participants, inclusion and exclusion criteria, sample size, demographics",
    "methods": "methods, study design, randomization, intervention, comparator, follow-up, statistical analysis",
    "results": "results, primary outcome, efficacy, effect size, adverse events, safety",
    "limitations": "limitations, bias, generalizability, under-represented groups, future work",
}

SUMMARY_SYSTEM = (
    "You summarize clinical research papers for trial analysts. "
    "Use only the numbered excerpts in the user message. Do not add facts from outside them. "
    f"If the excerpts do not cover a field, write exactly: {NOT_STATED} "
    "Write one or two plain sentences per field, with ASCII punctuation and no markdown. "
    "In cited_excerpts, list the numbers of the excerpts you relied on."
)


class UnsupportedDocument(ValueError):
    """The uploaded file type cannot be read, or it contains no text."""


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    """Local ONNX embeddings through fastembed. The model is downloaded on first use."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        cache_dir = os.getenv("FASTEMBED_CACHE_PATH", str(BACKEND_DIR / ".model_cache"))
        self._model = TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=cache_dir)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = FastEmbedEmbedder()
    return _embedder


class PaperSummary(BaseModel):
    study_objective: str
    population: str
    methods: str
    results: str
    limitations: str
    cited_excerpts: list[int] = Field(default_factory=list)


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            document = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as error:
        raise UnsupportedDocument("the .docx file could not be read") from error
    root = etree.fromstring(document, etree.XMLParser(resolve_entities=False, no_network=True))
    paragraphs = []
    for paragraph in root.iter(f"{{{WORD_NAMESPACE}}}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{{{WORD_NAMESPACE}}}t"))
        if text.strip():
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as error:
        raise UnsupportedDocument("the PDF could not be read") from error


def extract_text(filename: str, data: bytes) -> str:
    """Plain text of an uploaded .txt, .md, .pdf or .docx paper."""
    suffix = os.path.splitext(filename.lower())[1]
    if suffix == ".pdf" or data[:5] == b"%PDF-":
        text = _pdf_text(data)
    elif suffix == ".docx":
        text = _docx_text(data)
    elif suffix in ("", ".txt", ".md", ".text"):
        text = data.decode("utf-8", errors="replace")
    else:
        raise UnsupportedDocument(f"unsupported file type {suffix}; upload a .pdf, .docx, .txt or .md file")
    text = text.replace("\x00", "").strip()
    if not text:
        raise UnsupportedDocument("no text could be extracted from the file")
    return text


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks of about `size` characters that overlap by about `overlap`.

    Chunks end on a paragraph, sentence or word boundary when one falls in the second half of the window.
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    text = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            for boundary in ("\n\n", ". ", "\n", " "):
                position = window.rfind(boundary)
                if position >= size // 2:
                    end = start + position + len(boundary)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        next_start = max(end - overlap, start + 1)
        # Begin the next chunk at a word start instead of in the middle of a word.
        boundary = re.search(r"\s", text[next_start - 1 : end])
        if boundary and next_start - 1 + boundary.end() < end:
            next_start = next_start - 1 + boundary.end()
        start = next_start
    return chunks


def index_paper(session: Session, filename: str, text: str) -> PaperRecord:
    """Chunk a paper, embed the chunks and store them."""
    chunks = chunk_text(text)
    embeddings = get_embedder().embed_documents(chunks)
    return save_paper(session, filename, len(text), chunks, embeddings)


def search_papers(session: Session, query: str, top_k: int = 5, paper_id: int | None = None) -> list[dict[str, Any]]:
    """The chunks most similar to the query across indexed papers, best first."""
    embedding = get_embedder().embed_query(query)
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(f"query embedding has {len(embedding)} dimensions, expected {EMBEDDING_DIM}")
    return search_chunks(session, embedding, top_k=top_k, paper_id=paper_id)


def retrieve_for_summary(session: Session, paper_id: int) -> list[dict[str, Any]]:
    """Union of the top chunks for each summary field, in document order."""
    found: dict[int, dict[str, Any]] = {}
    for query in FIELD_QUERIES.values():
        for chunk in search_papers(session, query, top_k=SUMMARY_TOP_K, paper_id=paper_id):
            current = found.get(chunk["chunk_id"])
            if current is None or chunk["score"] > current["score"]:
                found[chunk["chunk_id"]] = chunk
    best = sorted(found.values(), key=lambda chunk: -chunk["score"])[:SUMMARY_MAX_CHUNKS]
    return sorted(best, key=lambda chunk: chunk["chunk_index"])


def source_entry(chunk: dict[str, Any]) -> dict[str, Any]:
    excerpt = chunk["content"] if len(chunk["content"]) <= 240 else chunk["content"][:237].rstrip() + "..."
    return {
        "chunk_id": chunk["chunk_id"],
        "paper": chunk["paper"],
        "chunk_index": chunk["chunk_index"],
        "score": chunk["score"],
        "excerpt": excerpt,
    }


def summarize_paper(session: Session, paper: PaperRecord, client: Any) -> dict[str, Any]:
    """Summarize a stored paper from its retrieved chunks only, and return the chunks used as sources."""
    chunks = retrieve_for_summary(session, paper.id)
    if not chunks:
        raise LLMError("The paper has no indexed chunks to summarize.")
    excerpts = "\n\n".join(f"[{number}] (chunk {chunk['chunk_index']})\n{chunk['content']}" for number, chunk in enumerate(chunks, start=1))
    response = client.messages.parse(
        **request_options(max_tokens=SUMMARY_MAX_TOKENS),
        system=SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": f"Paper: {paper.filename}\n\nExcerpts:\n\n{excerpts}\n\nSummarize this paper from the excerpts."}],
        output_format=PaperSummary,
    )
    if response.stop_reason == "refusal":
        raise LLMError("The model declined to summarize this paper.")
    summary = response.parsed_output
    if summary is None:
        raise LLMError(f"The model did not return a complete summary (stop reason: {response.stop_reason}).")
    cited = [number for number in dict.fromkeys(summary.cited_excerpts) if 1 <= number <= len(chunks)]
    used = [chunks[number - 1] for number in cited] or chunks
    return {
        "filename": paper.filename,
        "paper_id": paper.id,
        "chunks_indexed": paper.chunk_count,
        "study_objective": summary.study_objective,
        "population": summary.population,
        "methods": summary.methods,
        "results": summary.results,
        "limitations": summary.limitations,
        "sources": [source_entry(chunk) for chunk in used],
    }
