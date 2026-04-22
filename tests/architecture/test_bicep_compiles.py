"""Fitness function: every Bicep template must compile.

Bicep syntax and schema errors slip through silently today — infra isn't
touched often, and nobody re-runs `az bicep build` on every PR. A working
compile is the minimum bar any template must clear before it's even
worth reading.

RATCHET PATTERN (same as tests/architecture/test_fitness_functions.py
::test_file_size_limit):

    known_broken = {<set of currently-failing .bicep files>}

    - Files NOT in the set must compile cleanly.
    - Files IN the set that now compile must be removed from the set
      (the allowlist only ratchets down).

That way:
  1. Any NEW Bicep file or any NEW regression to an existing file
     FAILS the build immediately — you can't slip a broken template in.
  2. Any fix to a known-broken file FORCES you to remove it from the
     allowlist — the grandfather list can never grow stale.

SKIP CONDITIONS:
  - Azure CLI not installed (CI without az tooling)
  - az bicep subcommand not available

This keeps the test opt-in on machines that don't have the toolchain.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

# Repo root is two levels up from this file (tests/architecture/...).
REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_DIR = REPO_ROOT / "infrastructure"

# Known-broken Bicep templates: grandfathered-in allowlist.
#
# The initial audit (2026-04-21) found 10 broken templates. All were fixed
# over the course of a single cleanup pass. The allowlist is kept as an empty
# set so future regressions have a documented place to land, but the default
# invariant is "empty": any addition must cite a bd issue explaining why the
# file is broken and tracking the fix.
KNOWN_BROKEN_BICEP: set[str] = set()


def _az_bicep_available() -> bool:
    """Return True if `az bicep build` can be invoked from this shell."""
    if shutil.which("az") is None:
        return False
    try:
        result = subprocess.run(
            ["az", "bicep", "version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def _compile_bicep(path: Path) -> tuple[bool, str]:
    """Return (ok, stderr) for a single `az bicep build --file …` invocation."""
    try:
        result = subprocess.run(
            ["az", "bicep", "build", "--file", str(path), "--stdout"],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"az bicep build timed out after 60s for {path}"

    if result.returncode == 0:
        return True, ""

    stderr = result.stderr.decode("utf-8", errors="replace")
    return False, stderr


@pytest.fixture(scope="module")
def _bicep_files() -> list[Path]:
    """All .bicep templates in the repo, rooted at the repo."""
    if not INFRA_DIR.exists():
        pytest.skip("infrastructure/ directory not found")
    return sorted(INFRA_DIR.rglob("*.bicep"))


@pytest.fixture(scope="module")
def _bicep_results(_bicep_files: list[Path]) -> dict[str, tuple[bool, str]]:
    """Compile every Bicep file once, reuse across tests in this module."""
    if not _az_bicep_available():
        pytest.skip("Azure CLI with bicep subcommand not available")
    return {str(f.relative_to(REPO_ROOT)): _compile_bicep(f) for f in _bicep_files}


def test_all_non_allowlisted_bicep_files_compile(
    _bicep_results: dict[str, tuple[bool, str]],
) -> None:
    """Every Bicep file not in KNOWN_BROKEN_BICEP must compile cleanly."""
    new_failures: list[tuple[str, str]] = []
    for rel_path, (ok, stderr) in _bicep_results.items():
        if ok:
            continue
        if rel_path in KNOWN_BROKEN_BICEP:
            continue
        # Keep the error summary short — first real ERROR line.
        first_error = next(
            (line for line in stderr.splitlines() if "Error " in line),
            stderr.splitlines()[0] if stderr else "(no stderr captured)",
        )
        new_failures.append((rel_path, first_error))

    if new_failures:
        summary = "\n".join(f"  ✗ {path}\n      {err}" for path, err in new_failures)
        raise AssertionError(
            f"\n{len(new_failures)} Bicep file(s) failed to compile "
            f"(not on the grandfather list):\n{summary}\n\n"
            "Either fix the template, or (for justified architectural reasons) "
            "add its repo-relative path to KNOWN_BROKEN_BICEP in this test."
        )


def test_known_broken_bicep_allowlist_is_not_stale(
    _bicep_results: dict[str, tuple[bool, str]],
) -> None:
    """Ratchet invariant: allowlisted files must STILL be broken.

    The moment a listed file is fixed (or deleted), it must be removed
    from ``KNOWN_BROKEN_BICEP`` — otherwise a future regression to that
    exact file would pass silently.
    """
    stale: list[tuple[str, str]] = []
    for allowlisted in KNOWN_BROKEN_BICEP:
        result = _bicep_results.get(allowlisted)
        if result is None:
            stale.append((allowlisted, "file no longer exists in repo"))
            continue
        ok, _ = result
        if ok:
            stale.append((allowlisted, "now compiles — ratchet it out"))

    if stale:
        summary = "\n".join(f"  - {path}: {reason}" for path, reason in stale)
        raise AssertionError(
            f"\n{len(stale)} stale entries in KNOWN_BROKEN_BICEP:\n{summary}\n\n"
            "Remove them from the allowlist. Leaving stale entries lets future "
            "regressions slip through silently."
        )
