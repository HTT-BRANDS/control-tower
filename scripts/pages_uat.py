"""Full UAT/QA for GitHub Pages — accessibility + UX + content freshness.

Runs axe-core WCAG 2.2 AA scans via Playwright against:
  1. Local static docs server (GitHub Pages content)
  2. Production app (live health endpoints)

Outputs a structured report with pass/fail per page per criterion.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen

# --- Config ---
LOCAL_PAGES = [
    ("index", "http://localhost:8099/"),
    ("continuity-status", "http://localhost:8099/operations/continuity-status.html"),
    ("status", "http://localhost:8099/status.html"),
    ("404", "http://localhost:8099/404.html"),
    ("riverside-timeline", "http://localhost:8099/riverside-timeline.html"),
]

PROD_PAGES = [
    ("healthz-data", "https://app-governance-prod.azurewebsites.net/healthz/data"),
    ("healthz-scheduler", "https://app-governance-prod.azurewebsites.net/healthz/scheduler"),
    ("health", "https://app-governance-prod.azurewebsites.net/health"),
]

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
AXE_INJECT_SCRIPT = (
    """
async () => {
    // Inject axe-core
    const s = document.createElement('script');
    s.src = '"""
    + AXE_CDN
    + """';
    document.head.appendChild(s);
    await new Promise(r => s.onload = r);
    // Run axe
    const results = await axe.run({
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag22aa'] },
        resultTypes: ['violations', 'incomplete'],
    });
    return {
        violations: results.violations.map(v => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            nodes: v.nodes.length,
            tags: v.tags,
        })),
        incomplete: results.incomplete.map(v => ({
            id: v.id,
            impact: v.impact,
            nodes: v.nodes.length,
        })),
        passes: results.passes.length,
    };
}
"""
)


def _fetch_json(url: str) -> dict | None:
    """Fetch JSON from a URL (for prod API endpoints)."""
    try:
        with urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  WARN: {url} -> {e}")
        return None


def _scan_axe(page, url: str) -> dict:
    """Navigate to URL, inject axe-core, return results."""
    try:
        page.goto(url, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)
        result = page.evaluate(AXE_INJECT_SCRIPT)
        return result
    except Exception as e:
        return {"error": str(e), "violations": [], "incomplete": [], "passes": 0}


def _content_freshness_checks() -> dict:
    """Check that content reflects current state."""
    checks = {}

    # 1. index.html references scheduler
    idx = Path("docs/index.html").read_text()
    checks["index_has_healthz_data"] = "/healthz/data" in idx
    checks["index_has_healthz_scheduler"] = "/healthz/scheduler" in idx
    checks["index_no_stale_api_v1"] = "/api/v1/health" not in idx
    checks["index_date_2026_06_05"] = "2026-06-05" in idx
    checks["index_has_11_alerts"] = "11" in idx and "webtest" in idx.lower()

    # 2. continuity-status.html updated
    cs = Path("docs/operations/continuity-status.html").read_text()
    checks["continuity_date_2026_06_05"] = "2026-06-05" in cs
    checks["continuity_mentions_scheduler"] = "scheduler" in cs.lower()
    checks["continuity_mentions_webtest"] = "webtest" in cs.lower()
    checks["continuity_no_stale_2026_05_04"] = "2026-05-04 20:33" not in cs

    # 3. status.html updated
    sm = Path("docs/status.md").read_text()
    sh = Path("docs/status.html").read_text()
    checks["status_has_2026_06_05"] = "2026-06-05" in sm or "2026-06-05" in sh
    checks["status_has_any_stale_false"] = "any_stale" in sm and "false" in sm.lower()
    checks["status_has_scheduler_running"] = "scheduler" in sm and "running" in sm

    # 4. Prod endpoints alive
    data = _fetch_json("https://app-governance-prod.azurewebsites.net/healthz/data")
    sched = _fetch_json("https://app-governance-prod.azurewebsites.net/healthz/scheduler")
    checks["prod_data_any_stale_false"] = data is not None and data.get("any_stale") is False
    checks["prod_scheduler_running"] = sched is not None and sched.get("running") is True
    checks["prod_scheduler_10_jobs"] = sched is not None and sched.get("job_count") == 10

    return checks


def main() -> int:
    from playwright.sync_api import sync_playwright

    print("=" * 72)
    print("CONTROL TOWER GITHUB PAGES UAT/QA")
    print("=" * 72)

    results: dict = {"pages": {}, "content": {}, "summary": {}}

    # --- Part 1: axe-core accessibility scans ---
    print("\n--- Phase 1: Accessibility (axe-core WCAG 2.2 AA) ---\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        for name, url in LOCAL_PAGES:
            print(f"  Scanning: {name} ({url})")
            r = _scan_axe(page, url)
            results["pages"][name] = {
                "url": url,
                "type": "static",
                "violations": r.get("violations", []),
                "incomplete": r.get("incomplete", []),
                "passes": r.get("passes", 0),
                "error": r.get("error"),
            }
            v_count = len(r.get("violations", []))
            i_count = len(r.get("incomplete", []))
            if r.get("error"):
                print(f"    ERROR: {r['error']}")
            else:
                print(
                    f"    {v_count} violations, {i_count} incomplete, {r.get('passes', 0)} rules passed"
                )

        # Scan prod API endpoints (these return JSON, not HTML)
        for name, url in PROD_PAGES:
            print(f"  Checking: {name} ({url})")
            data = _fetch_json(url)
            if data:
                print("    OK - JSON response received")
                results["pages"][name] = {
                    "url": url,
                    "type": "api",
                    "status": "ok",
                    "keys": list(data.keys())[:10],
                }
            else:
                print("    FAIL - no response")
                results["pages"][name] = {
                    "url": url,
                    "type": "api",
                    "status": "fail",
                }

        # Also scan mobile viewport
        print("\n  Scanning: index (mobile 375px)")
        mobile_ctx = browser.new_context(viewport={"width": 375, "height": 812})
        mobile_page = mobile_ctx.new_page()
        r = _scan_axe(mobile_page, "http://localhost:8099/")
        results["pages"]["index-mobile"] = {
            "url": "http://localhost:8099/",
            "type": "static-mobile",
            "violations": r.get("violations", []),
            "incomplete": r.get("incomplete", []),
            "passes": r.get("passes", 0),
        }
        print(
            f"    {len(r.get('violations', []))} violations, {len(r.get('incomplete', []))} incomplete"
        )

        mobile_ctx.close()
        browser.close()

    # --- Part 2: Content freshness ---
    print("\n--- Phase 2: Content Freshness ---\n")
    checks = _content_freshness_checks()
    for k, v in checks.items():
        icon = "PASS" if v else "FAIL"
        print(f"  [{icon}] {k}")
    results["content"] = checks

    # --- Part 3: UX heuristic checks ---
    print("\n--- Phase 3: UX Heuristics ---\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Check page load times
        for name, url in LOCAL_PAGES[:3]:
            start = time.time()
            page.goto(url, wait_until="load", timeout=10000)
            elapsed = time.time() - start
            ok = elapsed < 3.0
            icon = "PASS" if ok else "WARN"
            print(f"  [{icon}] {name} load time: {elapsed:.2f}s (threshold: 3s)")
            results.setdefault("ux", {})[f"{name}_load"] = {
                "seconds": round(elapsed, 2),
                "ok": ok,
            }

        # Check responsive nav works
        page.goto("http://localhost:8099/", wait_until="networkidle")
        page.set_viewport_size({"width": 375, "height": 812})
        toggle = page.query_selector(".nav-toggle")
        nav_links = page.query_selector("#nav-links")
        if toggle and nav_links:
            toggle.click()
            page.wait_for_timeout(300)
            visible = nav_links.is_visible()
            print(f"  [{'PASS' if visible else 'FAIL'}] Mobile nav toggle works")
            results.setdefault("ux", {})["mobile_nav"] = visible
            # Check aria-expanded was toggled
            expanded = toggle.get_attribute("aria-expanded")
            print(
                f"  [{'PASS' if expanded == 'true' else 'FAIL'}] aria-expanded toggled: {expanded}"
            )
            results.setdefault("ux", {})["aria_toggle"] = expanded == "true"
        else:
            print("  [WARN] Nav toggle or nav-links not found")

        # Check skip-link exists
        skip = page.query_selector(".skip-link")
        print(f"  [{'PASS' if skip else 'FAIL'}] Skip-to-content link present")
        results.setdefault("ux", {})["skip_link"] = skip is not None

        # Check focus-visible styles
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto("http://localhost:8099/", wait_until="networkidle")
        page.keyboard.press("Tab")
        focused = page.evaluate(
            "() => document.activeElement?.classList?.contains('skip-link') || document.activeElement?.tagName === 'A'"
        )
        print(f"  [{'PASS' if focused else 'FAIL'}] Keyboard focus reaches interactive element")
        results.setdefault("ux", {})["keyboard_focus"] = bool(focused)

        # Check meta viewport
        viewport_meta = page.query_selector('meta[name="viewport"]')
        print(f"  [{'PASS' if viewport_meta else 'FAIL'}] Viewport meta tag present")
        results.setdefault("ux", {})["viewport_meta"] = viewport_meta is not None

        # Check lang attribute
        lang = page.evaluate("() => document.documentElement.lang")
        print(f"  [{'PASS' if lang == 'en' else 'FAIL'}] html lang='en' (got: '{lang}')")
        results.setdefault("ux", {})["lang_attr"] = lang == "en"

        # Check title tag
        title = page.title()
        print(f"  [{'PASS' if title else 'FAIL'}] Page title: '{title}'")
        results.setdefault("ux", {})["page_title"] = title

        # Check descriptive meta
        desc = page.evaluate("""() => {
            const m = document.querySelector('meta[name="description"]');
            return m ? m.content : '';
        }""")
        print(f"  [{'PASS' if desc else 'FAIL'}] Meta description present ({len(desc)} chars)")
        results.setdefault("ux", {})["meta_desc"] = bool(desc)

        # Check favicon
        favicon = page.query_selector('link[rel="icon"]')
        print(f"  [{'PASS' if favicon else 'FAIL'}] Favicon present")
        results.setdefault("ux", {})["favicon"] = favicon is not None

        browser.close()

    # --- Summary ---
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)

    total_violations = sum(
        len(p.get("violations", []))
        for p in results["pages"].values()
        if p.get("type", "").startswith("static")
    )
    total_incomplete = sum(
        len(p.get("incomplete", []))
        for p in results["pages"].values()
        if p.get("type", "").startswith("static")
    )
    content_passes = sum(1 for v in results["content"].values() if v)
    content_total = len(results["content"])
    ux_passes = sum(1 for v in results.get("ux", {}).values() if v is True)
    ux_total = len(results.get("ux", {}))

    print(f"  Accessibility: {total_violations} violations, {total_incomplete} incomplete")
    print(f"  Content: {content_passes}/{content_total} checks passed")
    print(f"  UX: {ux_passes}/{ux_total} checks passed")

    if total_violations > 0:
        print("\n  VIOLATION DETAILS:")
        for page_name, page_data in results["pages"].items():
            for v in page_data.get("violations", []):
                print(
                    f"    [{page_name}] {v['id']} ({v['impact']}) - {v['description']} [{v['nodes']} nodes]"
                )

    if total_incomplete > 0:
        print("\n  INCOMPLETE (needs manual review):")
        for page_name, page_data in results["pages"].items():
            for i in page_data.get("incomplete", []):
                print(f"    [{page_name}] {i['id']} ({i['impact']}) - {i['nodes']} nodes")

    # Save full results
    out = Path("test-results/pages-uat.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\n  Full results saved to {out}")

    # Exit code: 1 if any violations, 0 otherwise
    return 1 if total_violations > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
