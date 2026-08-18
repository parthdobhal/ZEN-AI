"""
Safety guardrails, path traversal prevention, and dangerous command blockers.
"""

from pathlib import Path
import re
from zen.config.constants import ROOT_DIR, WORKSPACE_DIR


# Disallowed system and dangerous shell patterns
BLOCKED_COMMAND_PATTERNS = [
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\brmdir\b.*[\\/][sq]", re.IGNORECASE),
    re.compile(r"\bdel\b.*[\\/][fsq]", re.IGNORECASE),
    re.compile(r"\bdiskpart\b", re.IGNORECASE),
    re.compile(r"\bcd\s+.*windows[\\/]system32", re.IGNORECASE),
    re.compile(r"\breg\s+delete\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b.*[\\/][srf]", re.IGNORECASE),
]

# Sensitive directories that should never be written to or deleted
PROTECTED_SYSTEM_PATHS = [
    Path("C:/Windows"),
    Path("C:/Windows/System32"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    ROOT_DIR / "zen",    # Core code self-modification defense
    ROOT_DIR / "config", # Core config protection
]


class GuardrailViolation(Exception):
    """Raised when an operation violates security guardrails."""
    pass


def validate_path_safety(target_path: Path, allow_read_only: bool = False) -> Path:
    """
    Validates that the target path does not violate protected directories
    or attempt to rewrite ZEN's own core code.
    """
    try:
        resolved_path = target_path.resolve()
    except Exception as e:
        raise GuardrailViolation(f"Invalid path structure: {e}")

    norm_resolved = str(resolved_path).lower().rstrip("\\/")

    # Check if target is inside a protected core folder
    for protected in PROTECTED_SYSTEM_PATHS:
        try:
            norm_protected = str(protected.resolve()).lower().rstrip("\\/")
            if (
                norm_resolved == norm_protected
                or norm_resolved.startswith(norm_protected + "\\")
                or norm_resolved.startswith(norm_protected + "/")
            ):
                if not allow_read_only:
                    raise GuardrailViolation(
                        f"Security Guardrail: Modification of core system/ZEN path '{resolved_path}' is strictly prohibited."
                    )
        except GuardrailViolation:
            raise
        except Exception:
            continue

    return resolved_path


def validate_command_safety(command: str) -> None:
    """Checks a shell command against known destructive patterns."""
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if pattern.search(command):
            raise GuardrailViolation(
                f"Security Guardrail: Command '{command}' matched restricted destructive pattern."
            )
