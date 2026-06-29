"""
Tests for the LLM routing engine.

The Anthropic client is mocked so no real API calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import WebhookEnvelope, WebhookSource
from app.router import RoutingDecision, route_webhook

_PAYMENT_ENVELOPE = WebhookEnvelope(
    source=WebhookSource.stripe,
    event_type="payment_intent.succeeded",
    event_id="evt_test_001",
    raw_payload={
        "id": "evt_test_001",
        "type": "payment_intent.succeeded",
        "data": {"object": {"amount": 2000, "currency": "usd"}},
    },
)


def _mock_client(
    action_id: str,
    confidence: float,
    extracted_params: dict,
    reasoning: str,
) -> MagicMock:
    """Return a mock AsyncAnthropic client pre-wired with a tool_use response."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {
        "action_id": action_id,
        "confidence": confidence,
        "extracted_params": extracted_params,
        "reasoning": reasoning,
    }

    response = MagicMock()
    response.content = [tool_block]

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# Return type and payload fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_webhook_returns_routing_decision():
    client = _mock_client(
        action_id="send_email",
        confidence=0.92,
        extracted_params={"amount": 2000, "currency": "usd"},
        reasoning="Payment succeeded — notify the customer via email.",
    )
    with patch("app.router.get_anthropic_client", return_value=client):
        decision = await route_webhook(_PAYMENT_ENVELOPE)

    assert isinstance(decision, RoutingDecision)
    assert decision.action_id == "send_email"
    assert decision.confidence == 0.92
    assert decision.extracted_params == {"amount": 2000, "currency": "usd"}
    assert decision.reasoning != ""


# ---------------------------------------------------------------------------
# needs_review flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_needs_review_false_when_confidence_above_threshold():
    client = _mock_client("send_slack_message", 0.85, {"channel": "#payments"}, "High confidence.")
    with patch("app.router.get_anthropic_client", return_value=client):
        decision = await route_webhook(_PAYMENT_ENVELOPE)

    assert decision.needs_review is False


@pytest.mark.asyncio
async def test_needs_review_true_when_confidence_below_threshold():
    client = _mock_client("log_event", 0.55, {}, "Uncertain about the correct action.")
    with patch("app.router.get_anthropic_client", return_value=client):
        decision = await route_webhook(_PAYMENT_ENVELOPE)

    assert decision.needs_review is True


@pytest.mark.asyncio
async def test_needs_review_false_at_exact_threshold():
    # 0.7 is NOT < 0.7, so should not be flagged
    client = _mock_client("send_email", 0.7, {}, "Exactly at boundary.")
    with patch("app.router.get_anthropic_client", return_value=client):
        decision = await route_webhook(_PAYMENT_ENVELOPE)

    assert decision.needs_review is False


@pytest.mark.asyncio
async def test_needs_review_true_just_below_threshold():
    client = _mock_client("log_event", 0.699, {}, "Just below threshold.")
    with patch("app.router.get_anthropic_client", return_value=client):
        decision = await route_webhook(_PAYMENT_ENVELOPE)

    assert decision.needs_review is True


# ---------------------------------------------------------------------------
# Claude is called with the right model and envelope context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calls_correct_model():
    client = _mock_client("log_event", 0.8, {}, "Fallback.")
    with patch("app.router.get_anthropic_client", return_value=client):
        await route_webhook(_PAYMENT_ENVELOPE)

    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_prompt_contains_envelope_fields():
    client = _mock_client("log_event", 0.8, {}, "Fallback.")
    with patch("app.router.get_anthropic_client", return_value=client):
        await route_webhook(_PAYMENT_ENVELOPE)

    user_content: str = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "payment_intent.succeeded" in user_content
    assert "stripe" in user_content
    assert "evt_test_001" in user_content


@pytest.mark.asyncio
async def test_tool_choice_forces_route_to_action():
    client = _mock_client("log_event", 0.8, {}, "Fallback.")
    with patch("app.router.get_anthropic_client", return_value=client):
        await route_webhook(_PAYMENT_ENVELOPE)

    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "route_to_action"}


# ---------------------------------------------------------------------------
# Error path: no tool_use block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_if_no_tool_use_block():
    response = MagicMock()
    response.content = []  # Claude replied in plain text — shouldn't happen but handle it

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)

    with patch("app.router.get_anthropic_client", return_value=client):
        with pytest.raises(ValueError, match="tool_use"):
            await route_webhook(_PAYMENT_ENVELOPE)
