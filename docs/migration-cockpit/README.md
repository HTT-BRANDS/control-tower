# OIDC Migration Cockpit

Interactive walkthrough for the home-tenant OIDC federation migration
(see `ct-6fj`).

## How to use

Just open `index.html` in any browser. No build, no server, no
dependencies.

```bash
# macOS
open docs/migration-cockpit/index.html

# Linux
xdg-open docs/migration-cockpit/index.html

# Windows
start docs/migration-cockpit/index.html
```

Your configuration values + step progress are persisted to the
browser's `localStorage`, so reload is safe.

## What's inside

- **Pre-flight checklist** — your tenant ID, app reg, App Service name,
  etc. Filled in once, templated into every command and portal link.
- **7 mission steps** — each with a portal deep-link, copy-paste
  commands, and a verification check.
- **Live progress bar** — visualises how far through you are.
- **Touchdown panel** — appears when all 7 steps are marked complete.

## Companion documents

- `../runbooks/migrate-to-oidc-federation.md` — the prose runbook
  (everything here, in long form)
- `../runbooks/oidc-federation-setup.md` — cross-tenant federation
  (already done)
- `../runbooks/enable-secret-fallback.md` — rollback procedure

## Single-file design rationale

`index.html` is ~1500 lines, which is over the project's usual
600-line guideline. The single-file design is intentional:

- **Foolproof:** no build step, no `npm install`, no path issues.
  Tyler can open the file from any branch, any worktree, any time.
- **Branded:** the HTT palette is inlined as CSS variables; no chance
  of a missing asset.
- **Self-contained:** every command, link, and verification step lives
  next to the context that explains why.

Splitting it into separate CSS/JS files would actually hurt
cohesion (the JS templating is tightly coupled to the markup that
defines the step structure) and breaks the "double-click and go"
property. The Zen of Python is loud here: practicality beats purity.
