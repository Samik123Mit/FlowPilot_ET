"""FlowPilot -- LLM abstraction layer with retry and fallback."""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import LLM clients
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


class LLMClient:
    """Unified LLM client with automatic fallback and retry logic."""

    def __init__(self):
        self.provider = None
        self.client = None
        self._init_provider()

    def _init_provider(self):
        # Try OpenAI first
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and HAS_OPENAI:
            self.client = OpenAI(api_key=openai_key)
            self.provider = "openai"
            logger.info("LLM provider: OpenAI (gpt-4o-mini)")
            return

        # Try Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and HAS_GEMINI:
            genai.configure(api_key=gemini_key)
            self.client = genai.GenerativeModel("gemini-2.0-flash")
            self.provider = "gemini"
            logger.info("LLM provider: Gemini 2.0 Flash")
            return

        # Fallback: mock mode for demo
        self.provider = "mock"
        logger.warning("No LLM API key found. Running in MOCK mode with pre-built responses.")

    def complete(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.3, max_tokens: int = 4000,
                 response_format: Optional[str] = "json") -> str:
        """Send a prompt and get a completion. Returns raw text."""
        for attempt in range(3):
            try:
                if self.provider == "openai":
                    return self._openai_complete(system_prompt, user_prompt, temperature, max_tokens)
                elif self.provider == "gemini":
                    return self._gemini_complete(system_prompt, user_prompt, temperature, max_tokens)
                else:
                    return self._mock_complete(system_prompt, user_prompt)
            except Exception as e:
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    logger.error("All LLM attempts failed, using mock fallback")
                    return self._mock_complete(system_prompt, user_prompt)

    def _openai_complete(self, system: str, user: str, temp: float, max_tok: int) -> str:
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temp,
            max_tokens=max_tok,
        )
        return resp.choices[0].message.content

    def _gemini_complete(self, system: str, user: str, temp: float, max_tok: int) -> str:
        full_prompt = f"{system}\n\n---\n\n{user}"
        resp = self.client.generate_content(
            full_prompt,
            generation_config={"temperature": temp, "max_output_tokens": max_tok},
        )
        return resp.text

    def _mock_complete(self, system: str, user: str) -> str:
        """Return contextual mock responses based on prompt content."""
        lower_sys = system.lower()

        # Order matters: more specific checks first
        if ("decision" in lower_sys and "extract" in lower_sys) or "action item" in lower_sys:
            return json.dumps({
                "decisions": [
                    {"text": "API migration must be completed by end of month", "made_by": "Sarah Chen", "context": "Q3 roadmap review", "confidence": 0.95},
                    {"text": "Dashboard redesign scope reduced to critical user flows only", "made_by": "Sarah Chen", "context": "Maria overloaded, scope compromise", "confidence": 0.92},
                    {"text": "Load testing report deadline set to Thursday noon", "made_by": "Sarah Chen", "context": "Alex requested extension from Wednesday", "confidence": 0.94},
                    {"text": "John and Maria to sync on Tuesday for API contract alignment", "made_by": "Sarah Chen", "context": "Cross-team coordination needed", "confidence": 0.90},
                ],
                "action_items": [
                    {"title": "Complete API integration for staging environment", "owner": "John Park", "deadline": "end of month", "priority": "high", "description": "Handle API migration with staging env access", "source_text": "I can handle the API integration", "confidence": 0.94},
                    {"title": "Coordinate frontend changes with API work", "owner": "Maria Lopez", "deadline": "end of month", "priority": "high", "description": "Align frontend with John's API changes, focus on critical user flows", "source_text": "Maria, can you coordinate the frontend changes", "confidence": 0.91},
                    {"title": "Investigate and fix auth module", "owner": "David Kim", "deadline": "end of sprint", "priority": "medium", "description": "Take ownership of auth module work", "source_text": "I'll take the auth module", "confidence": 0.89},
                    {"title": "Deliver load testing report", "owner": "Alex Rivera", "deadline": "Thursday noon", "priority": "high", "description": "Complete load testing report, extended from Wednesday", "source_text": "I need the load testing report by Wednesday", "confidence": 0.93},
                    {"title": "Schedule John-Maria sync for API contract", "owner": None, "deadline": "Tuesday", "priority": "medium", "description": "Coordinate sync meeting between John and Maria", "source_text": "schedule a sync between John and Maria for Tuesday", "confidence": 0.85},
                ],
                "ambiguities": [
                    "Auth module owner mentioned vaguely -- 'someone should look into' before David volunteered",
                    "No specific owner assigned for scheduling the John-Maria Tuesday sync",
                    "'End of month' deadline is ambiguous -- exact date not specified"
                ]
            })

        if "transcri" in lower_sys or "diariz" in lower_sys:
            return json.dumps({
                "segments": [
                    {"speaker": "Sarah Chen", "text": "Let's review the Q3 roadmap. The API migration needs to be done by end of month.", "timestamp": "00:00:15", "confidence": 0.95},
                    {"speaker": "John Park", "text": "I can handle the API integration. I'll need access to the staging environment.", "timestamp": "00:00:32", "confidence": 0.92},
                    {"speaker": "Sarah Chen", "text": "Great. Maria, can you coordinate the frontend changes with John's API work?", "timestamp": "00:00:48", "confidence": 0.94},
                    {"speaker": "Maria Lopez", "text": "Sure, but I'm also working on the dashboard redesign. Someone should look into the auth module too.", "timestamp": "00:01:05", "confidence": 0.88},
                    {"speaker": "David Kim", "text": "I'll take the auth module. But the deadline seems tight -- can we push the dashboard to next sprint?", "timestamp": "00:01:22", "confidence": 0.91},
                    {"speaker": "Sarah Chen", "text": "Let's keep the dashboard in this sprint but reduce scope. Maria, focus on the critical user flows only. Alex, I need the load testing report by Wednesday.", "timestamp": "00:01:40", "confidence": 0.93},
                    {"speaker": "Alex Rivera", "text": "Wednesday is tough with the production incident follow-up. Can I get it to you by Thursday?", "timestamp": "00:02:00", "confidence": 0.90},
                    {"speaker": "Sarah Chen", "text": "Thursday noon, final. Let's also schedule a sync between John and Maria for Tuesday to align on the API contract.", "timestamp": "00:02:15", "confidence": 0.96},
                ],
                "quality_score": 0.92,
                "duration_minutes": 12.5
            })

        if "task" in lower_sys or "orchestrat" in lower_sys or "workload" in lower_sys:
            return json.dumps({
                "tasks_created": True,
                "conflicts_detected": [
                    {"type": "overload", "person": "Maria Lopez", "current_hours": 48, "capacity": 40, "suggestion": "Reassign dashboard scope review to available team member"},
                ],
                "dependency_issues": [],
                "adjustments_made": [
                    {"action": "Added 1-day buffer to API integration deadline", "reason": "Dependency on staging env access which needs provisioning"},
                ]
            })

        if "follow" in lower_sys or "remind" in lower_sys or "escalat" in lower_sys:
            return json.dumps({
                "reminders_sent": [
                    {"recipient": "Alex Rivera", "message": "Reminder: Load testing report due Thursday noon (2 days remaining)", "channel": "slack"},
                    {"recipient": "John Park", "message": "Reminder: API integration in progress -- sync with Maria scheduled for Tuesday", "channel": "email"},
                ],
                "escalations": [
                    {"task": "Schedule John-Maria sync", "reason": "No owner assigned", "escalated_to": "Sarah Chen", "action": "Requesting explicit owner assignment"},
                ],
                "stalls_detected": []
            })

        if "audit" in lower_sys or "analytic" in lower_sys:
            return json.dumps({
                "meeting_effectiveness_score": 82,
                "action_item_clarity_score": 78,
                "ownership_coverage": 80,
                "deadline_specificity": 75,
                "follow_through_prediction": 85,
                "risk_factors": [
                    "Maria Lopez at 120% capacity -- risk of dropped tasks",
                    "Auth module has unclear scope -- may expand beyond estimate"
                ],
                "recommendations": [
                    "Consider redistributing Maria's workload across team",
                    "Clarify auth module scope in follow-up meeting",
                    "Set explicit calendar invites for Tuesday sync"
                ]
            })

        return json.dumps({"status": "ok", "message": "Processed successfully"})


# Singleton
_llm_client = None

def get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
