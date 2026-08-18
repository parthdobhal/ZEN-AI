"""
Data models for ZEN's 6-Tier Memory Hierarchy.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    USER_PREFERENCE = "user_preference"
    PROJECT_CONTEXT = "project_context"
    CORRECTION = "correction"
    LEARNED_FACT = "learned_fact"
    CONVERSATION_HISTORY = "conversation_history"
    SESSION_SCRATCHPAD = "session_scratchpad"


class MemoryItem(BaseModel):
    """An individual knowledge item stored within the memory subsystem."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    category: MemoryCategory
    key: str = Field(description="Unique key or topic label")
    content: str = Field(description="The memory content or structured fact")
    certainty_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (1.0 = explicit user rule, <0.8 = unverified inference)",
    )
    source: str = Field(default="user_explicit", description="Origin of memory (user, research, inference)")
    verified: bool = Field(default=True, description="Whether explicitly validated")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CorrectionItem(BaseModel):
    """A specific correction learned from user feedback to avoid repeating mistakes."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    trigger_context: str = Field(description="Situation or topic where mistake occurred")
    mistake_description: str = Field(description="What was done wrong previously")
    correct_behavior: str = Field(description="What should be done instead")
    project_scope: str | None = Field(default=None, description="Optional project restriction")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
