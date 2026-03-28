/**
 * Dashboard Charts — reads data from canvas data-* attributes
 * populated by the Jinja2 template.
 */
(function() {
  'use strict';

  const brandPrimary = getComputedStyle(document.documentElement)
    .getPropertyValue('--brand-primary').trim() || '#500711';
  const colorSuccess = getComputedStyle(document.documentElement)
    .getPropertyValue('--color-success').trim() || '#0369A1';
  const colorError = getComputedStyle(document.documentElement)
    .getPropertyValue('--color-error').trim() || '#C2410C';
  const colorWarning = getComputedStyle(document.documentElement)
    .getPropertyValue('--color-warning').trim() || '#D97706';

  function initCostTrendChart() {
    const el = document.getElementById('costTrendChart');
    if (!el) return;

    const rawLabels = el.dataset.labels;
    const rawData = el.dataset.values;

    // Parse JSON arrays from data attributes
    let labels, data;
    try {
      labels = JSON.parse(rawLabels || '[]');
      data = JSON.parse(rawData || '[]');
    } catch (e) {
      labels = [];
      data = [];
    }

    // Show empty state if no data
    if (!data.length || data.every(v => v === 0)) {
      el.parentElement.innerHTML = '<div class="flex items-center justify-center h-full text-muted-theme"><p>No cost data yet. Run a cost sync to see trends.</p></div>';
      return;
    }

    new Chart(el.getContext('2d'), {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Daily Cost ($)',
          data: data,
          borderColor: brandPrimary,
          backgroundColor: brandPrimary + '1A',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            beginAtZero: false,
            ticks: {
              callback: function(value) {
                return '$' + value.toLocaleString();
              }
            },
            grid: { color: 'rgba(0,0,0,0.05)' }
          },
          x: { grid: { display: false } }
        }
      }
    });
  }

  function initComplianceChart() {
    const el = document.getElementById('complianceChart');
    if (!el) return;

    const rawLabels = el.dataset.labels;
    const rawData = el.dataset.values;

    let labels, data;
    try {
      labels = JSON.parse(rawLabels || '[]');
      data = JSON.parse(rawData || '[]');
    } catch (e) {
      labels = [];
      data = [];
    }

    if (!data.length) {
      el.parentElement.innerHTML = '<div class="flex items-center justify-center h-full text-muted-theme"><p>No compliance data yet. Run a compliance sync to see scores.</p></div>';
      return;
    }

    // Color bars based on score
    const bgColors = data.map(score => {
      if (score >= 90) return colorSuccess;
      if (score >= 70) return colorWarning;
      return colorError;
    });

    new Chart(el.getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Compliance %',
          data: data,
          backgroundColor: bgColors,
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            ticks: {
              callback: function(value) { return value + '%'; }
            },
            grid: { color: 'rgba(0,0,0,0.05)' }
          },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // Initialize on DOMContentLoaded or immediately if already loaded
  function init() {
    initCostTrendChart();
    initComplianceChart();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-init after HTMX page swaps
  document.addEventListener('htmx:afterSettle', init);
})();
