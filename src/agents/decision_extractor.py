"""FlowPilot -- Agent 2: Decision & Action Extraction Agent.

Extracts decisions, action items, deadlines, owners, and dependencies
from structured transcript. Self-corrects for missing owners and ambiguities.
"""

import json
import logging
from datetime import datetime, timedelta

from src.models.schemas import (
    ActionItem, AgentName, AuditEvent, AuditEventType, CorrectionType,
    Decision, ExtractionResult, PipelineState, Priority, SelfCorrection,
)
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a decision and action extraction agent for enterprise meetings.
Analyze meeting transcripts to extract:

1. DECISIONS: Explicit agreements or rulings made during the meeting.
2. ACTION ITEMS: Tasks that need to be completed, with owner, deadline, priority.

Output JSON:
{
  "decisions": [
    {"text": "Decision text", "made_by": "Person Name", "context": "Why this was decided", "confidence": 0.95}
  ],
  "action_items": [
    {
      "title": "Short task title",
      "description": "Detailed description",
      "owner": "Person Name or null if unclear",
      "deadline": "Specific date/time or relative like 'end of sprint'",
      "priority": "critical|high|medium|low",
      "source_text": "Exact quote from transcript that implies this action",
      "confidence": 0.9
    }
  ],
  "ambiguities": ["List of unclear items that need human clarification"]
}

Rules:
- If someone says "someone should..." or uses passive voice, mark owner as null.
- Infer priority from urgency words: "ASAP", "critical", "blocker" -> critical/high.
- Flag vague deadlines like "soon" or "when possible" as ambiguities.
- Cross-reference: if Person A says they'll do X, they're the owner.
- Look for implicit actions: "We need to..." implies an action even without explicit assignment.
"""

# Known team members for owner resolution (simulated org chart)
DEFAULT_ORG = {
    "Sarah Chen": {"role": "Engineering Manager", "department": "Engineering", "reports_to": "VP Engineering"},
    "John Park": {"role": "Senior Backend Engineer", "department": "Engineering", "skills": ["API", "backend", "Python"]},
    "Maria Lopez": {"role": "Frontend Engineer", "department": "Engineering", "skills": ["React", "UI", "frontend"]},
    "David Kim": {"role": "Backend Engineer", "department": "Engineering", "skills": ["auth", "security", "backend"]},
    "Alex Rivera": {"role": "QA Engineer", "department": "Engineering", "skills": ["testing", "QA", "load testing"]},
    "Priya Sharma": {"role": "Product Manager", "department": "Product", "skills": ["product", "roadmap", "stakeholders"]},
    "Tom Wilson": {"role": "DevOps Engineer", "department": "Infrastructure", "skills": ["deployment", "CI/CD", "infra"]},
}


def run(state: PipelineState) -> PipelineState:
    """Extract decisions and action items from transcript."""
    logger.info(f"[DecisionExtractor] Processing meeting: {state.meeting_id}")

    state.current_agent = AgentName.DECISION_EXTRACTOR

    if not state.transcript:
        state.errors.append("No transcript available for decision extraction")
        return state

    # ── Step 1: Build context from transcript ─────────────────────────────
    transcript_text = "\n".join(
        f"[{seg.speaker}] ({seg.timestamp or 'N/A'}): {seg.text}"
        for seg in state.transcript.segments
    )
    participants = [p.name for p in state.transcript.participants]

    # ── Step 2: Extract via LLM ───────────────────────────────────────────
    llm = get_llm()
    response = llm.complete(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"Meeting participants: {', '.join(participants)}\n\nTranscript:\n{transcript_text}",
    )

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("[DecisionExtractor] Failed to parse LLM response")
        data = {"decisions": [], "action_items": [], "ambiguities": ["LLM parsing failed"]}

    # ── Step 3: Build decision objects ────────────────────────────────────
    decisions = []
    for d in data.get("decisions", []):
        decisions.append(Decision(
            text=d["text"],
            made_by=d.get("made_by"),
            context=d.get("context", ""),
            confidence=float(d.get("confidence", 0.9)),
        ))

    # ── Step 4: Build action items with self-correction ───────────────────
    action_items = []
    for item in data.get("action_items", []):
        owner = item.get("owner")
        owner_resolved = owner is not None and owner in DEFAULT_ORG

        ai = ActionItem(
            title=item["title"],
            description=item.get("description", ""),
            owner=owner,
            owner_resolved=owner_resolved,
            deadline=item.get("deadline"),
            priority=_parse_priority(item.get("priority", "medium")),
            source_text=item.get("source_text", ""),
            confidence=float(item.get("confidence", 0.9)),
        )

        # ── Self-Correction: Resolve missing owners ───────────────────
        if not owner_resolved:
            resolved_owner = _resolve_owner(ai, participants)
            if resolved_owner:
                before = {"owner": owner, "resolved": False}
                ai.owner = resolved_owner
                ai.owner_resolved = True

                state.corrections.append(SelfCorrection(
                    agent=AgentName.DECISION_EXTRACTOR,
                    correction_type=CorrectionType.OWNER_RESOLVED,
                    description=f"Action '{ai.title}' had no clear owner. Auto-resolved to '{resolved_owner}' based on skill matching and availability in org chart.",
                    before_state=before,
                    after_state={"owner": resolved_owner, "resolved": True, "method": "skill_match"},
                    meeting_id=state.meeting_id,
                ))

                state.audit_trail.append(AuditEvent(
                    event_type=AuditEventType.SELF_CORRECTION,
                    agent=AgentName.DECISION_EXTRACTOR,
                    description=f"Auto-assigned '{ai.title}' to {resolved_owner} (no owner specified in meeting)",
                    data={"action": ai.title, "assigned_to": resolved_owner, "method": "skill_match"},
                    meeting_id=state.meeting_id,
                ))
            else:
                ai.owner = "UNASSIGNED"
                state.corrections.append(SelfCorrection(
                    agent=AgentName.DECISION_EXTRACTOR,
                    correction_type=CorrectionType.ESCALATION,
                    description=f"Action '{ai.title}' has no clear owner and could not be auto-resolved. Flagged for manager review.",
                    before_state={"owner": None},
                    after_state={"owner": "UNASSIGNED", "escalated": True},
                    meeting_id=state.meeting_id,
                ))

        # Link to decisions
        if decisions:
            ai.source_decision_id = decisions[0].id

        action_items.append(ai)

    # ── Step 5: Validate deadline specificity ─────────────────────────────
    for ai in action_items:
        if ai.deadline and ai.deadline.lower() in ["soon", "when possible", "asap", "later", "tbd"]:
            original_deadline = ai.deadline
            ai.deadline = _resolve_vague_deadline(ai.deadline, ai.priority)
            state.corrections.append(SelfCorrection(
                agent=AgentName.DECISION_EXTRACTOR,
                correction_type=CorrectionType.DEADLINE_ADJUSTED,
                description=f"Vague deadline '{original_deadline}' for '{ai.title}' resolved to '{ai.deadline}' based on priority level.",
                before_state={"deadline": original_deadline},
                after_state={"deadline": ai.deadline, "method": "priority_based_default"},
                meeting_id=state.meeting_id,
            ))

    # ── Step 6: Store results ─────────────────────────────────────────────
    state.extraction = ExtractionResult(
        meeting_id=state.meeting_id,
        decisions=decisions,
        action_items=action_items,
        ambiguities=data.get("ambiguities", []),
    )
    state.completed_agents.append(AgentName.DECISION_EXTRACTOR)

    # ── Audit event ───────────────────────────────────────────────────────
    state.audit_trail.append(AuditEvent(
        event_type=AuditEventType.DECISION_EXTRACTED,
        agent=AgentName.DECISION_EXTRACTOR,
        description=f"Extracted {len(decisions)} decisions and {len(action_items)} action items. {len(data.get('ambiguities', []))} ambiguities flagged.",
        data={
            "decisions_count": len(decisions),
            "action_items_count": len(action_items),
            "ambiguities": data.get("ambiguities", []),
            "unresolved_owners": sum(1 for a in action_items if not a.owner_resolved),
        },
        meeting_id=state.meeting_id,
    ))

    logger.info(f"[DecisionExtractor] Done. {len(decisions)} decisions, {len(action_items)} actions")
    return state


def _parse_priority(raw: str) -> Priority:
    mapping = {
        "critical": Priority.CRITICAL, "high": Priority.HIGH,
        "medium": Priority.MEDIUM, "low": Priority.LOW,
    }
    return mapping.get(raw.lower(), Priority.MEDIUM)


def _resolve_owner(action: ActionItem, participants: list[str]) -> str | None:
    """Try to match an action to the most appropriate team member based on skills."""
    title_lower = action.title.lower() + " " + action.description.lower()

    best_match = None
    best_score = 0

    for name, info in DEFAULT_ORG.items():
        if name not in participants:
            continue
        skills = info.get("skills", [])
        score = sum(1 for skill in skills if skill.lower() in title_lower)
        if score > best_score:
            best_score = score
            best_match = name

    return best_match


def _resolve_vague_deadline(vague: str, priority: Priority) -> str:
    """Convert vague deadlines to concrete dates based on priority."""
    today = datetime.now()
    offset_map = {
        Priority.CRITICAL: 2,
        Priority.HIGH: 5,
        Priority.MEDIUM: 10,
        Priority.LOW: 14,
    }
    days = offset_map.get(priority, 7)
    target = today + timedelta(days=days)
    return target.strftime("%Y-%m-%d")
