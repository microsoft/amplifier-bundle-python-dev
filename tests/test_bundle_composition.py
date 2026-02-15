"""Validate python-dev bundle composition after lsp-python absorption."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent


def deep_merge(base, overlay):
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# --- Bundle metadata ---


def test_bundle_metadata():
    """Root bundle has required metadata and correct version."""
    bundle = yaml.safe_load((ROOT / "bundle.yaml").read_text())
    assert bundle["bundle"]["name"] == "python-dev"
    assert "version" in bundle["bundle"]
    assert "description" in bundle["bundle"]


def test_bundle_no_lsp_python_reference():
    """bundle.yaml must not reference the old lsp-python bundle."""
    content = (ROOT / "bundle.yaml").read_text()
    assert "lsp-python" not in content, "bundle.yaml still references lsp-python — should use internal behaviors"
    assert "amplifier-bundle-lsp-python" not in content


def test_bundle_uses_internal_composite():
    """bundle.yaml includes the internal composite behavior."""
    bundle = yaml.safe_load((ROOT / "bundle.yaml").read_text())
    includes = bundle["includes"]
    assert len(includes) == 1
    assert includes[0]["bundle"] == "python-dev:behaviors/python-dev"


# --- Behavior composition ---


def test_composite_behavior_includes_both():
    """Composite python-dev.yaml includes both LSP and quality behaviors."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-dev.yaml").read_text())
    includes = behavior["includes"]
    bundles = [i["bundle"] for i in includes]
    assert "python-dev:behaviors/python-lsp" in bundles
    assert "python-dev:behaviors/python-quality" in bundles


def test_composite_behavior_has_no_direct_tools():
    """Composite behavior should only include sub-behaviors, not define tools."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-dev.yaml").read_text())
    assert "tools" not in behavior, "Composite should not define tools directly"
    assert "hooks" not in behavior, "Composite should not define hooks directly"


def test_quality_behavior_has_tools_and_hooks():
    """Quality behavior defines tool-python-check and hooks-python-check."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-quality.yaml").read_text())
    assert behavior["bundle"]["name"] == "python-quality-behavior"
    tool_modules = [t["module"] for t in behavior["tools"]]
    assert "tool-python-check" in tool_modules
    hook_modules = [h["module"] for h in behavior["hooks"]]
    assert "hooks-python-check" in hook_modules


def test_quality_behavior_registers_python_dev_agent():
    """Quality behavior registers the python-dev agent."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-quality.yaml").read_text())
    agents = behavior["agents"]["include"]
    assert "python-dev:python-dev" in agents


def test_lsp_behavior_registers_code_intel_agent():
    """LSP behavior registers the code-intel agent."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-lsp.yaml").read_text())
    agents = behavior["agents"]["include"]
    assert "python-dev:code-intel" in agents


def test_lsp_behavior_includes_lsp_core():
    """LSP behavior includes the base lsp-core behavior."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-lsp.yaml").read_text())
    includes = behavior["includes"]
    assert any("lsp-core" in i["bundle"] for i in includes)


# --- LSP config and deep merge ---


def test_python_config_merges():
    """Python language config merges into lsp-core's empty languages slot."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-lsp.yaml").read_text())
    python_config = next(t["config"] for t in behavior["tools"] if t["module"] == "tool-lsp")
    core_config = {"languages": {}, "timeout_seconds": 30}
    merged = deep_merge(core_config, python_config)
    assert "python" in merged["languages"]
    assert merged["languages"]["python"]["extensions"] == [".py", ".pyi"]
    assert merged["languages"]["python"]["server"]["command"] == [
        "pyright-langserver",
        "--stdio",
    ]
    assert merged["timeout_seconds"] == 30


def test_python_server_config_complete():
    """Python server config has all required fields."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-lsp.yaml").read_text())
    python = next(t["config"] for t in behavior["tools"] if t["module"] == "tool-lsp")["languages"]["python"]
    assert "extensions" in python
    assert "workspace_markers" in python
    assert "server" in python
    assert "command" in python["server"]
    assert "install_check" in python["server"]
    assert "install_hint" in python["server"]


def test_python_capabilities_declared():
    """Python bundle declares capabilities matching live Pyright test results."""
    behavior = yaml.safe_load((ROOT / "behaviors" / "python-lsp.yaml").read_text())
    caps = next(t["config"] for t in behavior["tools"] if t["module"] == "tool-lsp")["languages"]["python"][
        "capabilities"
    ]
    # Supported
    assert caps["diagnostics"] is True
    assert caps["rename"] is True
    # Not supported by Pyright
    assert caps["codeAction"] is False
    assert caps["inlayHints"] is False
    assert caps["customRequest"] is False
    assert caps["goToImplementation"] is False


# --- Namespace consistency ---


def test_no_lsp_python_namespace_in_behaviors():
    """No behavior file should reference the old lsp-python: namespace."""
    for yaml_file in (ROOT / "behaviors").glob("*.yaml"):
        content = yaml_file.read_text()
        assert "lsp-python:" not in content, f"{yaml_file.name} still references lsp-python: namespace"


def test_no_lsp_python_namespace_in_agents():
    """No agent file should reference the old lsp-python: namespace."""
    for md_file in (ROOT / "agents").glob("*.md"):
        content = md_file.read_text()
        # Check frontmatter only (between first two --- markers)
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            assert "lsp-python:" not in frontmatter, f"{md_file.name} frontmatter references lsp-python: namespace"


# --- Agent frontmatter ---


def test_code_intel_agent_frontmatter():
    """code-intel agent has proper meta frontmatter."""
    content = (ROOT / "agents" / "code-intel.md").read_text()
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Agent must have YAML frontmatter between --- markers"
    meta = yaml.safe_load(parts[1])
    assert meta["meta"]["name"] == "code-intel"
    assert "description" in meta["meta"]
    # Agent must declare tools for sub-session independence
    assert "tools" in meta
    assert any(t["module"] == "tool-lsp" for t in meta["tools"])


def test_code_intel_description_uses_new_namespace():
    """code-intel description references python-dev:code-intel, not python-code-intel."""
    content = (ROOT / "agents" / "code-intel.md").read_text()
    parts = content.split("---", 2)
    meta = yaml.safe_load(parts[1])
    desc = meta["meta"]["description"]
    assert "python-dev:code-intel" in desc, "Description should reference python-dev:code-intel"
    assert "python-code-intel" not in desc, "Description should not use old name python-code-intel"


def test_code_intel_has_prerequisite_validation():
    """code-intel agent includes prerequisite validation section."""
    content = (ROOT / "agents" / "code-intel.md").read_text()
    assert "## Prerequisite Validation" in content, "Agent must have a '## Prerequisite Validation' section"
    # Must appear before strategies
    prereq_pos = content.index("## Prerequisite Validation")
    strategies_pos = content.index("## Python-Specific Strategies")
    assert prereq_pos < strategies_pos, "Prerequisite Validation must appear before Python-Specific Strategies"
    # Must provide Pyright-specific installation guidance
    assert "npm install -g pyright" in content, "Must provide Pyright installation guidance"


def test_code_intel_description_mentions_validation():
    """code-intel description mentions prerequisite validation."""
    content = (ROOT / "agents" / "code-intel.md").read_text()
    parts = content.split("---", 2)
    meta = yaml.safe_load(parts[1])
    desc = meta["meta"]["description"].lower()
    assert "validates" in desc or "validation" in desc, "Description should mention validation"
    assert "install" in desc, "Description should mention installation guidance"


def test_python_dev_agent_frontmatter():
    """python-dev agent has proper meta frontmatter with only quality tool."""
    content = (ROOT / "agents" / "python-dev.md").read_text()
    parts = content.split("---", 2)
    meta = yaml.safe_load(parts[1])
    assert meta["meta"]["name"] == "python-dev"
    tools = meta["tools"]
    tool_modules = [t["module"] for t in tools]
    assert "tool-python-check" in tool_modules
    assert "tool-lsp" not in tool_modules, "python-dev agent should not have tool-lsp (LSP work goes to code-intel)"


# --- YAML validity ---


def test_all_yaml_valid():
    """All YAML files in the bundle parse without error."""
    for yaml_file in ROOT.rglob("*.yaml"):
        # Skip node_modules, .venv, etc.
        if any(part.startswith(".") or part == "node_modules" for part in yaml_file.parts):
            continue
        content = yaml.safe_load(yaml_file.read_text())
        assert content is not None, f"{yaml_file} is empty or invalid"


# --- File structure ---


def test_expected_files_exist():
    """All expected files from the absorption are present."""
    expected = [
        "bundle.yaml",
        "behaviors/python-dev.yaml",
        "behaviors/python-lsp.yaml",
        "behaviors/python-quality.yaml",
        "agents/python-dev.md",
        "agents/code-intel.md",
        "context/python-dev-instructions.md",
        "context/python-lsp.md",
        "context/PYTHON_BEST_PRACTICES.md",
    ]
    for path in expected:
        assert (ROOT / path).exists(), f"Missing expected file: {path}"
