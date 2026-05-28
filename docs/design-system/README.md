# HTT Control Tower — Design System

This directory holds the design-system source of truth for the Control Tower app.

## Contents

| File | What |
|------|------|
| `issue-66-design-system-spec-v1.pdf` | Authoritative spec from Miro (8 pages). Covers principles, foundation, layout/grid, component library, interaction patterns, accessibility, implementation, governance, plus architecture + user-persona flow diagrams. Anchored to GitHub issue #66. |
| `gap-analysis-v1.md` | Side-by-side comparison of the spec vs the current codebase. Surface follow-ups, do not implement here. |

## How this fits together

```
Miro board  ←sync→  GitHub Issue #66  ←references→  this directory  ←implements→  app/static/css/design-tokens.css
                                                                                  app/templates/components/
                                                                                  app/core/auth/ (roles)
```

The PDF is the **canonical spec**. The code in `app/` is the **implementation**.
When they disagree, the gap analysis surfaces it and a bd issue tracks the resolution.

## Updating the spec

1. Edit the Miro board
2. Re-export PDF and replace `issue-66-design-system-spec-v1.pdf` (bump filename version when material changes)
3. Re-run gap analysis and update `gap-analysis-v1.md`
4. File bd issues for any new gaps
5. Reference issue #66 in the commit message
