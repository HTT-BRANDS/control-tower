# Manual Accessibility Testing Checklist

**Version:** 1.0  
**Last Updated:** March 26, 2026  
**Applies To:** Azure Governance Platform Web Interface

---

## Overview

This checklist ensures WCAG 2.1 Level AA compliance through systematic manual testing. Run these checks on every major UI change.

---

## 1. Keyboard Navigation (WCAG 2.1.1 - Keyboard)

### 1.1 Basic Navigation
- [ ] Tab key moves focus forward through interactive elements
- [ ] Shift+Tab moves focus backward
- [ ] Focus indicator is visible on all focused elements
- [ ] Tab order follows visual reading order (left-to-right, top-to-bottom)

### 1.2 Interactive Elements
- [ ] All buttons are reachable via keyboard
- [ ] All links are reachable via keyboard
- [ ] All form inputs are reachable via keyboard
- [ ] All menus are operable via keyboard (Arrow keys, Enter, Escape)
- [ ] All modals/dialogs are operable via keyboard

### 1.3 Focus Management
- [ ] Focus moves to modal when opened
- [ ] Focus returns to trigger when modal closed
- [ ] No focus traps (can Tab away from any element)
- [ ] Skip link present and functional (bypasses navigation)

**Test Method:**
```bash
# Use browser console to verify focus indicators
document.activeElement
# Should show currently focused element
```

---

## 2. Screen Reader Compatibility (WCAG 1.3.1 - Info and Relationships)

### 2.1 Semantic Structure
- [ ] Page has proper heading hierarchy (h1 → h2 → h3, no skips)
- [ ] All images have alt text (decorative images have empty alt="")
- [ ] Form inputs have associated labels (<label for="id"> or aria-label)
- [ ] Tables have proper headers (<th scope="col/row">)
- [ ] Lists use proper markup (<ul>, <ol>, <li>)

### 2.2 ARIA Landmarks
- [ ] <main> element contains primary content
- [ ] <nav> element contains navigation
- [ ] <header> element contains banner content
- [ ] <footer> element contains footer content
- [ ] Role attributes used appropriately (role="dialog", role="alert")

### 2.3 Dynamic Content
- [ ] Live regions announce important updates (aria-live="polite/assertive")
- [ ] Status messages are announced (role="status")
- [ ] Error messages are announced (role="alert")
- [ ] Loading states are communicated

**Test Method:**
```bash
# Test with NVDA (Windows) or VoiceOver (macOS)
# Enable screen reader and navigate entire page
# Verify all content is announced appropriately
```

---

## 3. Color and Contrast (WCAG 1.4.3 - Contrast Minimum)

### 3.1 Color Contrast
- [ ] Normal text (16px): 4.5:1 contrast ratio minimum
- [ ] Large text (18px+ bold, 24px+ normal): 3:1 contrast ratio minimum
- [ ] UI components (buttons, inputs): 3:1 contrast ratio minimum
- [ ] Graphs/charts don't rely solely on color

### 3.2 Color Independence
- [ ] Information is not conveyed by color alone (icons + text)
- [ ] Error states have non-color indicators (icons, text)
- [ ] Links are distinguishable without color (underline or icon)

**Test Tools:**
- Browser DevTools → Accessibility → Contrast
- WebAIM Contrast Checker: https://webaim.org/resources/contrastchecker/
- axe DevTools extension

---

## 4. Touch Targets (WCAG 2.5.5 - Target Size)

### 4.1 Minimum Sizes
- [ ] All touch targets at least 24×24 CSS pixels (AA)
- [ ] Recommended: 44×44 CSS pixels for mobile (AAA)
- [ ] Adequate spacing between adjacent targets
- [ ] No overlapping touch targets

### 4.2 Pointer Gestures
- [ ] All functionality available via single pointer (click/tap)
- [ ] Complex gestures (swipe, pinch) have alternatives
- [ ] Drag-and-drop has keyboard alternative

**Test Method:**
```javascript
// Run in browser console to check touch target sizes
document.querySelectorAll('button, a, input, [role="button"]').forEach(el => {
  const rect = el.getBoundingClientRect();
  if (rect.width < 24 || rect.height < 24) {
    console.warn('Small touch target:', el, rect.width + 'x' + rect.height);
  }
});
```

---

## 5. Motion and Animation (WCAG 2.2.2 - Pause, Stop, Hide)

### 5.1 Auto-Playing Content
- [ ] No auto-playing audio (or easy to pause/stop)
- [ ] No auto-playing video without user control
- [ ] Carousels/sliders have pause controls
- [ ] Animations respect prefers-reduced-motion

### 5.2 Time Limits
- [ ] Users can extend or disable session timeouts
- [ ] Forms don't timeout without warning
- [ ] Progress indicators show remaining time

---

## 6. Form Validation (WCAG 3.3.1 - Error Identification)

### 6.1 Error Detection
- [ ] Errors identified in text (not just color)
- [ ] Error messages associated with input fields (aria-describedby)
- [ ] Suggestions for correction provided
- [ ] Required fields clearly indicated

### 6.2 Form Labels
- [ ] All inputs have visible labels
- [ ] Labels persist when input is focused
- [ ] Placeholder text is not the only label

---

## 7. Page Structure (WCAG 2.4.1 - Bypass Blocks)

### 7.1 Navigation
- [ ] Skip link to main content (first focusable element)
- [ ] Consistent navigation across pages
- [ ] Current page indicated in navigation

### 7.2 Page Title
- [ ] Each page has unique, descriptive title
- [ ] Title format: [Page Name] - Azure Governance Platform

### 7.3 Language
- [ ] HTML lang attribute set (<html lang="en">)
- [ ] Language changes marked (lang="es" for Spanish text)

---

## 8. Zoom and Reflow (WCAG 1.4.10 - Reflow)

### 8.1 Responsive Design
- [ ] Content readable at 200% zoom (browser zoom)
- [ ] No horizontal scroll at 320px viewport width
- [ ] Text reflows without truncation
- [ ] Tables reflow or have horizontal scroll only

### 8.2 Text Spacing
- [ ] Text spacing can be increased without loss of content
- [ ] Line height can be set to 1.5x
- [ ] Paragraph spacing can be set to 2x

**Test Method:**
```css
/* Apply in browser DevTools to test text spacing */
* {
  line-height: 1.5 !important;
  letter-spacing: 0.12em !important;
  word-spacing: 0.16em !important;
}
```

---

## 9. Specific Component Checks

### 9.1 Navigation
- [ ] Mobile hamburger menu is keyboard accessible
- [ ] Dropdown menus work with keyboard (Arrow keys, Escape)
- [ ] Current page visually distinct in navigation

### 9.2 Tables
- [ ] Column headers are sortable via keyboard
- [ ] Row selection is keyboard accessible
- [ ] Pagination controls are keyboard accessible

### 9.3 Charts
- [ ] Chart data available in table format (or alt text)
- [ ] Colors have patterns or labels
- [ ] Tooltips are keyboard accessible

### 9.4 Modals
- [ ] Focus trapped within modal when open
- [ ] Escape key closes modal
- [ ] Click outside closes modal
- [ ] Return focus to trigger on close

---

## 10. Browser/AT Combinations

Test with at least one combination from each category:

| Category | Combination |
|----------|-------------|
| Windows + Screen Reader | Chrome + NVDA, Firefox + NVDA |
| Windows + Keyboard Only | Edge (no mouse) |
| macOS + Screen Reader | Safari + VoiceOver |
| iOS + Screen Reader | Safari + VoiceOver |
| Android + Screen Reader | Chrome + TalkBack |

---

## Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | |
| QA | | | |
| Accessibility Reviewer | | | |

---

## References

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [WCAG-EM Evaluation Methodology](https://www.w3.org/WAI/test-evaluate/conformance/)
- [axe DevTools](https://www.deque.com/axe/devtools/)
- [NVDA Screen Reader](https://www.nvaccess.org/)
- [VoiceOver Guide](https://www.apple.com/voiceover/info/guide/)
