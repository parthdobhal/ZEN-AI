"""
SQLite persistent storage engine for memories, corrections, and audit events.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zen.core.logger import logger
from zen.memory.models import CorrectionItem, MemoryCategory, MemoryItem


class SQLiteMemoryStore:
    """Manages transactional relational storage for long-term memory."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create connection with WAL mode and row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        """Initialize database schema if not already present."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    certainty_score REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(category, key)
                );

                CREATE INDEX IF NOT EXISTS idx_mem_cat_key ON memory_items(category, key);
                CREATE INDEX IF NOT EXISTS idx_mem_certainty ON memory_items(category, certainty_score);

                CREATE TABLE IF NOT EXISTS corrections (
                    id TEXT PRIMARY KEY,
                    trigger_context TEXT NOT NULL,
                    mistake_description TEXT NOT NULL,
                    correct_behavior TEXT NOT NULL,
                    project_scope TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parameters_json TEXT,
                    output_preview TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp);
                """
            )
            logger.debug("SQLite memory database initialized at %s", self.db_path)

    def save_memory_item(self, item: MemoryItem) -> None:
        """Upsert a memory item."""
        with self._get_connection() as conn:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO memory_items (
                    id, category, key, content, certainty_score, source, verified, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET
                    content = excluded.content,
                    certainty_score = excluded.certainty_score,
                    source = excluded.source,
                    verified = excluded.verified,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    item.id,
                    item.category.value,
                    item.key,
                    item.content,
                    item.certainty_score,
                    item.source,
                    1 if item.verified else 0,
                    json.dumps(item.metadata),
                    item.created_at.isoformat(),
                    now_iso,
                ),
            )

    def get_memory_item(self, category: MemoryCategory, key: str) -> MemoryItem | None:
        """Fetch a specific memory item by category and key."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM memory_items WHERE category = ? AND key = ?",
                (category.value, key),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_memory_item(row)

    def get_items_by_category(
        self,
        category: MemoryCategory,
        min_certainty: float = 0.5,
        only_verified: bool = False,
    ) -> list[MemoryItem]:
        """Fetch all memory items within a category meeting confidence thresholds."""
        with self._get_connection() as conn:
            query = "SELECT * FROM memory_items WHERE category = ? AND certainty_score >= ?"
            params: list[Any] = [category.value, min_certainty]
            if only_verified:
                query += " AND verified = 1"
            query += " ORDER BY updated_at DESC"

            cursor = conn.execute(query, params)
            return [self._row_to_memory_item(row) for row in cursor.fetchall()]

    def search_memories(self, query: str, limit: int = 10) -> list[MemoryItem]:
        """Simple keyword search across all memory content and keys."""
        pattern = f"%{query}%"
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM memory_items
                WHERE key LIKE ? OR content LIKE ?
                ORDER BY certainty_score DESC, updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            )
            return [self._row_to_memory_item(row) for row in cursor.fetchall()]

    def delete_memory_item(self, category: MemoryCategory, key: str) -> bool:
        """Delete a memory item."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_items WHERE category = ? AND key = ?",
                (category.value, key),
            )
            return cursor.rowcount > 0

    def save_correction(self, correction: CorrectionItem) -> None:
        """Save a learned correction."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO corrections (
                    id, trigger_context, mistake_description, correct_behavior, project_scope, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    correction.id,
                    correction.trigger_context,
                    correction.mistake_description,
                    correction.correct_behavior,
                    correction.project_scope,
                    correction.created_at.isoformat(),
                ),
            )

    def get_all_corrections(self, project_scope: str | None = None) -> list[CorrectionItem]:
        """Retrieve all recorded corrections relevant to the current project or global."""
        with self._get_connection() as conn:
            if project_scope:
                cursor = conn.execute(
                    "SELECT * FROM corrections WHERE project_scope IS NULL OR project_scope = ? ORDER BY created_at DESC",
                    (project_scope,),
                )
            else:
                cursor = conn.execute("SELECT * FROM corrections ORDER BY created_at DESC")
            
            results = []
            for row in cursor.fetchall():
                results.append(
                    CorrectionItem(
                        id=row["id"],
                        trigger_context=row["trigger_context"],
                        mistake_description=row["mistake_description"],
                        correct_behavior=row["correct_behavior"],
                        project_scope=row["project_scope"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return results

    def log_audit_event(
        self,
        event_id: str,
        tool_name: str,
        risk_level: str,
        status: str,
        parameters: dict[str, Any],
        output_preview: str,
    ) -> None:
        """Log tool execution to SQLite audit table."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, timestamp, tool_name, risk_level, status, parameters_json, output_preview
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    datetime.now(timezone.utc).isoformat(),
                    tool_name,
                    risk_level,
                    status,
                    json.dumps(parameters),
                    output_preview[:500],
                ),
            )

    def _row_to_memory_item(self, row: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            category=MemoryCategory(row["category"]),
            key=row["key"],
            content=row["content"],
            certainty_score=row["certainty_score"],
            source=row["source"],
            verified=bool(row["verified"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
