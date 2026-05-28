#!/usr/bin/env bash
# Build Tailwind v4 + DaisyUI v5 CSS for the app.
#
# Phase A of the DaisyUI migration (ct-uij): switched from the v3 standalone
# binary to the npm-installed v4 CLI so we get `@plugin "daisyui"` support
# without vendoring a 50MB binary. The output path is unchanged
# (``app/static/css/tailwind-output.css``) so base.html links keep working.
#
# Dockerfile / CI did NOT need updates: ``tailwind-output.css`` is committed
# to the repo, the runtime container just serves it as a static asset.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Auto-install npm deps on first run so dev workflow is one-shot.
if [ ! -d "node_modules" ]; then
  echo "→ node_modules missing; running npm install..."
  npm install --no-audit --no-fund --silent
fi

INPUT="app/static/css/input.css"
OUTPUT="app/static/css/tailwind-output.css"
MODE="${1:-build}"   # build | watch

case "$MODE" in
  build)
    echo "→ Building $OUTPUT (Tailwind v4 + DaisyUI v5, minified)"
    npx @tailwindcss/cli -i "$INPUT" -o "$OUTPUT" --minify
    SIZE=$(wc -c < "$OUTPUT")
    echo "✓ Wrote $OUTPUT ($SIZE bytes)"
    ;;
  watch)
    echo "→ Watching $INPUT (Ctrl+C to stop)"
    exec npx @tailwindcss/cli -i "$INPUT" -o "$OUTPUT" --watch
    ;;
  *)
    echo "Usage: $0 [build|watch]" >&2
    exit 1
    ;;
esac
