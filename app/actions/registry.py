from app.actions.base import BaseAction
from app.actions.email import SendEmail
from app.actions.log_event import LogEvent
from app.actions.slack import SendSlackMessage

ACTION_REGISTRY: dict[str, BaseAction] = {
    "send_slack_message": SendSlackMessage(),
    "send_email": SendEmail(),
    "log_event": LogEvent(),
}
