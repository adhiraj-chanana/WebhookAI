"""
Standalone async worker.

Run with:
    python -m app.worker

Polls the Upstash Redis LIST via HTTP, processes each WebhookEnvelope with
up to 3 retries (delays: 5 s → 30 s → 300 s), then dead-letters failures.
"""

import asyncio
import json
import logging

from upstash_redis.asyncio import Redis as UpstashRedis

from app.models import WebhookEnvelope
from app.queue import DLQ_KEY, QUEUE_KEY, get_redis

logger = logging.getLogger(__name__)

# Seconds to wait before retry 1, 2, 3  (gives 4 total attempts)
_RETRY_DELAYS = (5, 30, 300)


async def process_webhook(envelope_dict: dict) -> None:
    """
    Deserialise the envelope and dispatch it.
    Week 3 will replace the log statement with LLM routing.
    """
    envelope = WebhookEnvelope.model_validate(envelope_dict)
    logger.info(
        "Processing webhook source=%s event_type=%s event_id=%s",
        envelope.source,
        envelope.event_type,
        envelope.event_id,
    )
    # --- Week 3: LLM routing goes here ---


async def _run_with_retry(redis: UpstashRedis, envelope_dict: dict) -> None:
    last_exc: Exception | None = None
    total_attempts = len(_RETRY_DELAYS) + 1  # 4

    for attempt in range(total_attempts):
        try:
            await process_webhook(envelope_dict)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < len(_RETRY_DELAYS):
                wait = _RETRY_DELAYS[attempt]
                logger.warning(
                    "Attempt %d/%d failed, retrying in %ds: %r",
                    attempt + 1,
                    total_attempts,
                    wait,
                    exc,
                )
                await asyncio.sleep(wait)

    logger.error(
        "Dead-lettered after %d attempts | envelope=%r | error=%r",
        total_attempts,
        envelope_dict,
        last_exc,
    )
    dlq_entry = json.dumps({"envelope": envelope_dict, "error": str(last_exc)})
    await redis.lpush(DLQ_KEY, dlq_entry)


async def run_worker() -> None:
    redis = get_redis()
    logger.info("Worker started, polling list '%s'", QUEUE_KEY)

    while True:
        raw: str | None = await redis.rpop(QUEUE_KEY)
        if raw is None:
            await asyncio.sleep(1)
            continue

        try:
            envelope_dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Undecodable message, skipping | raw=%r | error=%r", raw, exc)
            continue

        await _run_with_retry(redis, envelope_dict)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker())
