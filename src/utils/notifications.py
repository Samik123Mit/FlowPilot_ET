"""FlowPilot -- Email and Slack notification simulation."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory notification log
_notification_log: list[dict] = []


def send_slack(recipient: str, message: str, channel: str = "general") -> dict:
    notif = {
        "type": "slack",
        "recipient": recipient,
        "channel": channel,
        "message": message,
        "sent_at": datetime.now().isoformat(),
        "status": "delivered",
    }
    _notification_log.append(notif)
    logger.info(f"[Slack -> #{channel}] @{recipient}: {message[:80]}...")
    return notif


def send_email(recipient: str, subject: str, body: str) -> dict:
    notif = {
        "type": "email",
        "recipient": recipient,
        "subject": subject,
        "message": body,
        "sent_at": datetime.now().isoformat(),
        "status": "delivered",
    }
    _notification_log.append(notif)
    logger.info(f"[Email -> {recipient}] Subject: {subject}")
    return notif


def send_escalation(recipient: str, task_title: str, reason: str, escalated_by: str = "FlowPilot") -> dict:
    message = f"ESCALATION: Task '{task_title}' requires attention. Reason: {reason}. Escalated by {escalated_by}."
    notif = {
        "type": "escalation",
        "recipient": recipient,
        "message": message,
        "reason": reason,
        "task_title": task_title,
        "sent_at": datetime.now().isoformat(),
        "status": "delivered",
    }
    _notification_log.append(notif)
    logger.warning(f"[ESCALATION -> {recipient}] {task_title}: {reason}")
    return notif


def get_all_notifications() -> list[dict]:
    return list(_notification_log)


def clear_notifications():
    _notification_log.clear()
