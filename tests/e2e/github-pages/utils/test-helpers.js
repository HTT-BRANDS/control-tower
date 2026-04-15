/**
 * Test utilities for GitHub Pages cross-browser testing
 * Helper functions for screenshots, console error checking, and responsive testing
 */

const fs = require('fs');
const path = require('path');

/**
 * Console error collector
 * Tracks console errors, warnings, and other messages during page navigation
 */
class ConsoleErrorCollector {
  constructor() {
    this.errors = [];
    this.warnings = [];
    this.logs = [];
  }

  /**
   * Attach to a page to collect console messages
   * @param {import('@playwright/test').Page} page - Playwright page object
   */
  attach(page) {
    page.on('console', (msg) => {
      const entry = {
        type: msg.type(),
        text: msg.text(),
        location: msg.location(),
        timestamp: new Date().toISOString(),
      };

      if (msg.type() === 'error') {
        this.errors.push(entry);
      } else if (msg.type() === 'warning') {
        this.warnings.push(entry);
      } else {
        this.logs.push(entry);
      }
    });

    // Also capture page errors (unhandled exceptions)
    page.on('pageerror', (error) => {
      this.errors.push({
        type: 'pageerror',
        text: error.message,
        stack: error.stack,
        timestamp: new Date().toISOString(),
      });
    });
  }

  /**
   * Get all collected errors
   * @returns {Array} Array of error objects
   */
  getErrors() {
    return this.errors;
  }

  /**
   * Get all collected warnings
   * @returns {Array} Array of warning objects
   */
  getWarnings() {
    return this.warnings;
  }

  /**
   * Check if there are any errors (excluding expected ones)
   * @param {Array<string>} expectedErrors - Array of error substrings to ignore
   * @returns {boolean} True if there are unexpected errors
   */
  hasUnexpectedErrors(expectedErrors = []) {
    return this.errors.some(error => 
      !expectedErrors.some(expected => error.text.includes(expected))
    );
  }

  /**
   * Get formatted error report
   * @returns {string} Formatted error report
   */
  getErrorReport() {
    const lines = [];
    
    if (this.errors.length > 0) {
      lines.push(`Errors (${this.errors.length}):`);
      this.errors.forEach((err, i) => {
        lines.push(`  ${i + 1}. [${err.type}] ${err.text.substring(0, 200)}`);
      });
    }

    if (this.warnings.length > 0) {
      lines.push(`\nWarnings (${this.warnings.length}):`);
      this.warnings.forEach((warn, i) => {
        lines.push(`  ${i + 1}. [${warn.type}] ${warn.text.substring(0, 200)}`);
      });
    }

    return lines.join('\n') || 'No console errors or warnings';
  }

  /**
   * Clear all collected messages
   */
  clear() {
    this.errors = [];
    this.warnings = [];
    this.logs = [];
  }
}

/**
 * Capture screenshot with organized naming
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} testName - Name of the test
 * @param {string} browserName - Browser name (chromium, firefox, webkit)
 * @param {Object} viewport - Viewport dimensions {width, height}
 * @param {string} screenshotsDir - Directory to save screenshots
 * @returns {Promise<string>} Path to saved screenshot
 */
async function captureScreenshot(
  page,
  testName,
  browserName,
  viewport,
  screenshotsDir = './screenshots'
) {
  // Ensure screenshots directory exists
  const dir = path.resolve(screenshotsDir);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // Create filename: testname-browser-viewport.png
  const sanitizedTestName = testName.replace(/[^a-zA-Z0-9-]/g, '_');
  const viewportLabel = `${viewport.width}x${viewport.height}`;
  const filename = `${sanitizedTestName}-${browserName}-${viewportLabel}.png`;
  const filepath = path.join(dir, filename);

  // Capture full page screenshot.
  // Webkit has a 32767px limit per dimension — fall back to viewport-only
  // screenshot to avoid crashing the test on long pages.
  try {
    await page.screenshot({
      path: filepath,
      fullPage: true,
    });
  } catch (screenshotError) {
    if (screenshotError.message.includes('32767')) {
      await page.screenshot({
        path: filepath,
        fullPage: false,
      });
    } else {
      throw screenshotError;
    }
  }

  return filepath;
}

/**
 * Check for console errors on the page
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {Object} options - Options for error checking
 * @param {boolean} options.allowWarnings - Whether to allow warnings (default: true)
 * @param {Array<string>} options.expectedErrors - Array of error substrings to ignore
 * @returns {Promise<{hasErrors: boolean, errors: Array, report: string}>}
 */
async function checkConsoleErrors(page, options = {}) {
  const { allowWarnings = true, expectedErrors = [] } = options;
  
  const collector = new ConsoleErrorCollector();
  collector.attach(page);

  // Wait a bit for any deferred errors
  await page.waitForTimeout(500);

  const hasErrors = collector.hasUnexpectedErrors(expectedErrors);
  const report = collector.getErrorReport();

  return {
    hasErrors,
    errors: collector.getErrors(),
    warnings: collector.getWarnings(),
    report,
  };
}

/**
 * Verify that key page elements exist and are visible
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {Object} selectors - Object mapping element names to CSS selectors
 * @returns {Promise<{passed: boolean, results: Object}>}
 */
async function verifyPageElements(page, selectors) {
  const results = {};
  let allPassed = true;

  for (const [name, selector] of Object.entries(selectors)) {
    try {
      const element = page.locator(selector).first();
      const isVisible = await element.isVisible({ timeout: 5000 });
      const count = await element.count();
      
      results[name] = {
        selector,
        found: count > 0,
        visible: isVisible,
        count,
        passed: count > 0 && isVisible,
      };

      if (!results[name].passed) {
        allPassed = false;
      }
    } catch (error) {
      results[name] = {
        selector,
        found: false,
        visible: false,
        count: 0,
        passed: false,
        error: error.message,
      };
      allPassed = false;
    }
  }

  return {
    passed: allPassed,
    results,
  };
}

/**
 * Run a test function at multiple viewport sizes
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {Function} testFn - Async function to run at each viewport
 * @param {Array<Object>} viewports - Array of viewport configs {width, height, name}
 * @returns {Promise<Object>} Results for each viewport
 */
async function responsiveTest(page, testFn, viewports) {
  const results = {};
  const originalViewport = page.viewportSize();

  for (const viewport of viewports) {
    // Set viewport
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });

    // Wait for layout to settle
    await page.waitForTimeout(300);

    // Run the test
    try {
      const result = await testFn(page, viewport);
      results[viewport.name] = {
        passed: true,
        result,
        viewport,
      };
    } catch (error) {
      results[viewport.name] = {
        passed: false,
        error: error.message,
        viewport,
      };
    }
  }

  // Restore original viewport
  if (originalViewport) {
    await page.setViewportSize(originalViewport);
  }

  return results;
}

/**
 * Wait for page to be fully loaded
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {Object} options - Options for wait
 * @returns {Promise<void>}
 */
async function waitForPageLoad(page, options = {}) {
  const { networkIdle = true, domContentLoaded = true } = options;

  if (domContentLoaded) {
    await page.waitForLoadState('domcontentloaded');
  }

  if (networkIdle) {
    await page.waitForLoadState('networkidle');
  }

  // Additional wait for any deferred content
  await page.waitForTimeout(500);
}

/**
 * Check page title matches expected pattern
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {RegExp|string} expectedTitle - Expected title or regex pattern
 * @returns {Promise<boolean>}
 */
async function verifyPageTitle(page, expectedTitle) {
  const title = await page.title();
  
  if (expectedTitle instanceof RegExp) {
    return expectedTitle.test(title);
  }
  
  return title.includes(expectedTitle);
}

/**
 * Common expected errors to ignore (e.g., analytics, third-party scripts)
 */
const COMMON_EXPECTED_ERRORS = [
  // Google Analytics / Tag Manager
  'googletagmanager',
  'gtm.js',
  'analytics',
  
  // Common third-party script errors
  'favicon',
  
  // GitHub Pages specific
  'github.githubassets.com',
  
  // Common browser extension errors
  'chrome-extension://',
  'moz-extension://',
];

/**
 * Test result reporter for CI/CD
 * @param {Array} results - Array of test results
 * @returns {string} Markdown formatted report
 */
function generateTestReport(results) {
  const lines = ['# Cross-Browser Test Results\n'];
  
  let passed = 0;
  let failed = 0;

  results.forEach((result) => {
    const icon = result.passed ? '✅' : '❌';
    lines.push(`${icon} **${result.testName}** (${result.browser} @ ${result.viewport})`);
    
    if (!result.passed && result.error) {
      lines.push(`   Error: ${result.error}`);
    }
    
    if (result.passed) {
      passed++;
    } else {
      failed++;
    }
  });

  lines.push('\n---\n');
  lines.push(`**Summary:** ${passed} passed, ${failed} failed`);
  lines.push(`**Total:** ${results.length} tests`);

  return lines.join('\n');
}

module.exports = {
  ConsoleErrorCollector,
  captureScreenshot,
  checkConsoleErrors,
  verifyPageElements,
  responsiveTest,
  waitForPageLoad,
  verifyPageTitle,
  COMMON_EXPECTED_ERRORS,
  generateTestReport,
};
