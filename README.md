# amplifier-bundle-python-dev

Comprehensive Python development tools for [Amplifier](https://github.com/microsoft/amplifier) - the "Python Development Home" in the Amplifier ecosystem.

## What's Included

| Component | Description |
|-----------|-------------|
| **Tool Module** | `python_check` - agent-callable tool for quality checks |
| **Hook Module** | Automatic checking on file write/edit events |
| **Agent** | `python-dev` - expert Python developer agent |
| **LSP Integration** | Includes lsp-python for code intelligence |
| **Shared Library** | Core checking logic used by tool and hook modules |

## Quick Start

### As Amplifier Bundle

```yaml
# In your bundle.yaml
includes:
  - bundle: git+https://github.com/microsoft/amplifier-bundle-python-dev@main
```

This gives you:
- Foundation tools and agents
- Python LSP (code intelligence)
- Python quality checks (tool + hook)
- Python development expert agent

## Checks Performed

| Check | Tool | What It Catches |
|-------|------|-----------------|
| **Format** | ruff format | Code style (PEP 8) |
| **Lint** | ruff check | Bugs, imports, style, complexity |
| **Types** | pyright | Type errors, missing annotations |
| **Stubs** | custom | TODOs, placeholders, incomplete code |
| **Complexity** | ruff C901 | Functions with too many independent paths |
| **Structure** | Python AST | Long authored files and functions |

## Configuration

Configure via `pyproject.toml`:

```toml
[tool.amplifier-python-dev]
# Enable/disable checks
enable_ruff_format = true
enable_ruff_lint = true
enable_pyright = true
enable_stub_check = true

# Exclude paths
exclude_patterns = [
    ".venv/**",
    "__pycache__/**",
    "tests/fixtures/**",
]

# Behavior
fail_on_warning = false

# Hook configuration
[tool.amplifier-python-dev.hook]
enabled = true
file_patterns = ["*.py"]
report_level = "warning"  # error | warning | info
auto_inject = true        # Add issues to agent context
```

## Agent Usage

The `python-dev` agent is an expert Python developer that wields both quality checks and LSP tools:

```
# Within Amplifier
> @python-dev Check src/auth.py for issues

# The agent will:
# 1. Run python_check on the file
# 2. Use LSP to understand code structure
# 3. Provide actionable recommendations
```

**Agent capabilities:**
- Code quality analysis
- Type error diagnosis
- Import organization
- Code structure understanding (via LSP)
- Best practices guidance

## Hook Behavior

When enabled, the hook automatically runs checks after Python file edits:

1. You write/edit a `.py` file
2. Hook triggers and runs lint + type checks
3. Issues are injected into agent context
4. Agent is aware of problems immediately

This creates a tight feedback loop - issues are caught as you work, not at the end.

### Complexity and size feedback

Complexity and size findings are advisory warnings. They do not block edits or
automatically split/refactor code. Treat a finding as a reason to inspect ownership,
cohesion and tests; fewer lines or a lower score alone do not prove a better design.

`complexity` adds C901 to the existing Ruff lint invocation, or runs only C901 when
selected without lint. Ruff owns the metric, threshold (default 10) and per-file
exceptions. Explicit rule selection follows Ruff's CLI precedence and overrides a
global `lint.ignore = ["C901"]`; omit `complexity` from the hook/tool checks to opt
out (or set `enable_complexity_check = false` when no explicit selection is used).
Configure the threshold in the project's native Ruff settings:

```toml
[tool.ruff.lint.mccabe]
max-complexity = 20  # Example project policy; the bundle does not override Ruff's default.

[tool.amplifier-python-dev]
enable_complexity_check = true
enable_structure_check = true
max_file_lines = 500
max_function_lines = 100
structure_max_bytes = 1048576
# Optional replacement for default structure-specific exclusions.
# Preserve these defaults when adding project exclusions:
structure_exclude_patterns = ["vendor/**", "generated/**", "_generated/**", "*_pb2.py", "*_pb2_grpc.py", "tests/fixtures/**"]
```

Size means physical lines (including comments/blanks); function size is its AST
source span, including nested definitions. Nested functions, methods and async
functions are also measured independently. These defaults are review prompts, not
universal limits. Unreadable, oversized or unparseable inputs produce an explicit
`STRUCTURE-SKIPPED` warning, not a clean result. The byte limit bounds the added
structure pass; it does not impose a timeout or size limit on existing external
checkers.

For a fast edit-time profile, override the existing hook's module configuration:

```yaml
config:
  checks: [lint, complexity, structure]
  check_options:
    max_file_lines: 500
    max_function_lines: 100
  report_level: warning
  auto_inject: true
```

The supplied behavior still retains format/type checks; their project-wide cost is
not part of this fast profile. Run deeper type checks explicitly when appropriate.
The hook handles single-file `write_file`, `edit_file`, `Write`, `Edit` and `MultiEdit`
events with a `file_path` or `path`; shell writes and patch batches are not inferred.
It resolves paths against the session working directory, ignores explicitly failed
writes, reports at most ten issues to the model and suppresses identical repeated
diagnostics. A changed diagnostic or score is reported even when counts are unchanged.

Project settings load first, then module `check_options`; an explicit `checks` list
(or the tool's `default_checks`) selects the enabled checks. Override that list to
disable checks supplied by a behavior. The `python_check` tool accepts `complexity`
and `structure` in its `checks` list and shares the same library implementation.
Deploy matching library and module revisions: the modules use the host-provided
Python-dev library. Merely updating this repository does not add it to bundles that
do not include Python quality tooling.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    amplifier-bundle-python-dev              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐│
│  │   CLI   │  │  Tool   │  │  Hook   │  │  python-dev     ││
│  │         │  │ Module  │  │ Module  │  │     Agent       ││
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬────────┘│
│       │            │            │                │         │
│       └────────────┴─────┬──────┴────────────────┘         │
│                          │                                  │
│                   ┌──────▼──────┐                          │
│                   │ SHARED CORE │                          │
│                   │ checker.py  │                          │
│                   └─────────────┘                          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  INCLUDES: foundation + lsp-python                          │
└─────────────────────────────────────────────────────────────┘
```

## Development Philosophy

This bundle embodies **pragmatic professionalism**:

1. **Readability over cleverness** - Code should be obvious
2. **Complete or not at all** - No stubs/TODOs in production
3. **Context-aware pragmatism** - Rules serve the code
4. **Type safety as aid** - Types help, don't constrain
5. **Clean imports** - One per line, properly sorted

See [PYTHON_BEST_PRACTICES.md](context/PYTHON_BEST_PRACTICES.md) for the full guide.

## Future Roadmap

This bundle is the "Python Development Home" - a collection point for Python-specific capabilities:

| Phase | Feature | Status |
|-------|---------|--------|
| MVP | Formatting, linting, types, stubs | ✅ Done |
| Testing | pytest integration, coverage | 🔮 Planned |
| Debugging | Debug session management | 🔮 Planned |
| Profiling | cProfile, py-spy integration | 🔮 Planned |
| Dependencies | pip-audit, outdated checks | 🔮 Planned |

## Contributing

> [!NOTE]
> This project is not currently accepting external contributions, but we're actively working toward opening this up. We value community input and look forward to collaborating in the future. For now, feel free to fork and experiment!

Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
