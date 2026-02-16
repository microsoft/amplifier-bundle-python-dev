"""Core Python checking logic.

This module contains all the checking logic, shared by:
- CLI (amplifier-python-check command)
- Tool module (python_check tool for agents)
- Hook module (automatic checks on file events)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from .config import load_config
from .models import CheckConfig, CheckResult, Issue, Severity


class PythonChecker:
    """Main checker that orchestrates ruff, pyright, and stub detection."""

    def __init__(self, config: CheckConfig | None = None):
        """Initialize checker with optional config."""
        self.config = config or load_config()

    def check_files(self, paths: list[str | Path], fix: bool = False) -> CheckResult:
        """Run all enabled checks on the given paths.

        Args:
            paths: Files or directories to check
            fix: If True, auto-fix issues where possible

        Returns:
            CheckResult with all issues found
        """
        if not paths:
            paths = [Path.cwd()]

        # Filter out non-Python files to prevent running linters on wrong file types.
        # When called on e.g. TypeScript files, ruff/pyright produce massive garbage
        # output (228K+ chars) that can exhaust context budgets.
        python_extensions = {".py", ".pyi"}
        valid_paths: list[str] = []
        skipped_files: list[str] = []
        for p in paths:
            path = Path(p)
            if path.is_dir() or path.suffix in python_extensions:
                valid_paths.append(str(path))
            else:
                skipped_files.append(str(path))

        if not valid_paths:
            return CheckResult(
                issues=[
                    Issue(
                        file="",
                        line=0,
                        column=0,
                        code="NON-PYTHON",
                        message=(
                            f"No Python files to check. "
                            f"Skipped {len(skipped_files)} non-Python file(s): "
                            f"{', '.join(skipped_files)}. "
                            f"python_check only supports .py and .pyi files."
                        ),
                        severity=Severity.INFO,
                        source="python-check",
                    )
                ],
            )

        path_strs = valid_paths
        results = CheckResult(files_checked=self._count_python_files(path_strs))

        if skipped_files:
            results.issues.append(
                Issue(
                    file="",
                    line=0,
                    column=0,
                    code="NON-PYTHON",
                    message=(f"Skipped {len(skipped_files)} non-Python file(s): {', '.join(skipped_files)}"),
                    severity=Severity.INFO,
                    source="python-check",
                )
            )

        if self.config.enable_ruff_format:
            format_result = self._run_ruff_format(path_strs, fix=fix)
            results = results.merge(format_result)

        if self.config.enable_ruff_lint:
            lint_result = self._run_ruff_lint(path_strs, fix=fix)
            results = results.merge(lint_result)

        if self.config.enable_pyright:
            type_result = self._run_pyright(path_strs)
            results = results.merge(type_result)

        if self.config.enable_stub_check:
            stub_result = self._run_stub_check(path_strs)
            results = results.merge(stub_result)

        return results

    def check_content(self, content: str, filename: str = "stdin.py") -> CheckResult:
        """Check Python content string (useful for hook use).

        Args:
            content: Python source code as string
            filename: Virtual filename for error reporting

        Returns:
            CheckResult with issues found
        """
        # Write to temp file and check
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = self.check_files([temp_path])
            # Rewrite paths to use the original filename
            for issue in result.issues:
                if issue.file == temp_path:
                    issue.file = filename
            return result
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _count_python_files(self, paths: list[str]) -> int:
        """Count Python files in the given paths."""
        count = 0
        for path_str in paths:
            path = Path(path_str)
            if path.is_file() and path.suffix == ".py":
                count += 1
            elif path.is_dir():
                count += len(list(path.rglob("*.py")))
        return count

    def _run_ruff_format(self, paths: list[str], fix: bool = False) -> CheckResult:
        """Run ruff format check."""
        cmd = [sys.executable, "-m", "ruff", "format"]
        if not fix:
            cmd.append("--check")
            cmd.append("--diff")
        cmd.extend(paths)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            return CheckResult(
                issues=[
                    Issue(
                        file="",
                        line=0,
                        column=0,
                        code="TOOL-NOT-FOUND",
                        message="ruff not found. Install with: uv add ruff",
                        severity=Severity.ERROR,
                        source="ruff-format",
                    )
                ],
                checks_run=["ruff-format"],
            )

        issues = []
        if result.returncode != 0 and not fix:
            # Parse diff output to find files that would be reformatted
            current_file = None
            for line in result.stdout.split("\n"):
                if line.startswith("--- "):
                    # Extract filename from diff header
                    current_file = line[4:].strip()
                    if current_file.startswith("a/"):
                        current_file = current_file[2:]
                elif line.startswith("+++ ") and current_file:
                    issues.append(
                        Issue(
                            file=current_file,
                            line=1,
                            column=1,
                            code="FORMAT",
                            message="File would be reformatted",
                            severity=Severity.WARNING,
                            source="ruff-format",
                            suggestion="Run with --fix to auto-format",
                        )
                    )
                    current_file = None

        return CheckResult(issues=issues, checks_run=["ruff-format"])

    def _run_ruff_lint(self, paths: list[str], fix: bool = False) -> CheckResult:
        """Run ruff lint check."""
        cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json"]
        if fix:
            cmd.append("--fix")
        cmd.extend(paths)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            return CheckResult(
                issues=[
                    Issue(
                        file="",
                        line=0,
                        column=0,
                        code="TOOL-NOT-FOUND",
                        message="ruff not found. Install with: uv add ruff",
                        severity=Severity.ERROR,
                        source="ruff-lint",
                    )
                ],
                checks_run=["ruff-lint"],
            )

        issues = []
        if result.stdout.strip():
            try:
                ruff_issues = json.loads(result.stdout)
                for item in ruff_issues:
                    # Determine severity from code
                    code = item.get("code", "")
                    if code.startswith("E") or code.startswith("F"):
                        severity = Severity.ERROR
                    else:
                        severity = Severity.WARNING

                    suggestion = None
                    if item.get("fix"):
                        suggestion = item["fix"].get("message", "Fix available")

                    issues.append(
                        Issue(
                            file=item.get("filename", ""),
                            line=item.get("location", {}).get("row", 0),
                            column=item.get("location", {}).get("column", 0),
                            code=code,
                            message=item.get("message", ""),
                            severity=severity,
                            source="ruff-lint",
                            suggestion=suggestion,
                            end_line=item.get("end_location", {}).get("row"),
                            end_column=item.get("end_location", {}).get("column"),
                        )
                    )
            except json.JSONDecodeError:
                pass

        return CheckResult(issues=issues, checks_run=["ruff-lint"])

    def _run_pyright(self, paths: list[str]) -> CheckResult:
        """Run pyright type checking."""
        cmd = [sys.executable, "-m", "pyright", "--outputjson"]
        cmd.extend(paths)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            return CheckResult(
                issues=[
                    Issue(
                        file="",
                        line=0,
                        column=0,
                        code="TOOL-NOT-FOUND",
                        message="pyright not found. Install with: uv add pyright",
                        severity=Severity.ERROR,
                        source="pyright",
                    )
                ],
                checks_run=["pyright"],
            )

        issues = []
        if result.stdout.strip():
            try:
                pyright_output = json.loads(result.stdout)
                for diag in pyright_output.get("generalDiagnostics", []):
                    severity_map = {
                        "error": Severity.ERROR,
                        "warning": Severity.WARNING,
                        "information": Severity.INFO,
                    }
                    severity = severity_map.get(diag.get("severity", "error"), Severity.ERROR)

                    issues.append(
                        Issue(
                            file=diag.get("file", ""),
                            line=diag.get("range", {}).get("start", {}).get("line", 0) + 1,
                            column=diag.get("range", {}).get("start", {}).get("character", 0) + 1,
                            code=diag.get("rule", "pyright"),
                            message=diag.get("message", ""),
                            severity=severity,
                            source="pyright",
                            end_line=diag.get("range", {}).get("end", {}).get("line", 0) + 1,
                            end_column=diag.get("range", {}).get("end", {}).get("character", 0) + 1,
                        )
                    )
            except json.JSONDecodeError:
                pass

        return CheckResult(issues=issues, checks_run=["pyright"])

    def _run_stub_check(self, paths: list[str]) -> CheckResult:
        """Check for TODOs, stubs, and placeholder code."""
        issues = []

        for path_str in paths:
            path = Path(path_str)
            if path.is_file() and path.suffix == ".py":
                issues.extend(self._check_file_for_stubs(path))
            elif path.is_dir():
                for py_file in path.rglob("*.py"):
                    # Skip excluded patterns
                    if self._should_exclude(py_file):
                        continue
                    issues.extend(self._check_file_for_stubs(py_file))

        return CheckResult(issues=issues, checks_run=["stub-check"])

    def _should_exclude(self, path: Path) -> bool:
        """Check if path matches any exclude pattern."""
        path_str = str(path)
        for pattern in self.config.exclude_patterns:
            # Simple glob matching
            if pattern.endswith("/**"):
                dir_pattern = pattern[:-3]
                if dir_pattern in path_str:
                    return True
            elif pattern in path_str:
                return True
        return False

    def _check_file_for_stubs(self, file_path: Path) -> list[Issue]:
        """Check a single file for stub patterns."""
        issues = []

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
        except Exception:
            return issues

        for line_num, line in enumerate(lines, 1):
            for pattern, description in self.config.stub_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check for legitimate patterns
                    if self._is_legitimate_pattern(file_path, line_num, line, lines):
                        continue

                    issues.append(
                        Issue(
                            file=str(file_path),
                            line=line_num,
                            column=1,
                            code="STUB",
                            message=f"{description}: {line.strip()[:60]}",
                            severity=Severity.WARNING,
                            source="stub-check",
                            suggestion="Remove placeholder or implement functionality",
                        )
                    )

        return issues

    def _is_legitimate_pattern(self, file_path: Path, line_num: int, line: str, lines: list[str]) -> bool:
        """Check if a stub pattern is actually legitimate."""
        # Test files are allowed to have mocks and stubs
        if "test" in str(file_path).lower():
            return True

        # Empty __init__.py files are fine
        if file_path.name == "__init__.py" and line.strip() in ("", "pass"):
            return True

        # Abstract methods with NotImplementedError are legitimate
        if "NotImplementedError" in line:
            for i in range(max(0, line_num - 3), line_num):
                if "@abstractmethod" in lines[i] or "@abc.abstractmethod" in lines[i]:
                    return True

        # Exception classes with just pass are legitimate
        if line.strip() == "pass":
            for i in range(max(0, line_num - 5), line_num):
                if "class" in lines[i] and ("Error" in lines[i] or "Exception" in lines[i]):
                    return True

        # Click command groups with pass are legitimate
        if "pass" in line:
            for i in range(max(0, line_num - 3), line_num):
                if "@click.group" in lines[i] or "@cli.group" in lines[i]:
                    return True
                if "@click.command" in lines[i] or "@cli.command" in lines[i]:
                    return True

        # Protocol definitions with pass or ... are legitimate
        if line.strip() in ("pass", "..."):
            if "Protocol" in "\n".join(lines[:50]):
                return True

        return False


# Convenience functions for direct use
def check_files(paths: list[str | Path], config: CheckConfig | None = None, fix: bool = False) -> CheckResult:
    """Check Python files for issues.

    Args:
        paths: Files or directories to check
        config: Optional config (defaults loaded from pyproject.toml)
        fix: If True, auto-fix issues where possible

    Returns:
        CheckResult with issues found
    """
    checker = PythonChecker(config)
    return checker.check_files(paths, fix=fix)


def check_content(content: str, filename: str = "stdin.py", config: CheckConfig | None = None) -> CheckResult:
    """Check Python content string.

    Args:
        content: Python source code as string
        filename: Virtual filename for error reporting
        config: Optional config

    Returns:
        CheckResult with issues found
    """
    checker = PythonChecker(config)
    return checker.check_content(content, filename)
