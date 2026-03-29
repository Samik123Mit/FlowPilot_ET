"""FlowPilot -- Error handling and recovery strategies."""

import logging
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


class FlowPilotError(Exception):
    """Base exception for FlowPilot."""
    pass


class AgentError(FlowPilotError):
    """Error within a specific agent."""
    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        super().__init__(f"[{agent_name}] {message}")


class LLMError(FlowPilotError):
    """Error communicating with LLM provider."""
    pass


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator: retry a function with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
            raise last_error
        return wrapper
    return decorator


def safe_json_parse(text: str, default: dict | None = None) -> dict:
    """Safely parse JSON with fallback."""
    import json
    try:
        # Try to extract JSON from markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return default or {}
