import httpx

from app.actions.base import ActionResult, BaseAction
from app.config import settings

_ACTION_ID = "send_slack_message"


def _build_text(params: dict) -> str:
    visible = {k: v for k, v in params.items() if not k.startswith("_")}
    if not visible:
        return "Webhook event received (no extracted parameters)."
    lines = "\n".join(f"• {k}: {v}" for k, v in visible.items())
    return f"Webhook event:\n{lines}"


class SendSlackMessage(BaseAction):
    async def execute(self, params: dict) -> ActionResult:
        text: str = params.get("text") or _build_text(params)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(settings.slack_webhook_url, json={"text": text})
                resp.raise_for_status()
            return ActionResult(success=True, action_id=_ACTION_ID, output={"text": text})
        except Exception as exc:
            return ActionResult(success=False, action_id=_ACTION_ID, error=str(exc))
