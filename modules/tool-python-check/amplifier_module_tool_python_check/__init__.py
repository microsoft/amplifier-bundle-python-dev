"""Amplifier tool module for Python code quality checks.

This module provides the `python_check` tool that agents can use to
check Python code for formatting, linting, type errors, and stubs.
"""

from typing import Any

from amplifier_bundle_python_dev import CheckConfig, check_content, check_files


class PythonCheckTool:
    """Tool for checking Python code quality."""

    @property
    def name(self) -> str:
        return "python_check"

    @property
    def description(self) -> str:
        return """Check Python code for quality issues.

Runs ruff (formatting and linting), pyright (type checking), and stub detection
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
                    "items": {"type": "string", "enum": ["format", "lint", "types", "stubs"]},
                    "description": "Specific checks to run (default: all)",
                },
            },
        }

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the Python check tool.

        Args:
            input_data: Tool input with paths, content, fix, and/or checks

        Returns:
            Tool result dictionary
        """
        paths = input_data.get("paths")
        content = input_data.get("content")
        fix = input_data.get("fix", False)
        checks = input_data.get("checks")

        # Build config based on requested checks
        config_overrides = {}
        if checks:
            config_overrides["enable_ruff_format"] = "format" in checks
            config_overrides["enable_ruff_lint"] = "lint" in checks
            config_overrides["enable_pyright"] = "types" in checks
            config_overrides["enable_stub_check"] = "stubs" in checks

        config = CheckConfig.from_dict(config_overrides) if config_overrides else None

        # Run checks
        if content:
            result = check_content(content, config=config)
        elif paths:
            result = check_files(paths, config=config, fix=fix)
        else:
            # Default to current directory
            result = check_files(["."], config=config, fix=fix)

        return result.to_tool_output()


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mount the python_check tool into the coordinator.

    Args:
        coordinator: The Amplifier coordinator instance
        config: Optional module configuration

    Returns:
        Module metadata
    """
    tool = PythonCheckTool()

    # Register the tool
    await coordinator.mount("tools", tool, name=tool.name)

    return {
        "name": "tool-python-check",
        "version": "0.1.0",
        "provides": ["python_check"],
    }
