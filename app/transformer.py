"""
LLM payload transformation step.

Makes a second Claude call (separate from routing) to convert raw
extracted_params into a clean, human-readable payload shaped for the
chosen action.
"""

import json
from typing import Any

import anthropic

from app.config import settings
from app.models import WebhookEnvelope

# ---------------------------------------------------------------------------
# Per-action tool input schemas
# ---------------------------------------------------------------------------

_ACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "send_slack_message": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Concise, human-readable Slack message.",
            },
        },
        "required": ["text"],
    },
    "send_email": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Clear email subject line.",
            },
            "body": {
                "type": "string",
                "description": "Plain-text email body. Professional and informative.",
            },
            "to": {
                "type": "string",
                "description": "Recipient email address.",
            },
        },
        "required": ["subject", "body", "to"],
    },
    "log_event": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "One-sentence audit-log summary of the event.",
            },
            "severity": {
                "type": "string",
                "enum": ["info", "warning", "error"],
                "description": "Severity level.",
            },
        },
        "required": ["summary", "severity"],
    },
}

_SYSTEM_PROMPT = (
    "You are a webhook payload transformer. "
    "Given a webhook event and its raw extracted parameters, produce a clean "
    "human-readable payload shaped for the specified action. "
    "You must always call the transformed_payload tool — never reply in plain text."
)


# ---------------------------------------------------------------------------
# Client factory (kept as a function so tests can patch it)
# ---------------------------------------------------------------------------


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def transform_payload(
    envelope: WebhookEnvelope,
    action_id: str,
    raw_params: dict,
) -> dict[str, Any]:
    """
    Transform *raw_params* into a clean payload for *action_id*.

    Returns *raw_params* unchanged for unknown action_ids so the worker
    can still call execute() without crashing.
    """
    schema = _ACTION_SCHEMAS.get(action_id)
    if schema is None:
        return raw_params

    tool: dict[str, Any] = {
        "name": "transformed_payload",
        "description": f"Produce a clean payload for the '{action_id}' action.",
        "input_schema": schema,
    }

    user_content = (
        f"Webhook event details:\n"
        f"  Source: {envelope.source}\n"
        f"  Event type: {envelope.event_type}\n"
        f"  Action to execute: {action_id}\n\n"
        f"Raw extracted parameters:\n{json.dumps(raw_params, indent=2)}\n\n"
        f"Call transformed_payload with a clean, human-readable payload for '{action_id}'."
    )

    client = get_anthropic_client()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": "transformed_payload"},
        messages=[{"role": "user", "content": user_content}],
    )

    tool_blocks = [b for b in response.content if b.type == "tool_use"]
    if not tool_blocks:
        raise ValueError("Claude did not return a tool_use block from transform_payload")

    return dict(tool_blocks[0].input)
