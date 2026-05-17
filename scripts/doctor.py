#!/usr/bin/env python3
"""Local development doctor for HTT Control Tower.

This script validates the local prerequisites that should be true before we use
staging/prod as a feedback loop. It intentionally avoids Azure connectivity and
secret-dependent checks; cloud validation belongs in deployment gates, not in a
local doctor.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 12)


@dataclass(frozen=True)
class CheckResult:
    """Result from a doctor check."""

    name: str
    status: str
    message: str
    remediation: str | None = None

    @property
    def is_failure(self) -> bool:
        return self.status == "fail"


Check = Callable[[], CheckResult]


def ok(name: str, message: str) -> CheckResult:
    return CheckResult(name, "pass", message)


def warn(name: str, message: str, remediation: str | None = None) -> CheckResult:
    return CheckResult(name, "warn", message, remediation)


def fail(name: str, message: str, remediation: str | None = None) -> CheckResult:
    return CheckResult(name, "fail", message, remediation)


def run_command(
    command: list[str],
    *,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def check_python_version() -> CheckResult:
    version = sys.version_info
    current = f"{version.major}.{version.minor}.{version.micro}"
    minimum = ".".join(str(part) for part in MIN_PYTHON)
    if (version.major, version.minor) < MIN_PYTHON:
        return fail(
            "Python version",
            f"Python {current} is too old; expected >= {minimum}.",
            "Install Python 3.12+ and recreate the uv environment.",
        )
    return ok("Python version", f"Python {current} is supported.")


def check_command(name: str, remediation: str) -> CheckResult:
    path = shutil.which(name)
    if path is None:
        return fail(f"{name} command", f"{name!r} was not found on PATH.", remediation)
    return ok(f"{name} command", f"Found {name} at {path}.")


def check_project_files() -> CheckResult:
    required = [
        "pyproject.toml",
        "Makefile",
        "alembic.ini",
        "app/main.py",
        "app/static/css/design-tokens.css",
        "app/static/css/tailwind-output.css",
        "app/static/css/design-utilities.css",
    ]
    missing = [path for path in required if not (PROJECT_ROOT / path).exists()]
    if missing:
        return fail(
            "Project files",
            f"Missing required files: {', '.join(missing)}.",
            "Run doctor from the repository root or restore missing files.",
        )
    return ok("Project files", "Required repo files and CSS assets are present.")


def check_env_file() -> CheckResult:
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"
    if env_path.exists():
        return ok("Environment file", ".env exists; values were not inspected or printed.")
    if example_path.exists():
        return warn(
            "Environment file",
            ".env is missing, but .env.example exists. Local test harness may still work.",
            "Copy .env.example to .env if you need to run the app outside test harness mode.",
        )
    return warn(
        "Environment file",
        "No .env or .env.example found. Doctor will continue using test harness overrides.",
    )


def check_python_imports() -> CheckResult:
    modules = [
        "fastapi",
        "jinja2",
        "playwright.sync_api",
        "pytest",
        "sqlalchemy",
    ]
    missing: list[str] = []
    for module in modules:
        try:
            importlib.import_module(module)
        except Exception as exc:  # pragma: no cover - defensive local diagnostic
            missing.append(f"{module} ({exc.__class__.__name__})")

    if missing:
        return fail(
            "Python dependencies",
            f"Could not import: {', '.join(missing)}.",
            "Run `uv sync --all-extras --dev` or `make install-dev`.",
        )
    return ok("Python dependencies", "Core Python dependencies import successfully.")


def check_app_import_openapi() -> CheckResult:
    script = """
from app.main import app
schema = app.openapi()
assert schema.get('openapi')
print(len(app.routes))
"""
    result = run_command(
        ["uv", "run", "python", "-c", script],
        timeout=45,
        env={
            "ENVIRONMENT": "test",
            "E2E_HARNESS": "true",
            "BROWSER_TEST_DISABLE_SCHEDULERS": "true",
        },
    )
    if result.returncode != 0:
        return fail(
            "App import/OpenAPI",
            "App import or OpenAPI generation failed in test harness mode.",
            _tail(result.stderr or result.stdout),
        )

    route_count = _tail(result.stdout).strip().splitlines()[-1]
    return ok("App import/OpenAPI", f"App imports and OpenAPI generates; {route_count} routes.")


def check_playwright_browser() -> CheckResult:
    script = """
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    browser.close()
print('chromium ok')
"""
    result = run_command(["uv", "run", "python", "-c", script], timeout=45)
    if result.returncode != 0:
        return fail(
            "Playwright browser",
            "Playwright Chromium could not launch.",
            "Run `uv run playwright install chromium`. Details: " + _tail(result.stderr),
        )
    return ok("Playwright browser", "Chromium launches through Playwright.")


def check_bd_ready() -> CheckResult:
    if shutil.which("bd") is None:
        return fail(
            "bd issue tracker",
            "bd command is missing.",
            "Install bd and run `bd onboard`.",
        )

    result = run_command(["bd", "ready"], timeout=30)
    if result.returncode != 0:
        return fail(
            "bd issue tracker",
            "bd ready failed.",
            "Run `bd onboard`. Details: " + _tail(result.stderr or result.stdout),
        )
    return ok("bd issue tracker", "bd is available and can read project issues.")


def _tail(value: str, *, max_chars: int = 700) -> str:
    cleaned = value.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return "..." + cleaned[-max_chars:]


def render_result(result: CheckResult) -> str:
    icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[result.status]
    output = f"{icon} {result.name}: {result.message}"
    if result.remediation:
        output += f"\n   ↳ {result.remediation}"
    return output


def main() -> int:
    checks: list[Check] = [
        check_python_version,
        lambda: check_command("uv", "Install uv: https://docs.astral.sh/uv/"),
        lambda: check_command("ruff", "Run commands through `uv run ruff` or install dev deps."),
        check_project_files,
        check_env_file,
        check_python_imports,
        check_app_import_openapi,
        check_playwright_browser,
        check_bd_ready,
    ]

    print("🐶 HTT Control Tower local doctor")
    print("Checking local prerequisites without touching Azure. Fancy, right?\n")

    results = [check() for check in checks]
    for result in results:
        print(render_result(result))

    failures = [result for result in results if result.is_failure]
    warnings = [result for result in results if result.status == "warn"]

    print("\nSummary:")
    print(f"  ✅ pass: {len(results) - len(failures) - len(warnings)}")
    print(f"  ⚠️ warn: {len(warnings)}")
    print(f"  ❌ fail: {len(failures)}")

    if failures:
        print("\nDoctor failed. Fix the ❌ items before using local-gate as release evidence.")
        return 1

    print("\nDoctor passed. Local machine is healthy enough for the next gate layer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
