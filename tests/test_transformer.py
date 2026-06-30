"""
Tests for the LLM payload transformation step.
The Anthropic client is mocked so no real API calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.actions.base import ActionResult
from app.models import WebhookEnvelope, WebhookSource
from app.router import RoutingDecision
from app.transformer import transform_payload
from app.worker import process_webhook

_ENVELOPE = WebhookEnvelope(
    source=WebhookSource.stripe,
    event_type="payment_intent.succeeded",
    event_id="evt_001",
    raw_payload={"id": "evt_001", "type": "payment_intent.succeeded", "data": {"object": {"amount": 2000}}},
)
_RAW_PARAMS = {"amount": 2000, "currency": "usd"}
_ENVELOPE_DICT = {
    "source": "stripe",
    "event_type": "payment_intent.succeeded",
    "event_id": "evt_001",
    "received_at": "2024-01-01T00:00:00+00:00",
    "raw_payload": {"id": "evt_001", "type": "payment_intent.succeeded"},
    "headers": {},
}


def _mock_client(tool_input: dict) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "transformed_payload"
    tool_block.input = tool_input

    response = MagicMock()
    response.content = [tool_block]

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# Tool name and tool_choice
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uses_tool_named_transformed_payload():
    client = _mock_client({"text": "Payment received"})
    with patch("app.transformer.get_anthropic_client", return_value=client):
        await transform_payload(_ENVELOPE, "send_slack_message", _RAW_PARAMS)

    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tools"][0]["name"] == "transformed_payload"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "transformed_payload"}


@pytest.mark.asyncio
async def test_uses_correct_claude_model():
    client = _mock_client({"text": "ok"})
    with patch("app.transformer.get_anthropic_client", return_value=client):
        await transform_payload(_ENVELOPE, "send_slack_message", _RAW_PARAMS)

    assert client.messages.create.call_args.kwargs["model"] == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Schema variants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slack_schema_has_only_text_field():
    client = _mock_client({"text": "Payment succeeded"})
    with patch("app.transformer.get_anthropic_client", return_value=client):
        result = await transform_payload(_ENVELOPE, "send_slack_message", _RAW_PARAMS)

    schema = client.messages.create.call_args.kwargs["tools"][0]["input_schema"]
    assert list(schema["properties"].keys()) == ["text"]
    assert schema["required"] == ["text"]
    assert result == {"text": "Payment succeeded"}


@pytest.mark.asyncio
async def test_email_schema_has_subject_body_to_fields():
    expected = {"subject": "Payment Succeeded", "body": "A payment was received.", "to": "test@example.com"}
    client = _mock_client(expected)
    with patch("app.transformer.get_anthropic_client", return_value=client):
        result = await transform_payload(_ENVELOPE, "send_email", _RAW_PARAMS)

    schema = client.messages.create.call_args.kwargs["tools"][0]["input_schema"]
    assert set(schema["properties"].keys()) == {"subject", "body", "to"}
    assert set(schema["required"]) == {"subject", "body", "to"}
    assert result == expected


@pytest.mark.asyncio
async def test_log_event_schema_has_summary_and_severity_enum():
    expected = {"summary": "Payment of $20 succeeded", "severity": "info"}
    client = _mock_client(expected)
    with patch("app.transformer.get_anthropic_client", return_value=client):
        result = await transform_payload(_ENVELOPE, "log_event", _RAW_PARAMS)

    schema = client.messages.create.call_args.kwargs["tools"][0]["input_schema"]
    assert set(schema["properties"].keys()) == {"summary", "severity"}
    assert schema["properties"]["severity"]["enum"] == ["info", "warning", "error"]
    assert result == expected


# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_envelope_source_and_event_type():
    client = _mock_client({"text": "ok"})
    with patch("app.transformer.get_anthropic_client", return_value=client):
        await transform_payload(_ENVELOPE, "send_slack_message", _RAW_PARAMS)

    content: str = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "stripe" in content
    assert "payment_intent.succeeded" in content
    assert "send_slack_message" in content


@pytest.mark.asyncio
async def test_prompt_contains_raw_params():
    client = _mock_client({"text": "ok"})
    with patch("app.transformer.get_anthropic_client", return_value=client):
        await transform_payload(_ENVELOPE, "send_slack_message", {"amount": 9999, "currency": "gbp"})

    content: str = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "9999" in content
    assert "gbp" in content


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_if_no_tool_use_block():
    response = MagicMock()
    response.content = []

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)

    with patch("app.transformer.get_anthropic_client", return_value=client):
        with pytest.raises(ValueError, match="tool_use"):
            await transform_payload(_ENVELOPE, "send_slack_message", _RAW_PARAMS)


@pytest.mark.asyncio
async def test_unknown_action_id_returns_raw_params_without_api_call():
    with patch("app.transformer.get_anthropic_client") as mock_factory:
        result = await transform_payload(_ENVELOPE, "nonexistent_action", {"k": "v"})

    mock_factory.assert_not_called()
    assert result == {"k": "v"}


# ---------------------------------------------------------------------------
# Worker integration: transformed params reach action.execute, not raw params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_passes_transformed_not_raw_params_to_action():
    decision = RoutingDecision(
        action_id="send_slack_message",
        confidence=0.9,
        extracted_params={"raw_amount": 500},
        reasoning="Slack alert.",
        needs_review=False,
    )
    transformed = {"text": "Clean Slack message from transformer"}

    mock_action = MagicMock()
    mock_action.execute = AsyncMock(return_value=ActionResult(success=True, action_id="send_slack_message"))

    with patch("app.worker.route_webhook", new=AsyncMock(return_value=decision)):
        with patch("app.worker.transform_payload", new=AsyncMock(return_value=transformed)):
            with patch("app.worker.ACTION_REGISTRY", {"send_slack_message": mock_action}):
                await process_webhook(_ENVELOPE_DICT)

    called_params = mock_action.execute.call_args.args[0]
    # Transformer output must be present
    assert called_params["text"] == "Clean Slack message from transformer"
    # Raw extracted_params must NOT be present
    assert "raw_amount" not in called_params
    # Routing metadata still injected by worker
    assert called_params["source"] == "stripe"
    assert called_params["event_type"] == "payment_intent.succeeded"
    assert called_params["confidence"] == 0.9
