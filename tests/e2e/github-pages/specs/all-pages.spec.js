// @ts-check
const { test, expect } = require('@playwright/test');
const { allPages, hubPages, detailPages } = require('../pages');
const {
  captureScreenshot,
  checkConsoleErrors,
  verifyPageElements,
  waitForPageLoad,
  verifyPageTitle,
  COMMON_EXPECTED_ERRORS,
} = require('../utils/test-helpers');

/**
 * Cross-browser test suite for all GitHub Pages
 */

test.describe('GitHub Pages - Cross-Browser Testing', () => {
  // Hub Pages (HTML pages)
  test.describe('Hub Pages', () => {
    for (const [pageName, pageConfig] of Object.entries(hubPages)) {
      test(`${pageConfig.description} (${pageName})`, async ({ page, browserName }, testInfo) => {
        const viewport = page.viewportSize();
        
        await page.goto(pageConfig.url);
        await waitForPageLoad(page);
        
        const titleOk = await verifyPageTitle(page, pageConfig.expectedTitle);
        expect(titleOk, 'Page title should match expected pattern').toBe(true);
        
        const consoleCheck = await checkConsoleErrors(page, {
          expectedErrors: COMMON_EXPECTED_ERRORS,
        });
        expect(consoleCheck.hasErrors, `Unexpected console errors`).toBe(false);
        
        const elementCheck = await verifyPageElements(page, pageConfig.keySelectors);
        expect(elementCheck.passed, `All key elements should be present`).toBe(true);
        
        const screenshotPath = await captureScreenshot(
          page,
          `hub-${pageName}`,
          browserName,
          viewport,
          './screenshots'
        );
        testInfo.attach('screenshot', { path: screenshotPath });
      });
    }
  });

  // Detail Pages
  test.describe('Detail Pages', () => {
    for (const [pageName, pageConfig] of Object.entries(detailPages)) {
      test(`${pageConfig.description} (${pageName})`, async ({ page, browserName }, testInfo) => {
        const viewport = page.viewportSize();
        
        const response = await page.goto(pageConfig.url, {
          waitUntil: 'domcontentloaded',
        });
        
        if (response && response.status() === 404) {
          testInfo.skip(`Page ${pageConfig.url} returned 404`);
          return;
        }
        
        await waitForPageLoad(page, { networkIdle: false });
        
        const consoleCheck = await checkConsoleErrors(page, {
          expectedErrors: [...COMMON_EXPECTED_ERRORS, '404'],
        });
        
        if (consoleCheck.hasErrors) {
          console.log(`Console errors on ${pageName}: ${consoleCheck.report}`);
        }
        
        const screenshotPath = await captureScreenshot(
          page,
          `detail-${pageName}`,
          browserName,
          viewport,
          './screenshots'
        );
        testInfo.attach('screenshot', { path: screenshotPath });
      });
    }
  });

  // Smoke tests
  test.describe('Smoke Tests', () => {
    test('Homepage loads', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);
      expect(await page.title()).toBeTruthy();
      await expect(page.locator('body')).toBeVisible();
    });
  });
});
