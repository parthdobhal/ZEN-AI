"""
Unit tests for Security Guardrails and Path Traversal Defense.
"""

from pathlib import Path
import pytest
from zen.config.constants import ROOT_DIR
from zen.tools.guardrails import (
    GuardrailViolation,
    validate_command_safety,
    validate_path_safety,
)


def test_command_safety_blocking() -> None:
    # Destructive commands must raise GuardrailViolation
    with pytest.raises(GuardrailViolation):
        validate_command_safety("format C:")

    with pytest.raises(GuardrailViolation):
        validate_command_safety("rmdir /s /q c:\\")

    with pytest.raises(GuardrailViolation):
        validate_command_safety("del /f /s /q c:\\")

    # Safe commands should pass
    validate_command_safety("python -m pytest")
    validate_command_safety("git status")


def test_path_safety_core_protection() -> None:
    # Modifying ZEN core code via tool is blocked
    core_code_path = ROOT_DIR / "zen" / "core" / "orchestrator.py"
    with pytest.raises(GuardrailViolation):
        validate_path_safety(core_code_path, allow_read_only=False)

    # Read-only inspection is allowed
    safe_path = validate_path_safety(core_code_path, allow_read_only=True)
    assert safe_path.exists()
