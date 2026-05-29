#!/usr/bin/env python3
"""Safe-rename migrator from raw Tailwind utilities to DaisyUI semantic tokens.

Phase B of the ct-uij DaisyUI 5.x migration. This script applies the *safe*
1:1 class-name rewrites that don't require structural changes to templates.
Complex component swaps (custom badges → ``badge badge-error``, hand-rolled
cards → ``card`` component) are intentionally NOT automated — those need a
human eye to preserve layout intent.

WHAT THIS RENAMES (theme-aware DaisyUI semantic equivalents):

    Background → surface:
        bg-white            →  bg-base-100
        bg-gray-50          →  bg-base-200
        bg-gray-100         →  bg-base-300

    Text → semantic content:
        text-gray-900       →  text-base-content
        text-gray-800       →  text-base-content/90
        text-gray-700       →  text-base-content/80
        text-gray-600       →  text-base-content/70
        text-gray-500       →  text-base-content/60
        text-gray-400       →  text-base-content/50

    Borders → semantic surface borders:
        border-gray-100     →  border-base-300
        border-gray-200     →  border-base-300
        border-gray-300     →  border-base-300

    Brand → DaisyUI primary token:
        text-brand-primary  →  text-primary
        bg-brand-primary    →  bg-primary
        border-brand-primary→  border-primary
        text-htt-primary    →  text-primary

WHAT IT DOES NOT TOUCH:
- Custom badge patterns (``bg-red-100 text-red-800`` etc.) — needs ``badge``
  component swap with the right variant; ambiguous from class alone.
- Custom card layouts — ``rounded-lg border bg-white`` could mean different
  things in different contexts; safer to migrate by hand to ``card``.
- Brand-specific ramp utilities (``bg-brand-primary-110`` etc.) — kept by
  the ``@utility`` shims in input.css.

USAGE::

    # Dry-run: show what would change in every template
    uv run python scripts/migrate_to_daisyui.py --dry-run

    # Apply to all templates (writes in place)
    uv run python scripts/migrate_to_daisyui.py

    # Apply to a single file
    uv run python scripts/migrate_to_daisyui.py --only app/templates/pages/dashboard.html

After running, rebuild CSS (``bash scripts/build-css.sh``) and run the test
suite to confirm no regressions.

Refs: ct-uij Phase B.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

TEMPLATE_ROOT = Path("app/templates")

# Order matters — apply more-specific patterns BEFORE more-general ones (e.g.
# 'text-brand-primary' before any generic '-primary' rules).
# Each tuple is (regex-pattern, replacement). \b boundaries keep us from
# mangling sub-strings like 'bg-white-glow' or attribute values that happen
# to contain a class-name fragment.
RENAMES: list[tuple[re.Pattern[str], str]] = [
    # Brand → DaisyUI primary (covered by @utility shims too, but this makes
    # the templates self-documenting once Phase B lands).
    (re.compile(r"\btext-brand-primary\b(?![-/])"), "text-primary"),
    (re.compile(r"\bbg-brand-primary\b(?![-/])"), "bg-primary"),
    (re.compile(r"\bborder-brand-primary\b(?![-/])"), "border-primary"),
    (re.compile(r"\btext-htt-primary\b(?![-/])"), "text-primary"),
    (re.compile(r"\bbg-htt-primary\b(?![-/])"), "bg-primary"),
    # Surface backgrounds
    (re.compile(r"\bbg-white\b(?!/)"), "bg-base-100"),
    (re.compile(r"\bbg-gray-50\b"), "bg-base-200"),
    (re.compile(r"\bbg-gray-100\b"), "bg-base-300"),
    # Borders — DaisyUI base-300 is the canonical subtle divider
    (re.compile(r"\bborder-gray-100\b"), "border-base-300"),
    (re.compile(r"\bborder-gray-200\b"), "border-base-300"),
    (re.compile(r"\bborder-gray-300\b"), "border-base-300"),
    # Text colours — most-specific first (text-gray-900 → text-base-content
    # has no slash, deeper shades get an alpha modifier so colour-contrast is
    # preserved across light/dark themes automatically).
    (re.compile(r"\btext-gray-900\b"), "text-base-content"),
    (re.compile(r"\btext-gray-800\b"), "text-base-content/90"),
    (re.compile(r"\btext-gray-700\b"), "text-base-content/80"),
    (re.compile(r"\btext-gray-600\b"), "text-base-content/70"),
    (re.compile(r"\btext-gray-500\b"), "text-base-content/60"),
    (re.compile(r"\btext-gray-400\b"), "text-base-content/50"),
]


def _migrate_text(text: str) -> tuple[str, Counter[str]]:
    """Apply the rename patterns to a single string. Returns (new_text, counts)."""
    counts: Counter[str] = Counter()
    for pattern, replacement in RENAMES:
        new_text, n = pattern.subn(replacement, text)
        if n:
            counts[f"{pattern.pattern} → {replacement}"] = n
            text = new_text
    return text, counts


def migrate_file(path: Path, *, dry_run: bool) -> Counter[str]:
    """Migrate one template file in place (or report on --dry-run)."""
    original = path.read_text()
    migrated, counts = _migrate_text(original)
    if counts and not dry_run:
        path.write_text(migrated)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned changes per file without writing.",
    )
    parser.add_argument(
        "--only",
        metavar="PATH",
        help="Migrate a single template (instead of the full tree).",
    )
    args = parser.parse_args()

    if args.only:
        paths = [Path(args.only)]
        if not paths[0].exists():
            print(f"✗ {paths[0]} does not exist", file=sys.stderr)
            return 1
    else:
        paths = sorted(TEMPLATE_ROOT.rglob("*.html"))

    total_changes = Counter()
    files_touched = 0

    for path in paths:
        counts = migrate_file(path, dry_run=args.dry_run)
        if not counts:
            continue
        files_touched += 1
        total_changes.update(counts)
        n_total = sum(counts.values())
        verb = "would rewrite" if args.dry_run else "rewrote"
        print(f"  {verb:<14} {n_total:>4}  {path}")

    print()
    print(
        f"── Summary: {files_touched} files {'would be ' if args.dry_run else ''}touched, "
        f"{sum(total_changes.values())} total class renames"
    )
    if total_changes:
        print("\n── Per-rule breakdown ──")
        for rule, n in total_changes.most_common():
            print(f"  {n:>5}  {rule}")

    if args.dry_run:
        print("\n(dry-run — no files were written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
