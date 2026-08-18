"""
Permission Engine and Security Auditor for ZEN Tools.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Coroutine
from uuid import uuid4

from zen.config.constants import (
    AUDIT_LOG_PATH,
    RISK_CONFIRM_NEEDED,
    RISK_READ_ONLY,
    RISK_RESTRICTED,
    RISK_SAFE_EXECUTE,
)
from zen.core.events import EventType, event_bus
from zen.core.logger import logger
from zen.memory.memory_manager import MemoryManager

ConfirmationCallback = Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, bool]]


class PermissionDeniedError(Exception):
    """Raised when user denies permission or action is restricted."""
    pass


class PermissionEngine:
    """Evaluates execution safety, requests user confirmation, and maintains audit logs."""

    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        audit_log_path: Path = AUDIT_LOG_PATH,
        require_confirmation: bool = True,
    ) -> None:
        self.memory_manager = memory_manager
        self.audit_log_path = audit_log_path
        self.require_confirmation = require_confirmation
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    async def verify_and_authorize(
        self,
        tool_name: str,
        risk_level: str,
        parameters: dict[str, Any],
        confirm_callback: ConfirmationCallback | None = None,
    ) -> bool:
        """
        Check permissions for a proposed tool execution.
        Returns True if authorized, raises PermissionDeniedError otherwise.
        """
        event_id = str(uuid4())
        await event_bus.emit(
            EventType.TOOL_CALL_PROPOSED,
            {"event_id": event_id, "tool_name": tool_name, "risk_level": risk_level, "parameters": parameters},
        )

        # 1. Blocked Risk Level
        if risk_level == RISK_RESTRICTED:
            self._log_audit(event_id, tool_name, risk_level, "BLOCKED", parameters, "Execution restricted by safety policy.")
            raise PermissionDeniedError(f"Tool '{tool_name}' is classified as RESTRICTED and cannot be executed.")

        # 2. Read-only and Safe-execute can run automatically
        if risk_level in (RISK_READ_ONLY, RISK_SAFE_EXECUTE):
            return True

        # 3. Confirmation Required
        if risk_level == RISK_CONFIRM_NEEDED and self.require_confirmation:
            await event_bus.emit(
                EventType.PERMISSION_REQUESTED,
                {"event_id": event_id, "tool_name": tool_name, "parameters": parameters},
            )
            
            prompt_msg = f"Tool '{tool_name}' requires confirmation with arguments: {json.dumps(parameters)}"
            granted = False
            if confirm_callback:
                granted = await confirm_callback(tool_name, prompt_msg, parameters)
            else:
                # Default non-interactive safety fallback: deny if no callback provided
                logger.warning(f"No confirmation callback provided for sensitive tool '{tool_name}'. Denying.")
                granted = False

            if not granted:
                await event_bus.emit(EventType.PERMISSION_DENIED, {"event_id": event_id, "tool_name": tool_name})
                self._log_audit(event_id, tool_name, risk_level, "DENIED_BY_USER", parameters, "User declined confirmation.")
                raise PermissionDeniedError(f"User denied permission to execute '{tool_name}'.")

            await event_bus.emit(EventType.PERMISSION_GRANTED, {"event_id": event_id, "tool_name": tool_name})

        return True

    def log_execution_result(
        self,
        tool_name: str,
        risk_level: str,
        status: str,
        parameters: dict[str, Any],
        output_preview: str,
    ) -> None:
        """Record completed tool execution in audit logs."""
        event_id = str(uuid4())
        self._log_audit(event_id, tool_name, risk_level, status, parameters, output_preview)

    def _log_audit(
        self,
        event_id: str,
        tool_name: str,
        risk_level: str,
        status: str,
        parameters: dict[str, Any],
        output_preview: str,
    ) -> None:
        """Write audit entry to file and SQLite."""
        log_entry = {
            "id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "risk_level": risk_level,
            "status": status,
            "parameters": parameters,
            "output_preview": output_preview[:500],
        }

        # Append to audit.log (JSON Lines format)
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")

        # Also log to SQLite if memory store is attached
        if self.memory_manager:
            try:
                self.memory_manager.store.log_audit_event(
                    event_id, tool_name, risk_level, status, parameters, output_preview
                )
            except Exception as e:
                logger.error(f"Failed to log audit event to SQLite: {e}")
