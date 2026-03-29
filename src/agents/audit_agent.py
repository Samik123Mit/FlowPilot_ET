"""FlowPilot -- Agent 5: Audit & Analytics Agent.

Maintains complete decision trail, generates meeting effectiveness scores,
tracks patterns, and produces intelligence reports.
"""

import json
import logging
from datetime import datetime

from src.models.schemas import (
    AgentName, AuditEvent, AuditEventType, CorrectionType,
    PipelineState, SelfCorrection, TaskStatus,
)
from src.models.database import (
    save_meeting, save_decision, save_task, save_audit_event,
    save_correction,
)
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    """Generate analytics, persist audit trail, and produce intelligence report."""
    logger.info(f"[AuditAgent] Processing meeting: {state.meeting_id}")

    state.current_agent = AgentName.AUDIT

    # ── Step 1: Calculate analytics ───────────────────────────────────────
    analytics = _compute_analytics(state)
    state.analytics = analytics

    # ── Step 2: Persist to database ───────────────────────────────────────
    _persist_state(state)

    # ── Step 3: Generate intelligence report via LLM ──────────────────────
    llm = get_llm()
    report_prompt = _build_report_prompt(state, analytics)
    report_response = llm.complete(
        system_prompt="You are an audit and analytics agent. Produce a meeting intelligence report with scores, risk factors, and recommendations. Return JSON with keys: meeting_effectiveness_score, action_item_clarity_score, ownership_coverage, deadline_specificity, follow_through_prediction, risk_factors, recommendations.",
        user_prompt=report_prompt,
    )

    try:
        report_data = json.loads(report_response)
        analytics.update(report_data)
        state.analytics = analytics
    except json.JSONDecodeError:
        logger.warning("[AuditAgent] Could not parse LLM report, using computed analytics only")

    # ── Step 4: Audit the audit ───────────────────────────────────────────
    state.completed_agents.append(AgentName.AUDIT)

    state.audit_trail.append(AuditEvent(
        event_type=AuditEventType.MEETING_PROCESSED,
        agent=AgentName.AUDIT,
        description=f"Audit complete. Effectiveness: {analytics.get('meeting_effectiveness_score', 'N/A')}%. {len(state.corrections)} self-corrections recorded. Full trail persisted to database.",
        data={
            "analytics_summary": {
                "effectiveness": analytics.get("meeting_effectiveness_score"),
                "total_decisions": analytics.get("total_decisions", 0),
                "total_actions": analytics.get("total_actions", 0),
                "total_tasks": analytics.get("total_tasks", 0),
                "corrections_count": len(state.corrections),
                "notifications_count": len(state.notifications),
            }
        },
        meeting_id=state.meeting_id,
    ))

    state.status = "completed"
    logger.info(f"[AuditAgent] Done. Meeting score: {analytics.get('meeting_effectiveness_score', 'N/A')}%")
    return state


def _compute_analytics(state: PipelineState) -> dict:
    """Compute detailed analytics from pipeline state."""
    tasks = state.task_board.tasks
    extraction = state.extraction

    total_tasks = len(tasks)
    total_decisions = len(extraction.decisions) if extraction else 0
    total_actions = len(extraction.action_items) if extraction else 0
    total_corrections = len(state.corrections)

    # Task breakdown
    by_status = {}
    for t in tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

    by_priority = {}
    for t in tasks:
        by_priority[t.priority.value] = by_priority.get(t.priority.value, 0) + 1

    # Ownership coverage
    assigned = sum(1 for t in tasks if t.assignee and t.assignee != "UNASSIGNED")
    ownership_pct = (assigned / total_tasks * 100) if total_tasks > 0 else 0

    # Deadline coverage
    with_deadline = sum(1 for t in tasks if t.deadline)
    deadline_pct = (with_deadline / total_tasks * 100) if total_tasks > 0 else 0

    # Workload distribution
    workload = {}
    for t in tasks:
        if t.assignee:
            workload[t.assignee] = workload.get(t.assignee, 0) + t.estimated_hours

    # Correction breakdown
    correction_types = {}
    for c in state.corrections:
        ct = c.correction_type.value
        correction_types[ct] = correction_types.get(ct, 0) + 1

    # Agent performance
    agent_corrections = {}
    for c in state.corrections:
        a = c.agent.value
        agent_corrections[a] = agent_corrections.get(a, 0) + 1

    # Meeting effectiveness (heuristic)
    effectiveness = min(100, int(
        (ownership_pct * 0.3) +
        (deadline_pct * 0.25) +
        (min(total_actions, 10) / 10 * 25) +
        (max(0, 20 - total_corrections * 3))
    ))

    return {
        "meeting_id": state.meeting_id,
        "meeting_title": state.transcript.title if state.transcript else "Unknown",
        "processed_at": datetime.now().isoformat(),
        "total_decisions": total_decisions,
        "total_actions": total_actions,
        "total_tasks": total_tasks,
        "total_corrections": total_corrections,
        "total_notifications": len(state.notifications),
        "meeting_effectiveness_score": effectiveness,
        "ownership_coverage": round(ownership_pct, 1),
        "deadline_specificity": round(deadline_pct, 1),
        "tasks_by_status": by_status,
        "tasks_by_priority": by_priority,
        "workload_distribution": workload,
        "correction_breakdown": correction_types,
        "agent_corrections": agent_corrections,
        "ambiguities": extraction.ambiguities if extraction else [],
        "transcript_quality": state.transcript.quality_score if state.transcript else 0,
    }


def _persist_state(state: PipelineState):
    """Save all pipeline data to SQLite for persistent audit trail."""
    try:
        # Save meeting
        if state.transcript:
            save_meeting(
                meeting_id=state.meeting_id,
                title=state.transcript.title,
                date=state.transcript.date,
                raw_text=state.transcript.raw_text,
                participants=[p.name for p in state.transcript.participants],
                quality_score=state.transcript.quality_score,
            )

        # Save decisions
        if state.extraction:
            for dec in state.extraction.decisions:
                save_decision(
                    decision_id=dec.id,
                    meeting_id=state.meeting_id,
                    text=dec.text,
                    made_by=dec.made_by,
                    context=dec.context,
                    confidence=dec.confidence,
                    source_segment_index=dec.source_segment_index,
                )

        # Save tasks
        for task in state.task_board.tasks:
            save_task(task.model_dump())

        # Save audit events
        for event in state.audit_trail:
            save_audit_event(event.model_dump())

        # Save corrections
        for correction in state.corrections:
            save_correction(correction.model_dump())

        logger.info(f"[AuditAgent] Persisted full state to database for meeting {state.meeting_id}")

    except Exception as e:
        logger.error(f"[AuditAgent] Database persistence error: {e}")


def _build_report_prompt(state: PipelineState, analytics: dict) -> str:
    """Build a comprehensive prompt for the LLM intelligence report."""
    tasks_summary = "\n".join(
        f"- {t.title} | Owner: {t.assignee} | Priority: {t.priority.value} | Status: {t.status.value}"
        for t in state.task_board.tasks
    )
    corrections_summary = "\n".join(
        f"- [{c.agent.value}] {c.description}"
        for c in state.corrections
    )

    return f"""Meeting: {analytics.get('meeting_title', 'Unknown')}
Total decisions: {analytics['total_decisions']}
Total action items: {analytics['total_actions']}
Total tasks created: {analytics['total_tasks']}
Ownership coverage: {analytics['ownership_coverage']}%
Deadline coverage: {analytics['deadline_specificity']}%

Tasks:
{tasks_summary}

Self-corrections applied:
{corrections_summary or 'None'}

Ambiguities: {', '.join(analytics.get('ambiguities', [])) or 'None'}

Provide meeting effectiveness score, risk factors, and recommendations."""
