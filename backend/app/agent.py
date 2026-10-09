"""Tool-calling chat agent: Claude answers dataset and paper questions by calling ClinicalPilot tools."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .llm import LLMError, request_options
from .persistence import patients_frame, session_scope
from .quality import dataset_stats, query_cohort
from .rag import search_papers

SAMPLE_DATASET = Path(__file__).resolve().parents[2] / "sample_data" / "cardiovascular_phase_ii.csv"
SAMPLE_DATASET_NAME = "Cardiovascular_Phase_II.csv"
INGESTED_DATASET_NAME = "Ingested patients (FHIR and CDA)"
MAX_TURNS = 8

SYSTEM_PROMPT = (
    "You are Pilot AI, the analyst inside ClinicalPilot. You answer questions about a clinical trial "
    "dataset and about research papers the user has uploaded.\n\n"
    "Ground every answer in tool results. Never state a count, percentage or statistic from memory or by "
    "estimating: call discover_cohort or dataset_stats and report what they return. For anything about an "
    "uploaded paper, call search_papers and answer only from the returned excerpts, citing each one you use "
    "as [filename, chunk N]. If the tools cannot answer the question, say so plainly instead of guessing.\n\n"
    "All dataset tools count unique patients: rows that repeat a PatientID are counted once. Tool results "
    "include notes about data quality, such as missing blood pressure values or implausible ages; mention a "
    "note when it affects the number you report. The default dataset is the packaged sample trial dataset; "
    "use dataset \"ingested\" only when the user asks about ingested FHIR or CDA patients.\n\n"
    "Lead with the answer, then give one short line of context such as the denominator or the filter you "
    "applied. The interface shows plain text, so write plain sentences with ASCII punctuation and no markdown."
)

COHORT_FILTER_PROPERTIES: dict[str, Any] = {
    "min_age": {"type": "number", "description": "Minimum age in years, inclusive."},
    "max_age": {"type": "number", "description": "Maximum age in years, inclusive."},
    "gender": {"type": "string", "description": "M or F."},
    "race": {"type": "string"},
    "site": {"type": "string", "description": "Trial site code, for example NYC-01."},
    "treatment": {"type": "string", "description": "Treatment arm, for example Compound-X or Standard Care."},
    "outcome": {"type": "string", "description": "Outcome, for example Controlled, Uncontrolled or Readmitted."},
    "diagnosis_contains": {"type": "string", "description": "Case-insensitive text that the Diagnosis column must contain."},
    "diabetes_type2": {"type": "boolean"},
    "hypertension": {"type": "boolean"},
    "kidney_disease": {"type": "boolean"},
    "min_systolic_bp": {"type": "number", "description": "Minimum systolic blood pressure in mmHg, inclusive."},
    "max_systolic_bp": {"type": "number", "description": "Maximum systolic blood pressure in mmHg, inclusive."},
    "min_diastolic_bp": {"type": "number", "description": "Minimum diastolic blood pressure in mmHg, inclusive."},
    "max_diastolic_bp": {"type": "number", "description": "Maximum diastolic blood pressure in mmHg, inclusive."},
    "missing_bp": {"type": "boolean", "description": "True keeps only patients with a missing blood pressure value; false keeps only patients with both values."},
    "exclude_invalid_age": {"type": "boolean", "description": "True leaves out patients whose age is outside 0-120."},
}
COHORT_FILTER_SCHEMA = {"type": "object", "properties": COHORT_FILTER_PROPERTIES, "additionalProperties": False}
DATASET_PROPERTY = {
    "type": "string",
    "enum": ["sample", "ingested"],
    "description": "sample (default) is the packaged trial dataset; ingested is patients loaded through FHIR or CDA ingestion.",
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "discover_cohort",
        "description": (
            "Count the unique patients that match a set of filters and list them. All filters are optional and "
            "combine with AND; range filters are inclusive, so use min_age 61 for 'older than 60'. With no filters it "
            "returns the whole population. Returns matching_patients, total_patients, population_share (percent), "
            "patient_ids, a preview of up to 10 patients, and data-quality notes. Use this for any 'how many', "
            "'which patients' or 'what share' question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"filters": COHORT_FILTER_SCHEMA, "dataset": DATASET_PROPERTY},
            "required": ["filters"],
            "additionalProperties": False,
        },
    },
    {
        "name": "dataset_stats",
        "description": (
            "Summary statistics over unique patients. With a column it returns that column's statistics: count, "
            "missing, mean, median, min, max and the patient ids holding the min and max for numeric columns; true and "
            "false counts for boolean columns; value counts for text columns. For Age it also returns valid_only, "
            "which excludes implausible ages. Without a column it returns a dataset overview: rows, unique_patients, "
            "duplicate_rows, columns, invalid_ages and missing_values per column. Pass filters to compute the "
            "statistics inside a cohort, for example the mean SystolicBP of patients on one treatment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "column": {"type": "string", "description": "Column name, for example Age, SystolicBP, Outcome or Site. Omit for the dataset overview."},
                "filters": COHORT_FILTER_SCHEMA,
                "dataset": DATASET_PROPERTY,
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "search_papers",
        "description": (
            "Semantic search over the research papers uploaded to ClinicalPilot. Returns the most relevant text "
            "excerpts with the paper filename, chunk index and similarity score. Use this for any question about "
            "what a paper says; an empty result means no uploaded paper covers the query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, phrased as a topic or question."},
                "top_k": {"type": "integer", "description": "How many excerpts to return, 1 to 10. Default 5."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]


class CohortFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_age: float | None = None
    max_age: float | None = None
    gender: str | None = None
    race: str | None = None
    site: str | None = None
    treatment: str | None = None
    outcome: str | None = None
    diagnosis_contains: str | None = None
    diabetes_type2: bool | None = None
    hypertension: bool | None = None
    kidney_disease: bool | None = None
    min_systolic_bp: float | None = None
    max_systolic_bp: float | None = None
    min_diastolic_bp: float | None = None
    max_diastolic_bp: float | None = None
    missing_bp: bool | None = None
    exclude_invalid_age: bool | None = None


class DiscoverCohortInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filters: CohortFilters = Field(default_factory=CohortFilters)
    dataset: Literal["sample", "ingested"] = "sample"


class DatasetStatsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str | None = None
    filters: CohortFilters = Field(default_factory=CohortFilters)
    dataset: Literal["sample", "ingested"] = "sample"


class SearchPapersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)


def load_sample_dataset() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DATASET)


def _load_frame(dataset: str) -> tuple[pd.DataFrame, str]:
    if dataset == "sample":
        return load_sample_dataset(), SAMPLE_DATASET_NAME
    with session_scope() as session:
        frame = patients_frame(session)
    if frame.empty:
        raise ValueError("no patients have been ingested yet; load a FHIR Bundle or C-CDA document first")
    return frame, INGESTED_DATASET_NAME


def execute_tool(name: str, tool_input: Any) -> tuple[dict[str, Any], list[str]]:
    """Run one tool call. Returns the JSON-serializable result and the sources it drew on.

    Raises ValueError (including pydantic's ValidationError) when the input is invalid; the caller reports
    that back to the model as a tool error.
    """
    if name == "discover_cohort":
        args = DiscoverCohortInput.model_validate(tool_input)
        frame, source = _load_frame(args.dataset)
        return query_cohort(args.filters.model_dump(exclude_none=True), frame), [source]
    if name == "dataset_stats":
        stats_args = DatasetStatsInput.model_validate(tool_input)
        frame, source = _load_frame(stats_args.dataset)
        return dataset_stats(stats_args.column, frame, stats_args.filters.model_dump(exclude_none=True)), [source]
    if name == "search_papers":
        search_args = SearchPapersInput.model_validate(tool_input)
        with session_scope() as session:
            chunks = search_papers(session, search_args.query, top_k=search_args.top_k)
        results = [{"paper": chunk["paper"], "chunk": chunk["chunk_index"], "score": chunk["score"], "text": chunk["content"]} for chunk in chunks]
        return {"query": search_args.query, "results": results}, [f"{chunk['paper']} (chunk {chunk['chunk_index']})" for chunk in chunks]
    raise ValueError(f"unknown tool {name!r}")


def _describe_error(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(str(item) for item in issue['loc']) or 'input'}: {issue['msg']}" for issue in error.errors())
    return str(error)


def _text_of(content: list[Any]) -> str:
    return "".join(block.text for block in content if block.type == "text").strip()


def run_agent(
    question: str,
    client: Any,
    tool_executor: Callable[[str, Any], tuple[dict[str, Any], list[str]]] = execute_tool,
    max_turns: int = MAX_TURNS,
) -> Iterator[dict[str, Any]]:
    """Answer a question with streaming and tool calling.

    Yields events as they happen:
      {"type": "token", "text": ...}        a piece of model text
      {"type": "tool_call", ...}            the model asked for a tool; text streamed so far was not the answer
      {"type": "tool_result", ...}          the tool finished (or failed, with is_error true)
      {"type": "done", ...}                 the final answer with its sources and tool calls
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    sources: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for _ in range(max_turns):
        with client.messages.stream(**request_options(), system=SYSTEM_PROMPT, tools=TOOLS, messages=messages) as stream:
            for text in stream.text_stream:
                yield {"type": "token", "text": text}
            response = stream.get_final_message()

        if response.stop_reason == "refusal":
            raise LLMError("The model declined to answer this question.")
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        tool_uses = [block for block in response.content if block.type == "tool_use"]
        if not tool_uses:
            if response.stop_reason == "max_tokens":
                raise LLMError("The answer was cut off at the token limit.")
            answer = _text_of(response.content)
            if not answer:
                raise LLMError("The model returned an empty answer.")
            yield {
                "type": "done",
                "question": question,
                "answer": answer,
                "sources": sources,
                "tool_calls": tool_calls,
            }
            return
        if response.stop_reason == "max_tokens":
            # A truncated tool input can parse as a valid partial object, so it must not be run.
            raise LLMError("A tool call was cut off at the token limit.")

        results = []
        for block in tool_uses:
            yield {"type": "tool_call", "id": block.id, "name": block.name, "input": block.input}
            try:
                result, used = tool_executor(block.name, block.input)
            except ValueError as error:
                message = _describe_error(error)
                tool_calls.append({"name": block.name, "input": block.input, "is_error": True})
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": message, "is_error": True})
                yield {"type": "tool_result", "id": block.id, "name": block.name, "is_error": True, "error": message}
                continue
            tool_calls.append({"name": block.name, "input": block.input, "is_error": False})
            for source in used:
                if source not in sources:
                    sources.append(source)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)})
            yield {"type": "tool_result", "id": block.id, "name": block.name, "is_error": False}
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})

    raise LLMError(f"The model did not finish within {max_turns} tool-calling turns.")


def answer_question(question: str, client: Any) -> dict[str, Any]:
    """Run the agent to completion and return the final answer payload."""
    for event in run_agent(question, client):
        if event["type"] == "done":
            return {key: value for key, value in event.items() if key != "type"}
    raise LLMError("The agent ended without an answer.")
