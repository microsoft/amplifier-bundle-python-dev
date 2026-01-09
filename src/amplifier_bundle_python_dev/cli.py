#!/usr/bin/env python3
"""CLI entry point for amplifier-python-check.

Usage:
    uvx --from git+https://github.com/microsoft/amplifier-bundle-python-dev amplifier-python-check [OPTIONS] [PATHS]...

Examples:
    amplifier-python-check src/                    # Check a directory
    amplifier-python-check src/main.py tests/      # Check specific paths
    amplifier-python-check --fix src/              # Auto-fix issues
    amplifier-python-check --format json src/      # JSON output for CI
"""

import sys
from pathlib import Path

import click

from .checker import PythonChecker
from .config import load_config
from .models import CheckConfig


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--fix", is_flag=True, help="Auto-fix issues where possible")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "github"]),
    default="text",
    help="Output format (default: text)",
)
@click.option("--config", "config_path", type=click.Path(exists=True), help="Path to pyproject.toml")
@click.option("--no-format", is_flag=True, help="Skip ruff format check")
@click.option("--no-lint", is_flag=True, help="Skip ruff lint check")
@click.option("--no-types", is_flag=True, help="Skip pyright type check")
@click.option("--no-stubs", is_flag=True, help="Skip stub/TODO check")
@click.option("--only-errors", is_flag=True, help="Only report errors, not warnings")
@click.version_option(package_name="amplifier-bundle-python-dev")
def main(
    paths: tuple[str, ...],
    fix: bool,
    output_format: str,
    config_path: str | None,
    no_format: bool,
    no_lint: bool,
    no_types: bool,
    no_stubs: bool,
    only_errors: bool,
) -> None:
    """Check Python code quality with ruff and pyright.

    Runs formatting checks, linting, type checking, and stub detection
    on the specified PATHS (files or directories). Defaults to current directory.
    """
    # Load configuration
    config = load_config(
        config_path=Path(config_path) if config_path else None,
        overrides={
            "enable_ruff_format": not no_format,
            "enable_ruff_lint": not no_lint,
            "enable_pyright": not no_types,
            "enable_stub_check": not no_stubs,
            "auto_fix": fix,
        },
    )

    # Default to current directory if no paths specified
    check_paths = list(paths) if paths else ["."]

    # Run checks
    checker = PythonChecker(config)

    if output_format == "text":
        click.echo()
        click.echo("=== Amplifier Python Check ===")
        click.echo()

    result = checker.check_files(check_paths, fix=fix)

    # Filter to errors only if requested
    if only_errors:
        from .models import Severity

        result.issues = [i for i in result.issues if i.severity == Severity.ERROR]

    # Output results
    if output_format == "json":
        import json

        click.echo(json.dumps(result.to_tool_output(), indent=2))
    elif output_format == "github":
        # GitHub Actions annotation format
        for issue in result.issues:
            level = "error" if issue.severity.value == "error" else "warning"
            click.echo(f"::{level} file={issue.file},line={issue.line},col={issue.column}::{issue.code}: {issue.message}")
        click.echo()
        click.echo(result.summary)
    else:
        # Text format
        if result.issues:
            click.echo(result.to_cli_output())
        else:
            click.echo(f"All checks passed ({result.files_checked} files)")

        click.echo()

        # Show what was checked
        checks_str = ", ".join(result.checks_run)
        click.echo(f"Checks run: {checks_str}")

        if fix and not result.clean:
            click.echo()
            click.echo("Note: Some issues were auto-fixed. Run again to verify.")

    # Exit with appropriate code
    sys.exit(result.exit_code)


def cli_entry() -> None:
    """Entry point for the CLI script."""
    main()


if __name__ == "__main__":
    cli_entry()
