"""FlowPilot -- Main multi-agent pipeline orchestrator.

Runs the 5-agent pipeline in sequence with error handling,
state management, and self-correction at the orchestration level.
"""

import logging
import time
from datetime import datetime

from src.models.schemas import (
    AgentName, AuditEvent, AuditEventType, MeetingInput,
    PipelineState, ProcessMeetingResponse,
)
from src.agents import (
    transcription_agent,
    decision_extractor,
    task_orchestrator,
    followup_agent,
    audit_agent,
)

logger = logging.getLogger(__name__)

# Agent execution order
AGENT_PIPELINE = [
    (AgentName.TRANSCRIPTION, transcription_agent),
    (AgentName.DECISION_EXTRACTOR, decision_extractor),
    (AgentName.TASK_ORCHESTRATOR, task_orchestrator),
    (AgentName.FOLLOWUP, followup_agent),
    (AgentName.AUDIT, audit_agent),
]


def process_meeting(meeting_input: MeetingInput) -> ProcessMeetingResponse:
    """Run the full FlowPilot pipeline on a meeting input."""
    start_time = time.time()

    # Initialize pipeline state
    state = PipelineState(
        meeting_input=meeting_input,
        status="processing",
    )

    logger.info(f"{'='*60}")
    logger.info(f"FlowPilot Pipeline Started | Meeting: {meeting_input.title}")
    logger.info(f"Meeting ID: {state.meeting_id}")
    logger.info(f"{'='*60}")

    # Run each agent in sequence
    for agent_name, agent_module in AGENT_PIPELINE:
        agent_start = time.time()
        logger.info(f"\n--- Running {agent_name.value} ---")

        try:
            state = agent_module.run(state)
            elapsed = time.time() - agent_start
            logger.info(f"--- {agent_name.value} completed in {elapsed:.2f}s ---")

        except Exception as e:
            elapsed = time.time() - agent_start
            error_msg = f"Agent {agent_name.value} failed after {elapsed:.2f}s: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)

            # Attempt recovery: skip to next agent
            state.audit_trail.append(AuditEvent(
                event_type=AuditEventType.SELF_CORRECTION,
                agent=agent_name,
                description=f"Agent {agent_name.value} encountered an error and was skipped. Error: {str(e)[:200]}",
                data={"error": str(e)[:500], "recovered": True},
                meeting_id=state.meeting_id,
            ))

            # Don't break -- continue with remaining agents if possible
            if agent_name in (AgentName.TRANSCRIPTION, AgentName.DECISION_EXTRACTOR):
                # These are critical -- can't continue without them
                logger.error(f"Critical agent {agent_name.value} failed. Pipeline aborted.")
                state.status = "failed"
                break

    total_time = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"Pipeline {'COMPLETED' if state.status != 'failed' else 'FAILED'} in {total_time:.2f}s")
    logger.info(f"Agents completed: {[a.value for a in state.completed_agents]}")
    logger.info(f"Self-corrections: {len(state.corrections)}")
    logger.info(f"Audit events: {len(state.audit_trail)}")
    logger.info(f"{'='*60}")

    # Build response
    return ProcessMeetingResponse(
        meeting_id=state.meeting_id,
        status=state.status,
        transcript=state.transcript,
        decisions=state.extraction.decisions if state.extraction else [],
        action_items=state.extraction.action_items if state.extraction else [],
        tasks=state.task_board.tasks,
        corrections=state.corrections,
        audit_trail=state.audit_trail,
        notifications=state.notifications,
        analytics=state.analytics,
    )


def process_meeting_streaming(meeting_input: MeetingInput):
    """Generator that yields state updates for real-time streaming."""
    state = PipelineState(
        meeting_input=meeting_input,
        status="processing",
    )

    for agent_name, agent_module in AGENT_PIPELINE:
        yield {
            "event": "agent_start",
            "agent": agent_name.value,
            "meeting_id": state.meeting_id,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            state = agent_module.run(state)
            yield {
                "event": "agent_complete",
                "agent": agent_name.value,
                "meeting_id": state.meeting_id,
                "corrections": [c.model_dump() for c in state.corrections if c.agent == agent_name],
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            yield {
                "event": "agent_error",
                "agent": agent_name.value,
                "error": str(e)[:200],
                "meeting_id": state.meeting_id,
                "timestamp": datetime.now().isoformat(),
            }
            if agent_name in (AgentName.TRANSCRIPTION, AgentName.DECISION_EXTRACTOR):
                state.status = "failed"
                break

    yield {
        "event": "pipeline_complete",
        "meeting_id": state.meeting_id,
        "status": state.status,
        "analytics": state.analytics,
        "total_corrections": len(state.corrections),
        "total_tasks": len(state.task_board.tasks),
    }
