import hashlib
import hmac
import time

from fastapi import HTTPException, Request, status


_TOLERANCE_SECONDS = 300


async def verify_slack(request: Request, secret: str) -> bytes:
    """
    Verify a Slack webhook signature (X-Slack-Signature / X-Slack-Request-Timestamp).

    Returns the raw body on success; raises HTTP 400 on failure.
    """
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    sig_header = request.headers.get("x-slack-signature", "")
    body = await request.body()

    if not timestamp or not sig_header:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing Slack signature headers")

    try:
        ts = int(timestamp)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Slack request timestamp")

    if abs(time.time() - ts) > _TOLERANCE_SECONDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Slack webhook timestamp too old")

    basestring = f"v0:{timestamp}:".encode() + body
    expected = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig_header):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Slack signature")

    return body
