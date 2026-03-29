"""FlowPilot -- FastAPI REST API routes."""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.models.schemas import MeetingInput, ProcessMeetingResponse, DashboardData
from src.models.database import (
    get_all_meetings, get_all_tasks, get_audit_trail, get_corrections,
)
from src.orchestrator.pipeline import process_meeting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["FlowPilot"])


@router.post("/meetings/process", response_model=ProcessMeetingResponse)
async def process_meeting_endpoint(meeting: MeetingInput):
    """Process a meeting transcript through the full FlowPilot pipeline."""
    try:
        result = process_meeting(meeting)
        return result
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_dashboard_data():
    """Get all data for the dashboard view."""
    return {
        "meetings": get_all_meetings(),
        "tasks": get_all_tasks(),
        "audit_events": get_audit_trail(),
        "corrections": get_corrections(),
    }


@router.get("/meetings")
async def list_meetings():
    """List all processed meetings."""
    return get_all_meetings()


@router.get("/meetings/{meeting_id}/audit")
async def get_meeting_audit(meeting_id: str):
    """Get the full audit trail for a specific meeting."""
    events = get_audit_trail(meeting_id)
    corrections = get_corrections(meeting_id)
    if not events and not corrections:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"audit_events": events, "corrections": corrections}


@router.get("/tasks")
async def list_tasks():
    """List all tasks across all meetings."""
    return get_all_tasks()


@router.get("/corrections")
async def list_corrections():
    """List all self-correction events."""
    return get_corrections()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "FlowPilot", "version": "1.0.0"}
