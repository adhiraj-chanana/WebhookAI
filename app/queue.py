from typing import Annotated

from fastapi import Depends
from upstash_redis.asyncio import Redis as UpstashRedis

from app.config import settings

QUEUE_KEY = "webhooks:queue"
DLQ_KEY = "webhooks:dlq"


def get_redis() -> UpstashRedis:
    return UpstashRedis(
        url=settings.upstash_redis_rest_url,
        token=settings.upstash_redis_rest_token,
    )


# Convenience type alias for route signatures
RedisDep = Annotated[UpstashRedis, Depends(get_redis)]
