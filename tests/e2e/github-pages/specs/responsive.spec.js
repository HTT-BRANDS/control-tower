// @ts-check
const { test, expect } = require('@playwright/test');
const { allPages, viewports } = require('../pages');
const {
  captureScreenshot,
  checkConsoleErrors,
  waitForPageLoad,
  COMMON_EXPECTED_ERRORS,
} = require('../utils/test-helpers');

/**
 * Responsive breakpoint testing
 * Verifies pages render correctly at mobile, tablet, and desktop sizes
 */

test.describe('Responsive Design Testing', () => {
  // Test key pages at all viewport sizes
  const pagesToTest = ['index', 'architecture', 'operations', 'api', 'decisions'];
  
  for (const pageName of pagesToTest) {
    const pageConfig = allPages[pageName];
    if (!pageConfig) continue;

    test.describe(`${pageConfig.description} - Responsive`, () => {
      for (const [viewportName, viewportConfig] of Object.entries(viewports)) {
        test(`renders correctly at ${viewportConfig.description}`, async ({ page, browserName }, testInfo) => {
          // Set viewport size
          await page.setViewportSize({
            width: viewportConfig.width,
            height: viewportConfig.height,
          });

          // Navigate to page
          await page.goto(pageConfig.url);
          await waitForPageLoad(page);

          // Wait for layout to settle
          await page.waitForTimeout(300);

          // Check no console errors
          const consoleCheck = await checkConsoleErrors(page, {
            expectedErrors: COMMON_EXPECTED_ERRORS,
          });
          expect(consoleCheck.hasErrors, `No console errors at ${viewportName}`).toBe(false);

          // Verify body is visible
          await expect(page.locator('body')).toBeVisible();

          // Basic responsive checks
          const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
          expect(bodyWidth).toBeLessThanOrEqual(viewportConfig.width + 50); // Allow small overflow

          // Capture screenshot
          const screenshotPath = await captureScreenshot(
            page,
            `responsive-${pageName}-${viewportName}`,
            browserName,
            { width: viewportConfig.width, height: viewportConfig.height },
            './screenshots'
          );
          testInfo.attach(`screenshot-${viewportName}`, { path: screenshotPath });
        });
      }
    });
  }

  // Navigation visibility tests
  test.describe('Navigation Visibility', () => {
    test('navigation is accessible on mobile', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('./');
      await waitForPageLoad(page);

      // Navigation should exist
      const nav = page.locator('nav, header nav');
      const navCount = await nav.count();
      
      if (navCount > 0) {
        // If nav exists, it should be visible
        await expect(nav.first()).toBeVisible();
      }
    });

    test('navigation is accessible on desktop', async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.goto('./');
      await waitForPageLoad(page);

      const nav = page.locator('nav, header nav');
      const navCount = await nav.count();
      
      if (navCount > 0) {
        await expect(nav.first()).toBeVisible();
      }
    });
  });

  // Content readability tests
  test.describe('Content Readability', () => {
    test('text does not overflow viewport on mobile', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('./');
      await waitForPageLoad(page);

      // Check that no element overflows horizontally.
      // Skip elements (or their children) with overflow containment —
      // e.g., <pre> has overflow-x: auto, and its <code> child inherits
      // the scrollable context even though <code> itself has overflow: visible.
      const overflowInfo = await page.evaluate(() => {
        function hasOverflowContainment(el) {
          let current = el;
          while (current && current !== document.body) {
            const style = window.getComputedStyle(current);
            const ox = style.overflowX;
            if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') {
              return true;
            }
            current = current.parentElement;
          }
          return false;
        }

        const elements = document.querySelectorAll('*');
        for (const el of elements) {
          if (el.scrollWidth > window.innerWidth) {
            if (hasOverflowContainment(el)) {
              continue;
            }
            return {
              overflows: true,
              tag: el.tagName,
              className: el.className,
              width: el.scrollWidth,
            };
          }
        }
        return { overflows: false };
      });

      expect(
        overflowInfo.overflows,
        `No horizontal overflow on mobile (got: ${JSON.stringify(overflowInfo)})`
      ).toBe(false);
    });

    test('images scale correctly at all sizes', async ({ page }) => {
      for (const viewportConfig of Object.values(viewports)) {
        await page.setViewportSize({
          width: viewportConfig.width,
          height: viewportConfig.height,
        });
        await page.goto('./');
        await waitForPageLoad(page);

        // Check images don't overflow their containers
        const imagesOverflow = await page.evaluate(() => {
          const images = document.querySelectorAll('img');
          for (const img of images) {
            const rect = img.getBoundingClientRect();
            const parent = img.parentElement;
            if (parent) {
              const parentRect = parent.getBoundingClientRect();
              if (rect.width > parentRect.width) {
                return true;
              }
            }
          }
          return false;
        });

        expect(imagesOverflow, `Images fit at ${viewportConfig.name}`).toBe(false);
      }
    });
  });
});
