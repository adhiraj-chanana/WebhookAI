"""
Tests for the enqueue behaviour: router must LPUSH a valid envelope JSON
to QUEUE_KEY via the Upstash HTTP client.
"""

import json
from unittest.mock import AsyncMock

from app.queue import QUEUE_KEY
from tests.conftest import TEST_GITHUB_SECRET, TEST_STRIPE_SECRET
from tests.helpers import github_sig_header, json_body, stripe_sig_header

STRIPE_ENDPOINT = "/webhook/stripe"
GITHUB_ENDPOINT = "/webhook/github"

_STRIPE_PAYLOAD = {
    "id": "evt_queue_001",
    "type": "payment_intent.succeeded",
    "object": "event",
    "data": {"object": {"amount": 500}},
}

_GITHUB_PAYLOAD = {
    "action": "opened",
    "pull_request": {"title": "feat: add queue"},
    "repository": {"full_name": "org/repo"},
}


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------


def test_stripe_enqueues_on_valid_webhook(client, redis_client):
    body = json_body(_STRIPE_PAYLOAD)
    resp = client.post(
        STRIPE_ENDPOINT,
        content=body,
        headers={
            "stripe-signature": stripe_sig_header(body, TEST_STRIPE_SECRET),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert resp.json()["event_id"] == "evt_queue_001"

    redis_client.lpush.assert_awaited_once()
    key, raw_json = redis_client.lpush.call_args.args
    assert key == QUEUE_KEY

    envelope_dict = json.loads(raw_json)
    assert envelope_dict["source"] == "stripe"
    assert envelope_dict["event_type"] == "payment_intent.succeeded"
    assert envelope_dict["event_id"] == "evt_queue_001"
    assert "received_at" in envelope_dict
    assert "raw_payload" in envelope_dict


def test_stripe_invalid_sig_does_not_enqueue(client, redis_client):
    body = json_body(_STRIPE_PAYLOAD)
    resp = client.post(
        STRIPE_ENDPOINT,
        content=body,
        headers={
            "stripe-signature": stripe_sig_header(body, "wrong_secret"),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 400
    redis_client.lpush.assert_not_awaited()


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


def test_github_enqueues_on_valid_webhook(client, redis_client):
    body = json_body(_GITHUB_PAYLOAD)
    resp = client.post(
        GITHUB_ENDPOINT,
        content=body,
        headers={
            "x-hub-signature-256": github_sig_header(body, TEST_GITHUB_SECRET),
            "x-github-event": "pull_request",
            "x-github-delivery": "delivery-gh-001",
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert resp.json()["event_id"] == "delivery-gh-001"

    redis_client.lpush.assert_awaited_once()
    key, raw_json = redis_client.lpush.call_args.args
    assert key == QUEUE_KEY

    envelope_dict = json.loads(raw_json)
    assert envelope_dict["source"] == "github"
    assert envelope_dict["event_type"] == "pull_request"
    assert envelope_dict["event_id"] == "delivery-gh-001"


def test_github_invalid_sig_does_not_enqueue(client, redis_client):
    body = json_body(_GITHUB_PAYLOAD)
    resp = client.post(
        GITHUB_ENDPOINT,
        content=body,
        headers={
            "x-hub-signature-256": github_sig_header(body, "bad_secret"),
            "x-github-event": "push",
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 400
    redis_client.lpush.assert_not_awaited()


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


def test_enqueue_exception_surfaces_as_500(client, redis_client):
    """If Upstash is unreachable the endpoint must return 500, not 200."""
    redis_client.lpush = AsyncMock(side_effect=ConnectionError("Upstash unreachable"))

    body = json_body(_STRIPE_PAYLOAD)
    resp = client.post(
        STRIPE_ENDPOINT,
        content=body,
        headers={
            "stripe-signature": stripe_sig_header(body, TEST_STRIPE_SECRET),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 500
