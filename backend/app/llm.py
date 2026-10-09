"""Claude client setup shared by the chat agent and the paper summarizer."""

import os
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]

# backend/.env is optional and never overrides variables already set in the environment.
load_dotenv(BACKEND_DIR / ".env")

MODEL = os.getenv("CLINICALPILOT_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("CLINICALPILOT_EFFORT", "medium")
MAX_TOKENS = int(os.getenv("CLINICALPILOT_MAX_TOKENS", "64000"))
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMNotConfigured(RuntimeError):
    """No Anthropic credentials are available to the server."""


class LLMError(RuntimeError):
    """The model call finished but did not produce a usable answer."""


def get_client() -> Any:
    client = anthropic.Anthropic()
    if client.api_key is None and client.auth_token is None and getattr(client, "credentials", None) is None:
        raise LLMNotConfigured("No Anthropic credentials found. Set ANTHROPIC_API_KEY in the environment or in backend/.env.")
    return client


def request_options(max_tokens: int = MAX_TOKENS) -> dict[str, Any]:
    """Keyword arguments shared by every model request."""
    options: dict[str, Any] = {"model": MODEL, "max_tokens": max_tokens, "output_config": {"effort": EFFORT}}
    if os.getenv("CLINICALPILOT_REFUSAL_FALLBACK", "").lower() in ("1", "true", "yes"):
        # Opt-in: let the API re-run a request the model declines on Anthropic's recommended fallback model.
        options["extra_headers"] = {"anthropic-beta": FALLBACK_BETA}
        options["extra_body"] = {"fallbacks": "default"}
    return options


def http_error(error: Exception) -> tuple[int, str]:
    """Map a model-call failure to an HTTP status and a message that is safe to return."""
    if isinstance(error, LLMNotConfigured):
        return 503, str(error)
    if isinstance(error, LLMError):
        return 502, str(error)
    if isinstance(error, anthropic.AuthenticationError):
        return 503, "The Anthropic API rejected the configured credentials."
    if isinstance(error, anthropic.RateLimitError):
        return 429, "The Anthropic API rate limit was reached. Try again shortly."
    if isinstance(error, anthropic.APIStatusError):
        return 502, f"The Anthropic API returned an error (status {error.status_code})."
    if isinstance(error, anthropic.APIConnectionError):
        return 502, "Could not reach the Anthropic API."
    raise error
