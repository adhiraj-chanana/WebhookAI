import json
from typing import Any

from fastapi import Request

from app.models import WebhookEnvelope, WebhookSource


def _safe_headers(request: Request) -> dict[str, str]:
    return dict(request.headers)


def _stripe_envelope(body: bytes, headers: dict[str, str]) -> WebhookEnvelope:
    payload: dict[str, Any] = json.loads(body)
    return WebhookEnvelope(
        source=WebhookSource.stripe,
        event_type=payload.get("type", "unknown"),
        event_id=payload.get("id"),
        raw_payload=payload,
        headers=headers,
    )


def _github_envelope(body: bytes, headers: dict[str, str]) -> WebhookEnvelope:
    payload: dict[str, Any] = json.loads(body)
    return WebhookEnvelope(
        source=WebhookSource.github,
        event_type=headers.get("x-github-event", "unknown"),
        event_id=headers.get("x-github-delivery"),
        raw_payload=payload,
        headers=headers,
    )


def _slack_envelope(body: bytes, headers: dict[str, str]) -> WebhookEnvelope:
    payload: dict[str, Any] = json.loads(body)
    # Slack event-type lives at payload["event"]["type"] for Events API
    event_type = payload.get("type", "unknown")
    if nested := payload.get("event", {}).get("type"):
        event_type = nested
    return WebhookEnvelope(
        source=WebhookSource.slack,
        event_type=event_type,
        event_id=payload.get("event_id"),
        raw_payload=payload,
        headers=headers,
    )


_BUILDERS = {
    WebhookSource.stripe: _stripe_envelope,
    WebhookSource.github: _github_envelope,
    WebhookSource.slack: _slack_envelope,
}


def build_envelope(source: WebhookSource, body: bytes, request: Request) -> WebhookEnvelope:
    headers = _safe_headers(request)
    return _BUILDERS[source](body, headers)
