"""FlowPilot -- Agent state machine for tracking pipeline transitions."""

from enum import Enum
from typing import Optional
from datetime import datetime


class PipelinePhase(str, Enum):
    IDLE = "idle"
    TRANSCRIBING = "transcribing"
    EXTRACTING = "extracting"
    ORCHESTRATING = "orchestrating"
    FOLLOWING_UP = "following_up"
    AUDITING = "auditing"
    COMPLETED = "completed"
    FAILED = "failed"


# Valid transitions
TRANSITIONS = {
    PipelinePhase.IDLE: [PipelinePhase.TRANSCRIBING],
    PipelinePhase.TRANSCRIBING: [PipelinePhase.EXTRACTING, PipelinePhase.FAILED],
    PipelinePhase.EXTRACTING: [PipelinePhase.ORCHESTRATING, PipelinePhase.FAILED],
    PipelinePhase.ORCHESTRATING: [PipelinePhase.FOLLOWING_UP, PipelinePhase.FAILED],
    PipelinePhase.FOLLOWING_UP: [PipelinePhase.AUDITING, PipelinePhase.FAILED],
    PipelinePhase.AUDITING: [PipelinePhase.COMPLETED, PipelinePhase.FAILED],
    PipelinePhase.COMPLETED: [],
    PipelinePhase.FAILED: [PipelinePhase.IDLE],  # Allow restart
}


class StateMachine:
    """Tracks and validates pipeline state transitions."""

    def __init__(self):
        self.current_phase = PipelinePhase.IDLE
        self.history: list[dict] = []

    def transition(self, target: PipelinePhase) -> bool:
        """Attempt to transition to a new phase. Returns True if valid."""
        valid = TRANSITIONS.get(self.current_phase, [])
        if target not in valid:
            return False

        self.history.append({
            "from": self.current_phase.value,
            "to": target.value,
            "timestamp": datetime.now().isoformat(),
        })
        self.current_phase = target
        return True

    def get_history(self) -> list[dict]:
        return list(self.history)

    def reset(self):
        self.current_phase = PipelinePhase.IDLE
        self.history.clear()
