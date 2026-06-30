"""
Unit tests for the custom worker: retry logic and dead-letter behaviour.
asyncio.sleep is patched to zero so tests run instantly.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models import WebhookSource
from app.queue import DLQ_KEY
from app.worker import _run_with_retry, process_webhook

_ENVELOPE_DICT = {
    "source": WebhookSource.stripe,
    "event_type": "payment_intent.succeeded",
    "event_id": "evt_worker_001",
    "received_at": "2024-01-01T00:00:00+00:00",
    "raw_payload": {"id": "evt_worker_001", "type": "payment_intent.succeeded"},
    "headers": {},
}


# ---------------------------------------------------------------------------
# process_webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_webhook_logs_envelope(caplog):
    import logging
    from app.actions.base import ActionResult
    from app.router import RoutingDecision

    mock_decision = RoutingDecision(
        action_id="log_event",
        confidence=0.9,
        extracted_params={},
        reasoning="Test routing decision.",
        needs_review=False,
    )
    mock_action = AsyncMock()
    mock_action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_id="log_event", output={"id": "uuid-x"})
    )
    mock_registry = {"log_event": mock_action}

    mock_transformed = {"text": "Test webhook received"}

    with patch("app.worker.route_webhook", new=AsyncMock(return_value=mock_decision)):
        with patch("app.worker.transform_payload", new=AsyncMock(return_value=mock_transformed)):
            with patch("app.worker.ACTION_REGISTRY", mock_registry):
                with caplog.at_level(logging.INFO, logger="app.worker"):
                    await process_webhook(_ENVELOPE_DICT)

    assert "payment_intent.succeeded" in caplog.text
    assert "evt_worker_001" in caplog.text


@pytest.mark.asyncio
async def test_process_webhook_raises_on_invalid_envelope():
    with pytest.raises(Exception):
        await process_webhook({"bad": "data"})


# ---------------------------------------------------------------------------
# _run_with_retry — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_retry_succeeds_first_attempt():
    redis = AsyncMock()

    with patch("app.worker.process_webhook", new=AsyncMock()) as mock_process:
        await _run_with_retry(redis, _ENVELOPE_DICT)

    mock_process.assert_awaited_once_with(_ENVELOPE_DICT)
    redis.lpush.assert_not_awaited()


# ---------------------------------------------------------------------------
# _run_with_retry — retry paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_retry_succeeds_on_second_attempt():
    redis = AsyncMock()
    call_count = 0

    async def flaky(envelope_dict):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("transient error")

    with patch("app.worker.process_webhook", new=flaky):
        with patch("asyncio.sleep", new=AsyncMock()):
            await _run_with_retry(redis, _ENVELOPE_DICT)

    assert call_count == 2
    redis.lpush.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_with_retry_dead_letters_after_all_attempts():
    redis = AsyncMock()
    redis.lpush = AsyncMock()

    async def always_fails(envelope_dict):
        raise RuntimeError("permanent error")

    with patch("app.worker.process_webhook", new=always_fails):
        with patch("asyncio.sleep", new=AsyncMock()):
            await _run_with_retry(redis, _ENVELOPE_DICT)

    redis.lpush.assert_awaited_once()
    dlq_key, dlq_raw = redis.lpush.call_args.args
    assert dlq_key == DLQ_KEY

    dlq_entry = json.loads(dlq_raw)
    assert dlq_entry["envelope"]["event_id"] == "evt_worker_001"
    assert "permanent error" in dlq_entry["error"]


@pytest.mark.asyncio
async def test_run_with_retry_uses_correct_delay_sequence():
    redis = AsyncMock()
    sleep_calls = []

    async def capture_sleep(seconds):
        sleep_calls.append(seconds)

    async def always_fails(envelope_dict):
        raise RuntimeError("fail")

    with patch("app.worker.process_webhook", new=always_fails):
        with patch("asyncio.sleep", new=capture_sleep):
            await _run_with_retry(redis, _ENVELOPE_DICT)

    assert sleep_calls == [5, 30, 300]
