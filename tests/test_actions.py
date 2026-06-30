"""
Tests for the action executor layer.

httpx calls are intercepted by pytest-httpx (httpx_mock fixture).
Supabase client is mocked via unittest.mock.patch.
"""

import logging
from unittest.mock import MagicMock, patch

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
# Fixtures
# ---------------------------------------------------------------------------

_EXEC_PARAMS = {
    "source": "stripe",
    "event_type": "payment_intent.succeeded",
    "action_id": "send_slack_message",
    "confidence": 0.92,
    "amount": 2000,
    "currency": "usd",
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
    """Cannot instantiate BaseAction without implementing execute."""
    with pytest.raises(TypeError):
        BaseAction()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# SendSlackMessage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slack_posts_to_webhook_url(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/services/T0/B0/xxx")
    httpx_mock.add_response(url=settings.slack_webhook_url, method="POST", status_code=200, text="ok")

    result = await SendSlackMessage().execute({"text": "Payment received!", **_EXEC_PARAMS})

    assert result.success is True
    assert result.action_id == "send_slack_message"
    assert result.error is None

    request = httpx_mock.get_requests()[0]
    import json
    body = json.loads(request.content)
    assert body["text"] == "Payment received!"


@pytest.mark.asyncio
async def test_slack_builds_text_from_params_when_no_text_key(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/services/T0/B0/xxx")
    httpx_mock.add_response(url=settings.slack_webhook_url, method="POST", status_code=200, text="ok")

    params = {"amount": 2000, "currency": "usd", "source": "stripe", "event_type": "payment_intent.succeeded"}
    result = await SendSlackMessage().execute(params)

    assert result.success is True
    import json
    body = json.loads(httpx_mock.get_requests()[0].content)
    # The formatted text should contain at least one of the extracted values
    assert "2000" in body["text"] or "stripe" in body["text"]


@pytest.mark.asyncio
async def test_slack_returns_failure_on_http_error(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/services/T0/B0/xxx")
    httpx_mock.add_response(url=settings.slack_webhook_url, method="POST", status_code=400, text="bad_request")

    result = await SendSlackMessage().execute({"text": "hello"})

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

    result = await SendEmail().execute(_EXEC_PARAMS)

    assert result.success is True
    assert result.output == {"id": "msg_abc"}

    request = httpx_mock.get_requests()[0]
    assert request.headers["authorization"] == "Bearer re_test_key"


@pytest.mark.asyncio
async def test_email_sends_to_correct_recipient(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_to_email", "adhirajmohanchanana@gmail.com")
    httpx_mock.add_response(url=_RESEND_URL, method="POST", status_code=200, json={"id": "msg_xyz"})

    await SendEmail().execute(_EXEC_PARAMS)

    import json
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["from"] == "onboarding@resend.dev"
    assert "adhirajmohanchanana@gmail.com" in body["to"]
    assert body["subject"]
    assert body["text"]


@pytest.mark.asyncio
async def test_email_returns_failure_on_http_error(httpx_mock: HTTPXMock, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_bad")
    monkeypatch.setattr(settings, "resend_to_email", "adhirajmohanchanana@gmail.com")
    httpx_mock.add_response(url=_RESEND_URL, method="POST", status_code=401, json={"error": "Unauthorized"})

    result = await SendEmail().execute({"event_type": "test"})

    assert result.success is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# LogEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_event_inserts_row_to_supabase():
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

    with patch("app.actions.log_event.get_supabase_client", return_value=mock_sb):
        result = await LogEvent().execute(_EXEC_PARAMS)

    assert result.success is True
    assert "id" in result.output

    # Verify the table and the inserted row
    mock_sb.table.assert_called_once_with("webhook_events")
    inserted = mock_sb.table.return_value.insert.call_args.args[0]
    assert inserted["source"] == "stripe"
    assert inserted["event_type"] == "payment_intent.succeeded"
    assert inserted["action_id"] == "send_slack_message"
    assert inserted["confidence"] == 0.92
    assert "amount" in inserted["params"]
    assert "source" not in inserted["params"]  # metadata stripped from params jsonb


@pytest.mark.asyncio
async def test_log_event_returns_failure_on_exception():
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB error")

    with patch("app.actions.log_event.get_supabase_client", return_value=mock_sb):
        result = await LogEvent().execute(_EXEC_PARAMS)

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
# Worker integration: unknown action_id + execution path
# ---------------------------------------------------------------------------


_ENVELOPE_DICT = {
    "source": "stripe",
    "event_type": "payment_intent.succeeded",
    "event_id": "evt_001",
    "received_at": "2024-01-01T00:00:00+00:00",
    "raw_payload": {"id": "evt_001", "type": "payment_intent.succeeded"},
    "headers": {},
}


@pytest.mark.asyncio
async def test_unknown_action_id_logs_warning_and_does_not_crash(caplog):
    from unittest.mock import AsyncMock

    from app.router import RoutingDecision

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
async def test_worker_calls_action_execute_with_enriched_params():
    from unittest.mock import AsyncMock

    from app.router import RoutingDecision

    decision = RoutingDecision(
        action_id="send_slack_message",
        confidence=0.88,
        extracted_params={"amount": 500},
        reasoning="Slack alert for payment.",
        needs_review=False,
    )
    mock_action = MagicMock()
    mock_action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_id="send_slack_message")
    )
    mock_registry = {"send_slack_message": mock_action}

    with patch("app.worker.route_webhook", new=AsyncMock(return_value=decision)):
        with patch("app.worker.ACTION_REGISTRY", mock_registry):
            await process_webhook(_ENVELOPE_DICT)

    mock_action.execute.assert_awaited_once()
    called_params = mock_action.execute.call_args.args[0]
    # Routing context must be present
    assert called_params["source"] == "stripe"
    assert called_params["event_type"] == "payment_intent.succeeded"
    assert called_params["confidence"] == 0.88
    # Extracted params must be present
    assert called_params["amount"] == 500
