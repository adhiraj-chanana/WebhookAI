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


# ---------------------------------------------------------------------------
# Replay — defined BEFORE /{source} so FastAPI doesn't consume it
# ---------------------------------------------------------------------------


@router.post("/replay/{event_id}")
async def replay_event(event_id: str, redis: RedisDep) -> dict:
    """
    Fetch a stored webhook_event row from Supabase, reconstruct its
    WebhookEnvelope, and re-enqueue it for processing.
    """
    from supabase import create_client

    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Supabase not configured")

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    result = client.table("webhook_events").select("*").eq("id", event_id).execute()

    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Event {event_id!r} not found")

    row = result.data[0]
    params: dict = row.get("params") or {}

    try:
        source = WebhookSource(row["source"])
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown source {row['source']!r}")

    envelope = WebhookEnvelope(
        source=source,
        event_type=row["event_type"],
        event_id=params.get("event_id"),
        raw_payload=params.get("raw_payload") or {},
        headers={},
    )

    await redis.lpush(QUEUE_KEY, envelope.model_dump_json())
    logger.info("Replayed event id=%s source=%s event_type=%s", event_id, source, row["event_type"])
    return {"status": "queued", "event_id": event_id}


# ---------------------------------------------------------------------------
# Inbound webhook ingestion
# ---------------------------------------------------------------------------


@router.post("/{source}")
async def receive_webhook(source: WebhookSource, request: Request, redis: RedisDep) -> dict:
    envelope = await _verify_and_build(source, request)
    await redis.lpush(QUEUE_KEY, envelope.model_dump_json())
    return {"status": "queued", "event_id": envelope.event_id}
