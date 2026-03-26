/**
 * Accessibility Testing Utilities
 * 
 * Client-side checks for WCAG compliance
 */

(function() {
    'use strict';
    
    window.AccessibilityTester = {
        
        /**
         * Check all interactive elements for minimum touch target size
         * WCAG 2.5.8: Target size ≥ 24×24 CSS pixels
         */
        checkTouchTargets: function() {
            const interactiveSelectors = [
                'button', 'a', 'input', 'select', 'textarea',
                '[role="button"]', '[role="link"]', '[role="checkbox"]',
                '[role="radio"]', '[role="tab"]', '[role="menuitem"]',
                '[onclick]', '[tabindex]:not([tabindex="-1"])'
            ];
            
            const elements = document.querySelectorAll(interactiveSelectors.join(', '));
            const violations = [];
            const MIN_SIZE = 24;
            
            elements.forEach(el => {
                const rect = el.getBoundingClientRect();
                const width = rect.width;
                const height = rect.height;
                
                // Check if element is visible
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') {
                    return;
                }
                
                // Check minimum size
                if (width < MIN_SIZE || height < MIN_SIZE) {
                    violations.push({
                        element: el.tagName.toLowerCase(),
                        selector: this.getUniqueSelector(el),
                        text: el.textContent?.substring(0, 50) || '',
                        width: Math.round(width * 100) / 100,
                        height: Math.round(height * 100) / 100,
                        location: window.location.pathname
                    });
                }
            });
            
            return {
                total: elements.length,
                violations: violations,
                compliant: violations.length === 0,
                score: Math.round(((elements.length - violations.length) / elements.length) * 100)
            };
        },
        
        /**
         * Get a unique CSS selector for an element
         */
        getUniqueSelector: function(el) {
            if (el.id) {
                return '#' + el.id;
            }
            
            let selector = el.tagName.toLowerCase();
            if (el.className) {
                selector += '.' + el.className.split(' ').join('.');
            }
            
            // Add nth-child if needed for uniqueness
            const siblings = Array.from(el.parentNode?.children || []);
            const sameTagSiblings = siblings.filter(s => s.tagName === el.tagName);
            if (sameTagSiblings.length > 1) {
                const index = siblings.indexOf(el) + 1;
                selector += `:nth-child(${index})`;
            }
            
            return selector;
        },
        
        /**
         * Check for focusable elements hidden by sticky headers
         * WCAG 2.4.11/2.4.12: Focus not obscured
         */
        checkFocusObscured: function() {
            const stickyElements = document.querySelectorAll(
                '.sticky, [style*="position: fixed"], [style*="position:sticky"]'
            );
            
            const focusable = document.querySelectorAll(
                'button, a, input, [tabindex]:not([tabindex="-1"])'
            );
            
            const obscured = [];
            
            focusable.forEach(el => {
                const rect = el.getBoundingClientRect();
                
                stickyElements.forEach(sticky => {
                    const stickyRect = sticky.getBoundingClientRect();
                    
                    // Check if element is behind sticky header
                    if (rect.top < stickyRect.bottom && 
                        rect.bottom > stickyRect.top &&
                        rect.left < stickyRect.right &&
                        rect.right > stickyRect.left) {
                        
                        obscured.push({
                            element: el.tagName.toLowerCase(),
                            obscuredBy: sticky.tagName.toLowerCase(),
                            selector: this.getUniqueSelector(el)
                        });
                    }
                });
            });
            
            return {
                totalFocusable: focusable.length,
                obscuredCount: obscured.length,
                obscured: obscured,
                compliant: obscured.length === 0
            };
        },
        
        /**
         * Run all accessibility checks and log results
         */
        runAllChecks: function() {
            console.group('🔍 Accessibility Audit');
            
            const touchTargets = this.checkTouchTargets();
            console.log('Touch Targets (WCAG 2.5.8):', 
                touchTargets.compliant ? '✅ PASS' : '❌ FAIL',
                touchTargets
            );
            
            const focusObscured = this.checkFocusObscured();
            console.log('Focus Not Obscured (WCAG 2.4.11):',
                focusObscured.compliant ? '✅ PASS' : '❌ FAIL',
                focusObscured
            );
            
            console.groupEnd();
            
            return {
                touchTargets,
                focusObscured,
                timestamp: new Date().toISOString()
            };
        }
    };
    
    // Auto-run on load if in development
    if (window.location.hostname === 'localhost' || 
        window.location.hostname.includes('staging')) {
        window.addEventListener('load', function() {
            setTimeout(function() {
                window.AccessibilityTester.runAllChecks();
            }, 1000); // Wait for dynamic content
        });
    }
})();
