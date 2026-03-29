"""FlowPilot -- Pydantic schemas for all data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    ESCALATED = "escalated"


class AgentName(str, Enum):
    TRANSCRIPTION = "transcription_agent"
    DECISION_EXTRACTOR = "decision_extractor"
    TASK_ORCHESTRATOR = "task_orchestrator"
    FOLLOWUP = "followup_agent"
    AUDIT = "audit_agent"


class CorrectionType(str, Enum):
    OWNER_RESOLVED = "owner_resolved"
    WORKLOAD_REBALANCE = "workload_rebalance"
    DEADLINE_ADJUSTED = "deadline_adjusted"
    DEPENDENCY_BROKEN = "dependency_broken"
    QUALITY_RETRY = "quality_retry"
    ESCALATION = "escalation"


class AuditEventType(str, Enum):
    DECISION_EXTRACTED = "decision_extracted"
    TASK_CREATED = "task_created"
    TASK_REASSIGNED = "task_reassigned"
    SELF_CORRECTION = "self_correction"
    ESCALATION = "escalation"
    DEADLINE_MISSED = "deadline_missed"
    TASK_COMPLETED = "task_completed"
    MEETING_PROCESSED = "meeting_processed"


# ── Meeting Domain ────────────────────────────────────────────────────────────

class Speaker(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    role: Optional[str] = None
    department: Optional[str] = None


class Utterance(BaseModel):
    speaker: str
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    confidence: float = 1.0


class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    timestamp: Optional[str] = None
    confidence: float = 1.0
    flagged_low_confidence: bool = False


class MeetingTranscript(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    date: str = Field(default_factory=lambda: datetime.now().isoformat())
    participants: list[Speaker] = []
    segments: list[TranscriptSegment] = []
    raw_text: str = ""
    duration_minutes: Optional[float] = None
    quality_score: float = 1.0


class MeetingInput(BaseModel):
    """Input payload for the API."""
    title: str = "Untitled Meeting"
    transcript_text: str
    participants: list[str] = []
    date: Optional[str] = None


# ── Decision & Action Domain ─────────────────────────────────────────────────

class Decision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str
    made_by: Optional[str] = None
    context: str = ""
    source_segment_index: Optional[int] = None
    confidence: float = 0.9


class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str = ""
    owner: Optional[str] = None
    owner_resolved: bool = True
    deadline: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    dependencies: list[str] = []
    source_decision_id: Optional[str] = None
    source_text: str = ""
    confidence: float = 0.9


class ExtractionResult(BaseModel):
    meeting_id: str
    decisions: list[Decision] = []
    action_items: list[ActionItem] = []
    ambiguities: list[str] = []


# ── Task Domain ───────────────────────────────────────────────────────────────

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str = ""
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    deadline: Optional[str] = None
    dependencies: list[str] = []
    created_from_action_id: Optional[str] = None
    meeting_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    assignment_history: list[dict] = []
    estimated_hours: float = 4.0


class TeamMember(BaseModel):
    name: str
    role: str = "Engineer"
    department: str = "Engineering"
    current_load_hours: float = 0.0
    max_capacity_hours: float = 40.0
    skills: list[str] = []

    @property
    def utilization(self) -> float:
        if self.max_capacity_hours == 0:
            return 1.0
        return self.current_load_hours / self.max_capacity_hours


class TaskBoard(BaseModel):
    tasks: list[Task] = []
    team: list[TeamMember] = []


# ── Self-Correction Domain ────────────────────────────────────────────────────

class SelfCorrection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: AgentName
    correction_type: CorrectionType
    description: str
    before_state: dict = {}
    after_state: dict = {}
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    meeting_id: Optional[str] = None


# ── Audit Domain ──────────────────────────────────────────────────────────────

class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: AuditEventType
    agent: AgentName
    description: str
    data: dict = {}
    meeting_id: Optional[str] = None
    task_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Pipeline State ────────────────────────────────────────────────────────────

class PipelineState(BaseModel):
    """Full state passed between agents in the pipeline."""
    meeting_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    meeting_input: Optional[MeetingInput] = None
    transcript: Optional[MeetingTranscript] = None
    extraction: Optional[ExtractionResult] = None
    task_board: TaskBoard = TaskBoard()
    corrections: list[SelfCorrection] = []
    audit_trail: list[AuditEvent] = []
    notifications: list[dict] = []
    analytics: dict = {}
    errors: list[str] = []
    current_agent: Optional[AgentName] = None
    completed_agents: list[AgentName] = []
    status: str = "pending"


# ── API Response Models ───────────────────────────────────────────────────────

class ProcessMeetingResponse(BaseModel):
    meeting_id: str
    status: str
    transcript: Optional[MeetingTranscript] = None
    decisions: list[Decision] = []
    action_items: list[ActionItem] = []
    tasks: list[Task] = []
    corrections: list[SelfCorrection] = []
    audit_trail: list[AuditEvent] = []
    notifications: list[dict] = []
    analytics: dict = {}


class DashboardData(BaseModel):
    meetings: list[dict] = []
    tasks: list[Task] = []
    corrections: list[SelfCorrection] = []
    audit_events: list[AuditEvent] = []
    analytics: dict = {}
