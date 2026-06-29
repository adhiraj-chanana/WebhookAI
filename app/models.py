from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WebhookSource(StrEnum):
    stripe = "stripe"
    github = "github"
    slack = "slack"


class WebhookEnvelope(BaseModel):
    """Normalised envelope written to Redis for every verified webhook."""

    source: WebhookSource
    event_type: str
    event_id: str | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: dict[str, Any]
    headers: dict[str, str] = Field(default_factory=dict)
