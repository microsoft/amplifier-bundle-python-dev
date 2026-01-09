"""Amplifier Python Development Bundle.

Provides comprehensive Python development tools including:
- Code quality checks (ruff format, ruff lint, pyright)
- Stub/placeholder detection
- Integration with Amplifier as tool and hook modules
"""

from .checker import PythonChecker, check_files, check_content
from .models import CheckResult, Issue, Severity, CheckConfig

__version__ = "0.1.0"

__all__ = [
    "PythonChecker",
    "check_files",
    "check_content",
    "CheckResult",
    "Issue",
    "Severity",
    "CheckConfig",
]
