"""Shared test setup: an isolated SQLite database and fakes for the LLM and the embedder.

No test calls the Anthropic API or downloads an embedding model, so the suite runs in CI without an API key.
"""

import atexit
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE_DATA = BACKEND_DIR.parent / "sample_data"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# The engine is created when app.persistence is first imported, so the database is chosen once per process.
if "app.persistence" not in sys.modules:
    _test_db = Path(tempfile.gettempdir()) / f"clinicalpilot_tests_{os.getpid()}.db"
    if _test_db.exists():
        _test_db.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{_test_db.as_posix()}"

from app.persistence import EMBEDDING_DIM, engine, init_db  # noqa: E402

init_db()


@atexit.register
def _remove_test_database() -> None:
    engine.dispose()
    database = engine.url.database
    if database and Path(database).name.startswith("clinicalpilot_tests_"):
        Path(database).unlink(missing_ok=True)


class FakeEmbedder:
    """Deterministic bag-of-words embeddings: texts that share words get similar vectors."""

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % EMBEDDING_DIM
            vector[bucket] += 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def tool_use_block(tool_id: str, name: str, tool_input: Any) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)


def message(content: list[SimpleNamespace], stop_reason: str = "end_turn", parsed_output: Any = None) -> SimpleNamespace:
    return SimpleNamespace(content=content, stop_reason=stop_reason, parsed_output=parsed_output)


class FakeStream:
    def __init__(self, final: SimpleNamespace) -> None:
        self._final = final

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        return False

    @property
    def text_stream(self) -> Any:
        for block in self._final.content:
            if block.type == "text":
                # Split into small pieces so tests can see incremental delivery.
                for piece in re.findall(r"\S+\s*", block.text):
                    yield piece

    def get_final_message(self) -> SimpleNamespace:
        return self._final


class FakeMessages:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def _next(self, kwargs: dict[str, Any]) -> SimpleNamespace:
        # The agent appends to its message list after each call, so keep a snapshot of what was sent.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        if not self._responses:
            raise AssertionError("the fake LLM was called more times than it has scripted responses")
        return self._responses.pop(0)

    def stream(self, **kwargs: Any) -> FakeStream:
        return FakeStream(self._next(kwargs))

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        return self._next(kwargs)


class FakeClient:
    """Stands in for anthropic.Anthropic with a scripted list of responses."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.messages = FakeMessages(responses)
