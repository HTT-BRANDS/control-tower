#!/usr/bin/env python3
"""Capture visual-parity baselines for the 5 migrated dashboard pages (py7u.4).

Spins up the app, authenticates a Playwright browser, and saves a full-page
PNG screenshot per page into ``tests/e2e/baselines/``. These images become
the pinned baselines for ``tests/e2e/test_visual_parity.py``.

USAGE::

    uv run python scripts/capture_visual_baselines.py
    uv run python scripts/capture_visual_baselines.py --only dashboard costs
    uv run python scripts/capture_visual_baselines.py --base-url https://staging.example.com

When --base-url is omitted, the script spins up the local app on port 8099
(same convention as tests/e2e/conftest.py).

⚠️ CAUTION: overwrites existing baselines. Commit before running if you
want to review the diff.
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
import time
from pathlib import Path

import httpx

# Match the test's page list exactly — single source of truth is the test
# file (avoid DRY drift between capturing and validating).
sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "e2e"))
from test_visual_parity import PAGES

BASELINE_DIR = Path(__file__).parent.parent / "tests" / "e2e" / "baselines"
LOCAL_URL = "http://127.0.0.1:8099"


def _run_local_server() -> None:
    """Run uvicorn on the e2e port (same as conftest.py)."""
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8099, log_level="warning")


def _wait_for_server(url: str, timeout_s: int = 15) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/api/v1/health", timeout=2)
            if r.status_code == 200:
                return
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.5)
    msg = f"Server at {url} did not respond to /api/v1/health within {timeout_s}s"
    raise RuntimeError(msg)


def _get_access_token(url: str) -> str:
    resp = httpx.post(
        f"{url}/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},  # pragma: allowlist secret
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    for cookie in resp.cookies.jar:
        if cookie.name == "access_token":
            return cookie.value
    msg = "access_token cookie not set by /api/v1/auth/login"
    raise RuntimeError(msg)


def capture(base_url: str, only: list[str] | None) -> None:
    """Drive Playwright through each page and write PNG baselines."""
    from playwright.sync_api import sync_playwright

    pages = [p for p in PAGES if (not only or p[0] in only)]
    if not pages:
        print(f"No pages match --only {only}; available: {[p[0] for p in PAGES]}")
        sys.exit(1)

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    access_token = _get_access_token(base_url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            base_url=base_url,
            extra_http_headers={"Authorization": f"Bearer {access_token}"},
        )
        page = context.new_page()

        for name, path, wait_sel in pages:
            print(f"  → capturing {name:<12} ({path}) ...", end=" ", flush=True)
            page.goto(path)
            page.wait_for_selector(wait_sel, timeout=10_000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)  # let CSS transitions settle
            out = BASELINE_DIR / f"{name}.png"
            page.screenshot(path=str(out), full_page=True)
            size_kb = out.stat().st_size // 1024
            print(f"✓ {out.relative_to(Path.cwd())} ({size_kb} KB)")

        context.close()
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-url",
        default=None,
        help="URL of a running app. If omitted, spins up the local app on port 8099.",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="PAGE",
        help=f"Capture only these pages (from {[p[0] for p in PAGES]}).",
    )
    args = parser.parse_args()

    if args.base_url:
        base_url = args.base_url.rstrip("/")
        _wait_for_server(base_url)
        capture(base_url, args.only)
        return

    # Local-server mode: fork uvicorn, capture, clean up.
    proc = multiprocessing.Process(target=_run_local_server, daemon=True)
    proc.start()
    try:
        _wait_for_server(LOCAL_URL)
        capture(LOCAL_URL, args.only)
    finally:
        proc.kill()
        proc.join(timeout=5)


if __name__ == "__main__":
    main()
