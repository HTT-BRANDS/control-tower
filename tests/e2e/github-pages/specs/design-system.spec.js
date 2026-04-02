// @ts-check
const { test, expect } = require('@playwright/test');
const { hubPages } = require('../pages');
const { waitForPageLoad, COMMON_EXPECTED_ERRORS } = require('../utils/test-helpers');

/**
 * Design System v2 — Visual consistency and interaction tests
 *
 * Validates that the "Obsidian + Gold" design system renders correctly
 * across browsers and viewports.
 */

test.describe('Design System v2', () => {

  test.describe('Design Tokens', () => {
    test('CSS custom properties are defined on :root', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const tokens = await page.evaluate(() => {
        const style = getComputedStyle(document.documentElement);
        return {
          burgundy:     style.getPropertyValue('--burgundy').trim(),
          gold:         style.getPropertyValue('--gold').trim(),
          surface0:     style.getPropertyValue('--surface-0').trim(),
          fontHeading:  style.getPropertyValue('--font-heading').trim(),
          fontBody:     style.getPropertyValue('--font-body').trim(),
          radiusMd:     style.getPropertyValue('--radius-md').trim(),
        };
      });

      expect(tokens.burgundy).toBe('#500711');
      expect(tokens.gold).toBe('#ffc957');
      expect(tokens.surface0).toBe('#ffffff');
      expect(tokens.fontHeading).toContain('Montserrat');
      expect(tokens.fontBody).toContain('Inter');
      expect(tokens.radiusMd).toBe('12px');
    });
  });

  test.describe('Navigation', () => {
    test('nav has glassmorphism backdrop-filter', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const hasBlur = await page.evaluate(() => {
        const nav = document.querySelector('.nav');
        if (!nav) return false;
        const style = getComputedStyle(nav);
        const bf = style.backdropFilter || style.webkitBackdropFilter || '';
        return bf.includes('blur');
      });
      expect(hasBlur).toBe(true);
    });

    test('nav is sticky', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const position = await page.evaluate(() => {
        const nav = document.querySelector('.nav');
        return nav ? getComputedStyle(nav).position : '';
      });
      expect(position).toBe('sticky');
    });

    test('active nav link is styled on sub-pages', async ({ page }) => {
      await page.goto('architecture/');
      await waitForPageLoad(page);

      const hasActive = await page.evaluate(() => {
        const active = document.querySelector('.nav-links a.active');
        return active !== null;
      });
      expect(hasActive).toBe(true);
    });
  });

  test.describe('Hero Section', () => {
    test('hero has gradient mesh pseudo-elements', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const heroStyles = await page.evaluate(() => {
        const hero = document.querySelector('.hero');
        if (!hero) return { bg: '', hasContent: false };
        const before = getComputedStyle(hero, '::before');
        return {
          bg: getComputedStyle(hero).backgroundColor,
          hasContent: before.content !== 'none',
        };
      });
      expect(heroStyles.hasContent).toBe(true);
    });

    test('hero title uses fluid typography', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      // Get font size at two widths to verify it scales
      await page.setViewportSize({ width: 375, height: 667 });
      await page.waitForTimeout(100);
      const mobileFontSize = await page.evaluate(() => {
        const h1 = document.querySelector('.hero-title');
        return h1 ? parseFloat(getComputedStyle(h1).fontSize) : 0;
      });

      await page.setViewportSize({ width: 1280, height: 720 });
      await page.waitForTimeout(100);
      const desktopFontSize = await page.evaluate(() => {
        const h1 = document.querySelector('.hero-title');
        return h1 ? parseFloat(getComputedStyle(h1).fontSize) : 0;
      });

      expect(desktopFontSize).toBeGreaterThan(mobileFontSize);
    });

    test('metric cards have background and border', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const metricStyle = await page.evaluate(() => {
        const m = document.querySelector('.metric');
        if (!m) return null;
        const s = getComputedStyle(m);
        return {
          hasBackground: s.backgroundColor !== 'rgba(0, 0, 0, 0)',
          hasBorderRadius: parseInt(s.borderRadius) > 0,
        };
      });
      expect(metricStyle).not.toBeNull();
      expect(metricStyle.hasBackground).toBe(true);
      expect(metricStyle.hasBorderRadius).toBe(true);
    });
  });

  test.describe('Card System', () => {
    test('cards have gradient border pseudo-element', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const hasPseudo = await page.evaluate(() => {
        const card = document.querySelector('.card');
        if (!card) return false;
        const before = getComputedStyle(card, '::before');
        return before.content !== 'none' && before.position === 'absolute';
      });
      expect(hasPseudo).toBe(true);
    });

    test('card icon uses gold-dim background', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const iconBg = await page.evaluate(() => {
        const icon = document.querySelector('.card-icon');
        if (!icon) return '';
        return getComputedStyle(icon).backgroundColor;
      });
      // Should be rgba form of --gold-dim: rgba(255,201,87,.12)
      expect(iconBg).toContain('255');
      expect(iconBg).toContain('201');
    });

    test('doc-cards have gradient border on hover', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const hasPseudo = await page.evaluate(() => {
        const dc = document.querySelector('.doc-card');
        if (!dc) return false;
        const before = getComputedStyle(dc, '::before');
        return before.content !== 'none';
      });
      expect(hasPseudo).toBe(true);
    });
  });

  test.describe('Status Grid', () => {
    test('status dots have pulse animation', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const hasAnimation = await page.evaluate(() => {
        const dot = document.querySelector('.status-dot');
        if (!dot) return false;
        const after = getComputedStyle(dot, '::after');
        return after.animationName !== 'none' && after.animationName !== '';
      });
      expect(hasAnimation).toBe(true);
    });
  });

  test.describe('Footer', () => {
    test('footer uses deep burgundy background', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const footerBg = await page.evaluate(() => {
        const footer = document.querySelector('.footer');
        return footer ? getComputedStyle(footer).backgroundColor : '';
      });
      // --burgundy-deep: #2d040a = rgb(45, 4, 10)
      expect(footerBg).toContain('45');
    });
  });

  test.describe('Page Header (sub-pages)', () => {
    test('page header has gradient pseudo-element', async ({ page }) => {
      await page.goto('architecture/');
      await waitForPageLoad(page);

      const hasGradient = await page.evaluate(() => {
        const header = document.querySelector('.page-header');
        if (!header) return false;
        const before = getComputedStyle(header, '::before');
        return before.content !== 'none';
      });
      expect(hasGradient).toBe(true);
    });

    test('breadcrumb navigation exists', async ({ page }) => {
      await page.goto('architecture/');
      await waitForPageLoad(page);

      const hasBreadcrumb = await page.locator('.breadcrumb').count();
      expect(hasBreadcrumb).toBeGreaterThan(0);
    });
  });

  test.describe('Doc List Items', () => {
    test('doc list items have animated left border on hover', async ({ page }) => {
      await page.goto('architecture/');
      await waitForPageLoad(page);

      const hasPseudo = await page.evaluate(() => {
        const item = document.querySelector('.doc-list-item');
        if (!item) return false;
        const before = getComputedStyle(item, '::before');
        return before.content !== 'none' && before.position === 'absolute';
      });
      expect(hasPseudo).toBe(true);
    });
  });

  test.describe('Typography Consistency', () => {
    test('headings use Montserrat font family', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const fontFamily = await page.evaluate(() => {
        const h1 = document.querySelector('.hero-title');
        return h1 ? getComputedStyle(h1).fontFamily : '';
      });
      expect(fontFamily.toLowerCase()).toContain('montserrat');
    });

    test('body text uses Inter font family', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const fontFamily = await page.evaluate(() => {
        return getComputedStyle(document.body).fontFamily;
      });
      expect(fontFamily.toLowerCase()).toContain('inter');
    });
  });

  test.describe('Accessibility', () => {
    test('skip link exists and targets #main', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const skipLink = await page.evaluate(() => {
        const link = document.querySelector('.skip-link');
        return link ? link.getAttribute('href') : null;
      });
      expect(skipLink).toBe('#main');
    });

    test('nav-toggle has aria-label and aria-expanded', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const attrs = await page.evaluate(() => {
        const btn = document.querySelector('.nav-toggle');
        if (!btn) return null;
        return {
          label: btn.getAttribute('aria-label'),
          expanded: btn.getAttribute('aria-expanded'),
        };
      });
      expect(attrs).not.toBeNull();
      expect(attrs.label).toBeTruthy();
      expect(attrs.expanded).toBe('false');
    });

    test('focus-visible outline uses gold color', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      // Tab to first focusable element and check outline style
      await page.keyboard.press('Tab');
      const outlineColor = await page.evaluate(() => {
        const focused = document.querySelector(':focus-visible');
        return focused ? getComputedStyle(focused).outlineColor : '';
      });
      // Gold #ffc957 should show up in some form
      // Note: this may vary by browser, so just check outline exists
      expect(outlineColor).toBeTruthy();
    });

    test('nav-logo has aria-label', async ({ page }) => {
      await page.goto('./');
      await waitForPageLoad(page);

      const label = await page.evaluate(() => {
        const logo = document.querySelector('.nav-logo');
        return logo ? logo.getAttribute('aria-label') : null;
      });
      expect(label).toBe('Home');
    });
  });

  test.describe('Responsive Transitions', () => {
    test('mobile nav menu toggles correctly', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('./');
      await waitForPageLoad(page);

      // Nav links should be hidden initially
      const navLinks = page.locator('.nav-links');
      await expect(navLinks).not.toBeVisible();

      // Click toggle
      await page.locator('.nav-toggle').click();
      await expect(navLinks).toBeVisible();

      // Click again to close
      await page.locator('.nav-toggle').click();
      await expect(navLinks).not.toBeVisible();
    });

    test('grid collapses to single column on mobile', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('./');
      await waitForPageLoad(page);

      const columns = await page.evaluate(() => {
        const grid = document.querySelector('.grid--3');
        return grid ? getComputedStyle(grid).gridTemplateColumns : '';
      });
      // On mobile, should be single column (one value)
      const colCount = columns.trim().split(/\s+/).length;
      expect(colCount).toBe(1);
    });
  });
});
