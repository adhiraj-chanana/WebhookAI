import logging

from app.actions.base import ActionResult, BaseAction
from app.config import settings

logger = logging.getLogger(__name__)

_ACTION_ID = "log_event"
_TABLE = "webhook_events"

# Keys that map to named columns — everything else is nested into params jsonb
_COLUMN_KEYS = {"source", "event_type", "action_id", "confidence"}


def get_supabase_client():
    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_key)


class LogEvent(BaseAction):
    async def execute(self, params: dict) -> ActionResult:
        row = {
            "source": params.get("source", "unknown"),
            "event_type": params.get("event_type", "unknown"),
            "action_id": params.get("action_id", _ACTION_ID),
            "confidence": params.get("confidence"),
            # Everything not in a named column goes into the jsonb blob
            "params": {k: v for k, v in params.items() if k not in _COLUMN_KEYS},
        }
        try:
            client = get_supabase_client()
            response = client.table(_TABLE).insert(row).execute()
            row_id = response.data[0].get("id") if response.data else None
            return ActionResult(success=True, action_id=_ACTION_ID, output={"id": row_id})
        except Exception as exc:
            logger.error(
                "LogEvent insert failed | table=%s | row=%r | error=%r",
                _TABLE,
                row,
                exc,
                exc_info=True,
            )
            return ActionResult(success=False, action_id=_ACTION_ID, error=str(exc))
