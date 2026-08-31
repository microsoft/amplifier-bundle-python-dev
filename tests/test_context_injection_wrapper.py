"""Tests that the auto-injected context is wrapped in <system-reminder> tags.

Ecosystem convention: hook-driven context injections are wrapped in
`<system-reminder source="...">...</system-reminder>` so models can
distinguish system-injected content from actual user requests. See
hooks-status-context / hooks-todo-reminder for the reference shape.
"""

import sys
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


class MockHookResult:
    """Minimal stand-in for amplifier_core.HookResult."""

    def __init__(self, **kwargs):
        self.action = kwargs.get("action", "continue")
        self.user_message = kwargs.get("user_message")
        self.user_message_level = kwargs.get("user_message_level")
        self.user_message_source = kwargs.get("user_message_source")
        self.context_injection = kwargs.get("context_injection")
        self.context_injection_role = kwargs.get("context_injection_role")
        self.ephemeral = kwargs.get("ephemeral")
        self.append_to_last_tool_result = kwargs.get("append_to_last_tool_result")


# Mock amplifier_core before importing the hook module
_mock_core = MagicMock()
_mock_core.HookResult = MockHookResult
sys.modules["amplifier_core"] = _mock_core

# Now safe to import
from amplifier_module_hooks_python_check import PythonCheckHooks  # noqa: E402  # type: ignore[import-untyped]

from amplifier_bundle_python_dev.models import CheckResult  # noqa: E402
from amplifier_bundle_python_dev.models import Issue  # noqa: E402
from amplifier_bundle_python_dev.models import Severity  # noqa: E402


def _normal_error_result() -> CheckResult:
    """A CheckResult containing a normal F401 lint issue."""
    return CheckResult(
        issues=[
            Issue(
                file="test.py",
                line=1,
                column=1,
                code="F401",
                message="'os' imported but unused",
                severity=Severity.WARNING,
                source="ruff-lint",
            )
        ],
        files_checked=1,
        checks_run=["ruff-lint"],
    )


def _write_event(path: str = "test.py") -> dict:
    """Build a minimal tool:post event data dict for a write_file call."""
    return {
        "tool_name": "write_file",
        "tool_input": {"file_path": path},
        "tool_result": {},
    }


@pytest.mark.asyncio
@patch("amplifier_module_hooks_python_check.Path.exists", return_value=True)
@patch("amplifier_module_hooks_python_check.check_files")
async def test_context_injection_wrapped_in_system_reminder(mock_check_files, mock_exists):
    """The context_injection for detected issues must be wrapped in <system-reminder>."""
    mock_check_files.return_value = _normal_error_result()

    hooks = PythonCheckHooks()
    result = await hooks.handle_tool_post("tool:post", _write_event())

    assert result.action == "inject_context"
    assert result.context_injection is not None
    assert result.context_injection.startswith('<system-reminder source="hooks-python-check">'), (
        f"Injection should open with the system-reminder wrapper; got: {result.context_injection!r}"
    )
    assert result.context_injection.endswith("</system-reminder>"), (
        f"Injection should close with the system-reminder wrapper; got: {result.context_injection!r}"
    )
    # The original message content must still be present, byte-identical, inside the wrapper.
    assert "Python check found issues in test.py:" in result.context_injection
    assert "- test.py:1:1: [F401] 'os' imported but unused" in result.context_injection
