"""Amplifier hook module for automatic Python code checking.

This hook triggers on file write/edit events and runs Python quality
checks, injecting feedback into the agent's context when issues are found.
"""

import fnmatch
from pathlib import Path
from typing import Any

from amplifier_bundle_python_dev import CheckConfig, check_files
from amplifier_bundle_python_dev.config import load_config
from amplifier_bundle_python_dev.models import Severity


class PythonCheckHooks:
    """Hook handlers for automatic Python quality checking."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize hooks with configuration.

        Args:
            config: Hook configuration dict with:
                - enabled: bool (default: True)
                - file_patterns: list[str] (default: ["*.py"])
                - report_level: str (default: "warning") - minimum level to report
                - auto_inject: bool (default: True) - inject issues into context
                - checks: list[str] (default: all) - which checks to run
        """
        config = config or {}
        self.enabled = config.get("enabled", True)
        self.file_patterns = config.get("file_patterns", ["*.py"])
        self.report_level = config.get("report_level", "warning")
        self.auto_inject = config.get("auto_inject", True)
        self.checks = config.get("checks", ["format", "lint", "types", "stubs"])

        # Build check config
        self.check_config = CheckConfig(
            enable_ruff_format="format" in self.checks,
            enable_ruff_lint="lint" in self.checks,
            enable_pyright="types" in self.checks,
            enable_stub_check="stubs" in self.checks,
        )

    def _matches_patterns(self, file_path: str) -> bool:
        """Check if file path matches any configured pattern."""
        path = Path(file_path)
        for pattern in self.file_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return True
            if fnmatch.fnmatch(str(path), pattern):
                return True
        return False

    def _filter_by_level(self, issues: list) -> list:
        """Filter issues by configured report level."""
        level_order = {"error": 0, "warning": 1, "info": 2}
        min_level = level_order.get(self.report_level, 1)

        return [i for i in issues if level_order.get(i.severity.value, 0) <= min_level]

    async def handle_tool_post(self, event: str, data: dict[str, Any]) -> dict[str, Any]:
        """Handle post-tool-use events to check Python files.

        Triggers on: write_file, edit_file, Write, Edit, MultiEdit

        Args:
            event: Event name (e.g., "tool:post")
            data: Event data with tool_name, tool_input, tool_result

        Returns:
            HookResult dict with action and optional context injection
        """
        if not self.enabled:
            return {"action": "continue"}

        # Check if this is a file write/edit operation
        tool_name = data.get("tool_name", "")
        write_tools = ["write_file", "edit_file", "Write", "Edit", "MultiEdit"]

        if tool_name not in write_tools:
            return {"action": "continue"}

        # Extract file path from tool input
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", tool_input.get("path", ""))

        if not file_path:
            return {"action": "continue"}

        # Check if this is a Python file
        if not self._matches_patterns(file_path):
            return {"action": "continue"}

        # Check if file exists (might have been deleted)
        if not Path(file_path).exists():
            return {"action": "continue"}

        # Run checks
        result = check_files([file_path], config=self.check_config)

        # Filter by report level
        result.issues = self._filter_by_level(result.issues)

        if result.clean:
            return {"action": "continue"}

        # Build response based on configuration
        hook_output = result.to_hook_output()

        if self.auto_inject:
            # Inject issues into agent context
            context_text = f"Python check found issues in {file_path}:\n{hook_output['issues_text']}"

            return {
                "action": "inject_context",
                "context_injection": context_text,
                "context_injection_role": "system",
                "user_message": f"Found {len(result.issues)} issue(s) in {file_path}",
                "user_message_level": "warning" if result.success else "error",
            }
        else:
            # Just report to user without context injection
            return {
                "action": "continue",
                "user_message": hook_output["summary"],
                "user_message_level": "warning" if result.success else "error",
            }


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mount the Python check hooks into the coordinator.

    Args:
        coordinator: The Amplifier coordinator instance
        config: Module configuration for the hooks

    Returns:
        Module metadata
    """
    hooks = PythonCheckHooks(config)

    # Register the post-tool hook
    coordinator.hooks.register(
        "tool:post",
        hooks.handle_tool_post,
        priority=15,  # Run after most other hooks but before logging
    )

    return {
        "name": "hooks-python-check",
        "version": "0.1.0",
        "provides": ["python_check_hook"],
        "config": {
            "enabled": hooks.enabled,
            "file_patterns": hooks.file_patterns,
            "report_level": hooks.report_level,
            "auto_inject": hooks.auto_inject,
            "checks": hooks.checks,
        },
    }
