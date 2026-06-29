import hashlib
import hmac

from fastapi import HTTPException, Request, status


async def verify_github(request: Request, secret: str) -> bytes:
    """
    Verify a GitHub webhook signature (X-Hub-Signature-256).

    Returns the raw body on success; raises HTTP 400 on failure.
    """
    sig_header = request.headers.get("x-hub-signature-256", "")
    body = await request.body()

    if not sig_header.startswith("sha256="):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing X-Hub-Signature-256 header")

    received_sig = sig_header.removeprefix("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received_sig):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid GitHub signature")

    return body
