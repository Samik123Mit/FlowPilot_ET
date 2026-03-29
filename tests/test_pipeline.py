"""FlowPilot -- Test suite for agents and pipeline."""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.schemas import MeetingInput, PipelineState, AgentName
from src.orchestrator.pipeline import process_meeting


def load_sample(filename: str) -> MeetingInput:
    path = os.path.join("data", "sample_meetings", filename)
    with open(path) as f:
        data = json.load(f)
    return MeetingInput(
        title=data["title"],
        transcript_text=data["transcript_text"],
        participants=data.get("participants", []),
        date=data.get("date"),
    )


def test_full_pipeline():
    """Test the complete pipeline end-to-end."""
    meeting = load_sample("sprint_planning.json")
    result = process_meeting(meeting)

    assert result.status == "completed", f"Pipeline failed: {result.status}"
    assert result.meeting_id, "No meeting ID generated"
    assert result.transcript is not None, "No transcript produced"
    assert len(result.decisions) > 0, "No decisions extracted"
    assert len(result.action_items) > 0, "No action items extracted"
    assert len(result.tasks) > 0, "No tasks created"
    assert len(result.audit_trail) > 0, "No audit trail"

    print(f"[PASS] Full pipeline: {len(result.decisions)} decisions, "
          f"{len(result.action_items)} actions, {len(result.tasks)} tasks, "
          f"{len(result.corrections)} corrections, {len(result.audit_trail)} audit events")


def test_self_corrections():
    """Test that self-correction mechanisms fire."""
    meeting = load_sample("sprint_planning.json")
    result = process_meeting(meeting)

    assert len(result.corrections) > 0, "No self-corrections recorded"

    correction_types = {c.correction_type for c in result.corrections}
    print(f"[PASS] Self-corrections: {len(result.corrections)} corrections of types: {correction_types}")


def test_audit_trail_completeness():
    """Test that audit trail tracks all agent actions."""
    meeting = load_sample("sprint_planning.json")
    result = process_meeting(meeting)

    agents_in_trail = {e.agent for e in result.audit_trail}
    expected_agents = {AgentName.TRANSCRIPTION, AgentName.DECISION_EXTRACTOR,
                       AgentName.TASK_ORCHESTRATOR, AgentName.FOLLOWUP, AgentName.AUDIT}

    assert expected_agents.issubset(agents_in_trail), \
        f"Missing agents in audit trail. Expected: {expected_agents}, Got: {agents_in_trail}"

    print(f"[PASS] Audit trail: all 5 agents represented ({len(result.audit_trail)} events)")


def test_ambiguous_meeting():
    """Test pipeline handles ambiguous ownership and vague deadlines."""
    meeting = load_sample("product_review.json")
    result = process_meeting(meeting)

    assert result.status == "completed"

    # Check for owner resolution corrections
    owner_corrections = [c for c in result.corrections if c.correction_type.value == "owner_resolved"]
    escalations = [c for c in result.corrections if c.correction_type.value == "escalation"]

    print(f"[PASS] Ambiguous meeting: {len(owner_corrections)} owner resolutions, "
          f"{len(escalations)} escalations")


def test_failed_followup_meeting():
    """Test pipeline handles meetings about missed deliverables."""
    meeting = load_sample("retro_failed_followup.json")
    result = process_meeting(meeting)

    assert result.status == "completed"
    assert len(result.tasks) > 0

    print(f"[PASS] Retro meeting: {len(result.tasks)} tasks, "
          f"{len(result.corrections)} corrections")


def test_all_sample_meetings():
    """Process all sample meetings to verify consistency."""
    samples = ["sprint_planning.json", "product_review.json",
               "strategy_meeting.json", "retro_failed_followup.json"]

    for sample in samples:
        meeting = load_sample(sample)
        result = process_meeting(meeting)
        assert result.status == "completed", f"Failed on {sample}"
        print(f"[PASS] {sample}: {len(result.tasks)} tasks, {len(result.corrections)} corrections")


def test_analytics_output():
    """Test that analytics are generated with expected keys."""
    meeting = load_sample("sprint_planning.json")
    result = process_meeting(meeting)

    analytics = result.analytics
    assert "meeting_effectiveness_score" in analytics
    assert "total_tasks" in analytics
    assert "ownership_coverage" in analytics

    print(f"[PASS] Analytics: effectiveness={analytics.get('meeting_effectiveness_score')}%, "
          f"ownership={analytics.get('ownership_coverage')}%")


if __name__ == "__main__":
    print("=" * 60)
    print("FlowPilot Test Suite")
    print("=" * 60)

    tests = [
        test_full_pipeline,
        test_self_corrections,
        test_audit_trail_completeness,
        test_ambiguous_meeting,
        test_failed_followup_meeting,
        test_all_sample_meetings,
        test_analytics_output,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'=' * 60}")
