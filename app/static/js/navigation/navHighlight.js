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
        activeClass: 'bg-wm-blue-110',
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
                link.classList.remove('bg-wm-blue-110', 'text-white');
                link.removeAttribute('aria-current');
                
                // Check if this link matches current path
                const isActive = href === currentPath || 
                                (href !== '/' && currentPath.startsWith(href));
                
                if (isActive) {
                    link.classList.add('bg-wm-blue-110', 'text-white');
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
