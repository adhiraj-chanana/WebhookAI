"""Signature-generation helpers shared across test modules."""

import hashlib
import hmac
import json
import time


def stripe_sig_header(body: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    signed = f"{ts}.".encode() + body
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def github_sig_header(body: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def slack_sig_header(
    body: bytes, secret: str, timestamp: int | None = None
) -> tuple[str, str]:
    ts = timestamp if timestamp is not None else int(time.time())
    basestring = f"v0:{ts}:".encode() + body
    sig = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return str(ts), sig


def json_body(data: dict) -> bytes:
    return json.dumps(data).encode()
