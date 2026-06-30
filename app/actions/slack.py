import httpx

from app.actions.base import ActionResult, BaseAction
from app.config import settings

_ACTION_ID = "send_slack_message"


class SendSlackMessage(BaseAction):
    async def execute(self, params: dict) -> ActionResult:
        text: str = params["text"]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(settings.slack_webhook_url, json={"text": text})
                resp.raise_for_status()
            return ActionResult(success=True, action_id=_ACTION_ID, output={"text": text})
        except Exception as exc:
            return ActionResult(success=False, action_id=_ACTION_ID, error=str(exc))
