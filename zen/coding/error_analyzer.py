"""
Python Error & Stack Trace Analyzer.
"""

from dataclasses import dataclass
import re


@dataclass
class DiagnosticError:
    """Structured breakdown of a Python error."""
    exception_type: str
    message: str
    failing_file: str | None
    line_number: int | None
    raw_traceback: str


class ErrorAnalyzer:
    """Extracts root cause information from stdout/stderr test outputs."""

    # Regex for standard Python traceback lines: File "path.py", line 12, in <func>
    TRACE_PATTERN = re.compile(r'File "([^"]+)", line (\d+)(?:, in (.+))?')
    EXCEPTION_PATTERN = re.compile(r"^([A-Za-z0-9_]+Error|[A-Za-z0-9_]+Exception):\s*(.*)$", re.MULTILINE)

    @classmethod
    def analyze(cls, stderr: str, stdout: str = "") -> DiagnosticError | None:
        """Parse combined output to identify the exact error."""
        full_text = stderr + "\n" + stdout
        if not full_text.strip():
            return None

        # Find exception type & message
        exc_match = cls.EXCEPTION_PATTERN.search(full_text)
        exception_type = exc_match.group(1) if exc_match else "ExecutionFailure"
        message = exc_match.group(2) if exc_match else "Command failed with non-zero exit code."

        # Find failing file and line (last occurrence in stack)
        trace_matches = list(cls.TRACE_PATTERN.finditer(full_text))
        failing_file = None
        line_number = None

        if trace_matches:
            last_trace = trace_matches[-1]
            failing_file = last_trace.group(1)
            line_number = int(last_trace.group(2))

        return DiagnosticError(
            exception_type=exception_type,
            message=message.strip(),
            failing_file=failing_file,
            line_number=line_number,
            raw_traceback=full_text,
        )
