// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Cross-browser testing configuration for GitHub Pages site
 * Tests across Chromium, Firefox, and WebKit (Safari)
 * Includes responsive breakpoint testing
 */
module.exports = defineConfig({
  testDir: './specs',
  
  // Run tests in files in parallel
  fullyParallel: true,
  
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter to use
  reporter: [
    ['html', { outputFolder: './report', open: 'never' }],
    ['json', { outputFile: './report/results.json' }],
    ['list'],
  ],
  
  // Shared settings for all the projects below
  use: {
    // Base URL to use in actions like `await page.goto('/')`
    baseURL: process.env.GH_PAGES_URL || 'https://htt-brands.github.io/azure-governance-platform/',
    
    // Collect trace when retrying the failed test
    trace: 'on-first-retry',
    
    // Capture screenshot on failure
    screenshot: 'only-on-failure',
    
    // Record video on failure
    video: 'on-first-retry',
    
    // Console logging
    console: 'verbose',
  },

  // Configure projects for major browsers with different viewports
  projects: [
    // ========== CHROMIUM ==========
    {
      name: 'chromium-desktop',
      use: { 
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'chromium-tablet',
      use: { 
        ...devices['Desktop Chrome'],
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: 'chromium-mobile',
      use: { 
        ...devices['Pixel 5'],
        viewport: { width: 375, height: 667 },
      },
    },

    // ========== FIREFOX ==========
    {
      name: 'firefox-desktop',
      use: { 
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'firefox-tablet',
      use: { 
        ...devices['Desktop Firefox'],
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: 'firefox-mobile',
      use: { 
        ...devices['Desktop Firefox'],
        viewport: { width: 375, height: 667 },
      },
    },

    // ========== WEBKIT (SAFARI) ==========
    {
      name: 'webkit-desktop',
      use: { 
        ...devices['Desktop Safari'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'webkit-tablet',
      use: { 
        ...devices['Desktop Safari'],
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: 'webkit-mobile',
      use: { 
        ...devices['iPhone 12'],
        viewport: { width: 375, height: 667 },
      },
    },
  ],

  // Run local dev server before starting the tests (if needed)
  webServer: process.env.LOCAL_SERVER_PORT ? {
    command: `npx http-server ./docs -p ${process.env.LOCAL_SERVER_PORT}`,
    url: `http://localhost:${process.env.LOCAL_SERVER_PORT}`,
    reuseExistingServer: !process.env.CI,
  } : undefined,
});
