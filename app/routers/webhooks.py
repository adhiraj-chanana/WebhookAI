import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.models import WebhookEnvelope, WebhookSource
from app.normalisation import build_envelope
from app.queue import QUEUE_KEY, RedisDep
from app.verification.github import verify_github
from app.verification.slack import verify_slack
from app.verification.stripe import verify_stripe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhooks"])


async def _verify_and_build(source: WebhookSource, request: Request) -> WebhookEnvelope:
    if source == WebhookSource.stripe:
        if not settings.stripe_webhook_secret:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe secret not configured")
        body = await verify_stripe(request, settings.stripe_webhook_secret)

    elif source == WebhookSource.github:
        if not settings.github_webhook_secret:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GitHub secret not configured")
        body = await verify_github(request, settings.github_webhook_secret)

    elif source == WebhookSource.slack:
        if not settings.slack_signing_secret:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Slack secret not configured")
        body = await verify_slack(request, settings.slack_signing_secret)

    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown source: {source}")

    return build_envelope(source, body, request)


@router.post("/{source}")
async def receive_webhook(source: WebhookSource, request: Request, redis: RedisDep) -> dict:
    envelope = await _verify_and_build(source, request)
    await redis.lpush(QUEUE_KEY, envelope.model_dump_json())
    return {"status": "queued", "event_id": envelope.event_id}
