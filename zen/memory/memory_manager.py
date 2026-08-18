"""
High-level Memory Manager coordinating all 6 tiers of memory.
"""

from pathlib import Path
from typing import Any
from zen.config.constants import MEMORY_DB_PATH
from zen.core.logger import logger
from zen.memory.models import CorrectionItem, MemoryCategory, MemoryItem
from zen.memory.storage.sqlite_store import SQLiteMemoryStore


class MemoryManager:
    """Orchestrates persistent and volatile memory access across all tiers."""

    def __init__(self, db_path: Path = MEMORY_DB_PATH) -> None:
        self.store = SQLiteMemoryStore(db_path)
        self._session_scratchpad: dict[str, Any] = {}

    # Tier 1: User Preferences
    def set_preference(self, key: str, value: str, verified: bool = True) -> None:
        """Store or update a user preference."""
        item = MemoryItem(
            category=MemoryCategory.USER_PREFERENCE,
            key=key,
            content=value,
            certainty_score=1.0 if verified else 0.7,
            source="user_preference",
            verified=verified,
        )
        self.store.save_memory_item(item)
        logger.info(f"Saved user preference: [bold]{key}[/bold] -> {value}")

    def get_preference(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a specific user preference."""
        item = self.store.get_memory_item(MemoryCategory.USER_PREFERENCE, key)
        return item.content if item else default

    def get_all_preferences(self) -> dict[str, str]:
        """Retrieve all active user preferences."""
        items = self.store.get_items_by_category(MemoryCategory.USER_PREFERENCE)
        return {item.key: item.content for item in items}

    # Tier 2: Project Context
    def set_project_context(self, project_name: str, context: str) -> None:
        """Store context, conventions, and status for a specific project."""
        item = MemoryItem(
            category=MemoryCategory.PROJECT_CONTEXT,
            key=project_name,
            content=context,
            certainty_score=1.0,
            source="project_scaffold",
            verified=True,
        )
        self.store.save_memory_item(item)

    def get_project_context(self, project_name: str) -> str | None:
        """Retrieve context for a specific project."""
        item = self.store.get_memory_item(MemoryCategory.PROJECT_CONTEXT, project_name)
        return item.content if item else None

    # Tier 3: Corrections
    def record_correction(
        self,
        trigger_context: str,
        mistake_description: str,
        correct_behavior: str,
        project_scope: str | None = None,
    ) -> CorrectionItem:
        """Record a mistake and its learned solution to prevent recurrence."""
        correction = CorrectionItem(
            trigger_context=trigger_context,
            mistake_description=mistake_description,
            correct_behavior=correct_behavior,
            project_scope=project_scope,
        )
        self.store.save_correction(correction)
        logger.info(f"Learned correction recorded for: {trigger_context}")
        return correction

    def get_corrections(self, project_scope: str | None = None) -> list[CorrectionItem]:
        """Fetch all recorded corrections."""
        return self.store.get_all_corrections(project_scope)

    # Tier 4: Learned Facts
    def record_fact(
        self,
        key: str,
        content: str,
        certainty_score: float = 1.0,
        source: str = "user",
        verified: bool = True,
    ) -> None:
        """Store a verified fact or piece of domain knowledge."""
        item = MemoryItem(
            category=MemoryCategory.LEARNED_FACT,
            key=key,
            content=content,
            certainty_score=certainty_score,
            source=source,
            verified=verified,
        )
        self.store.save_memory_item(item)

    # Tier 6: Session Scratchpad
    def set_scratchpad(self, key: str, value: Any) -> None:
        """Store temporary session data."""
        self._session_scratchpad[key] = value

    def get_scratchpad(self, key: str, default: Any = None) -> Any:
        """Retrieve temporary session data."""
        return self._session_scratchpad.get(key, default)

    def clear_scratchpad(self) -> None:
        """Wipe volatile scratchpad."""
        self._session_scratchpad.clear()

    # Context Prompt Injection Builder
    def build_memory_prompt_injection(self, active_project: str | None = None) -> str:
        """Assemble relevant memory facts, preferences, and corrections for LLM context."""
        sections = []

        # 1. Preferences
        preferences = self.get_all_preferences()
        if preferences:
            pref_lines = [f"- {k}: {v}" for k, v in preferences.items()]
            sections.append("### User Preferences:\n" + "\n".join(pref_lines))

        # 2. Corrections
        corrections = self.get_corrections(active_project)
        if corrections:
            corr_lines = [
                f"- When {c.trigger_context}: DON'T {c.mistake_description} -> DO {c.correct_behavior}"
                for c in corrections[:5]
            ]
            sections.append("### Learned Rules & Corrections:\n" + "\n".join(corr_lines))

        # 3. Active Project Context
        if active_project:
            proj_context = self.get_project_context(active_project)
            if proj_context:
                sections.append(f"### Active Project ({active_project}):\n{proj_context}")

        return "\n\n".join(sections)
