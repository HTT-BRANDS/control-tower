/**
 * Page Object Model for GitHub Pages site
 * Defines all pages, their URLs, expected titles, and key selectors
 */

const BASE_URL = process.env.GH_PAGES_URL || 'https://htt-brands.github.io/azure-governance-platform';

/**
 * Hub Pages - HTML landing pages
 */
const hubPages = {
  index: {
    url: './',
    expectedTitle: /Azure Governance Platform/,
    keySelectors: {
      heading: 'h1',
      nav: 'nav, header nav',
      footer: 'footer',
      hero: '.hero, [class*="hero"], section:first-of-type',
    },
    description: 'Homepage - Hero landing',
  },
  architecture: {
    url: 'architecture/',
    expectedTitle: /Architecture/,
    keySelectors: {
      heading: 'h1',
      nav: 'nav, header nav',
      footer: 'footer',
      content: 'main, article',
    },
    description: 'Architecture hub page',
  },
  operations: {
    url: 'operations/',
    expectedTitle: /Operations/,
    keySelectors: {
      heading: 'h1',
      nav: 'nav, header nav',
      footer: 'footer',
      content: 'main, article',
    },
    description: 'Operations hub page',
  },
  api: {
    url: 'api/',
    expectedTitle: /API/,
    keySelectors: {
      heading: 'h1',
      nav: 'nav, header nav',
      footer: 'footer',
      content: 'main, article',
    },
    description: 'API reference hub page',
  },
  decisions: {
    url: 'decisions/',
    expectedTitle: /Decisions|ADR/,
    keySelectors: {
      heading: 'h1',
      nav: 'nav, header nav',
      footer: 'footer',
      content: 'main, article',
    },
    description: 'ADR (Architecture Decision Records) hub page',
  },
};

/**
 * Detail Pages - Markdown rendered by GitHub
 */
const detailPages = {
  architectureOverview: {
    url: 'architecture/overview',
    expectedTitle: /Architecture Overview/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'Architecture overview documentation',
  },
  architectureAuthentication: {
    url: 'architecture/authentication',
    expectedTitle: /Authentication/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'Authentication documentation',
  },
  architectureDataFlow: {
    url: 'architecture/data-flow',
    expectedTitle: /Data Flow/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'Data flow documentation',
  },
  operationsRunbook: {
    url: 'operations/runbook',
    expectedTitle: /Runbook/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'Operational runbook',
  },
  operationsPlaybook: {
    url: 'operations/playbook',
    expectedTitle: /Playbook/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'Operations playbook',
  },
  operationsCostAnalysis: {
    url: 'operations/cost-analysis',
    expectedTitle: /Cost Analysis/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'Cost analysis documentation',
  },
  apiOverview: {
    url: 'api/overview',
    expectedTitle: /API Overview/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'API overview documentation',
  },
  adr0001: {
    url: 'decisions/adr-0001-multi-agent-architecture',
    expectedTitle: /ADR-0001|Multi-Agent Architecture/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0001: Multi-agent Architecture',
  },
  adr0002: {
    url: 'decisions/adr-0002-per-agent-tool-filtering',
    expectedTitle: /ADR-0002|Per-Agent Tool Filtering/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0002: Per-agent Tool Filtering',
  },
  adr0003: {
    url: 'decisions/adr-0003-local-first-issue-tracking',
    expectedTitle: /ADR-0003|Local-First Issue Tracking/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0003: Local-First Issue Tracking',
  },
  adr0004: {
    url: 'decisions/adr-0004-research-first-protocol',
    expectedTitle: /ADR-0004|Research-First Protocol/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0004: Research-First Protocol',
  },
  adr0005: {
    url: 'decisions/adr-0005-custom-compliance-rules',
    expectedTitle: /ADR-0005|Custom Compliance Rules/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0005: Custom Compliance Rules',
  },
  adr0006: {
    url: 'decisions/adr-0006-regulatory-framework-mapping',
    expectedTitle: /ADR-0006|Regulatory Framework Mapping/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0006: Regulatory Framework Mapping',
  },
  adr0007: {
    url: 'decisions/adr-0007-auth-evolution',
    expectedTitle: /ADR-0007|Auth Evolution/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0007: Auth Evolution',
  },
  adr0008: {
    url: 'decisions/adr-0008-container-registry',
    expectedTitle: /ADR-0008|Container Registry/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0008: Container Registry',
  },
  adr0009: {
    url: 'decisions/adr-0009-database-tier',
    expectedTitle: /ADR-0009|Database Tier/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0009: Database Tier',
  },
  adr0010: {
    url: 'decisions/adr-0010-sync-reliability',
    expectedTitle: /ADR-0010|Sync Reliability/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0010: Sync Reliability',
  },
  adr0011: {
    url: 'decisions/adr-0011-granular-rbac',
    expectedTitle: /ADR-0011|Granular RBAC/,
    keySelectors: {
      heading: 'h1',
      content: '#readme, article, .markdown-body',
    },
    description: 'ADR 0011: Granular RBAC',
  },
};

/**
 * All pages combined
 */
const allPages = { ...hubPages, ...detailPages };

/**
 * Viewport configurations for responsive testing
 */
const viewports = {
  mobile: {
    width: 375,
    height: 667,
    name: 'mobile',
    description: 'Mobile (iPhone SE size)',
  },
  tablet: {
    width: 768,
    height: 1024,
    name: 'tablet',
    description: 'Tablet (iPad portrait)',
  },
  desktop: {
    width: 1280,
    height: 720,
    name: 'desktop',
    description: 'Desktop (HD)',
  },
};

/**
 * Browser configurations
 */
const browsers = {
  chromium: 'chromium',
  firefox: 'firefox',
  webkit: 'webkit',
};

module.exports = {
  BASE_URL,
  hubPages,
  detailPages,
  allPages,
  viewports,
  browsers,
};
