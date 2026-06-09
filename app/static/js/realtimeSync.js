/**
 * Real-time Sync Status (Server-Sent Events)
 * ==========================================
 * Subscribes to /api/v1/sync/stream and live-updates sync indicators without
 * polling. SSE is used (not WebSocket) deliberately: the data flow is one-way
 * (server -> client), EventSource auto-reconnects, it works under the existing
 * `connect-src 'self'` CSP and session-cookie auth with zero infra config, and
 * it needs no Azure App Service WebSocket toggle. See bd ct-7d6.
 *
 * The endpoint emits JSON snapshots of the form:
 *   {
 *     "ts": "2026-06-09T03:10:00Z",
 *     "last_sync_at": "2026-06-09T03:00:00Z" | null,
 *     "jobs": [{ "type": "costs", "status": "completed"|"running"|"failed"|"idle",
 *                "last_run_at": "...", "next_run_at": "..." }],
 *     "running": 0
 *   }
 *
 * Behavior:
 *   - Updates #last-sync text and any [data-sync-indicator] dots.
 *   - Fires a toast when a job transitions into completed / failed.
 *   - Sets [data-realtime-status] on <body> to connecting|live|offline so CSS
 *     can show a small live dot.
 *
 * @module realtimeSync
 * @version 1.0.0
 */
(function () {
  'use strict';

  if (typeof window.EventSource === 'undefined') {
    // Old browser: leave the existing HTMX polling in place.
    return;
  }

  var ENDPOINT = '/api/v1/sync/stream';
  var source = null;
  var lastStatusByType = {};
  var firstSnapshot = true;

  function setConnectionState(state) {
    document.body.setAttribute('data-realtime-status', state);
  }

  function toast(type, message) {
    if (window.NavigationToast && typeof window.NavigationToast[type] === 'function') {
      window.NavigationToast[type](message);
    }
  }

  function relativeTime(iso) {
    if (!iso) return 'no sync data';
    var then = new Date(iso).getTime();
    if (isNaN(then)) return 'no sync data';
    var secs = Math.round((Date.now() - then) / 1000);
    if (secs < 60) return 'just now';
    var mins = Math.round(secs / 60);
    if (mins < 60) return mins + 'm ago';
    var hrs = Math.round(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    var days = Math.round(hrs / 24);
    return days + 'd ago';
  }

  function updateLastSync(iso) {
    var el = document.getElementById('last-sync');
    if (el) el.textContent = relativeTime(iso);
  }

  function updateIndicators(snapshot) {
    // Generic per-type indicator dots: <span data-sync-indicator="costs">.
    (snapshot.jobs || []).forEach(function (job) {
      var dots = document.querySelectorAll('[data-sync-indicator="' + job.type + '"]');
      dots.forEach(function (dot) {
        dot.setAttribute('data-sync-state', job.status);
      });
    });
    var counter = document.querySelector('[data-sync-running-count]');
    if (counter) counter.textContent = String(snapshot.running || 0);
  }

  function diffAndNotify(snapshot) {
    (snapshot.jobs || []).forEach(function (job) {
      var prev = lastStatusByType[job.type];
      lastStatusByType[job.type] = job.status;
      // Don't spam toasts on the very first snapshot (initial page state).
      if (firstSnapshot || prev === undefined || prev === job.status) return;

      var label = job.type.charAt(0).toUpperCase() + job.type.slice(1);
      if (job.status === 'completed' && prev === 'running') {
        toast('success', label + ' sync completed');
      } else if (job.status === 'failed') {
        toast('error', label + ' sync failed');
      } else if (job.status === 'running' && prev !== 'running') {
        toast('info', label + ' sync started');
      }
    });
  }

  function handleSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return;
    updateLastSync(snapshot.last_sync_at);
    updateIndicators(snapshot);
    diffAndNotify(snapshot);
    firstSnapshot = false;
  }

  function connect() {
    setConnectionState('connecting');
    try {
      source = new EventSource(ENDPOINT);
    } catch (err) {
      setConnectionState('offline');
      return;
    }

    source.addEventListener('open', function () {
      setConnectionState('live');
    });

    source.addEventListener('sync', function (event) {
      try {
        handleSnapshot(JSON.parse(event.data));
      } catch (err) {
        /* ignore malformed frame */
      }
    });

    // Default unnamed messages (fallback if server omits the event name).
    source.addEventListener('message', function (event) {
      try {
        handleSnapshot(JSON.parse(event.data));
      } catch (err) {
        /* ignore */
      }
    });

    source.addEventListener('error', function () {
      // EventSource reconnects automatically; reflect the gap in the UI.
      setConnectionState('offline');
    });
  }

  // Tidy up on navigation so we don't leak connections.
  window.addEventListener('beforeunload', function () {
    if (source) source.close();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connect);
  } else {
    connect();
  }

  window.RealtimeSync = {
    reconnect: function () {
      if (source) source.close();
      connect();
    },
    _handleSnapshot: handleSnapshot,
  };
})();
