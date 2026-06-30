import httpx

from app.actions.base import ActionResult, BaseAction
from app.config import settings

_ACTION_ID = "send_email"
_RESEND_URL = "https://api.resend.com/emails"


def _build_subject(params: dict) -> str:
    event_type = params.get("event_type", "webhook event")
    source = params.get("source", "")
    return f"[{source}] {event_type}".strip(" []").title() if source else event_type.title()


def _build_body(params: dict) -> str:
    visible = {k: v for k, v in params.items() if k not in ("subject", "text")}
    if not visible:
        return "A webhook event was received with no extracted parameters."
    lines = "\n".join(f"  {k}: {v}" for k, v in visible.items())
    return f"Webhook event details:\n{lines}"


class SendEmail(BaseAction):
    async def execute(self, params: dict) -> ActionResult:
        subject = params.get("subject") or _build_subject(params)
        text = params.get("text") or _build_body(params)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _RESEND_URL,
                    json={
                        "from": "onboarding@resend.dev",
                        "to": [settings.resend_to_email],
                        "subject": subject,
                        "text": text,
                    },
                    headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                )
                resp.raise_for_status()
            return ActionResult(success=True, action_id=_ACTION_ID, output=resp.json())
        except Exception as exc:
            return ActionResult(success=False, action_id=_ACTION_ID, error=str(exc))
