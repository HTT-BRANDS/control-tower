#!/usr/bin/env node
/**
 * Build Detail Pages — Generates HTML pages from Markdown docs
 *
 * Reads .md files from docs sub-directories and wraps them in the
 * site's design system (nav, footer, responsive layout, Lucide icons).
 *
 * Usage: node scripts/build-detail-pages.js
 */

const fs = require('fs');
const path = require('path');
const { marked } = require('marked');

const DOCS_DIR = path.join(__dirname, '..', 'docs');

// ─── Page Manifest ───────────────────────────────────────────────────
// Each entry maps a URL slug to its source .md file and metadata.
// The build script creates {section}/{slug}/index.html for each entry.
const PAGES = [
  // Architecture
  { section: 'architecture', slug: 'overview', md: 'overview.md', title: 'System Overview' },
  { section: 'architecture', slug: 'authentication', md: 'authentication.md', title: 'Authentication & Authorization' },
  { section: 'architecture', slug: 'data-flow', md: 'data-flow.md', title: 'Data Flow & Connections' },

  // Operations
  { section: 'operations', slug: 'runbook', md: 'runbook.md', title: 'Operations Runbook' },
  { section: 'operations', slug: 'playbook', md: 'playbook.md', title: 'Operations Playbook' },
  { section: 'operations', slug: 'cost-analysis', md: 'cost-analysis.md', title: 'Cost Analysis & Scaling' },

  // API
  { section: 'api', slug: 'overview', md: 'overview.md', title: 'API Reference' },

  // Decisions (ADRs)
  { section: 'decisions', slug: 'adr-0001-multi-agent-architecture', md: 'adr-0001-multi-agent-architecture.md', title: 'ADR-0001: Multi-Agent Architecture' },
  { section: 'decisions', slug: 'adr-0002-per-agent-tool-filtering', md: 'adr-0002-per-agent-tool-filtering.md', title: 'ADR-0002: Per-Agent Tool Filtering' },
  { section: 'decisions', slug: 'adr-0003-local-first-issue-tracking', md: 'adr-0003-local-first-issue-tracking.md', title: 'ADR-0003: Local-First Issue Tracking' },
  { section: 'decisions', slug: 'adr-0004-research-first-protocol', md: 'adr-0004-research-first-protocol.md', title: 'ADR-0004: Research-First Protocol' },
  { section: 'decisions', slug: 'adr-0005-custom-compliance-rules', md: 'adr-0005-custom-compliance-rules.md', title: 'ADR-0005: Custom Compliance Rules' },
  { section: 'decisions', slug: 'adr-0006-regulatory-framework-mapping', md: 'adr-0006-regulatory-framework-mapping.md', title: 'ADR-0006: Regulatory Framework Mapping' },
  { section: 'decisions', slug: 'adr-0007-auth-evolution', md: 'adr-0007-auth-evolution.md', title: 'ADR-0007: Auth Evolution' },
  { section: 'decisions', slug: 'adr-0008-container-registry', md: 'adr-0008-container-registry.md', title: 'ADR-0008: Container Registry' },
  { section: 'decisions', slug: 'adr-0009-database-tier', md: 'adr-0009-database-tier.md', title: 'ADR-0009: Database Tier' },
];

const SECTION_LABELS = {
  architecture: 'Architecture',
  operations: 'Operations',
  api: 'API Reference',
  decisions: 'Decisions',
};

// ─── HTML Template ───────────────────────────────────────────────────
function buildPage({ title, section, sectionLabel, breadcrumbSlug, htmlContent }) {
  const activeNav = (s) =>
    s === section ? ' class="active"' : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)} — Azure Governance Platform</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%23500711'/><text x='16' y='22' font-family='sans-serif' font-size='16' font-weight='bold' fill='%23ffc957' text-anchor='middle'>HT</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Montserrat:wght@600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../../assets/main.css">
  <link rel="stylesheet" href="../../assets/icons.css">
</head>
<body>
  <a href="#main" class="skip-link">Skip to content</a>

  <nav class="nav" role="navigation" aria-label="Main">
    <div class="nav-inner">
      <a href="../../" class="nav-logo" aria-label="Home">HT</a>
      <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
      <div class="nav-links">
        <a href="../../architecture/"${activeNav('architecture')}>Architecture</a>
        <a href="../../operations/"${activeNav('operations')}>Operations</a>
        <a href="../../api/"${activeNav('api')}>API</a>
        <a href="../../decisions/"${activeNav('decisions')}>Decisions</a>
        <a href="https://github.com/HTT-BRANDS/azure-governance-platform" target="_blank" rel="noopener">GitHub ↗</a>
      </div>
    </div>
  </nav>

  <div class="page-header">
    <div class="page-header-inner">
      <div class="breadcrumb">
        <a href="../../">Home</a><span>›</span>
        <a href="../">${escapeHtml(sectionLabel)}</a><span>›</span>
        ${escapeHtml(breadcrumbSlug)}
      </div>
      <h1 class="page-title">${escapeHtml(title)}</h1>
    </div>
  </div>

  <main id="main">
    <section class="section">
      <div class="prose" style="max-width:800px;margin:0 auto">
${htmlContent}
      </div>
    </section>
  </main>

  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-logo">HT</div>
      <div class="footer-links">
        <a href="../../architecture/">Architecture</a>
        <a href="../../operations/">Operations</a>
        <a href="../../api/">API</a>
        <a href="../../decisions/">Decisions</a>
        <a href="https://github.com/HTT-BRANDS/azure-governance-platform" target="_blank" rel="noopener">GitHub</a>
      </div>
    </div>
    <div class="footer-bottom">
      <p>Production Certified · Rock Solid · v1.9.0</p>
    </div>
  </footer>

  <script>
  (function() {
    var toggle = document.querySelector('.nav-toggle');
    var navLinks = document.querySelector('.nav-links');
    if (toggle && navLinks) {
      toggle.addEventListener('click', function() {
        navLinks.classList.toggle('open');
        this.setAttribute('aria-expanded', navLinks.classList.contains('open'));
      });
    }
  })();
  </script>
</body>
</html>
`;
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ─── Configure Marked ────────────────────────────────────────────────
marked.setOptions({
  gfm: true,
  breaks: false,
});

// ─── Build ───────────────────────────────────────────────────────────
function build() {
  let built = 0;
  let errors = 0;

  for (const page of PAGES) {
    const mdPath = path.join(DOCS_DIR, page.section, page.md);

    if (!fs.existsSync(mdPath)) {
      console.error(`❌ Missing: ${mdPath}`);
      errors++;
      continue;
    }

    const mdContent = fs.readFileSync(mdPath, 'utf-8');

    // Strip the first H1 heading (we render our own in page-header)
    const mdWithoutH1 = mdContent.replace(/^#\s+.*$/m, '').trim();
    const htmlContent = marked.parse(mdWithoutH1);

    const outDir = path.join(DOCS_DIR, page.section, page.slug);
    fs.mkdirSync(outDir, { recursive: true });

    const outPath = path.join(outDir, 'index.html');
    const html = buildPage({
      title: page.title,
      section: page.section,
      sectionLabel: SECTION_LABELS[page.section] || page.section,
      breadcrumbSlug: page.title,
      htmlContent,
    });

    fs.writeFileSync(outPath, html, 'utf-8');
    built++;
    console.log(`✅ ${page.section}/${page.slug}/index.html`);
  }

  console.log(`\nDone: ${built} built, ${errors} errors`);
  return errors === 0 ? 0 : 1;
}

process.exit(build());
