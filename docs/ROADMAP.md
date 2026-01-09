# Python Development Bundle Roadmap

This document outlines the future extensibility plans for `amplifier-bundle-python-dev`.

## Vision

The Python Development Bundle is the **"Python Development Home"** in the Amplifier ecosystem - a collection point for all Python-specific development capabilities.

## Current State (MVP)

### ✅ Completed

| Feature | Component | Description |
|---------|-----------|-------------|
| **CLI Tool** | `amplifier-python-check` | Standalone code quality checker via uvx |
| **Format Check** | ruff format | PEP 8 style enforcement |
| **Lint Check** | ruff check | Bug detection, import sorting, style rules |
| **Type Check** | pyright | Static type analysis |
| **Stub Detection** | custom | TODO/placeholder/incomplete code detection |
| **Tool Module** | `python_check` | Agent-callable tool |
| **Hook Module** | `hooks-python-check` | Automatic checking on file events |
| **Agent** | `python-dev` | Expert Python developer agent |
| **LSP Integration** | via lsp-python | Code intelligence (hover, definition, refs) |
| **Configuration** | pyproject.toml | Flexible check configuration |

---

## Phase 2: Testing Integration

### Goals
- Run and analyze pytest results
- Test discovery and selection
- Coverage analysis and gap detection
- Test generation assistance

### Planned Components

#### `tool-python-test`
```python
# Run tests
python_test(paths=["tests/"])
python_test(paths=["tests/test_auth.py::test_login"])
python_test(markers=["not integration"])

# Coverage
python_test(paths=["tests/"], coverage=True)
python_test(coverage_report="html")
```

#### `hooks-python-test`
- Trigger on test file changes
- Run affected tests automatically
- Report failures to agent context

#### Agent Enhancement
- Test-aware recommendations
- "This change may affect these tests: ..."
- Test generation suggestions

### Configuration
```toml
[tool.amplifier-python-dev.testing]
enabled = true
framework = "pytest"
coverage_threshold = 80
auto_run_on_change = true
markers_exclude = ["slow", "integration"]
```

---

## Phase 3: Debugging Support

### Goals
- Debug session management
- Breakpoint suggestions
- Variable inspection
- Stack trace analysis

### Planned Components

#### `tool-python-debug`
```python
# Analyze an exception
python_debug(exception=traceback_str)

# Suggest breakpoints for a function
python_debug(analyze="src/auth.py:login")

# Explain a stack trace
python_debug(stacktrace=error_output)
```

#### Agent Enhancement
- Exception pattern recognition
- "This looks like X error, commonly caused by Y"
- Debugging strategy recommendations

---

## Phase 4: Profiling & Performance

### Goals
- Performance profiling
- Memory analysis
- Hot path identification
- Optimization suggestions

### Planned Components

#### `tool-python-profile`
```python
# Profile a function
python_profile(module="src.processor", function="process_batch")

# Memory profiling
python_profile(memory=True, script="scripts/run.py")

# Identify hot paths
python_profile(paths=["src/"], hotspots=True)
```

#### Integrations
- cProfile / profile
- py-spy (sampling profiler)
- memory_profiler
- line_profiler

---

## Phase 5: Dependency Management

### Goals
- Security vulnerability detection
- Outdated package identification
- License compliance
- Dependency graph analysis

### Planned Components

#### `tool-python-deps`
```python
# Security audit
python_deps(audit=True)

# Check for updates
python_deps(outdated=True)

# Analyze dependency tree
python_deps(tree=True, package="requests")

# License check
python_deps(licenses=True)
```

#### Integrations
- pip-audit (security)
- pip list --outdated
- pipdeptree
- pip-licenses

---

## Phase 6: Documentation

### Goals
- Docstring validation
- API documentation generation
- README maintenance
- Example code validation

### Planned Components

#### `tool-python-docs`
```python
# Check docstring coverage
python_docs(coverage=True)

# Validate docstring format
python_docs(validate="google")  # or numpy, sphinx

# Generate API docs
python_docs(generate=True, output="docs/api/")
```

---

## Behavior Composition Strategy

As features are added, they'll be organized into composable behaviors:

```yaml
# behaviors/python-quality.yaml    - format, lint, types, stubs (current)
# behaviors/python-testing.yaml    - pytest, coverage
# behaviors/python-debug.yaml      - debugging tools
# behaviors/python-perf.yaml       - profiling
# behaviors/python-deps.yaml       - dependency management
# behaviors/python-docs.yaml       - documentation

# behaviors/python-full.yaml       - everything combined
```

Users can pick and choose:
```yaml
includes:
  - bundle: python-dev:behaviors/python-quality
  - bundle: python-dev:behaviors/python-testing
```

---

## Agent Evolution

The `python-dev` agent will grow to wield all tools:

| Phase | New Capabilities |
|-------|------------------|
| MVP | Quality checks + LSP |
| Testing | Test running, coverage analysis, test suggestions |
| Debugging | Exception analysis, breakpoint suggestions |
| Profiling | Performance analysis, optimization tips |
| Deps | Security alerts, update recommendations |
| Docs | Docstring assistance, API documentation |

The agent's context file will expand to include domain knowledge for each area.

---

## Technical Principles

All additions should follow:

1. **Shared Core**: New capabilities share logic between CLI, tool, and hook
2. **Thin Bundle**: Bundle only composes behaviors, doesn't implement logic
3. **Configurable**: Everything toggleable via pyproject.toml
4. **Incremental**: Each phase is independently valuable
5. **Agent-First**: Tools designed for agent consumption, CLI is bonus

---

## Contributing

Want to help build the Python Development Home? Here's how:

1. **Pick a phase** from the roadmap
2. **Design the tool** following existing patterns
3. **Implement shared core** first
4. **Add CLI, tool module, hook module** as wrappers
5. **Update the agent** to wield the new tool
6. **Document everything** in context files

See the existing implementation for patterns to follow.
