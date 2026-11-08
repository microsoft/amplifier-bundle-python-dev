"""Tests for TOOL-NOT-FOUND early-return handling in the python-check hook.

Verifies that when check_files returns TOOL-NOT-FOUND issues, the hook:
1. Returns an error message and ephemeral context feedback when enabled
2. Does NOT suppress the message on repeat calls (bypasses redundancy logic)
3. Does NOT affect the normal path for real code issues (e.g., F401)
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

# --- Helpers ---


def _tool_not_found_result() -> CheckResult:
    """A CheckResult containing a single TOOL-NOT-FOUND issue."""
    return CheckResult(
        issues=[
            Issue(
                file="test.py",
                line=0,
                column=0,
                code="TOOL-NOT-FOUND",
                message="ruff not installed; run: uv add ruff",
                severity=Severity.ERROR,
                source="ruff-format",
            )
        ],
        files_checked=1,
        checks_run=["ruff-format"],
    )


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


# --- Tests ---


@pytest.mark.asyncio
@patch("amplifier_module_hooks_python_check.Path.exists", return_value=True)
@patch("amplifier_module_hooks_python_check.check_files")
async def test_tool_not_found_returns_error_level(mock_check_files, mock_exists):
    """When check_files returns TOOL-NOT-FOUND, hook returns user_message_level='error'."""
    mock_check_files.return_value = _tool_not_found_result()

    hooks = PythonCheckHooks()
    result = await hooks.handle_tool_post("tool:post", _write_event())

    assert result.user_message_level == "error", (
        f"Expected user_message_level='error', got {result.user_message_level!r}"
    )
    assert "Python dev tools not installed" in result.user_message, (
        f"Expected 'Python dev tools not installed' in message, got: {result.user_message!r}"
    )
    assert "ruff not installed" in result.user_message, (
        f"Expected tool message detail in result, got: {result.user_message!r}"
    )
    assert result.action == "inject_context"
    assert result.context_injection == (
        f'<system-reminder source="hooks-python-check">\n{result.user_message}\n</system-reminder>'
    )
    assert result.context_injection_role == "user"
    assert result.ephemeral is True
    assert result.append_to_last_tool_result is True


@pytest.mark.asyncio
@patch("amplifier_module_hooks_python_check.Path.exists", return_value=True)
@patch("amplifier_module_hooks_python_check.check_files")
async def test_tool_not_found_respects_context_injection_opt_out(mock_check_files, mock_exists):
    """Display-only configuration must not inject or block when a checker is absent."""
    mock_check_files.return_value = _tool_not_found_result()
    hooks = PythonCheckHooks({"auto_inject": False})
    result = await hooks.handle_tool_post("tool:post", _write_event())

    assert result.action == "continue"
    assert result.context_injection is None
    assert result.ephemeral is False
    assert result.append_to_last_tool_result is False
    assert result.user_message_level == "error"
    assert result.user_message_source == "python-check"
    assert "ruff not installed" in result.user_message


@pytest.mark.asyncio
@patch("amplifier_module_hooks_python_check.Path.exists", return_value=True)
@patch("amplifier_module_hooks_python_check.check_files")
async def test_tool_not_found_bypasses_redundancy_suppression(mock_check_files, mock_exists):
    """TOOL-NOT-FOUND messages must NOT be suppressed on repeated calls to the same file.

    The normal hook suppresses identical repeat results. This test verifies that
    TOOL-NOT-FOUND bypasses that logic — every write should surface the error.
    """
    mock_check_files.return_value = _tool_not_found_result()

    hooks = PythonCheckHooks()
    event = _write_event()

    # First call
    result1 = await hooks.handle_tool_post("tool:post", event)
    # Second call (same file, same error — would normally be suppressed)
    result2 = await hooks.handle_tool_post("tool:post", event)

    assert result1.user_message_level == "error", (
        f"First call: expected level='error', got {result1.user_message_level!r}"
    )
    assert result2.user_message_level == "error", (
        f"Second call should NOT be suppressed; expected level='error', got {result2.user_message_level!r}"
    )
    assert "Python dev tools not installed" in (result2.user_message or ""), (
        f"Second call message should still contain warning; got: {result2.user_message!r}"
    )
    assert result1.action == result2.action == "inject_context"
    assert result1.context_injection == result2.context_injection


@pytest.mark.asyncio
@patch("amplifier_module_hooks_python_check.Path.exists", return_value=True)
@patch("amplifier_module_hooks_python_check.check_files")
async def test_normal_errors_not_affected(mock_check_files, mock_exists):
    """Normal code issues (F401, etc.) must NOT trigger the TOOL-NOT-FOUND path."""
    mock_check_files.return_value = _normal_error_result()

    hooks = PythonCheckHooks()
    result = await hooks.handle_tool_post("tool:post", _write_event())

    # Should NOT contain the "Python dev tools not installed" message
    assert result.user_message is None or "Python dev tools not installed" not in result.user_message, (
        f"Normal F401 error should not produce TOOL-NOT-FOUND message; got: {result.user_message!r}"
    )
