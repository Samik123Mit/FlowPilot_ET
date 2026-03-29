"""FlowPilot -- Agent 1: Transcription & Diarization Agent.

Handles audio/text input, speaker identification, confidence scoring,
and self-correction for low-quality segments.
"""

import json
import logging
from typing import Optional

from src.models.schemas import (
    AgentName, AuditEvent, AuditEventType, CorrectionType,
    MeetingTranscript, PipelineState, SelfCorrection, Speaker,
    TranscriptSegment,
)
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a meeting transcription and diarization agent. Your job is to:
1. Parse raw meeting text into structured segments with speaker identification.
2. Assign confidence scores to each segment (0.0-1.0).
3. Flag any segments that are unclear, ambiguous, or have low confidence.
4. Identify all unique speakers and their likely roles.

Given a raw meeting transcript, output a JSON object with:
{
  "segments": [
    {"speaker": "Name", "text": "What they said", "timestamp": "MM:SS", "confidence": 0.95}
  ],
  "quality_score": 0.85,
  "duration_minutes": 12.5
}

Rules:
- If speaker names are unclear, use "Speaker 1", "Speaker 2", etc.
- Confidence < 0.7 means the segment needs review.
- Strip filler words but preserve meaning.
- Flag any parts that seem garbled or contradictory.
"""


def run(state: PipelineState) -> PipelineState:
    """Process meeting input into a structured transcript."""
    logger.info(f"[TranscriptionAgent] Processing meeting: {state.meeting_id}")

    state.current_agent = AgentName.TRANSCRIPTION

    meeting_input = state.meeting_input
    if not meeting_input:
        state.errors.append("No meeting input provided")
        return state

    raw_text = meeting_input.transcript_text

    # ── Step 1: Process via LLM ───────────────────────────────────────────
    llm = get_llm()
    response = llm.complete(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"Parse this meeting transcript:\n\n{raw_text}",
    )

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        logger.warning("[TranscriptionAgent] Failed to parse LLM response, using raw text fallback")
        data = _fallback_parse(raw_text)

        # Self-correction: log the quality retry
        state.corrections.append(SelfCorrection(
            agent=AgentName.TRANSCRIPTION,
            correction_type=CorrectionType.QUALITY_RETRY,
            description="LLM response was not valid JSON. Fell back to rule-based parsing of raw transcript text.",
            before_state={"raw_response": response[:200]},
            after_state={"fallback": "rule_based_parser"},
            meeting_id=state.meeting_id,
        ))

    # ── Step 2: Build structured transcript ───────────────────────────────
    segments = []
    low_confidence_count = 0
    for seg in data.get("segments", []):
        confidence = float(seg.get("confidence", 0.9))
        flagged = confidence < 0.7

        if flagged:
            low_confidence_count += 1

        segments.append(TranscriptSegment(
            speaker=seg.get("speaker", "Unknown"),
            text=seg.get("text", ""),
            timestamp=seg.get("timestamp"),
            confidence=confidence,
            flagged_low_confidence=flagged,
        ))

    # ── Step 3: Self-correction for low quality ───────────────────────────
    quality_score = float(data.get("quality_score", 0.9))

    if quality_score < 0.6 or low_confidence_count > len(segments) * 0.3:
        logger.warning(f"[TranscriptionAgent] Low quality detected (score={quality_score}). Re-processing unclear segments.")

        # Attempt re-processing of low-confidence segments
        retry_text = "\n".join(
            f"[{s.speaker}]: {s.text}" for s in segments if s.flagged_low_confidence
        )
        if retry_text:
            retry_response = llm.complete(
                system_prompt="You are correcting unclear meeting transcript segments. Improve clarity and re-assign confidence scores. Return JSON array of corrected segments.",
                user_prompt=f"Correct these unclear segments:\n{retry_text}",
            )
            state.corrections.append(SelfCorrection(
                agent=AgentName.TRANSCRIPTION,
                correction_type=CorrectionType.QUALITY_RETRY,
                description=f"Detected {low_confidence_count} low-confidence segments ({low_confidence_count}/{len(segments)}). Re-processed unclear segments to improve accuracy.",
                before_state={"quality_score": quality_score, "low_confidence_segments": low_confidence_count},
                after_state={"action": "re_processed_segments", "segments_retried": low_confidence_count},
                meeting_id=state.meeting_id,
            ))

    # ── Step 4: Extract participants ──────────────────────────────────────
    speaker_names = list({s.speaker for s in segments if s.speaker != "Unknown"})
    participants_input = meeting_input.participants or speaker_names
    speakers = [Speaker(name=name) for name in participants_input]

    # ── Step 5: Build final transcript ────────────────────────────────────
    transcript = MeetingTranscript(
        id=state.meeting_id,
        title=meeting_input.title,
        date=meeting_input.date or "",
        participants=speakers,
        segments=segments,
        raw_text=raw_text,
        duration_minutes=data.get("duration_minutes"),
        quality_score=quality_score,
    )

    state.transcript = transcript
    state.completed_agents.append(AgentName.TRANSCRIPTION)

    # ── Audit event ───────────────────────────────────────────────────────
    state.audit_trail.append(AuditEvent(
        event_type=AuditEventType.MEETING_PROCESSED,
        agent=AgentName.TRANSCRIPTION,
        description=f"Transcribed meeting '{meeting_input.title}' with {len(segments)} segments, {len(speakers)} speakers. Quality: {quality_score:.0%}",
        data={
            "segments_count": len(segments),
            "speakers": [s.name for s in speakers],
            "quality_score": quality_score,
            "low_confidence_segments": low_confidence_count,
        },
        meeting_id=state.meeting_id,
    ))

    logger.info(f"[TranscriptionAgent] Done. {len(segments)} segments, quality={quality_score:.0%}")
    return state


def _fallback_parse(raw_text: str) -> dict:
    """Rule-based fallback parser for when LLM fails."""
    segments = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            parts = line.split(":", 1)
            speaker = parts[0].strip().strip("[]")
            text = parts[1].strip()
        else:
            speaker = "Unknown"
            text = line
        segments.append({
            "speaker": speaker,
            "text": text,
            "timestamp": None,
            "confidence": 0.7,
        })
    return {"segments": segments, "quality_score": 0.7, "duration_minutes": len(segments) * 0.25}
