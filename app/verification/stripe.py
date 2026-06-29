import hashlib
import hmac
import time

from fastapi import HTTPException, Request, status


_TOLERANCE_SECONDS = 300  # Stripe default: 5 minutes


async def verify_stripe(request: Request, secret: str) -> bytes:
    """
    Verify a Stripe webhook signature.

    Stripe sends:
      Stripe-Signature: t=<timestamp>,v1=<sig>[,v1=<sig2>...]

    Returns the raw body on success; raises HTTP 400 on failure.
    """
    sig_header = request.headers.get("stripe-signature", "")
    body = await request.body()

    parts: dict[str, list[str]] = {}
    for part in sig_header.split(","):
        k, _, v = part.partition("=")
        parts.setdefault(k, []).append(v)

    timestamp_str = parts.get("t", [None])[0]
    signatures = parts.get("v1", [])

    if not timestamp_str or not signatures:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing Stripe-Signature header fields")

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Stripe-Signature timestamp")

    if abs(time.time() - timestamp) > _TOLERANCE_SECONDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stripe webhook timestamp too old")

    signed_payload = f"{timestamp_str}.".encode() + body
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Stripe signature")

    return body
