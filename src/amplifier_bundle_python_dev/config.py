"""Configuration loading for Python checks."""

import os
from pathlib import Path

from .models import CheckConfig

# Try to import tomllib (Python 3.11+) or tomli (fallback)
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


def find_pyproject_toml(start_path: Path | None = None) -> Path | None:
    """Find pyproject.toml by walking up from start_path."""
    current = start_path or Path.cwd()

    while current != current.parent:
        candidate = current / "pyproject.toml"
        if candidate.exists():
            return candidate
        current = current.parent

    return None


def load_config(
    config_path: Path | None = None,
    overrides: dict | None = None,
) -> CheckConfig:
    """Load configuration from pyproject.toml with optional overrides.

    Config is loaded from (in order of priority):
    1. Explicit overrides dict
    2. Environment variables (AMPLIFIER_PYTHON_*)
    3. pyproject.toml [tool.amplifier-python-dev] section
    4. Default values

    Args:
        config_path: Explicit path to pyproject.toml (auto-discovered if None)
        overrides: Dict of config values to override

    Returns:
        Merged CheckConfig
    """
    config_data: dict = {}

    # Load from pyproject.toml
    if tomllib:
        toml_path = config_path or find_pyproject_toml()
        if toml_path and toml_path.exists():
            try:
                with open(toml_path, "rb") as f:
                    pyproject = tomllib.load(f)
                    config_data = pyproject.get("tool", {}).get("amplifier-python-dev", {})
            except Exception:
                pass  # Graceful fallback to defaults

    # Apply environment variables
    env_mapping = {
        "AMPLIFIER_PYTHON_ENABLE_RUFF_FORMAT": "enable_ruff_format",
        "AMPLIFIER_PYTHON_ENABLE_RUFF_LINT": "enable_ruff_lint",
        "AMPLIFIER_PYTHON_ENABLE_PYRIGHT": "enable_pyright",
        "AMPLIFIER_PYTHON_ENABLE_STUB_CHECK": "enable_stub_check",
        "AMPLIFIER_PYTHON_FAIL_ON_WARNING": "fail_on_warning",
        "AMPLIFIER_PYTHON_AUTO_FIX": "auto_fix",
    }

    for env_var, config_key in env_mapping.items():
        value = os.environ.get(env_var)
        if value is not None:
            # Parse boolean strings
            if value.lower() in ("true", "1", "yes"):
                config_data[config_key] = True
            elif value.lower() in ("false", "0", "no"):
                config_data[config_key] = False

    # Apply explicit overrides
    if overrides:
        config_data.update(overrides)

    return CheckConfig.from_dict(config_data)


def get_ruff_config_args(config: CheckConfig) -> list[str]:
    """Get ruff CLI arguments based on config."""
    args = []

    # Add exclude patterns
    for pattern in config.exclude_patterns:
        args.extend(["--exclude", pattern])

    return args


def get_pyright_config_args(config: CheckConfig) -> list[str]:
    """Get pyright CLI arguments based on config."""
    args = []

    # Add exclude patterns via --ignore
    for pattern in config.exclude_patterns:
        args.extend(["--ignore", pattern])

    return args
