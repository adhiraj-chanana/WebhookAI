"""
Tests for the action executor layer.

httpx calls are intercepted by pytest-httpx (httpx_mock fixture).
Supabase client is mocked via unittest.mock.patch.

Params are shaped as the transformer would produce them (not raw extracted_params).
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_httpx import HTTPXMock

from app.actions.base import ActionResult, BaseAction
from app.actions.email import SendEmail, _RESEND_URL
from app.actions.log_event import LogEvent
from app.actions.registry import ACTION_REGISTRY
from app.actions.slack import SendSlackMessage
from app.config import settings
from app.router import RoutingDecision
from app.worker import process_webhook

# ---------------------------------------------------------------------------
# Per-action param fixtures (transformer output + routing metadata merged)
# ---------------------------------------------------------------------------

_SLACK_PARAMS = {
    "text": "Payment of $20 received on Stripe",
    "source": "stripe",
    "event_type": "payment_intent.succeeded",
    "action_id": "send_slack_message",
    "confidence": 0.92,
}

_EMAIL_PARAMS = {
    "subject": "Payment Succeeded — $20 USD",
    "body": "A payment of $20 USD was successfully processed on Stripe.",
    "to": "adhirajmohanchanana@gmail.com",
    "source": "stripe",
    "event_type": "payment_intent.succeeded",
    "action_id": "send_email",
    "confidence": 0.92,
}

_LOG_PARAMS = {
    "summary": "Stripe payment_intent.succeeded for $20 USD",
    "severity": "info",
    "source": "stripe",
    "event_type": "payment_intent.succeeded",
    "action_id": "log_event",
    "confidence": 0.92,
}

_ENVELOPE_DICT = {
    "source": "stripe",
    "event_type": "payment_intent.succeeded",
    "event_id": "evt_001",
    "received_at": "2024-01-01T00:00:00+00:00",
    "raw_payload": {"id": "evt_001", "type": "payment_intent.succeeded"},
    "headers": {},
}


# ---------------------------------------------------------------------------
# base.py — sanity
# ---------------------------------------------------------------------------


def test_action_result_fields():
    r = ActionResult(success=True, action_id="log_event", output={"id": "x"})
    assert r.success is True
    assert r.action_id == "log_event"
    assert r.output == {"id": "x"}
    assert r.error is None


def test_base_action_is_abstract():
    with pytest.raises(TypeError):
        BaseAction()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# SendSlackMessage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slack_posts_to_webhook_url(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/T0/B0/xxx")
    httpx_mock.add_response(url=settings.slack_webhook_url, method="POST", status_code=200, text="ok")

    result = await SendSlackMessage().execute(_SLACK_PARAMS)

    assert result.success is True
    assert result.action_id == "send_slack_message"
    assert result.error is None

    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["text"] == _SLACK_PARAMS["text"]


@pytest.mark.asyncio
async def test_slack_returns_failure_on_http_error(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/T0/B0/xxx")
    httpx_mock.add_response(url=settings.slack_webhook_url, method="POST", status_code=400, text="bad_request")

    result = await SendSlackMessage().execute(_SLACK_PARAMS)

    assert result.success is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# SendEmail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_posts_to_resend_with_auth_header(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_to_email", "adhirajmohanchanana@gmail.com")
    httpx_mock.add_response(url=_RESEND_URL, method="POST", status_code=200, json={"id": "msg_abc"})

    result = await SendEmail().execute(_EMAIL_PARAMS)

    assert result.success is True
    assert result.output == {"id": "msg_abc"}
    assert httpx_mock.get_requests()[0].headers["authorization"] == "Bearer re_test_key"


@pytest.mark.asyncio
async def test_email_sends_correct_fields_to_resend(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_to_email", "adhirajmohanchanana@gmail.com")
    httpx_mock.add_response(url=_RESEND_URL, method="POST", status_code=200, json={"id": "msg_xyz"})

    await SendEmail().execute(_EMAIL_PARAMS)

    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["from"] == "onboarding@resend.dev"
    assert "adhirajmohanchanana@gmail.com" in body["to"]
    assert body["subject"] == _EMAIL_PARAMS["subject"]
    assert body["text"] == _EMAIL_PARAMS["body"]


@pytest.mark.asyncio
async def test_email_falls_back_to_config_recipient_when_to_absent(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_to_email", "fallback@example.com")
    httpx_mock.add_response(url=_RESEND_URL, method="POST", status_code=200, json={"id": "msg_fb"})

    params = {**_EMAIL_PARAMS}
    params.pop("to")
    await SendEmail().execute(params)

    body = json.loads(httpx_mock.get_requests()[0].content)
    assert "fallback@example.com" in body["to"]


@pytest.mark.asyncio
async def test_email_returns_failure_on_http_error(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_bad")
    monkeypatch.setattr(settings, "resend_to_email", "adhirajmohanchanana@gmail.com")
    httpx_mock.add_response(url=_RESEND_URL, method="POST", status_code=401, json={"error": "Unauthorized"})

    result = await SendEmail().execute(_EMAIL_PARAMS)

    assert result.success is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# LogEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_event_inserts_row_with_summary_and_severity():
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

    with patch("app.actions.log_event.get_supabase_client", return_value=mock_sb):
        result = await LogEvent().execute(_LOG_PARAMS)

    assert result.success is True
    assert "id" in result.output

    mock_sb.table.assert_called_once_with("webhook_events")
    inserted = mock_sb.table.return_value.insert.call_args.args[0]

    # Routing metadata in named columns
    assert inserted["source"] == "stripe"
    assert inserted["event_type"] == "payment_intent.succeeded"
    assert inserted["action_id"] == "log_event"
    assert inserted["confidence"] == 0.92

    # Transformer output in params jsonb
    assert inserted["params"]["summary"] == _LOG_PARAMS["summary"]
    assert inserted["params"]["severity"] == "info"

    # Routing metadata NOT duplicated into params jsonb
    assert "source" not in inserted["params"]
    assert "confidence" not in inserted["params"]


@pytest.mark.asyncio
async def test_log_event_returns_failure_on_exception():
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB error")

    with patch("app.actions.log_event.get_supabase_client", return_value=mock_sb):
        result = await LogEvent().execute(_LOG_PARAMS)

    assert result.success is False
    assert "DB error" in result.error


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_contains_all_three_actions():
    assert "send_slack_message" in ACTION_REGISTRY
    assert "send_email" in ACTION_REGISTRY
    assert "log_event" in ACTION_REGISTRY


def test_registry_returns_correct_types():
    assert isinstance(ACTION_REGISTRY["send_slack_message"], SendSlackMessage)
    assert isinstance(ACTION_REGISTRY["send_email"], SendEmail)
    assert isinstance(ACTION_REGISTRY["log_event"], LogEvent)


# ---------------------------------------------------------------------------
# Worker integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_action_id_logs_warning_and_does_not_crash(caplog):
    bad_decision = RoutingDecision(
        action_id="nonexistent_action",
        confidence=0.9,
        extracted_params={},
        reasoning="This action does not exist.",
        needs_review=False,
    )

    with patch("app.worker.route_webhook", new=AsyncMock(return_value=bad_decision)):
        with caplog.at_level(logging.WARNING, logger="app.worker"):
            await process_webhook(_ENVELOPE_DICT)

    assert "nonexistent_action" in caplog.text
    assert any(r.levelname == "WARNING" for r in caplog.records)


@pytest.mark.asyncio
async def test_worker_exec_params_contain_transformed_output_and_routing_metadata():
    decision = RoutingDecision(
        action_id="send_slack_message",
        confidence=0.88,
        extracted_params={"raw_amount": 500},
        reasoning="Slack alert for payment.",
        needs_review=False,
    )
    transformed = {"text": "Payment of $5 received"}

    mock_action = MagicMock()
    mock_action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_id="send_slack_message")
    )

    with patch("app.worker.route_webhook", new=AsyncMock(return_value=decision)):
        with patch("app.worker.transform_payload", new=AsyncMock(return_value=transformed)):
            with patch("app.worker.ACTION_REGISTRY", {"send_slack_message": mock_action}):
                await process_webhook(_ENVELOPE_DICT)

    called_params = mock_action.execute.call_args.args[0]
    assert called_params["text"] == "Payment of $5 received"
    assert "raw_amount" not in called_params
    assert called_params["source"] == "stripe"
    assert called_params["confidence"] == 0.88
