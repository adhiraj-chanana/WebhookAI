"""
LLM routing engine.

Calls Claude Haiku with the webhook envelope and a hardcoded action registry.
Claude must call the route_to_action tool — we parse its input as the decision.
"""

import json
from typing import Any

import anthropic
from pydantic import BaseModel

from app.config import settings
from app.models import WebhookEnvelope

# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------

ACTIONS: dict[str, str] = {
    "send_slack_message": (
        "Send a notification to a Slack channel. "
        "Best for operational events: PRs opened/merged, payment failures, deploys."
    ),
    "send_email": (
        "Send an email to a recipient. "
        "Best for customer-facing events: successful payments, subscription changes, refunds."
    ),
    "log_event": (
        "Record the event in the database for auditing. "
        "Use when no immediate user action is needed, or as a safe fallback."
    ),
}

# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

_ROUTE_TOOL: dict[str, Any] = {
    "name": "route_to_action",
    "description": (
        "Select the single best action for this webhook event and extract "
        "the parameters needed to execute it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action_id": {
                "type": "string",
                "enum": list(ACTIONS.keys()),
                "description": "Identifier of the chosen action.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score in the range [0.0, 1.0].",
            },
            "extracted_params": {
                "type": "object",
                "description": (
                    "Key-value pairs extracted from the payload that the action handler "
                    "will need (e.g. amount, currency, channel, email address)."
                ),
            },
            "reasoning": {
                "type": "string",
                "description": "One-sentence explanation of why this action was chosen.",
            },
        },
        "required": ["action_id", "confidence", "extracted_params", "reasoning"],
    },
}

_SYSTEM_PROMPT = (
    "You are a webhook routing engine. "
    "Given a webhook event you must select the single best action from the registry "
    "and extract the parameters the action handler will need. "
    "You must always call the route_to_action tool — never reply in plain text."
)

# ---------------------------------------------------------------------------
# Decision model
# ---------------------------------------------------------------------------

_CONFIDENCE_THRESHOLD = 0.7


class RoutingDecision(BaseModel):
    action_id: str
    confidence: float
    extracted_params: dict[str, Any]
    reasoning: str
    needs_review: bool


# ---------------------------------------------------------------------------
# Client factory (kept as a function so tests can patch it)
# ---------------------------------------------------------------------------


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def route_webhook(envelope: WebhookEnvelope) -> RoutingDecision:
    """Call Claude Haiku to pick an action for *envelope*."""
    action_lines = "\n".join(f"- {k}: {v}" for k, v in ACTIONS.items())
    user_content = (
        f"Webhook event to route:\n\n"
        f"Source: {envelope.source}\n"
        f"Event type: {envelope.event_type}\n"
        f"Event ID: {envelope.event_id}\n\n"
        f"Payload:\n{json.dumps(envelope.raw_payload, indent=2)}\n\n"
        f"Available actions:\n{action_lines}\n\n"
        "Call route_to_action with your decision."
    )

    client = get_anthropic_client()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        tools=[_ROUTE_TOOL],
        tool_choice={"type": "tool", "name": "route_to_action"},
        messages=[{"role": "user", "content": user_content}],
    )

    tool_blocks = [b for b in response.content if b.type == "tool_use"]
    if not tool_blocks:
        raise ValueError("Claude did not return a tool_use block")

    result: dict[str, Any] = tool_blocks[0].input
    confidence: float = float(result["confidence"])

    return RoutingDecision(
        action_id=result["action_id"],
        confidence=confidence,
        extracted_params=result["extracted_params"],
        reasoning=result["reasoning"],
        needs_review=confidence < _CONFIDENCE_THRESHOLD,
    )
