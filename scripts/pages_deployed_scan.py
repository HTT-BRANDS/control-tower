"""Scan DEPLOYED GitHub Pages with axe-core WCAG 2.2 AA."""

import time

from playwright.sync_api import sync_playwright

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
PAGES = [
    ("index", "https://htt-brands.github.io/control-tower/"),
    (
        "continuity-status",
        "https://htt-brands.github.io/control-tower/operations/continuity-status.html",
    ),
    ("status", "https://htt-brands.github.io/control-tower/status.html"),
    ("riverside-timeline", "https://htt-brands.github.io/control-tower/riverside-timeline.html"),
]


def scan_page(page, name: str, url: str) -> dict:
    page.goto(url, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(1500)
    page.add_script_tag(url=AXE_CDN)
    page.wait_for_timeout(500)
    result = page.evaluate("""async () => {
        const results = await axe.run({
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag22aa'] },
            resultTypes: ['violations', 'incomplete'],
        });
        return {
            violations: results.violations.map(v => ({
                id: v.id, impact: v.impact, nodes: v.nodes.length
            })),
            incomplete_count: results.incomplete.length,
            passes: results.passes.length,
        };
    }""")
    return result


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        print("=" * 60)
        print("DEPLOYED GITHUB PAGES - axe-core WCAG 2.2 AA")
        print("=" * 60)

        total_v = 0
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        for name, url in PAGES:
            start = time.time()
            r = scan_page(page, name, url)
            elapsed = time.time() - start
            v_count = len(r["violations"])
            total_v += v_count
            icon = "PASS" if v_count == 0 else "FAIL"
            print(
                f"  [{icon}] {name}: {v_count} violations, "
                f"{r['incomplete_count']} incomplete, "
                f"{r['passes']} rules ({elapsed:.1f}s)"
            )
            for v in r["violations"]:
                print(f"       {v['id']} ({v['impact']}) - {v['nodes']} nodes")

        # Mobile
        mobile = browser.new_context(viewport={"width": 375, "height": 812})
        mpage = mobile.new_page()
        start = time.time()
        r = scan_page(mpage, "index-mobile", PAGES[0][1])
        elapsed = time.time() - start
        v_count = len(r["violations"])
        total_v += v_count
        icon = "PASS" if v_count == 0 else "FAIL"
        print(
            f"  [{icon}] index (mobile 375px): {v_count} violations, "
            f"{r['incomplete_count']} incomplete ({elapsed:.1f}s)"
        )
        for v in r["violations"]:
            print(f"       {v['id']} ({v['impact']}) - {v['nodes']} nodes")

        browser.close()

    print()
    print(f"TOTAL VIOLATIONS: {total_v}")
    print(f"RESULT: {'ALL PASS' if total_v == 0 else 'HAS FAILURES'}")
    return 1 if total_v > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
