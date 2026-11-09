"""Amplifier tool module for Python code quality checks.

This module provides the `python_check` tool that agents can use to
check Python code for formatting, linting, type errors, and stubs.
"""

from pathlib import Path
from typing import Any

from amplifier_core import ToolResult

from amplifier_bundle_python_dev import check_content
from amplifier_bundle_python_dev import check_files
from amplifier_bundle_python_dev.config import CHECK_FLAGS
from amplifier_bundle_python_dev.config import find_pyproject_toml
from amplifier_bundle_python_dev.config import load_config


class PythonCheckTool:
    """Tool for checking Python code quality."""

    def __init__(self, config: dict[str, Any] | None = None, working_dir: Path | None = None):
        self.config = config or {}
        self.working_dir = (working_dir or Path.cwd()).resolve()

    @property
    def name(self) -> str:
        return "python_check"

    @property
    def description(self) -> str:
        return """Check Python code for quality issues.

Runs ruff (formatting, linting and complexity), file/function size warnings, pyright (type checking), and stub detection
on Python files or code content.

Input options:
- paths: List of file paths or directories to check
- content: Python code as a string to check
- fix: If true, auto-fix issues where possible (only works with paths)

Examples:
- Check a file: {"paths": ["src/main.py"]}
- Check a directory: {"paths": ["src/"]}
- Check multiple paths: {"paths": ["src/", "tests/test_main.py"]}
- Check code string: {"content": "def foo():\\n    pass"}
- Auto-fix issues: {"paths": ["src/"], "fix": true}

Returns:
- success: True if no errors (warnings are OK)
- clean: True if no issues at all
- summary: Human-readable summary
- issues: List of issues with file, line, code, message, severity"""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths or directories to check",
                },
                "content": {
                    "type": "string",
                    "description": "Python code as a string to check (alternative to paths)",
                },
                "fix": {
                    "type": "boolean",
                    "description": "Auto-fix issues where possible",
                    "default": False,
                },
                "checks": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(CHECK_FLAGS)},
                    "description": "Specific checks to run (default: all)",
                },
            },
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolResult:
        """Execute the Python check tool.

        Args:
            input_data: Tool input with paths, content, fix, and/or checks

        Returns:
            ToolResult with check output
        """
        paths = input_data.get("paths")
        content = input_data.get("content")
        fix = input_data.get("fix", False)
        checks = input_data.get("checks", self.config.get("default_checks"))

        # Build config based on requested checks
        config_overrides = dict(self.config.get("check_options", {}))
        if checks is not None:
            config_overrides.update({flag: name in checks for name, flag in CHECK_FLAGS.items()})
        config_path = find_pyproject_toml(self.working_dir) or self.working_dir / "pyproject.toml"
        config = load_config(config_path, overrides=config_overrides)

        # Run checks
        if content is not None:
            result = check_content(content, filename=str(self.working_dir / "stdin.py"), config=config)
        elif paths:
            result = check_files([self.working_dir / path for path in paths], config=config, fix=fix)
        else:
            # Default to current directory
            result = check_files([self.working_dir], config=config, fix=fix)

        return ToolResult(success=result.success, output=result.to_tool_output())


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mount the python_check tool into the coordinator.

    Args:
        coordinator: The Amplifier coordinator instance
        config: Optional module configuration

    Returns:
        Module metadata
    """
    working_dir = coordinator.get_capability("session.working_dir")
    tool = PythonCheckTool(config, Path(working_dir) if working_dir else None)

    # Register the tool
    await coordinator.mount("tools", tool, name=tool.name)

    return {
        "name": "tool-python-check",
        "version": "0.3.1",
        "provides": ["python_check"],
    }
