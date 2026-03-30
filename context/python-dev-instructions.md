# Python Development Tools

Python code quality via `python_check` (ruff + pyright). Code intelligence via `python-dev:code-intel` agent.

## Auto-checking Hook

After write/edit operations on `*.py` files, checks run automatically and inject issues into agent context. Configure via `pyproject.toml` under `[tool.amplifier-python-dev.hook]` (e.g., `enabled`, `report_level`, `file_patterns`). For full tool reference, configuration options, and CLI usage, use `load_skill(skill_name='python-dev-reference')`.
