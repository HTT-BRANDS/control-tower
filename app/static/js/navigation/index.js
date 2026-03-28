/**
 * HTMX Navigation Enhancement Module - Main Entry Point
 * 
 * Orchestrates all navigation modules:
 * - Progress Bar: Shows loading progress during HTMX requests
 * - Toast: Notifications for errors and confirmations
 * - NavHighlight: Active navigation item highlighting
 * - ConfirmDialog: Custom confirmation dialogs
 * 
 * Also handles HTMX events and accessibility features.
 * 
 * @module navigation
 * @version 1.0.0
 */

(function() {
    'use strict';

    // State management
    const state = {
        requestCount: 0,
        isNavigating: false
    };

    // Module references (will be loaded from separate files)
    let ProgressBar, Toast, NavHighlight, ConfirmDialog;

    /**
     * Load module references from global scope
     */
    function loadModules() {
        ProgressBar = window.NavigationProgressBar;
        Toast = window.NavigationToast;
        NavHighlight = window.NavigationHighlight;
        ConfirmDialog = window.NavigationConfirmDialog;
    }

    /**
     * Initialize HTMX event listeners
     */
    function initHtmxEvents() {
        if (typeof htmx === 'undefined') {
            console.warn('HTMX not loaded - navigation enhancements disabled');
            return;
        }

        // Before request starts
        document.body.addEventListener('htmx:beforeRequest', (event) => {
            state.requestCount++;
            
            if (state.requestCount === 1) {
                ProgressBar.start();
            }
            
            const el = event.detail.elt;
            el.classList.add('htmx-requesting');
        });

        // After request completes
        document.body.addEventListener('htmx:afterRequest', (event) => {
            state.requestCount = Math.max(0, state.requestCount - 1);
            
            if (state.requestCount === 0) {
                ProgressBar.finish();
            }
            
            const el = event.detail.elt;
            el.classList.remove('htmx-requesting');
            
            if (event.detail.successful && event.detail.xhr) {
                const url = event.detail.xhr.responseURL || window.location.href;
                const path = new URL(url).pathname;
                NavHighlight.update(path);
            }
        });

        // Request error
        document.body.addEventListener('htmx:responseError', (event) => {
            state.requestCount = Math.max(0, state.requestCount - 1);
            ProgressBar.error();
            
            const xhr = event.detail.xhr;
            let message = 'An error occurred while processing your request.';
            
            if (xhr.status === 404) {
                message = 'The requested resource was not found.';
            } else if (xhr.status === 403) {
                message = 'You do not have permission to perform this action.';
            } else if (xhr.status === 500) {
                message = 'A server error occurred. Please try again later.';
            } else if (xhr.status === 0) {
                message = 'Network error. Please check your connection.';
            }
            
            Toast.error(message);
            
            const el = event.detail.elt;
            el.classList.remove('htmx-requesting');
        });

        // Network error
        document.body.addEventListener('htmx:sendError', (event) => {
            state.requestCount = Math.max(0, state.requestCount - 1);
            ProgressBar.error();
            Toast.error('Network error. Please check your connection and try again.');
            
            const el = event.detail.elt;
            el.classList.remove('htmx-requesting');
        });

        // Timeout
        document.body.addEventListener('htmx:timeout', (event) => {
            state.requestCount = Math.max(0, state.requestCount - 1);
            ProgressBar.error();
            Toast.error('Request timed out. Please try again.');
            
            const el = event.detail.elt;
            el.classList.remove('htmx-requesting');
        });

        // Confirm prompt
        document.body.addEventListener('htmx:confirm', (event) => {
            if (event.detail.elt.hasAttribute('hx-confirm')) {
                event.preventDefault();
                
                const message = event.detail.elt.getAttribute('hx-confirm');
                ConfirmDialog.show(
                    message,
                    () => event.detail.issueRequest(true),
                    () => {
                        const el = event.detail.elt;
                        el.classList.remove('htmx-requesting');
                    }
                );
            }
        });

        // After swap - with focus management
        document.body.addEventListener('htmx:afterSwap', (event) => {
            // Update page title
            if (event.detail.target) {
                const title = event.detail.target.querySelector('title');
                if (title) {
                    document.title = title.textContent;
                }
            }
            
            // Focus management - set focus to main content after swap
            if (event.detail.target.closest('main')) {
                const main = document.querySelector('main');
                if (main) {
                    main.setAttribute('tabindex', '-1');
                    main.focus({ preventScroll: true });
                }
            }
        });

        // Before swap - scroll to top for page navigations
        document.body.addEventListener('htmx:beforeSwap', (event) => {
            if (event.detail.target === document.body || 
                event.detail.target.closest('main') === document.querySelector('main')) {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    }

    /**
     * Initialize accessibility features
     */
    function initAccessibility() {
        // Announce page changes to screen readers (avoid duplicates)
        let announcer = document.getElementById('page-announcer');
        if (!announcer) {
            announcer = document.createElement('div');
            announcer.id = 'page-announcer';
            announcer.setAttribute('aria-live', 'polite');
            announcer.setAttribute('aria-atomic', 'true');
            announcer.className = 'sr-only';
            document.body.appendChild(announcer);
        }

        // Announce navigation
        document.body.addEventListener('htmx:afterSwap', (event) => {
            if (event.detail.target === document.querySelector('main')) {
                const title = document.title || 'Page updated';
                announcer.textContent = `Navigated to ${title}`;
            }
        });
    }

    /**
     * No-JS fallback handling
     */
    function initNoJsFallback() {
        document.documentElement.classList.remove('no-js');
        
        document.querySelectorAll('[hx-boost="true"] a[href]').forEach(link => {
            if (!link.getAttribute('href')) {
                console.warn('Link missing href for no-js fallback:', link);
            }
        });
    }

    /**
     * Initialize all navigation modules
     */
    function init() {
        loadModules();
        
        if (!ProgressBar || !Toast || !NavHighlight || !ConfirmDialog) {
            console.error('Navigation modules not loaded');
            return;
        }
        
        // Initialize modules
        ProgressBar.init();
        NavHighlight.init();
        initHtmxEvents();
        initAccessibility();
        initNoJsFallback();
        
        // Expose utilities globally
        window.NavigationUtils = {
            Toast,
            ProgressBar,
            NavHighlight,
            ConfirmDialog
        };
        
        // Navigation initialized (debug log removed for production)
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
