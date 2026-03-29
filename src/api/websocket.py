"""FlowPilot -- WebSocket endpoint for real-time pipeline streaming."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.models.schemas import MeetingInput
from src.orchestrator.pipeline import process_meeting_streaming

logger = logging.getLogger(__name__)

ws_router = APIRouter()


@ws_router.websocket("/ws/pipeline")
async def pipeline_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time pipeline updates."""
    await websocket.accept()
    try:
        # Receive meeting input
        data = await websocket.receive_text()
        meeting_data = json.loads(data)
        meeting_input = MeetingInput(**meeting_data)

        # Stream pipeline events
        for event in process_meeting_streaming(meeting_input):
            await websocket.send_text(json.dumps(event, default=str))

        await websocket.close()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({"event": "error", "message": str(e)}))
        await websocket.close()
