"""Successful edit receipts select the checked file without changing check policy."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amplifier_bundle_python_dev.models import CheckResult


@pytest.fixture
def hook_module(monkeypatch):
    # Keep tests independent of an installed Core while matching its result fields.
    monkeypatch.setitem(sys.modules, "amplifier_core", SimpleNamespace(HookResult=SimpleNamespace))
    path = Path(__file__).parents[1] / "modules/hooks-python-check/amplifier_module_hooks_python_check/__init__.py"
    spec = importlib.util.spec_from_file_location("python_edit_hooks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def checked(hook_module, tmp_path, monkeypatch):
    working_dir = tmp_path / "workspace"
    working_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    checker = Mock(return_value=CheckResult(files_checked=1, checks_run=["fixture"]))
    monkeypatch.setattr(hook_module, "check_files", checker)
    return hook_module.PythonCheckHooks(working_dir=working_dir), checker, working_dir


def result_value(shape, **fields):
    return fields if shape == "dict" else SimpleNamespace(**fields)


def invoke(hook, data):
    return asyncio.run(hook.handle_tool_post("tool:post", data))


@pytest.mark.parametrize("shape", ["dict", "object"])
@pytest.mark.parametrize("field", ["result", "tool_result"])
@pytest.mark.parametrize("tool", ["write_file", "edit_file"])
def test_success_uses_resolved_target_instead_of_mention_input(checked, shape, field, tool):
    hook, checker, root = checked
    target = root / "resolved.py"
    target.write_text("source")
    invoke(
        hook,
        {
            "tool_name": tool,
            "tool_input": {"file_path": "@bundle:unresolved-mention"},
            field: result_value(shape, success=True, output={"file_path": str(target)}, error=None),
        },
    )
    assert checker.call_count == 1
    assert [Path(p) for p in checker.call_args.args[0]] == [target]
    assert checker.call_args.kwargs["config"] is hook.check_config


@pytest.mark.parametrize("shape", ["dict", "object"])
@pytest.mark.parametrize("field", ["result", "tool_result"])
@pytest.mark.parametrize("tool", ["write_file", "edit_file"])
def test_failed_edit_never_checks_old_or_output_file(checked, shape, field, tool):
    hook, checker, root = checked
    target = root / "existing.py"
    target.write_text("unchanged old contents")
    response = invoke(
        hook,
        {
            "tool_name": tool,
            "tool_input": {"file_path": str(target)},
            field: result_value(shape, success=False, output={"file_path": str(target)}, error={"message": "failed"}),
        },
    )
    checker.assert_not_called()
    assert response.action == "continue" and not getattr(response, "context_injection", None)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"output": {"file_path": "wrong.py"}},
        {"success": True},
        {"success": True, "output": "written"},
        {"success": True, "output": {"file_path": None}},
        {"success": True, "output": {"file_path": ""}},
        {"success": True, "output": {"file_path": 3}},
    ],
)
@pytest.mark.parametrize("input_key", ["file_path", "path"])
def test_legacy_or_missing_resolved_path_uses_session_working_directory(checked, payload, input_key):
    hook, checker, root = checked
    target = root / "legacy.py"
    target.write_text("source")
    data = {"tool_name": "Edit", "tool_input": {input_key: target.name}}
    if payload is not None:
        data["result"] = payload
    invoke(hook, data)
    assert checker.call_count == 1
    assert [Path(p) for p in checker.call_args.args[0]] == [target]


def test_resolved_path_controls_language_selection(checked):
    hook, checker, root = checked
    raw = root / "old.py"
    raw.write_text("source")
    actual = root / "actual.txt"
    actual.write_text("source")
    invoke(
        hook,
        {
            "tool_name": "write_file",
            "tool_input": {"file_path": str(raw)},
            "result": {"success": True, "output": {"file_path": str(actual)}},
        },
    )
    checker.assert_not_called()


@pytest.mark.parametrize("tool,enabled", [("read_file", True), ("apply_patch", True), ("write_file", False)])
def test_non_edits_and_disabled_hooks_do_not_check(checked, tool, enabled):
    hook, checker, root = checked
    hook.enabled = enabled
    target = root / "source.py"
    target.write_text("source")
    invoke(
        hook,
        {
            "tool_name": tool,
            "tool_input": {"file_path": str(target)},
            "result": {"success": True, "output": {"file_path": str(target)}},
        },
    )
    checker.assert_not_called()


def test_patch_feedback_uses_only_live_call_writes(checked):
    import gc
    import weakref

    class CallIdentity:
        pass

    hook, checker, root = checked
    dispatch = Mock()
    hook.coordinator = Mock()
    hook.coordinator.get_capability.return_value = dispatch

    def select(call_id):
        call = SimpleNamespace(name="apply_patch", call_id=call_id, identity=CallIdentity())
        dispatch.current_call.return_value = call
        return call

    def write(path):
        target = root / path
        target.write_text("x = 1\n")
        asyncio.run(hook.observe_patch("apply-patch:applied", {"written_path": str(target)}))
        return target

    def finish(id_):
        return invoke(hook, {"tool_name": "apply_patch", "tool_call_id": id_, "result": {"success": False}})

    first = select("first")
    renamed = write("destination.py")
    write("destination.py")
    write("deleted.py").unlink()
    write("ignored.txt")
    select("second")
    other = write("other.py")
    finish("first")  # A different call cannot consume this call's effects.
    checker.assert_not_called()
    finish("second")
    dispatch.current_call.return_value = first
    finish("first")
    assert [call.args[0] for call in checker.call_args_list] == [[str(other)], [str(renamed)]]
    finish("first")
    assert checker.call_count == 2

    cancelled = select("cancelled")
    ref = weakref.ref(cancelled.identity)
    write("cancelled.py")
    dispatch.current_call.return_value = None
    del cancelled
    gc.collect()
    assert ref() is None and not hook.patch_writes
    finish("cancelled")
    assert checker.call_count == 2
