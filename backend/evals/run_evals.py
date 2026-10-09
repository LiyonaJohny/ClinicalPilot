"""Score the chat agent against the golden questions and record the result.

Run from the repository root (needs Anthropic credentials, see backend/.env.example):

    .venv\\Scripts\\python.exe backend\\evals\\run_evals.py

Check the golden answers against the tools without calling the LLM:

    .venv\\Scripts\\python.exe backend\\evals\\run_evals.py --check-golden

An answer is correct when the value on its final "ANSWER:" line matches the expected value.
An answer is grounded when the agent made at least one successful tool call and cited a source.
"""

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import anthropic  # noqa: E402

from app import agent, llm  # noqa: E402

EVALS_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = EVALS_DIR / "golden.json"
RESULTS_PATH = EVALS_DIR / "results.json"
ANSWER_INSTRUCTION = (
    "\n\nFinish with a final line in exactly this form: ANSWER: <value>, "
    "where <value> is only the number or identifier asked for, with no units or extra words."
)
ANSWER_LINE = re.compile(r"^\s*ANSWER:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def load_golden(path: Path = GOLDEN_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def final_answer(answer: str) -> str | None:
    """The value on the last ANSWER: line, or None when the answer has no such line."""
    matches = ANSWER_LINE.findall(answer)
    return matches[-1] if matches else None


def score_answer(item: dict[str, Any], answer: str) -> tuple[bool, str]:
    """Return (correct, explanation) for one answer."""
    value = final_answer(answer)
    if value is None:
        return False, "no ANSWER line"
    expected = item["expected"]
    if item["answer_type"] == "number":
        found = NUMBER.search(value.replace(",", ""))
        if found is None:
            return False, f"no number in ANSWER line {value!r}"
        got = float(found.group())
        correct = abs(got - float(expected)) <= float(item.get("tolerance", 0)) + 1e-9
        return correct, f"got {found.group()}, expected {expected}"
    correct = str(expected).strip().lower() in value.lower()
    return correct, f"got {value!r}, expected {expected!r}"


def is_grounded(result: dict[str, Any]) -> bool:
    succeeded = any(not call["is_error"] for call in result.get("tool_calls", []))
    return succeeded and bool(result.get("sources"))


def lookup(result: Any, path: str) -> Any:
    for key in path.split("."):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def check_golden(items: list[dict[str, Any]]) -> list[str]:
    """Recompute every expected value with the tools. Returns a list of mismatches (empty when all agree)."""
    problems = []
    for item in items:
        check = item["check"]
        result, _ = agent.execute_tool(check["tool"], check["input"])
        value = lookup(result, check["path"])
        if item["answer_type"] == "number":
            agrees = abs(float(value) - float(item["expected"])) <= float(item.get("tolerance", 0)) + 1e-9
        else:
            agrees = str(value) == str(item["expected"])
        if not agrees:
            problems.append(f"{item['id']}: tool returned {value!r}, golden expects {item['expected']!r}")
    return problems


def evaluate(items: list[dict[str, Any]], ask: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """Ask every question and score the answers. `ask` returns the agent's result for one question."""
    scored = []
    for item in items:
        entry: dict[str, Any] = {"id": item["id"], "question": item["question"], "expected": item["expected"]}
        try:
            result = ask(item["question"] + ANSWER_INSTRUCTION)
        except (llm.LLMError, anthropic.APIError) as error:
            entry.update(correct=False, grounded=False, detail=f"error: {error}", answer=None, tools=[], sources=[])
        else:
            correct, detail = score_answer(item, result["answer"])
            entry.update(
                correct=correct,
                grounded=is_grounded(result),
                detail=detail,
                answer=result["answer"],
                tools=[call["name"] for call in result["tool_calls"]],
                sources=result["sources"],
            )
        scored.append(entry)
        print(f"{entry['id']}  {'PASS' if entry['correct'] else 'FAIL'}  {'grounded' if entry['grounded'] else 'ungrounded'}  {entry['detail']}")
    return {
        "total": len(scored),
        "correct": sum(entry["correct"] for entry in scored),
        "grounded": sum(entry["grounded"] for entry in scored),
        "correct_and_grounded": sum(entry["correct"] and entry["grounded"] for entry in scored),
        "items": scored,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the ClinicalPilot chat agent against the golden questions.")
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--out", type=Path, default=RESULTS_PATH)
    parser.add_argument("--limit", type=int, default=None, help="only run the first N questions")
    parser.add_argument("--check-golden", action="store_true", help="verify the golden answers against the tools, without the LLM")
    args = parser.parse_args()

    items = load_golden(args.golden)
    problems = check_golden(items)
    if problems:
        print("The golden file disagrees with the tools:", *problems, sep="\n  ")
        return 1
    if args.check_golden:
        print(f"All {len(items)} golden answers match the tools.")
        return 0

    try:
        client = llm.get_client()
    except llm.LLMNotConfigured as error:
        print(error)
        return 2

    items = items[: args.limit] if args.limit else items
    summary = evaluate(items, lambda question: agent.answer_question(question, client))
    report = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": llm.MODEL,
        "effort": llm.EFFORT,
        "golden": args.golden.name,
        **summary,
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"\nCorrect: {report['correct']}/{report['total']}  "
        f"Grounded: {report['grounded']}/{report['total']}  "
        f"Correct and grounded: {report['correct_and_grounded']}/{report['total']}"
    )
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
