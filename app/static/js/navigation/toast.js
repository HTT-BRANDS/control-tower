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
                    bg: 'bg-green-50',
                    border: 'border-green-400',
                    text: 'text-green-800',
                    icon: 'text-green-400',
                    iconPath: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
                },
                error: {
                    bg: 'bg-red-50',
                    border: 'border-red-400',
                    text: 'text-red-800',
                    icon: 'text-red-400',
                    iconPath: 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z'
                },
                warning: {
                    bg: 'bg-yellow-50',
                    border: 'border-yellow-400',
                    text: 'text-yellow-800',
                    icon: 'text-yellow-400',
                    iconPath: 'M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z'
                },
                info: {
                    bg: 'bg-blue-50',
                    border: 'border-blue-400',
                    text: 'text-blue-800',
                    icon: 'text-blue-400',
                    iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
                }
            };
            
            const style = styles[type] || styles.info;
            
            const toast = document.createElement('div');
            toast.setAttribute('role', 'alert');
            toast.style.pointerEvents = 'auto';
            toast.className = `
                ${style.bg} border-l-4 ${style.border} ${style.text}
                p-4 rounded shadow-lg flex items-start gap-3
                transform transition-all duration-300 ease-out
                translate-x-full opacity-0
            `;
            
            toast.innerHTML = `
                <svg class="w-5 h-5 ${style.icon} flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                toast.classList.remove('translate-x-full', 'opacity-0');
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
            toast.classList.add('translate-x-full', 'opacity-0');
            
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
