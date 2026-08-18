"""
Asynchronous Event Bus for decoupled inter-component messaging.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

from zen.core.logger import logger


class EventType(str, Enum):
    # User Input Events
    USER_INPUT_RECEIVED = "user_input_received"
    WAKE_WORD_DETECTED = "wake_word_detected"
    
    # Brain / Planning Events
    THINKING_STARTED = "thinking_started"
    PLAN_GENERATED = "plan_generated"
    RESPONSE_CHUNK = "response_chunk"
    RESPONSE_FINISHED = "response_finished"
    
    # Tool Execution Events
    TOOL_CALL_PROPOSED = "tool_call_proposed"
    PERMISSION_REQUESTED = "permission_requested"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    TOOL_FAILED = "tool_failed"
    
    # Voice Output Events
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    SPEECH_INTERRUPTED = "speech_interrupted"

    # Coding Loop Events
    CODING_PROJECT_STARTED = "coding_project_started"
    CODING_TEST_RUN = "coding_test_run"
    CODING_AUTO_FIX = "coding_auto_fix"
    CODING_VERIFIED = "coding_verified"


@dataclass
class Event:
    """Represents a system event dispatched on the event bus."""
    event_type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Lightweight asynchronous publish-subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an async event listener."""
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unregister an event listener."""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def emit(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """Broadcast an event to all subscribed listeners."""
        event = Event(event_type=event_type, data=data or {})
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        tasks = [asyncio.create_task(self._safe_call(handler, event)) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error in event handler {handler.__name__} for {event.event_type}: {e}", exc_info=True)


# Global event bus instance
event_bus = EventBus()
