"""Unit tests for payload normalisation — no HTTP needed."""

import json

import pytest
from fastapi import Request
from starlette.datastructures import Headers

from app.models import WebhookSource
from app.normalisation import build_envelope


def _make_request(body: bytes, headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }

    async def receive():
        return {"type": "http.request", "body": body}

    return Request(scope, receive)


def test_stripe_envelope_fields():
    payload = {"id": "evt_abc", "type": "charge.succeeded", "object": "event"}
    body = json.dumps(payload).encode()
    req = _make_request(body, {"content-type": "application/json"})
    env = build_envelope(WebhookSource.stripe, body, req)
    assert env.source == WebhookSource.stripe
    assert env.event_type == "charge.succeeded"
    assert env.event_id == "evt_abc"
    assert env.raw_payload == payload


def test_github_envelope_fields():
    payload = {"action": "created"}
    body = json.dumps(payload).encode()
    req = _make_request(
        body,
        {
            "content-type": "application/json",
            "x-github-event": "issues",
            "x-github-delivery": "del-123",
        },
    )
    env = build_envelope(WebhookSource.github, body, req)
    assert env.source == WebhookSource.github
    assert env.event_type == "issues"
    assert env.event_id == "del-123"


def test_slack_envelope_nested_event_type():
    payload = {
        "type": "event_callback",
        "event_id": "Ev12345",
        "event": {"type": "message", "text": "hello"},
    }
    body = json.dumps(payload).encode()
    req = _make_request(body, {"content-type": "application/json"})
    env = build_envelope(WebhookSource.slack, body, req)
    assert env.event_type == "message"
    assert env.event_id == "Ev12345"


def test_envelope_has_received_at():
    payload = {"id": "evt_x", "type": "foo", "object": "event"}
    body = json.dumps(payload).encode()
    req = _make_request(body, {})
    env = build_envelope(WebhookSource.stripe, body, req)
    assert env.received_at is not None
