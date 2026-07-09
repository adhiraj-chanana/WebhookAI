"""
Routing accuracy eval framework.

Runs the real route_webhook() against golden_dataset.json and reports
how often the LLM picks the expected action.

Usage:
    python -m evals.run_evals
    # or from the project root:
    python evals/run_evals.py
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Make sure the project root is on sys.path so `app.*` imports work
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.models import WebhookEnvelope, WebhookSource  # noqa: E402
from app.router import route_webhook  # noqa: E402

_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
_RESULTS_PATH = Path(__file__).parent / "results.json"

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_BOLD = "\033[1m"

_DELAY_BETWEEN_CALLS = 1.0  # seconds — avoid Anthropic rate limits


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_dataset() -> list[dict]:
    with open(_DATASET_PATH) as f:
        return json.load(f)


def _build_envelope(fixture: dict) -> WebhookEnvelope:
    return WebhookEnvelope(
        source=WebhookSource(fixture["source"]),
        event_type=fixture["event_type"],
        event_id=fixture.get("id"),
        raw_payload=fixture["payload"],
    )


def _conf_color(confidence: float) -> str:
    if confidence >= 0.85:
        return _GREEN
    if confidence >= 0.70:
        return _YELLOW
    return _RED


def _print_row(
    index: int,
    total: int,
    fixture: dict,
    predicted: str,
    expected: str,
    confidence: float,
    correct: bool,
) -> None:
    tick = f"{_GREEN}✓{_RESET}" if correct else f"{_RED}✗{_RESET}"
    conf_str = f"{_conf_color(confidence)}{confidence:.2f}{_RESET}"
    source = fixture["source"].ljust(7)
    event = fixture["event_type"][:38].ljust(38)
    if correct:
        action_str = f"{_DIM}{predicted}{_RESET}"
    else:
        action_str = f"{_RED}{predicted}{_RESET} {_DIM}(expected {expected}){_RESET}"
    print(f"  [{index:>2}/{total}] {tick} {_CYAN}{source}{_RESET} {event}  {action_str}  {conf_str}")


# ---------------------------------------------------------------------------
# Main eval loop
# ---------------------------------------------------------------------------


async def run_evals() -> dict:
    dataset = _load_dataset()
    total = len(dataset)

    print(f"\n{_BOLD}WebhookAI Routing Accuracy Eval{_RESET}")
    print(f"{_DIM}Dataset: {_DATASET_PATH.name}  ({total} fixtures){_RESET}\n")

    results: list[dict] = []
    correct_count = 0

    per_source: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    confidences: list[float] = []

    # false_positives[action] = times predicted when NOT expected
    false_positives: dict[str, int] = defaultdict(int)

    for i, fixture in enumerate(dataset, start=1):
        envelope = _build_envelope(fixture)
        expected = fixture["expected_action"]

        try:
            decision = await route_webhook(envelope)
        except Exception as exc:
            print(f"  [{i:>2}/{total}] {_RED}ERROR{_RESET} {fixture['id']}: {exc}")
            results.append({
                "id": fixture["id"],
                "source": fixture["source"],
                "event_type": fixture["event_type"],
                "expected": expected,
                "predicted": None,
                "confidence": None,
                "correct": False,
                "error": str(exc),
            })
            if i < total:
                await asyncio.sleep(_DELAY_BETWEEN_CALLS)
            continue

        predicted = decision.action_id
        confidence = decision.confidence
        correct = predicted == expected

        if correct:
            correct_count += 1
        else:
            false_positives[predicted] += 1

        per_source[fixture["source"]]["total"] += 1
        per_source[fixture["source"]]["correct"] += int(correct)
        confidences.append(confidence)

        _print_row(i, total, fixture, predicted, expected, confidence, correct)

        results.append({
            "id": fixture["id"],
            "source": fixture["source"],
            "event_type": fixture["event_type"],
            "expected": expected,
            "predicted": predicted,
            "confidence": confidence,
            "correct": correct,
            "reasoning": decision.reasoning,
            "needs_review": decision.needs_review,
        })

        if i < total:
            await asyncio.sleep(_DELAY_BETWEEN_CALLS)

    # ---------------------------------------------------------------------------
    # Summary report
    # ---------------------------------------------------------------------------

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    accuracy = correct_count / total if total else 0.0

    width = 62
    bar = "═" * width

    print(f"\n  {_BOLD}╔{bar}╗{_RESET}")
    print(f"  {_BOLD}║{_RESET}{'Routing Accuracy Report':^{width}}{_BOLD}║{_RESET}")
    print(f"  {_BOLD}╠{bar}╣{_RESET}")

    acc_color = _GREEN if accuracy >= 0.9 else (_YELLOW if accuracy >= 0.75 else _RED)
    overall = f"Overall  {acc_color}{correct_count}/{total}  ({accuracy:.1%}){_RESET}"
    print(f"  {_BOLD}║{_RESET}  {overall:<{width + 9}}{_BOLD}║{_RESET}")

    conf_color = _conf_color(avg_conf)
    avg_line = f"Avg confidence  {conf_color}{avg_conf:.3f}{_RESET}"
    print(f"  {_BOLD}║{_RESET}  {avg_line:<{width + 9}}{_BOLD}║{_RESET}")

    print(f"  {_BOLD}╠{bar}╣{_RESET}")
    print(f"  {_BOLD}║{_RESET}  {'Per-source accuracy':<{width}}{_BOLD}║{_RESET}")

    for src in ("stripe", "github", "slack"):
        s = per_source[src]
        if s["total"] == 0:
            continue
        src_acc = s["correct"] / s["total"]
        src_color = _GREEN if src_acc >= 0.9 else (_YELLOW if src_acc >= 0.75 else _RED)
        line = f"  {src.capitalize():<8}  {src_color}{s['correct']}/{s['total']}  ({src_acc:.1%}){_RESET}"
        print(f"  {_BOLD}║{_RESET}{line:<{width + 9}}{_BOLD}║{_RESET}")

    if false_positives:
        print(f"  {_BOLD}╠{bar}╣{_RESET}")
        print(f"  {_BOLD}║{_RESET}  {'False positives per action (predicted when wrong)':<{width}}{_BOLD}║{_RESET}")
        for action, count in sorted(false_positives.items(), key=lambda x: -x[1]):
            line = f"  {action:<28}  {_RED}{count:>2} false positive{'s' if count != 1 else ''}{_RESET}"
            print(f"  {_BOLD}║{_RESET}{line:<{width + 9}}{_BOLD}║{_RESET}")

    incorrect = [r for r in results if not r.get("correct") and r.get("predicted")]
    if incorrect:
        print(f"  {_BOLD}╠{bar}╣{_RESET}")
        print(f"  {_BOLD}║{_RESET}  {'Mispredictions':<{width}}{_BOLD}║{_RESET}")
        for r in incorrect:
            label = f"  [{r['source']}] {r['event_type']}"[:width - 2]
            print(f"  {_BOLD}║{_RESET}{label:<{width + 2}}{_BOLD}║{_RESET}")
            detail = f"    expected {_GREEN}{r['expected']}{_RESET} → got {_RED}{r['predicted']}{_RESET}"
            print(f"  {_BOLD}║{_RESET}  {detail:<{width + 18}}{_BOLD}║{_RESET}")

    print(f"  {_BOLD}╚{bar}╝{_RESET}\n")

    # ---------------------------------------------------------------------------
    # Persist results
    # ---------------------------------------------------------------------------

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": _DATASET_PATH.name,
        "total": total,
        "correct": correct_count,
        "accuracy": round(accuracy, 4),
        "avg_confidence": round(avg_conf, 4),
        "per_source": {
            src: {
                "correct": d["correct"],
                "total": d["total"],
                "accuracy": round(d["correct"] / d["total"], 4) if d["total"] else 0,
            }
            for src, d in per_source.items()
        },
        "false_positives_per_action": dict(false_positives),
        "fixtures": results,
    }

    with open(_RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  {_DIM}Results saved to {_RESULTS_PATH}{_RESET}\n")
    return output


if __name__ == "__main__":
    asyncio.run(run_evals())
