import uuid
from datetime import datetime, timezone

from app.actions.base import ActionResult, BaseAction
from app.config import settings

_ACTION_ID = "log_event"
_TABLE = "webhook_events"


def get_supabase_client():
    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_key)


class LogEvent(BaseAction):
    async def execute(self, params: dict) -> ActionResult:
        row_id = str(uuid.uuid4())
        # Extract routing metadata injected by the worker; remaining keys go to params jsonb
        metadata_keys = {"source", "event_type", "action_id", "confidence"}
        row = {
            "id": row_id,
            "source": params.get("source", "unknown"),
            "event_type": params.get("event_type", "unknown"),
            "action_id": params.get("action_id", _ACTION_ID),
            "confidence": params.get("confidence"),
            "params": {k: v for k, v in params.items() if k not in metadata_keys},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            client = get_supabase_client()
            client.table(_TABLE).insert(row).execute()
            return ActionResult(success=True, action_id=_ACTION_ID, output={"id": row_id})
        except Exception as exc:
            return ActionResult(success=False, action_id=_ACTION_ID, error=str(exc))
