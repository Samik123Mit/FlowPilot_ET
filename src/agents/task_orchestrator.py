"""FlowPilot -- Agent 3: Task Orchestration Agent.

Creates tasks from action items, detects conflicts (overload, circular deps,
impossible deadlines), and self-corrects by redistributing work.
"""

import json
import logging
from datetime import datetime

from src.models.schemas import (
    ActionItem, AgentName, AuditEvent, AuditEventType, CorrectionType,
    PipelineState, Priority, SelfCorrection, Task, TaskBoard, TaskStatus,
    TeamMember,
)
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

# Simulated team roster with current workload
DEFAULT_TEAM = [
    TeamMember(name="Sarah Chen", role="Engineering Manager", department="Engineering", current_load_hours=32, max_capacity_hours=40, skills=["management", "architecture"]),
    TeamMember(name="John Park", role="Senior Backend Engineer", department="Engineering", current_load_hours=36, max_capacity_hours=40, skills=["API", "backend", "Python", "databases"]),
    TeamMember(name="Maria Lopez", role="Frontend Engineer", department="Engineering", current_load_hours=44, max_capacity_hours=40, skills=["React", "UI", "frontend", "CSS"]),
    TeamMember(name="David Kim", role="Backend Engineer", department="Engineering", current_load_hours=28, max_capacity_hours=40, skills=["auth", "security", "backend", "Go"]),
    TeamMember(name="Alex Rivera", role="QA Engineer", department="Engineering", current_load_hours=30, max_capacity_hours=40, skills=["testing", "QA", "load testing", "automation"]),
    TeamMember(name="Tom Wilson", role="DevOps Engineer", department="Infrastructure", current_load_hours=22, max_capacity_hours=40, skills=["deployment", "CI/CD", "infra", "Docker"]),
]


def run(state: PipelineState) -> PipelineState:
    """Create tasks from extracted actions, detect conflicts, self-correct."""
    logger.info(f"[TaskOrchestrator] Processing meeting: {state.meeting_id}")

    state.current_agent = AgentName.TASK_ORCHESTRATOR

    if not state.extraction:
        state.errors.append("No extraction results available for task orchestration")
        return state

    team = list(DEFAULT_TEAM)
    state.task_board.team = team
    tasks = []

    # ── Step 1: Create tasks from action items ────────────────────────────
    for action in state.extraction.action_items:
        task = Task(
            title=action.title,
            description=action.description,
            assignee=action.owner if action.owner != "UNASSIGNED" else None,
            status=TaskStatus.TODO,
            priority=action.priority,
            deadline=action.deadline,
            dependencies=action.dependencies,
            created_from_action_id=action.id,
            meeting_id=state.meeting_id,
            estimated_hours=_estimate_hours(action),
            assignment_history=[{
                "assignee": action.owner or "unassigned",
                "assigned_at": datetime.now().isoformat(),
                "reason": "Initial assignment from meeting decision",
            }],
        )
        tasks.append(task)

        state.audit_trail.append(AuditEvent(
            event_type=AuditEventType.TASK_CREATED,
            agent=AgentName.TASK_ORCHESTRATOR,
            description=f"Created task '{task.title}' assigned to {task.assignee or 'UNASSIGNED'} (priority: {task.priority.value})",
            data={
                "task_id": task.id,
                "assignee": task.assignee,
                "priority": task.priority.value,
                "deadline": task.deadline,
                "source_action_id": action.id,
            },
            meeting_id=state.meeting_id,
            task_id=task.id,
        ))

    # ── Step 2: Detect and resolve workload conflicts ─────────────────────
    tasks = _check_workload_balance(tasks, team, state)

    # ── Step 3: Detect circular dependencies ──────────────────────────────
    tasks = _check_circular_dependencies(tasks, state)

    # ── Step 4: Detect deadline conflicts ─────────────────────────────────
    tasks = _check_deadline_feasibility(tasks, state)

    # ── Step 5: Update task board ─────────────────────────────────────────
    state.task_board.tasks = tasks
    state.completed_agents.append(AgentName.TASK_ORCHESTRATOR)

    state.audit_trail.append(AuditEvent(
        event_type=AuditEventType.TASK_CREATED,
        agent=AgentName.TASK_ORCHESTRATOR,
        description=f"Task board finalized: {len(tasks)} tasks created, {sum(1 for c in state.corrections if c.agent == AgentName.TASK_ORCHESTRATOR)} corrections applied.",
        data={
            "total_tasks": len(tasks),
            "by_status": _count_by_status(tasks),
            "by_priority": _count_by_priority(tasks),
        },
        meeting_id=state.meeting_id,
    ))

    logger.info(f"[TaskOrchestrator] Done. {len(tasks)} tasks created.")
    return state


def _estimate_hours(action: ActionItem) -> float:
    """Estimate task hours based on priority and description complexity."""
    base = {"critical": 8, "high": 6, "medium": 4, "low": 2}
    hours = base.get(action.priority.value, 4)
    if len(action.description) > 100:
        hours += 2
    if action.dependencies:
        hours += 1
    return float(hours)


def _check_workload_balance(tasks: list[Task], team: list[TeamMember], state: PipelineState) -> list[Task]:
    """Detect overloaded team members and redistribute tasks."""
    # Calculate projected load per person
    load_map: dict[str, float] = {}
    for member in team:
        load_map[member.name] = member.current_load_hours

    for task in tasks:
        if task.assignee and task.assignee in load_map:
            load_map[task.assignee] = load_map.get(task.assignee, 0) + task.estimated_hours

    # Check for overloaded members
    capacity_map = {m.name: m.max_capacity_hours for m in team}

    for i, task in enumerate(tasks):
        assignee = task.assignee
        if not assignee or assignee not in capacity_map:
            continue

        utilization = load_map.get(assignee, 0) / capacity_map.get(assignee, 40)

        if utilization > 1.1:  # More than 110% capacity
            # Find alternative assignee
            new_assignee = _find_available_member(task, team, load_map, capacity_map, exclude=[assignee])

            if new_assignee:
                old_assignee = assignee
                old_util = utilization

                # Redistribute
                load_map[old_assignee] -= task.estimated_hours
                load_map[new_assignee] = load_map.get(new_assignee, 0) + task.estimated_hours

                tasks[i].assignee = new_assignee
                tasks[i].assignment_history.append({
                    "assignee": new_assignee,
                    "assigned_at": datetime.now().isoformat(),
                    "reason": f"Auto-reassigned: {old_assignee} at {old_util:.0%} capacity",
                    "previous_assignee": old_assignee,
                })

                state.corrections.append(SelfCorrection(
                    agent=AgentName.TASK_ORCHESTRATOR,
                    correction_type=CorrectionType.WORKLOAD_REBALANCE,
                    description=f"Detected {old_assignee} at {old_util:.0%} capacity. Reassigned '{task.title}' to {new_assignee} who has available bandwidth.",
                    before_state={"assignee": old_assignee, "utilization": f"{old_util:.0%}"},
                    after_state={"assignee": new_assignee, "new_utilization": f"{load_map[new_assignee]/capacity_map.get(new_assignee, 40):.0%}"},
                    meeting_id=state.meeting_id,
                ))

                state.audit_trail.append(AuditEvent(
                    event_type=AuditEventType.TASK_REASSIGNED,
                    agent=AgentName.TASK_ORCHESTRATOR,
                    description=f"Workload rebalance: '{task.title}' moved from {old_assignee} ({old_util:.0%}) to {new_assignee}",
                    data={"task_id": task.id, "from": old_assignee, "to": new_assignee},
                    meeting_id=state.meeting_id,
                    task_id=task.id,
                ))

                logger.info(f"[TaskOrchestrator] Rebalanced: {task.title} from {old_assignee} -> {new_assignee}")

    return tasks


def _find_available_member(task: Task, team: list[TeamMember],
                           load_map: dict, capacity_map: dict,
                           exclude: list[str] | None = None) -> str | None:
    """Find the best available team member for a task based on skills and load."""
    exclude = exclude or []
    candidates = []

    for member in team:
        if member.name in exclude:
            continue
        current_load = load_map.get(member.name, 0)
        capacity = capacity_map.get(member.name, 40)
        available = capacity - current_load

        if available < task.estimated_hours:
            continue

        # Score by available capacity and skill match
        title_lower = task.title.lower() + " " + task.description.lower()
        skill_score = sum(1 for s in member.skills if s.lower() in title_lower)
        capacity_score = available / capacity

        candidates.append((member.name, skill_score * 2 + capacity_score))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


def _check_circular_dependencies(tasks: list[Task], state: PipelineState) -> list[Task]:
    """Detect and break circular dependency chains."""
    task_map = {t.id: t for t in tasks}

    for task in tasks:
        visited = set()
        current = task.id

        while current in task_map:
            if current in visited:
                # Circular dependency found
                state.corrections.append(SelfCorrection(
                    agent=AgentName.TASK_ORCHESTRATOR,
                    correction_type=CorrectionType.DEPENDENCY_BROKEN,
                    description=f"Circular dependency detected involving task '{task.title}'. Removed dependency to break cycle.",
                    before_state={"task_id": task.id, "dependencies": task.dependencies},
                    after_state={"task_id": task.id, "dependencies": [], "cycle_broken": True},
                    meeting_id=state.meeting_id,
                ))
                task.dependencies = []
                break

            visited.add(current)
            deps = task_map[current].dependencies
            if deps:
                current = deps[0]
            else:
                break

    return tasks


def _check_deadline_feasibility(tasks: list[Task], state: PipelineState) -> list[Task]:
    """Check if deadlines are realistic given estimated hours and current date."""
    now = datetime.now()

    for task in tasks:
        if not task.deadline:
            continue
        try:
            deadline_dt = datetime.fromisoformat(task.deadline)
        except ValueError:
            continue

        days_available = (deadline_dt - now).days
        if days_available < 0:
            days_available = 0

        hours_per_day = 6  # realistic work hours
        feasible_hours = days_available * hours_per_day

        if task.estimated_hours > feasible_hours and days_available < 14:
            # Deadline is too tight
            from datetime import timedelta
            new_deadline = now + timedelta(days=max(int(task.estimated_hours / hours_per_day) + 1, days_available + 2))
            old_deadline = task.deadline
            task.deadline = new_deadline.strftime("%Y-%m-%d")

            state.corrections.append(SelfCorrection(
                agent=AgentName.TASK_ORCHESTRATOR,
                correction_type=CorrectionType.DEADLINE_ADJUSTED,
                description=f"Deadline for '{task.title}' is infeasible ({old_deadline}). Requires ~{task.estimated_hours}h but only {feasible_hours}h available. Extended to {task.deadline}.",
                before_state={"deadline": old_deadline, "estimated_hours": task.estimated_hours, "available_hours": feasible_hours},
                after_state={"deadline": task.deadline, "buffer_added": True},
                meeting_id=state.meeting_id,
            ))

    return tasks


def _count_by_status(tasks: list[Task]) -> dict:
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t.status.value] = counts.get(t.status.value, 0) + 1
    return counts


def _count_by_priority(tasks: list[Task]) -> dict:
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t.priority.value] = counts.get(t.priority.value, 0) + 1
    return counts
