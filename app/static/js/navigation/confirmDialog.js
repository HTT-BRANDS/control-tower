/**
 * Confirm Dialog Module
 * Custom confirmation dialogs for destructive actions
 * 
 * @module navigation/confirmDialog
 * @version 1.0.0
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
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 z-[10001] flex items-center justify-center p-4';
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
                            <h3 class="text-lg font-semibold text-gray-900">Confirm Action</h3>
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
            confirmBtn.focus();
            
            const close = () => modal.remove();
            
            confirmBtn.addEventListener('click', () => {
                close();
                if (onConfirm) onConfirm();
            });
            
            cancelBtn.addEventListener('click', () => {
                close();
                if (onCancel) onCancel();
            });
            
            modal.querySelector('.fixed.inset-0').addEventListener('click', () => {
                close();
                if (onCancel) onCancel();
            });
            
            modal.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    close();
                    if (onCancel) onCancel();
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
