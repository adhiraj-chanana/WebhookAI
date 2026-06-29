import time

from tests.conftest import TEST_STRIPE_SECRET
from tests.helpers import json_body, stripe_sig_header

ENDPOINT = "/webhook/stripe"

_PAYLOAD = {
    "id": "evt_test_001",
    "type": "payment_intent.succeeded",
    "object": "event",
    "data": {"object": {"amount": 2000, "currency": "usd"}},
}


def test_stripe_valid_signature(client):
    body = json_body(_PAYLOAD)
    headers = {
        "stripe-signature": stripe_sig_header(body, TEST_STRIPE_SECRET),
        "content-type": "application/json",
    }
    resp = client.post(ENDPOINT, content=body, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["event_id"] == "evt_test_001"


def test_stripe_wrong_secret(client):
    body = json_body(_PAYLOAD)
    headers = {
        "stripe-signature": stripe_sig_header(body, "wrong_secret"),
        "content-type": "application/json",
    }
    resp = client.post(ENDPOINT, content=body, headers=headers)
    assert resp.status_code == 400


def test_stripe_missing_header(client):
    body = json_body(_PAYLOAD)
    resp = client.post(ENDPOINT, content=body, headers={"content-type": "application/json"})
    assert resp.status_code == 400


def test_stripe_tampered_body(client):
    body = json_body(_PAYLOAD)
    sig = stripe_sig_header(body, TEST_STRIPE_SECRET)
    tampered = body + b"extra"
    resp = client.post(
        ENDPOINT,
        content=tampered,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_stripe_expired_timestamp(client):
    body = json_body(_PAYLOAD)
    old_ts = int(time.time()) - 400  # beyond 5-minute tolerance
    sig = stripe_sig_header(body, TEST_STRIPE_SECRET, timestamp=old_ts)
    resp = client.post(
        ENDPOINT,
        content=body,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_stripe_unknown_source(client):
    resp = client.post("/webhook/unknown_source", content=b"{}", headers={"content-type": "application/json"})
    assert resp.status_code == 422  # Pydantic rejects unknown WebhookSource
