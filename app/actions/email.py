import httpx

from app.actions.base import ActionResult, BaseAction
from app.config import settings

_ACTION_ID = "send_email"
_RESEND_URL = "https://api.resend.com/emails"


class SendEmail(BaseAction):
    async def execute(self, params: dict) -> ActionResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _RESEND_URL,
                    json={
                        "from": "onboarding@resend.dev",
                        "to": [params.get("to", settings.resend_to_email)],
                        "subject": params["subject"],
                        "text": params["body"],
                    },
                    headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                )
                resp.raise_for_status()
            return ActionResult(success=True, action_id=_ACTION_ID, output=resp.json())
        except Exception as exc:
            return ActionResult(success=False, action_id=_ACTION_ID, error=str(exc))
