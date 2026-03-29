"""FlowPilot -- Agent 4: Follow-Up & Compliance Agent.

Monitors task completion, sends automated reminders, detects stalls,
and escalates to managers when deadlines are missed.
"""

import json
import logging
from datetime import datetime, timedelta

from src.models.schemas import (
    AgentName, AuditEvent, AuditEventType, CorrectionType,
    PipelineState, SelfCorrection, TaskStatus,
)
from src.utils.llm import get_llm
from src.utils.notifications import send_email, send_escalation, send_slack

logger = logging.getLogger(__name__)

# Simulated manager mapping
MANAGER_MAP = {
    "John Park": "Sarah Chen",
    "Maria Lopez": "Sarah Chen",
    "David Kim": "Sarah Chen",
    "Alex Rivera": "Sarah Chen",
    "Tom Wilson": "Sarah Chen",
    "Sarah Chen": "VP Engineering",
}

# SLA thresholds (in days)
SLA_CONFIG = {
    "critical": {"reminder_days": 1, "escalation_days": 2},
    "high": {"reminder_days": 2, "escalation_days": 4},
    "medium": {"reminder_days": 3, "escalation_days": 7},
    "low": {"reminder_days": 5, "escalation_days": 14},
}


def run(state: PipelineState) -> PipelineState:
    """Monitor tasks, send reminders, detect stalls, and escalate."""
    logger.info(f"[FollowUpAgent] Processing meeting: {state.meeting_id}")

    state.current_agent = AgentName.FOLLOWUP

    tasks = state.task_board.tasks
    if not tasks:
        state.errors.append("No tasks to monitor")
        return state

    now = datetime.now()
    notifications = []

    for task in tasks:
        # ── Check for unassigned tasks ────────────────────────────────
        if not task.assignee or task.assignee == "UNASSIGNED":
            manager = "Sarah Chen"  # Default escalation target
            notif = send_escalation(
                recipient=manager,
                task_title=task.title,
                reason="Task has no assigned owner after automated resolution attempt",
                escalated_by="FollowUp Agent",
            )
            notifications.append(notif)

            state.corrections.append(SelfCorrection(
                agent=AgentName.FOLLOWUP,
                correction_type=CorrectionType.ESCALATION,
                description=f"Task '{task.title}' remains unassigned. Escalated to {manager} for manual owner assignment.",
                before_state={"assignee": None, "status": task.status.value},
                after_state={"escalated_to": manager, "status": "escalated"},
                meeting_id=state.meeting_id,
            ))

            task.status = TaskStatus.ESCALATED
            continue

        # ── Determine SLA thresholds ──────────────────────────────────
        priority = task.priority.value
        sla = SLA_CONFIG.get(priority, SLA_CONFIG["medium"])

        # ── Send proactive reminders ──────────────────────────────────
        if task.deadline:
            try:
                deadline_dt = datetime.fromisoformat(task.deadline)
            except ValueError:
                deadline_dt = now + timedelta(days=7)

            days_until = (deadline_dt - now).days

            if task.status == TaskStatus.TODO:
                if days_until <= sla["reminder_days"]:
                    notif = send_slack(
                        recipient=task.assignee,
                        message=f"Reminder: '{task.title}' is due in {days_until} day(s) ({task.deadline}). Status: Not started. Please update progress.",
                        channel="task-reminders",
                    )
                    notifications.append(notif)

                    notif2 = send_email(
                        recipient=task.assignee,
                        subject=f"[FlowPilot] Task Due Soon: {task.title}",
                        body=f"Hi {task.assignee},\n\nYour task '{task.title}' is due on {task.deadline} ({days_until} days remaining).\nPriority: {priority.upper()}\nStatus: Not Started\n\nPlease update your progress or reach out if you need help.\n\nBest,\nFlowPilot",
                    )
                    notifications.append(notif2)

            # ── Detect missed deadlines ───────────────────────────────
            if days_until < 0 and task.status != TaskStatus.DONE:
                manager = MANAGER_MAP.get(task.assignee, "VP Engineering")

                notif = send_escalation(
                    recipient=manager,
                    task_title=task.title,
                    reason=f"Deadline missed by {abs(days_until)} day(s). Assignee: {task.assignee}. Original deadline: {task.deadline}",
                    escalated_by="FollowUp Agent",
                )
                notifications.append(notif)

                # Also notify the assignee
                send_slack(
                    recipient=task.assignee,
                    message=f"OVERDUE: '{task.title}' was due {task.deadline} ({abs(days_until)} day(s) ago). Your manager {manager} has been notified.",
                    channel="task-reminders",
                )

                state.corrections.append(SelfCorrection(
                    agent=AgentName.FOLLOWUP,
                    correction_type=CorrectionType.ESCALATION,
                    description=f"Deadline missed for '{task.title}' (due {task.deadline}, {abs(days_until)} days overdue). Escalated to {manager}. Suggesting new deadline: {(now + timedelta(days=3)).strftime('%Y-%m-%d')}.",
                    before_state={
                        "assignee": task.assignee,
                        "deadline": task.deadline,
                        "status": task.status.value,
                        "days_overdue": abs(days_until),
                    },
                    after_state={
                        "escalated_to": manager,
                        "suggested_new_deadline": (now + timedelta(days=3)).strftime("%Y-%m-%d"),
                        "status": "escalated",
                    },
                    meeting_id=state.meeting_id,
                ))

                task.status = TaskStatus.ESCALATED

                state.audit_trail.append(AuditEvent(
                    event_type=AuditEventType.DEADLINE_MISSED,
                    agent=AgentName.FOLLOWUP,
                    description=f"Deadline missed: '{task.title}' by {task.assignee}. Overdue by {abs(days_until)} days. Escalated to {manager}.",
                    data={
                        "task_id": task.id,
                        "assignee": task.assignee,
                        "deadline": task.deadline,
                        "days_overdue": abs(days_until),
                        "escalated_to": manager,
                    },
                    meeting_id=state.meeting_id,
                    task_id=task.id,
                ))

        # ── Detect stalls (tasks in progress too long) ────────────────
        if task.status == TaskStatus.IN_PROGRESS:
            created = datetime.fromisoformat(task.created_at)
            days_in_progress = (now - created).days

            if days_in_progress > sla["escalation_days"]:
                manager = MANAGER_MAP.get(task.assignee, "VP Engineering")
                notif = send_slack(
                    recipient=manager,
                    message=f"STALL DETECTED: '{task.title}' has been in progress for {days_in_progress} days (SLA: {sla['escalation_days']} days). Assignee: {task.assignee}.",
                    channel="escalations",
                )
                notifications.append(notif)

    # ── Compile follow-up summary via LLM ─────────────────────────────────
    llm = get_llm()
    task_summary = "\n".join(
        f"- [{t.priority.value.upper()}] {t.title} | Assignee: {t.assignee or 'NONE'} | Deadline: {t.deadline or 'N/A'} | Status: {t.status.value}"
        for t in tasks
    )
    response = llm.complete(
        system_prompt="You are a follow-up and compliance agent. Analyze task statuses and generate a brief summary of reminders sent, escalations raised, and stalls detected. Return JSON with keys: reminders_sent, escalations, stalls_detected.",
        user_prompt=f"Current task board:\n{task_summary}\n\nNotifications sent: {len(notifications)}",
    )

    state.notifications.extend(notifications)
    state.completed_agents.append(AgentName.FOLLOWUP)

    state.audit_trail.append(AuditEvent(
        event_type=AuditEventType.ESCALATION if any(t.status == TaskStatus.ESCALATED for t in tasks) else AuditEventType.TASK_CREATED,
        agent=AgentName.FOLLOWUP,
        description=f"Follow-up complete: {len(notifications)} notifications sent. {sum(1 for t in tasks if t.status == TaskStatus.ESCALATED)} tasks escalated.",
        data={
            "notifications_sent": len(notifications),
            "tasks_escalated": sum(1 for t in tasks if t.status == TaskStatus.ESCALATED),
            "tasks_on_track": sum(1 for t in tasks if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)),
        },
        meeting_id=state.meeting_id,
    ))

    logger.info(f"[FollowUpAgent] Done. {len(notifications)} notifications, {sum(1 for t in tasks if t.status == TaskStatus.ESCALATED)} escalations.")
    return state
