// Dark Mode ThemeProvider — ported from microsoft-group-management
// Toggles the .dark/.light class on <html> AND swaps DaisyUI's data-theme.
//
// Why both? Two theming layers coexist (see input.css + design-tokens.css):
//   1. Hand-authored tokens keyed on the .dark/.light CLASS (page chrome).
//   2. DaisyUI components keyed on the data-theme ATTRIBUTE (badges, cards…).
// The brand theme (httbrands/bishops/…) is a *light* color-scheme, so toggling
// only the class left every DaisyUI component rendering light boxes on a dark
// background (bd ct-6vn). We now swap data-theme to the built-in `dark` theme
// when dark is active and restore the brand theme (preserved in data-brand)
// for light. localStorage persists the user's choice.
(function () {
  var root = document.documentElement;
  var brandTheme =
    root.getAttribute('data-brand') || root.getAttribute('data-theme') || 'light';

  var saved = localStorage.getItem('theme');
  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  var theme = saved || (prefersDark ? 'dark' : 'light');

  function applyTheme(next) {
    root.classList.remove('light', 'dark');
    root.classList.add(next);
    // DaisyUI reads data-theme: dark -> built-in dark theme, light -> brand.
    root.setAttribute('data-theme', next === 'dark' ? 'dark' : brandTheme);
  }

  applyTheme(theme);

  // Follow system preference only when the user hasn't chosen explicitly.
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    if (!localStorage.getItem('theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });

  window.toggleTheme = function () {
    var current = root.classList.contains('dark') ? 'dark' : 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('theme', next);
  };

  // CSP-safe: bind click via addEventListener instead of inline onclick.
  var btn = document.getElementById('theme-toggle-btn');
  if (btn) btn.addEventListener('click', window.toggleTheme);
})();
