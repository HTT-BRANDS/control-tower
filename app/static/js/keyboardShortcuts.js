/**
 * Global Keyboard Shortcuts
 * =========================
 * Gmail-style keyboard navigation for power users. CSP-safe (loaded as an
 * external file with a nonce; binds via addEventListener, no inline handlers).
 *
 * Shortcuts:
 *   ?            Toggle the shortcuts help overlay
 *   /            Open global search
 *   t            Toggle light/dark theme
 *   g then d     Go to Dashboard         g then s   Go to Sync dashboard
 *   g then c     Go to Costs             g then p   Go to Compliance
 *   g then r     Go to Resources         g then i   Go to Identity
 *   g then v     Go to Privacy           g then b   Go to Riverside
 *   Escape       Close help overlay / open modal
 *
 * Design notes:
 *   - Never fires while the user is typing in an input, textarea, select, or
 *     contenteditable element (except Escape, which always works).
 *   - The "g" prefix opens a 1.5s window for the second key (sequence combos).
 *   - All navigation targets are real routes; see ROUTES below.
 *
 * @module keyboardShortcuts
 * @version 1.0.0
 */
(function () {
  'use strict';

  var ROUTES = {
    d: '/dashboard',
    s: '/sync-dashboard',
    c: '/costs',
    p: '/compliance',
    r: '/resources',
    i: '/identity',
    v: '/privacy',
    b: '/riverside',
  };

  var ROUTE_LABELS = {
    d: 'Dashboard',
    s: 'Sync dashboard',
    c: 'Costs',
    p: 'Compliance',
    r: 'Resources',
    i: 'Identity',
    v: 'Privacy',
    b: 'Riverside',
  };

  var SEQUENCE_TIMEOUT_MS = 1500;
  var pendingPrefix = null;
  var pendingTimer = null;

  /** True when the user is typing somewhere we must not hijack keystrokes. */
  function isEditableTarget(el) {
    if (!el) return false;
    var tag = (el.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (el.isContentEditable) return true;
    // Honor an explicit opt-out on any custom widget.
    if (el.getAttribute && el.getAttribute('data-no-shortcuts') !== null) return true;
    return false;
  }

  function announce(message) {
    // Toast is published by navigation.bundle.js as window.NavigationToast.
    // Signature: info(message, durationMs).
    if (window.NavigationToast && typeof window.NavigationToast.info === 'function') {
      window.NavigationToast.info(message, 1500);
    }
  }

  function navigate(key) {
    var path = ROUTES[key];
    if (!path) return false;
    announce('Going to ' + ROUTE_LABELS[key]);
    window.location.href = path;
    return true;
  }

  function openSearch() {
    var trigger = document.getElementById('search-trigger');
    var input = document.getElementById('search-input');
    if (trigger) {
      trigger.click();
    }
    // Focus the field once the modal is visible.
    window.setTimeout(function () {
      var field = document.getElementById('search-input') || input;
      if (field) field.focus();
    }, 60);
  }

  function toggleTheme() {
    if (typeof window.toggleTheme === 'function') {
      window.toggleTheme();
      var mode = document.documentElement.classList.contains('dark') ? 'Dark' : 'Light';
      announce(mode + ' mode');
    }
  }

  function clearPrefix() {
    pendingPrefix = null;
    if (pendingTimer) {
      window.clearTimeout(pendingTimer);
      pendingTimer = null;
    }
  }

  // ----- Help overlay -------------------------------------------------------

  function buildHelpOverlay() {
    var existing = document.getElementById('kbd-help-overlay');
    if (existing) return existing;

    var overlay = document.createElement('div');
    overlay.id = 'kbd-help-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'kbd-help-title');
    overlay.hidden = true;
    overlay.className = 'kbd-help-overlay';

    var rows = [
      ['?', 'Show / hide this help'],
      ['/', 'Open global search'],
      ['t', 'Toggle light / dark theme'],
      ['g d', 'Go to Dashboard'],
      ['g s', 'Go to Sync dashboard'],
      ['g c', 'Go to Costs'],
      ['g p', 'Go to Compliance'],
      ['g r', 'Go to Resources'],
      ['g i', 'Go to Identity'],
      ['g v', 'Go to Privacy'],
      ['g b', 'Go to Riverside'],
      ['Esc', 'Close dialogs'],
    ];

    var rowsHtml = rows
      .map(function (r) {
        var keys = r[0]
          .split(' ')
          .map(function (k) {
            return '<kbd class="kbd-key">' + k + '</kbd>';
          })
          .join(' ');
        return (
          '<div class="kbd-help-row"><span class="kbd-help-keys">' +
          keys +
          '</span><span class="kbd-help-desc">' +
          r[1] +
          '</span></div>'
        );
      })
      .join('');

    overlay.innerHTML =
      '<div class="kbd-help-panel" data-no-shortcuts>' +
      '<div class="kbd-help-header">' +
      '<h2 id="kbd-help-title" class="kbd-help-title">Keyboard shortcuts</h2>' +
      '<button type="button" id="kbd-help-close" class="kbd-help-close" aria-label="Close keyboard shortcuts">&times;</button>' +
      '</div>' +
      '<div class="kbd-help-grid">' +
      rowsHtml +
      '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    // Close interactions.
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) hideHelp();
    });
    var closeBtn = overlay.querySelector('#kbd-help-close');
    if (closeBtn) closeBtn.addEventListener('click', hideHelp);

    return overlay;
  }

  function helpVisible() {
    var o = document.getElementById('kbd-help-overlay');
    return !!o && !o.hidden;
  }

  function showHelp() {
    var o = buildHelpOverlay();
    o.hidden = false;
    var closeBtn = o.querySelector('#kbd-help-close');
    if (closeBtn) closeBtn.focus();
  }

  function hideHelp() {
    var o = document.getElementById('kbd-help-overlay');
    if (o) o.hidden = true;
  }

  function toggleHelp() {
    if (helpVisible()) hideHelp();
    else showHelp();
  }

  // ----- Key handling -------------------------------------------------------

  function handleKeydown(e) {
    // Escape always works: close help, then let other handlers (modals) run.
    if (e.key === 'Escape') {
      if (helpVisible()) {
        hideHelp();
        e.preventDefault();
      }
      clearPrefix();
      return;
    }

    // Respect modifier combos and text entry.
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isEditableTarget(e.target)) return;

    var key = e.key;

    // Second key of a "g <x>" sequence.
    if (pendingPrefix === 'g') {
      clearPrefix();
      if (ROUTES[key]) {
        e.preventDefault();
        navigate(key);
      }
      return;
    }

    switch (key) {
      case '?':
        e.preventDefault();
        toggleHelp();
        return;
      case '/':
        e.preventDefault();
        openSearch();
        return;
      case 't':
        e.preventDefault();
        toggleTheme();
        return;
      case 'g':
        e.preventDefault();
        pendingPrefix = 'g';
        pendingTimer = window.setTimeout(clearPrefix, SEQUENCE_TIMEOUT_MS);
        return;
      default:
        return;
    }
  }

  document.addEventListener('keydown', handleKeydown);

  // Expose a tiny API for tests / programmatic use.
  window.KeyboardShortcuts = {
    showHelp: showHelp,
    hideHelp: hideHelp,
    toggleHelp: toggleHelp,
    routes: ROUTES,
  };
})();
