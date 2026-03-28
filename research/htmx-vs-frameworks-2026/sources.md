# Source Credibility Assessment

**Research Date**: March 27, 2026

---

## Sources Used

### Tier 1 — Official Documentation / Primary Data

| Source | URL | Type | Last Verified | Credibility |
|--------|-----|------|---------------|-------------|
| htmx.org | https://htmx.org | Official documentation | 2026-03-27 | ⭐⭐⭐⭐⭐ Authoritative |
| HTMX Migration Guide | https://htmx.org/migration-guide-htmx-1/ | Official docs | 2026-03-27 | ⭐⭐⭐⭐⭐ Primary source |
| HTMX Extensions | https://htmx.org/extensions/ | Official docs | 2026-03-27 | ⭐⭐⭐⭐⭐ Primary source |
| Alpine.js | https://alpinejs.dev | Official documentation | 2026-03-27 | ⭐⭐⭐⭐⭐ Authoritative |
| GitHub Releases (all) | github.com/*/releases | Primary data | 2026-03-27 | ⭐⭐⭐⭐⭐ Authoritative |
| Bundlephobia | https://bundlephobia.com | Package analysis tool | 2026-03-27 | ⭐⭐⭐⭐ Automated data |
| npm trends | https://npmtrends.com | Download statistics | 2026-03-27 | ⭐⭐⭐⭐ Aggregated npm data |
| Qwik Blog | https://qwik.dev/blog | Official blog | 2026-03-27 | ⭐⭐⭐⭐⭐ Primary source |

### Tier 2 — Established Publications / Vendor Blogs with Data

| Source | URL | Type | Credibility | Bias Assessment |
|--------|-----|------|-------------|-----------------|
| HTMX React→HTMX Essay | htmx.org/essays/a-real-world-react-to-htmx-port/ | Case study | ⭐⭐⭐⭐ Strong data | Pro-HTMX bias but data from independent third party (Contexte/DjangoCon) |
| DjangoCon 2022 Presentation | Conference video/slides | Primary research | ⭐⭐⭐⭐⭐ | Independent conference presentation |

### Tier 3 — Community / Synthesized Knowledge

| Source | Type | Credibility | Notes |
|--------|------|-------------|-------|
| Project codebase analysis | Direct inspection | ⭐⭐⭐⭐⭐ | Primary source for project-specific context |
| Known framework characteristics | Industry consensus | ⭐⭐⭐⭐ | Bundle sizes, paradigms well-established |

---

## Version Data Cross-Validation

| Framework | GitHub Release | npm Data | Bundlephobia | Consistent? |
|-----------|---------------|----------|-------------|-------------|
| HTMX | v2.0.7 (Sep 2025) | 2.0.8 | 2.0.8 (17.6 kB) | ⚠️ Minor discrepancy — npm may have post-release patch |
| Alpine.js | v3.15.9 (Mar 26, 2026) | 3.15.9 | Error (too new) | ✅ GitHub/npm match |
| React | 19.2.4 | 19.2.4 | 1.3 kB (entry only) | ⚠️ Bundlephobia shows entry shim, not full runtime |
| Vue | v3.5.31 (Mar 24, 2026) | 3.5.31 | Not checked | ✅ GitHub/npm match |
| Nuxt | v4.4.0/v4.4.2 (Mar 13, 2026) | 4.4.2 | N/A | ✅ Consistent |
| Svelte | 5.55.0 (Mar 23, 2026) | 5.55.0 | Not checked | ✅ Consistent |
| Solid.js | v1.9.0 (Sep 24, 2024) | 1.9.12 | Not checked | ⚠️ npm has patch releases not tagged on GitHub |
| Qwik | create-qwik@1.19.2 | 1.19.2 | Not checked | ✅ Consistent |

---

## Sources NOT Used (and Why)

| Source Type | Reason Excluded |
|-------------|-----------------|
| Medium/Dev.to blog posts | Unverified, often outdated, inconsistent quality |
| Stack Overflow answers | Useful for debugging but unreliable for architectural decisions |
| YouTube tutorials | Time-consuming, often promotional, hard to verify currency |
| Framework benchmarks (js-framework-benchmark) | Synthetic benchmarks don't reflect real-world internal tool usage |
| Hacker News discussions | Opinionated, often biased toward novelty |

---

## Potential Biases in This Research

1. **Status quo bias**: The recommendation to stay with HTMX could be influenced by
   the sunk cost of the existing implementation. Mitigated by honestly evaluating
   migration costs vs. benefits.

2. **HTMX essay bias**: The Contexte case study is published on htmx.org. However,
   the underlying data comes from an independent conference presentation with
   concrete metrics.

3. **Bundle size fixation**: Bundle sizes are less relevant for an internal LAN tool.
   The analysis accounts for this by focusing on maintenance burden and migration cost
   as primary decision factors.

4. **Framework comparison scope**: This analysis doesn't cover every possible framework
   (Lit, Preact, etc.) — focused on the most relevant options for this specific use case.
