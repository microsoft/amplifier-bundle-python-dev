# Python Development Tools

This bundle provides comprehensive Python development capabilities for Amplifier.

## Available Tools

### python_check

Run code quality checks on Python files or code content.

```
python_check(paths=["src/"])           # Check a directory
python_check(paths=["src/main.py"])    # Check a specific file
python_check(content="def foo(): ...")  # Check code string
python_check(paths=["src/"], fix=True)  # Auto-fix issues
```

**Checks performed:**
- **ruff format**: Code formatting (PEP 8 style)
- **ruff lint**: Linting rules (pycodestyle, pyflakes, isort, bugbear, comprehensions, etc.)
- **pyright**: Static type checking
- **stub detection**: TODOs, placeholders, incomplete code

### LSP Tools (via lsp-python)

Semantic code intelligence for Python:

| Tool | Use For |
|------|---------|
| `hover` | Get type info and docstrings |
| `goToDefinition` | Find where a symbol is defined |
| `findReferences` | Find all usages of a symbol |
| `incomingCalls` | What calls this function? |
| `outgoingCalls` | What does this function call? |

## Automatic Checking Hook

When enabled, Python files are automatically checked after write/edit operations.

**Behavior:**
- Triggers on `write_file`, `edit_file`, and similar tools
- Checks `*.py` files only
- Runs lint and type checks (fast subset)
- Injects issues into agent context for awareness

**Configuration** (in `pyproject.toml`):
```toml
[tool.amplifier-python-dev.hook]
enabled = true
file_patterns = ["*.py"]
report_level = "warning"  # error | warning | info
auto_inject = true
```

## CLI Usage

For standalone use outside Amplifier:

```bash
# Install and run
uvx --from git+https://github.com/microsoft/amplifier-bundle-python-dev amplifier-python-check src/

# With options
amplifier-python-check src/ --fix           # Auto-fix issues
amplifier-python-check src/ --format=json   # JSON output for CI
amplifier-python-check src/ --no-types      # Skip type checking
```

## Configuration

Configure via `pyproject.toml`:

```toml
[tool.amplifier-python-dev]
# Enable/disable specific checks
enable_ruff_format = true
enable_ruff_lint = true
enable_pyright = true
enable_stub_check = true

# Paths to exclude
exclude_patterns = [
    ".venv/**",
    "__pycache__/**",
    "build/**",
]

# Behavior
fail_on_warning = false  # Exit code 1 on warnings
auto_fix = false         # Auto-fix by default

[tool.amplifier-python-dev.hook]
enabled = true
file_patterns = ["*.py"]
report_level = "warning"
auto_inject = true
```

## Best Practices

See @python-dev:context/PYTHON_BEST_PRACTICES.md for the full development philosophy.

**Key points:**
1. Run `python_check` after writing Python code
2. Fix issues immediately - don't accumulate debt
3. Use LSP tools to understand code before modifying
4. Type hints at boundaries, not everywhere
5. Readability over cleverness
