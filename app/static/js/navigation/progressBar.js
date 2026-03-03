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
        color: '#0053e2', // wm-blue-100
        colorError: '#ea1100', // wm-red-100
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
