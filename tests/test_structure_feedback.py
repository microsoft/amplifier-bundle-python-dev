"""Exercise edited-file feedback and explicit tool selection with the shared checker."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("amplifier_core", MagicMock())

import amplifier_module_hooks_python_check as hook_module  # noqa: E402
import amplifier_module_tool_python_check as tool_module  # noqa: E402

from amplifier_bundle_python_dev.models import CheckResult  # noqa: E402
from amplifier_bundle_python_dev.models import Issue  # noqa: E402
from amplifier_bundle_python_dev.models import Severity  # noqa: E402


@pytest.fixture(autouse=True)
def core_results(monkeypatch):
    """Use only the result surface consumed by these modules, without installing Core."""

    def hook_result(**kwargs):
        return SimpleNamespace(**{"user_message": None, "context_injection": None, **kwargs})

    monkeypatch.setattr(hook_module, "HookResult", hook_result)
    monkeypatch.setattr(tool_module, "ToolResult", lambda **kwargs: SimpleNamespace(**kwargs))


def write_event(path, **extra):
    return {"tool_name": "write_file", "tool_input": {"file_path": path}, **extra}


@pytest.mark.asyncio
async def test_project_path_and_changed_warning_with_same_count(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.amplifier-python-dev]\nmax_file_lines = 2\n")
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n" * 3)
    hooks = hook_module.PythonCheckHooks({"checks": ["structure"]}, working_dir=tmp_path)
    first = await hooks.handle_tool_post("tool:post", write_event("sample.py"))
    assert first.action == "inject_context"
    assert "FILE-LENGTH" in first.context_injection
    repeated = await hooks.handle_tool_post("tool:post", write_event("sample.py"))
    assert repeated.action == "continue"
    assert repeated.context_injection is None
    source.write_text("x = 1\n" * 4)
    changed = await hooks.handle_tool_post("tool:post", write_event("sample.py"))
    assert changed.action == "inject_context"
    assert changed.context_injection != first.context_injection
    source.write_text("x = 1\n")
    resolved = await hooks.handle_tool_post("tool:post", write_event("sample.py"))
    assert resolved.action == "continue"
    assert resolved.context_injection is None
    assert resolved.user_message is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("result_key", ["result", "tool_result"])
async def test_failed_write_does_not_report_old_file(tmp_path, monkeypatch, result_key):
    (tmp_path / "sample.py").write_text("x = 1\n")
    check = MagicMock()
    monkeypatch.setattr(hook_module, "check_files", check)
    hooks = hook_module.PythonCheckHooks(working_dir=tmp_path)
    result = await hooks.handle_tool_post("tool:post", write_event("sample.py", **{result_key: {"success": False}}))
    assert result.action == "continue"
    check.assert_not_called()


@pytest.mark.asyncio
async def test_tool_keeps_project_thresholds_and_explicit_selection(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[tool.amplifier-python-dev]\nmax_file_lines = 2\n")
    (tmp_path / "sample.py").write_text("x = 1\n" * 3)
    # Structure-only must not silently launch Ruff or a project type check.
    subprocess = MagicMock(side_effect=AssertionError("unexpected external checker"))
    monkeypatch.setattr("amplifier_bundle_python_dev.checker.subprocess.run", subprocess)
    tool = tool_module.PythonCheckTool(working_dir=tmp_path)
    result = await tool.execute({"paths": ["sample.py"], "checks": ["structure"]})
    assert result.success
    assert "FILE-LENGTH" in str(result.output)
    subprocess.assert_not_called()


@pytest.mark.asyncio
async def test_tool_content_uses_session_project_ruff_threshold(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff.lint.mccabe]\nmax-complexity = 2\n")
    content = "def choose(x):\n    if x == 1: return 1\n    if x == 2: return 2\n    if x == 3: return 3\n"
    tool = tool_module.PythonCheckTool(working_dir=tmp_path)
    result = await tool.execute({"content": content, "checks": ["complexity"]})
    assert result.success
    assert "C901" in str(result.output)


def test_project_disables_are_preserved_without_explicit_selection(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.amplifier-python-dev]\nenable_structure_check = false\nenable_complexity_check = false\n"
    )
    hooks = hook_module.PythonCheckHooks(working_dir=tmp_path)
    assert not hooks.check_config.enable_structure_check
    assert not hooks.check_config.enable_complexity_check


@pytest.mark.asyncio
async def test_oversized_edit_reports_skip_without_claiming_clean(tmp_path):
    (tmp_path / "sample.py").write_text("x = 1\n" * 20)
    hooks = hook_module.PythonCheckHooks(
        {"checks": ["structure"], "check_options": {"structure_max_bytes": 32}}, working_dir=tmp_path
    )
    result = await hooks.handle_tool_post("tool:post", write_event("sample.py"))
    assert result.action == "inject_context"
    assert "STRUCTURE-SKIPPED" in result.context_injection


def test_diagnostic_history_is_bounded(tmp_path):
    hooks = hook_module.PythonCheckHooks(working_dir=tmp_path)
    for index in range(300):
        hooks._get_file_state(str(tmp_path / f"file_{index}.py"))
    assert len(hooks._file_states) == 256


@pytest.mark.asyncio
async def test_excluded_edit_is_not_announced_as_checked(tmp_path):
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "sample.py").write_text("x = 1\n")
    hooks = hook_module.PythonCheckHooks({"checks": ["structure"]}, working_dir=tmp_path)
    result = await hooks.handle_tool_post("tool:post", write_event("vendor/sample.py"))
    assert result.action == "continue"
    assert result.user_message is None


@pytest.mark.asyncio
async def test_structure_is_visible_with_many_lint_issues(tmp_path, monkeypatch):
    (tmp_path / "sample.py").write_text("x = 1\n")
    issues = [Issue("sample.py", n + 1, 1, "F401", "unused import", Severity.ERROR, "ruff-lint") for n in range(12)]
    issues.append(Issue("sample.py", 1, 1, "C901", "complexity 40 > 20", Severity.WARNING, "ruff-lint"))
    monkeypatch.setattr(
        hook_module, "check_files", lambda *_args, **_kwargs: CheckResult(issues=issues, checks_run=["ruff-lint"])
    )
    hooks = hook_module.PythonCheckHooks(working_dir=tmp_path)
    result = await hooks.handle_tool_post("tool:post", write_event("sample.py"))
    assert "C901" in result.context_injection
    assert sum(line.startswith("- ") for line in result.context_injection.splitlines()) == 10
    assert "review prompts" in result.context_injection
