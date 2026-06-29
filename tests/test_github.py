from tests.conftest import TEST_GITHUB_SECRET
from tests.helpers import github_sig_header, json_body

ENDPOINT = "/webhook/github"

_PAYLOAD = {
    "action": "opened",
    "number": 42,
    "pull_request": {"title": "Add feature", "state": "open"},
    "repository": {"full_name": "org/repo"},
}


def test_github_valid_signature(client):
    body = json_body(_PAYLOAD)
    headers = {
        "x-hub-signature-256": github_sig_header(body, TEST_GITHUB_SECRET),
        "x-github-event": "pull_request",
        "x-github-delivery": "abc-delivery-id",
        "content-type": "application/json",
    }
    resp = client.post(ENDPOINT, content=body, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["event_id"] == "abc-delivery-id"


def test_github_wrong_secret(client):
    body = json_body(_PAYLOAD)
    headers = {
        "x-hub-signature-256": github_sig_header(body, "wrong_secret"),
        "x-github-event": "push",
        "content-type": "application/json",
    }
    resp = client.post(ENDPOINT, content=body, headers=headers)
    assert resp.status_code == 400


def test_github_missing_header(client):
    body = json_body(_PAYLOAD)
    resp = client.post(
        ENDPOINT,
        content=body,
        headers={"x-github-event": "push", "content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_github_tampered_body(client):
    body = json_body(_PAYLOAD)
    sig = github_sig_header(body, TEST_GITHUB_SECRET)
    tampered = body + b"x"
    resp = client.post(
        ENDPOINT,
        content=tampered,
        headers={
            "x-hub-signature-256": sig,
            "x-github-event": "push",
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 400


def test_github_push_event_type(client):
    body = json_body({"ref": "refs/heads/main", "commits": []})
    headers = {
        "x-hub-signature-256": github_sig_header(body, TEST_GITHUB_SECRET),
        "x-github-event": "push",
        "x-github-delivery": "push-delivery-xyz",
        "content-type": "application/json",
    }
    resp = client.post(ENDPOINT, content=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
