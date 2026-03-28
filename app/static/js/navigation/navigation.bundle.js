/**
 * Progress Bar Module
 * Creates and manages the top progress bar for HTMX requests
 * 
 * @module navigation/progressBar
 * @version 1.0.0
 */

(function() {
    'use strict';

    const CONFIG = {
        height: '3px',
        color: '#0053e2',       // fallback, resolved in init()
        colorError: '#ea1100',  // fallback, resolved in init()
        animationDuration: 200
    };

    /**
     * Progress Bar manager
     */
    const ProgressBar = {
        element: null,
        
        /**
         * Initialize the progress bar
         */
        init() {
            // Resolve brand colors from CSS custom properties
            const root = getComputedStyle(document.documentElement);
            CONFIG.color = root.getPropertyValue('--brand-primary-100').trim() || CONFIG.color;
            CONFIG.colorError = root.getPropertyValue('--brand-error').trim() || CONFIG.colorError;

            this.element = document.getElementById('htmx-progress-bar');
            if (this.element) return;

            this.element = document.createElement('div');
            this.element.id = 'htmx-progress-bar';
            this.element.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                height: ${CONFIG.height};
                background: ${CONFIG.color};
                width: 0%;
                z-index: 9999;
                transition: width ${CONFIG.animationDuration}ms ease-out;
                box-shadow: 0 0 10px ${CONFIG.color};
            `;
            
            document.body.appendChild(this.element);
        },

        /**
         * Start the progress bar animation
         */
        start() {
            if (!this.element) this.init();
            
            this.element.style.transition = 'none';
            this.element.style.width = '0%';
            this.element.style.background = CONFIG.color;
            
            // Force reflow
            this.element.offsetHeight;
            
            requestAnimationFrame(() => {
                this.element.style.transition = `width ${CONFIG.animationDuration * 3}ms ease-out`;
                this.element.style.width = '70%';
            });
        },

        /**
         * Complete the progress bar animation
         */
        finish() {
            if (!this.element) return;
            
            this.element.style.transition = `width ${CONFIG.animationDuration}ms ease-out`;
            this.element.style.width = '100%';
            
            setTimeout(() => {
                this.element.style.transition = 'opacity 200ms ease-out';
                this.element.style.opacity = '0';
                
                setTimeout(() => {
                    this.element.style.width = '0%';
                    this.element.style.opacity = '1';
                }, 200);
            }, CONFIG.animationDuration);
        },

        /**
         * Show error state on progress bar
         */
        error() {
            if (!this.element) return;
            
            this.element.style.background = CONFIG.colorError;
            this.element.style.width = '100%';
            this.element.style.boxShadow = `0 0 10px ${CONFIG.colorError}`;
            
            setTimeout(() => {
                this.element.style.transition = 'opacity 200ms ease-out';
                this.element.style.opacity = '0';
                
                setTimeout(() => {
                    this.element.style.width = '0%';
                    this.element.style.opacity = '1';
                    this.element.style.background = CONFIG.color;
                    this.element.style.boxShadow = `0 0 10px ${CONFIG.color}`;
                }, 200);
            }, 500);
        }
    };

    // Export for use in other modules
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = ProgressBar;
    } else {
        window.NavigationProgressBar = ProgressBar;
    }
})();
/**
 * Toast Notifications Module
 * Creates and manages toast notifications for user feedback
 * 
 * @module navigation/toast
 * @version 1.0.0
 */

(function() {
    'use strict';

    const CONFIG = {
        duration: 5000,
        maxVisible: 5,
        position: 'top-right'
    };

    let activeToasts = [];

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Toast notification manager
     */
    const Toast = {
        container: null,
        
        /**
         * Initialize toast container
         */
        init() {
            this.container = document.getElementById('toast-container');
            if (this.container) return;

            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.setAttribute('aria-live', 'polite');
            this.container.setAttribute('aria-atomic', 'true');
            
            const positionStyles = {
                'top-right': 'top: 1rem; right: 1rem;',
                'top-left': 'top: 1rem; left: 1rem;',
                'bottom-right': 'bottom: 1rem; right: 1rem;',
                'bottom-left': 'bottom: 1rem; left: 1rem;'
            };
            
            this.container.style.cssText = `
                position: fixed;
                ${positionStyles[CONFIG.position]}
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                max-width: 400px;
                pointer-events: none;
            `;
            
            document.body.appendChild(this.container);
        },

        /**
         * Show a toast notification
         * @param {string} message - Toast message
         * @param {string} type - Toast type: success, error, warning, info
         * @param {number} duration - Duration in ms
         * @returns {HTMLElement} Toast element
         */
        show(message, type = 'info', duration = CONFIG.duration) {
            if (!this.container) this.init();
            
            // Limit visible toasts
            while (activeToasts.length >= CONFIG.maxVisible) {
                const oldest = activeToasts.shift();
                if (oldest) oldest.remove();
            }
            
            const styles = {
                success: {
                    bg: 'var(--color-success, #10B981)',
                    bgLight: 'color-mix(in srgb, var(--color-success, #10B981) 10%, white)',
                    iconPath: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
                },
                error: {
                    bg: 'var(--color-error, #EF4444)',
                    bgLight: 'color-mix(in srgb, var(--color-error, #EF4444) 10%, white)',
                    iconPath: 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z'
                },
                warning: {
                    bg: 'var(--color-warning, #F59E0B)',
                    bgLight: 'color-mix(in srgb, var(--color-warning, #F59E0B) 10%, white)',
                    iconPath: 'M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z'
                },
                info: {
                    bg: 'var(--color-info, #3B82F6)',
                    bgLight: 'color-mix(in srgb, var(--color-info, #3B82F6) 10%, white)',
                    iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
                }
            };
            
            const style = styles[type] || styles.info;
            
            const toast = document.createElement('div');
            toast.setAttribute('role', 'alert');
            toast.style.cssText = `
                pointer-events: auto;
                background-color: ${style.bgLight};
                border-left: 4px solid ${style.bg};
                color: ${style.bg};
                padding: 1rem;
                border-radius: 0.25rem;
                box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
                display: flex;
                align-items: flex-start;
                gap: 0.75rem;
                transform: translateX(100%);
                opacity: 0;
                transition: all 300ms ease-out;
            `;
            
            toast.innerHTML = `
                <svg class="w-5 h-5 flex-shrink-0 mt-0.5" style="color: ${style.bg}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${style.iconPath}"/>
                </svg>
                <div class="flex-1">
                    <p class="text-sm font-medium">${escapeHtml(message)}</p>
                </div>
                <button type="button" class="text-gray-400 hover:text-gray-600 flex-shrink-0" aria-label="Close">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            `;
            
            const closeBtn = toast.querySelector('button');
            closeBtn.addEventListener('click', () => this.dismiss(toast));
            
            this.container.appendChild(toast);
            activeToasts.push(toast);
            
            requestAnimationFrame(() => {
                toast.style.transform = 'translateX(0)';
                toast.style.opacity = '1';
            });
            
            if (duration > 0) {
                setTimeout(() => this.dismiss(toast), duration);
            }
            
            return toast;
        },

        /**
         * Dismiss a toast
         * @param {HTMLElement} toast - Toast to dismiss
         */
        dismiss(toast) {
            toast.style.transform = 'translateX(100%)';
            toast.style.opacity = '0';
            
            setTimeout(() => {
                toast.remove();
                const index = activeToasts.indexOf(toast);
                if (index > -1) activeToasts.splice(index, 1);
            }, 300);
        },

        // Convenience methods
        success(message, duration) { return this.show(message, 'success', duration); },
        error(message, duration) { return this.show(message, 'error', duration); },
        warning(message, duration) { return this.show(message, 'warning', duration); },
        info(message, duration) { return this.show(message, 'info', duration); }
    };

    // Export
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = Toast;
    } else {
        window.NavigationToast = Toast;
    }
})();
/**
 * Navigation Highlighting Module
 * Manages active navigation state based on current URL
 * 
 * @module navigation/navHighlight
 * @version 1.0.0
 */

(function() {
    'use strict';

    const CONFIG = {
        activeClass: 'bg-brand-primary-110',
        selector: 'nav a[href]'
    };

    /**
     * Navigation highlighting manager
     */
    const NavHighlight = {
        /**
         * Initialize navigation highlighting
         */
        init() {
            this.highlightCurrentPage();
            window.addEventListener('popstate', () => this.highlightCurrentPage());
        },

        /**
         * Highlight current page in navigation
         */
        highlightCurrentPage() {
            const currentPath = window.location.pathname;
            const navLinks = document.querySelectorAll(CONFIG.selector);
            
            navLinks.forEach(link => {
                const href = link.getAttribute('href');
                if (!href) return;
                
                // Remove existing active classes
                link.classList.remove('bg-brand-primary-110', 'text-white');
                link.removeAttribute('aria-current');
                
                // Check if this link matches current path
                const isActive = href === currentPath || 
                                (href !== '/' && currentPath.startsWith(href));
                
                if (isActive) {
                    link.classList.add('bg-brand-primary-110', 'text-white');
                    link.setAttribute('aria-current', 'page');
                }
            });
        },

        /**
         * Update navigation after HTMX navigation
         * @param {string} path - New path
         */
        update(path) {
            window.history.pushState({}, '', path);
            this.highlightCurrentPage();
        }
    };

    // Export
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = NavHighlight;
    } else {
        window.NavigationHighlight = NavHighlight;
    }
})();
/**
 * Confirm Dialog Module
 * Custom confirmation dialogs for destructive actions
 * 
 * @module navigation/confirmDialog
 * @version 1.1.0
 */

(function() {
    'use strict';

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Confirm dialog manager
     */
    const ConfirmDialog = {
        /**
         * Show a confirmation dialog
         * @param {string} message - Confirmation message
         * @param {Function} onConfirm - Callback when confirmed
         * @param {Function} onCancel - Callback when cancelled
         */
        show(message, onConfirm, onCancel) {
            const previouslyFocused = document.activeElement;

            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 z-[10001] flex items-center justify-center p-4';
            modal.setAttribute('role', 'alertdialog');
            modal.setAttribute('aria-modal', 'true');
            modal.setAttribute('aria-labelledby', 'confirm-dialog-title');
            modal.innerHTML = `
                <div class="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity" aria-hidden="true"></div>
                <div class="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6 transform transition-all">
                    <div class="flex items-start gap-4">
                        <div class="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                            </svg>
                        </div>
                        <div class="flex-1">
                            <h3 id="confirm-dialog-title" class="text-lg font-semibold text-gray-900">Confirm Action</h3>
                            <p class="text-sm text-gray-500 mt-1">${escapeHtml(message)}</p>
                            <div class="flex justify-end gap-3 mt-6">
                                <button type="button" class="cancel-btn px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                                    Cancel
                                </button>
                                <button type="button" class="confirm-btn px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
                                    Confirm
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            const confirmBtn = modal.querySelector('.confirm-btn');
            const cancelBtn = modal.querySelector('.cancel-btn');
            cancelBtn.focus();
            
            const close = () => {
                modal.remove();
                if (previouslyFocused && previouslyFocused.focus) {
                    previouslyFocused.focus();
                }
            };
            
            confirmBtn.addEventListener('click', () => {
                close();
                if (onConfirm) onConfirm();
            });
            
            cancelBtn.addEventListener('click', () => {
                close();
                if (onCancel) onCancel();
            });
            
            modal.querySelector('[aria-hidden="true"]').addEventListener('click', () => {
                close();
                if (onCancel) onCancel();
            });
            
            // Focus trap + Escape handling
            modal.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    close();
                    if (onCancel) onCancel();
                    return;
                }

                if (e.key === 'Tab') {
                    const focusable = modal.querySelectorAll('button');
                    const first = focusable[0];
                    const last = focusable[focusable.length - 1];

                    if (e.shiftKey) {
                        if (document.activeElement === first) {
                            e.preventDefault();
                            last.focus();
                        }
                    } else {
                        if (document.activeElement === last) {
                            e.preventDefault();
                            first.focus();
                        }
                    }
                }
            });
        }
    };

    // Export
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = ConfirmDialog;
    } else {
        window.NavigationConfirmDialog = ConfirmDialog;
    }
})();
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
