/**
 * ds-tabs.js — keyboard nav for ds_tabs primitive (WAI-ARIA APG).
 *
 * Auto-inits every element with [data-ds-tabs]. Implements:
 *   • Click a tab → activate it (show its panel, hide others)
 *   • ← / →     → move focus between tabs (wraps, skips aria-disabled)
 *   • Home / End → first / last enabled tab
 *   • Roving tabindex: only the active tab has tabindex=0
 *
 * WCAG 2.2 AAA: focus stays visible (CSS), aria-selected stays in sync,
 * disabled tabs are skipped by keyboard nav (2.1.1 Keyboard).
 * CSP-safe: no inline handlers, no eval.
 */
(function () {
  'use strict';

  function initTabs(root) {
    var tabs = Array.prototype.slice.call(
      root.querySelectorAll('[role="tab"]')
    );
    if (tabs.length === 0) return;
    var panels = tabs.map(function (t) {
      return document.getElementById(t.getAttribute('aria-controls'));
    });

    function isEnabled(t) {
      return t.getAttribute('aria-disabled') !== 'true' && !t.disabled;
    }

    function activate(index, setFocus) {
      var target = tabs[index];
      if (!target || !isEnabled(target)) return;
      tabs.forEach(function (t, i) {
        var selected = i === index;
        t.setAttribute('aria-selected', selected ? 'true' : 'false');
        t.setAttribute('tabindex', selected ? '0' : '-1');
        if (panels[i]) {
          if (selected) panels[i].removeAttribute('hidden');
          else panels[i].setAttribute('hidden', '');
        }
      });
      if (setFocus) target.focus();
    }

    function nextEnabled(from, dir) {
      var n = tabs.length;
      for (var step = 1; step <= n; step++) {
        var i = ((from + dir * step) % n + n) % n;
        if (isEnabled(tabs[i])) return i;
      }
      return from;
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function (e) {
        if (!isEnabled(tab)) { e.preventDefault(); return; }
        activate(i, false);
      });
      tab.addEventListener('keydown', function (e) {
        var key = e.key;
        var target = -1;
        if (key === 'ArrowRight') target = nextEnabled(i, 1);
        else if (key === 'ArrowLeft') target = nextEnabled(i, -1);
        else if (key === 'Home') target = nextEnabled(-1, 1);
        else if (key === 'End') target = nextEnabled(tabs.length, -1);
        else return;
        e.preventDefault();
        activate(target, true);
      });
    });
  }

  function initAll() {
    document.querySelectorAll('[data-ds-tabs]').forEach(initTabs);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
  // Re-init after HTMX swaps (so tabs injected via hx-boost work too)
  document.addEventListener('htmx:afterSettle', initAll);
})();
