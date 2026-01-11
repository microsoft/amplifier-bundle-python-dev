"""Amplifier hook module for automatic Python code checking.

This hook triggers on file write/edit events and runs Python quality
checks, injecting feedback into the agent's context when issues are found.

Features:
- Severity-adaptive display (more detail for errors, less for warnings)
- Progress tracking across repeated edits to same file
- Clean pass indicator for checked files
- Relative path display for readability
- Configurable verbosity levels
"""

import fnmatch
import os
from pathlib import Path
from typing import Any
from typing import Literal

from amplifier_core import HookResult

from amplifier_bundle_python_dev import CheckConfig
from amplifier_bundle_python_dev import check_files
from amplifier_bundle_python_dev.models import CheckResult
from amplifier_bundle_python_dev.models import Issue
from amplifier_bundle_python_dev.models import Severity

# Icons for different states (work in monospace terminals)
ICONS = {
    "clean": "\u2713",  # ✓ - checkmark
    "minor": "\u25d0",  # ◐ - half circle (warnings/style)
    "errors": "\u25cf",  # ● - filled circle (errors)
    "stubs": "\u25d1",  # ◑ - half circle reversed (incomplete)
}


class FileCheckState:
    """Tracks check state for a single file across edits."""

    def __init__(self):
        self.error_count: int = 0
        self.warning_count: int = 0
        self.check_count: int = 0  # How many times we've checked this file

    def update(self, errors: int, warnings: int) -> tuple[int, int]:
        """Update state and return previous counts for comparison."""
        prev_errors, prev_warnings = self.error_count, self.warning_count
        self.error_count = errors
        self.warning_count = warnings
        self.check_count += 1
        return prev_errors, prev_warnings

    @property
    def total_issues(self) -> int:
        return self.error_count + self.warning_count


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
                - verbosity: str (default: "normal") - "minimal", "normal", "detailed"
                - show_clean: bool (default: True) - show clean pass indicator
        """
        config = config or {}
        self.enabled = config.get("enabled", True)
        self.file_patterns = config.get("file_patterns", ["*.py"])
        self.report_level = config.get("report_level", "warning")
        self.auto_inject = config.get("auto_inject", True)
        self.checks = config.get("checks", ["format", "lint", "types", "stubs"])
        self.verbosity: Literal["minimal", "normal", "detailed"] = config.get("verbosity", "normal")
        self.show_clean = config.get("show_clean", True)

        # Build check config
        self.check_config = CheckConfig(
            enable_ruff_format="format" in self.checks,
            enable_ruff_lint="lint" in self.checks,
            enable_pyright="types" in self.checks,
            enable_stub_check="stubs" in self.checks,
        )

        # Track file state for progress tracking (keyed by absolute path)
        self._file_states: dict[str, FileCheckState] = {}

    def _matches_patterns(self, file_path: str) -> bool:
        """Check if file path matches any configured pattern."""
        path = Path(file_path)
        for pattern in self.file_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return True
            if fnmatch.fnmatch(str(path), pattern):
                return True
        return False

    def _filter_by_level(self, issues: list[Issue]) -> list[Issue]:
        """Filter issues by configured report level."""
        level_order = {"error": 0, "warning": 1, "info": 2}
        min_level = level_order.get(self.report_level, 1)

        return [i for i in issues if level_order.get(i.severity.value, 0) <= min_level]

    def _get_relative_path(self, file_path: str) -> str:
        """Convert absolute path to relative path for display."""
        try:
            path = Path(file_path)
            cwd = Path.cwd()

            # If file is under cwd, show relative path
            if path.is_absolute():
                try:
                    rel_path = path.relative_to(cwd)
                    return str(rel_path)
                except ValueError:
                    pass

                # Try relative to home
                home = Path.home()
                try:
                    rel_path = path.relative_to(home)
                    return f"~/{rel_path}"
                except ValueError:
                    pass

            # Fallback to just filename
            return path.name
        except Exception:
            return Path(file_path).name

    def _get_file_state(self, file_path: str) -> FileCheckState:
        """Get or create file state tracker."""
        abs_path = str(Path(file_path).resolve())
        if abs_path not in self._file_states:
            self._file_states[abs_path] = FileCheckState()
        return self._file_states[abs_path]

    def _categorize_issues(self, issues: list[Issue]) -> dict[str, list[Issue]]:
        """Categorize issues by type for display."""
        categories: dict[str, list[Issue]] = {
            "type_errors": [],
            "lint_errors": [],
            "style_issues": [],
            "stubs": [],
        }

        for issue in issues:
            if issue.source == "pyright":
                categories["type_errors"].append(issue)
            elif issue.source == "stub-check":
                categories["stubs"].append(issue)
            elif issue.source == "ruff-format":
                categories["style_issues"].append(issue)
            elif issue.severity == Severity.ERROR:
                categories["lint_errors"].append(issue)
            else:
                categories["style_issues"].append(issue)

        return categories

    def _format_category_summary(self, categories: dict[str, list[Issue]]) -> str:
        """Format issue categories into a readable summary."""
        parts = []

        type_errors = len(categories["type_errors"])
        lint_errors = len(categories["lint_errors"])
        style_issues = len(categories["style_issues"])
        stubs = len(categories["stubs"])

        if type_errors:
            parts.append(f"{type_errors} type error{'s' if type_errors != 1 else ''}")
        if lint_errors:
            parts.append(f"{lint_errors} lint error{'s' if lint_errors != 1 else ''}")
        if style_issues:
            parts.append(f"{style_issues} style issue{'s' if style_issues != 1 else ''}")
        if stubs:
            parts.append(f"{stubs} stub{'s' if stubs != 1 else ''}")

        return ", ".join(parts) if parts else "no issues"

    def _get_severity_icon(self, result: CheckResult, categories: dict[str, list[Issue]]) -> str:
        """Get appropriate icon based on severity."""
        if result.clean:
            return ICONS["clean"]
        if categories["stubs"] and not categories["type_errors"] and not categories["lint_errors"]:
            return ICONS["stubs"]
        if result.error_count > 0:
            return ICONS["errors"]
        return ICONS["minor"]

    def _format_user_message(
        self,
        result: CheckResult,
        display_path: str,
        file_state: FileCheckState,
        prev_errors: int,
        prev_warnings: int,
    ) -> tuple[str, Literal["info", "warning", "error"]]:
        """Format the user-facing message based on verbosity and state."""
        categories = self._categorize_issues(result.issues)
        icon = self._get_severity_icon(result, categories)
        category_summary = self._format_category_summary(categories)

        # Determine message level
        if result.clean:
            level: Literal["info", "warning", "error"] = "info"
        elif result.error_count > 0:
            level = "error"
        else:
            level = "warning"

        # Build the message based on verbosity
        if result.clean:
            # Clean pass
            if file_state.check_count > 1 and (prev_errors > 0 or prev_warnings > 0):
                # Was dirty, now clean - celebrate progress
                return f"{icon} {display_path}: clean (was {prev_errors + prev_warnings} issues)", "info"
            else:
                # First check or was already clean
                return f"{icon} {display_path}: clean", "info"

        # Has issues
        if self.verbosity == "minimal":
            # Just icon and count
            total = len(result.issues)
            return f"{icon} {display_path}: {total} issue{'s' if total != 1 else ''}", level

        # Normal verbosity - show category summary
        message = f"{icon} {display_path}: {category_summary}"

        # Add progress info if this is a repeat check with improvement
        if file_state.check_count > 1:
            prev_total = prev_errors + prev_warnings
            curr_total = result.error_count + result.warning_count
            if curr_total < prev_total:
                message += f" (was {prev_total})"

        return message, level

    def _format_detailed_issues(self, result: CheckResult, max_issues: int = 5) -> str:
        """Format detailed issue lines for expanded display."""
        lines = []

        # Sort issues: errors first, then by line number
        sorted_issues = sorted(
            result.issues,
            key=lambda i: (0 if i.severity == Severity.ERROR else 1, i.line),
        )

        for issue in sorted_issues[:max_issues]:
            severity_label = "error" if issue.severity == Severity.ERROR else "warn "
            # Truncate message if too long
            msg = issue.message[:60] + "..." if len(issue.message) > 63 else issue.message
            # No leading spaces - display system handles alignment
            lines.append(f"\u2502 {severity_label}  line {issue.line:<4}  {msg}")

        if len(result.issues) > max_issues:
            remaining = len(result.issues) - max_issues
            lines.append(f"\u2502 ... and {remaining} more")

        return "\n".join(lines)

    def _should_show_details(self, result: CheckResult) -> bool:
        """Determine if we should show detailed issue list."""
        if self.verbosity == "detailed":
            return True
        if self.verbosity == "minimal":
            return False

        # Normal verbosity: show details for errors, not for warnings-only
        return result.error_count > 0

    async def handle_tool_post(self, event: str, data: dict[str, Any]) -> HookResult:
        """Handle post-tool-use events to check Python files.

        Triggers on: write_file, edit_file, Write, Edit, MultiEdit

        Args:
            event: Event name (e.g., "tool:post")
            data: Event data with tool_name, tool_input, tool_result

        Returns:
            HookResult with action and optional context injection
        """
        if not self.enabled:
            return HookResult(action="continue")

        # Check if this is a file write/edit operation
        tool_name = data.get("tool_name", "")
        write_tools = ["write_file", "edit_file", "Write", "Edit", "MultiEdit"]

        if tool_name not in write_tools:
            return HookResult(action="continue")

        # Extract file path from tool input
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", tool_input.get("path", ""))

        if not file_path:
            return HookResult(action="continue")

        # Check if this is a Python file
        if not self._matches_patterns(file_path):
            return HookResult(action="continue")

        # Check if file exists (might have been deleted)
        if not Path(file_path).exists():
            return HookResult(action="continue")

        # Run checks
        result = check_files([file_path], config=self.check_config)

        # Filter by report level
        result.issues = self._filter_by_level(result.issues)

        # Get display path and file state
        display_path = self._get_relative_path(file_path)
        file_state = self._get_file_state(file_path)
        prev_errors, prev_warnings = file_state.update(result.error_count, result.warning_count)

        # Handle clean pass
        if result.clean:
            if self.show_clean:
                message, level = self._format_user_message(result, display_path, file_state, prev_errors, prev_warnings)
                return HookResult(
                    action="continue",
                    user_message=message,
                    user_message_level=level,
                )
            return HookResult(action="continue")

        # Check for redundant message (same count as before)
        if (
            file_state.check_count > 1
            and result.error_count == prev_errors
            and result.warning_count == prev_warnings
            and self.verbosity != "detailed"
        ):
            # Same as before, skip redundant message
            return HookResult(action="continue")

        # Format user message
        user_message, user_level = self._format_user_message(
            result, display_path, file_state, prev_errors, prev_warnings
        )

        # Add detailed issues if appropriate
        if self._should_show_details(result):
            details = self._format_detailed_issues(result)
            user_message = f"{user_message}\n{details}"

        if self.auto_inject:
            # Inject issues into agent context (always full detail for agent)
            context_lines = [f"Python check found issues in {display_path}:"]
            for issue in result.issues[:10]:
                context_lines.append(f"- {issue.format_short()}")
            if len(result.issues) > 10:
                context_lines.append(f"  ... and {len(result.issues) - 10} more issues")

            context_text = "\n".join(context_lines)

            return HookResult(
                action="inject_context",
                context_injection=context_text,
                context_injection_role="system",
                # ephemeral=False (default) - coordinator adds to context manager
                # for inclusion in next LLM request
                user_message=user_message,
                user_message_level=user_level,
            )
        else:
            # Just report to user without context injection
            return HookResult(
                action="continue",
                user_message=user_message,
                user_message_level=user_level,
            )


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
        name="python-check",  # Explicit name for source attribution
    )

    return {
        "name": "hooks-python-check",
        "version": "0.2.0",
        "provides": ["python_check_hook"],
        "config": {
            "enabled": hooks.enabled,
            "file_patterns": hooks.file_patterns,
            "report_level": hooks.report_level,
            "auto_inject": hooks.auto_inject,
            "checks": hooks.checks,
            "verbosity": hooks.verbosity,
            "show_clean": hooks.show_clean,
        },
    }
