"""
Global constants and path definitions for ZEN.
"""

from pathlib import Path

# Base Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
WORKSPACE_DIR = ROOT_DIR / "workspace"
DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
MEMORY_DB_PATH = DATA_DIR / "memory.db"
AUDIT_LOG_PATH = DATA_DIR / "audit.log"

# Assistant Identity
ASSISTANT_NAME = "ZEN"
WAKE_WORD_DEFAULT = "hey zen"

# Safety Defaults
MAX_CODING_ITERATIONS_DEFAULT = 5
COMMAND_TIMEOUT_SECONDS = 30
HTTP_TIMEOUT_SECONDS = 20

# Risk Levels
RISK_READ_ONLY = "read_only"
RISK_SAFE_EXECUTE = "safe_execute"
RISK_CONFIRM_NEEDED = "confirm_needed"
RISK_RESTRICTED = "restricted"
