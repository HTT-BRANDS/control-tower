# DaisyUI 5.x — Raw Findings

**Source:** https://daisyui.com/ (Official documentation, accessed 2026-03-27)
**Source credibility:** Tier 1 — Official project documentation

## Version Info
- Latest: **5.5.19** (visible in header nav on daisyui.com)
- GitHub: https://github.com/saadeghi/daisyui
- Stars: 40.6k | Forks: 1.6k | Open issues: 37
- License: MIT
- Last commit: 3 days ago (very active)
- Total commits: 2,921

## Tailwind v4 Compatibility
- **Fully native** — uses Tailwind v4's `@plugin` directive
- Installation: `@plugin "daisyui"` in CSS file
- No config file needed (unlike v3 which required tailwind.config.js)
- Theme configuration via brackets: `@plugin "daisyui" { themes: light, dark }`

## Theming System
- 35 built-in themes (light, dark, cupcake, bumblebee, emerald, corporate, synthwave, retro, cyberpunk, valentine, halloween, garden, forest, aqua, lofi, pastel, fantasy, wireframe, black, luxury, dracula, cmyk, autumn, business, acid, lemonade, night, coffee, winter, dim, nord, sunset, caramellatte, abyss, silk)
- Custom themes via CSS custom properties
- `--default` flag for default theme
- `--prefersdark` flag for dark mode theme
- Runtime theme switching via `data-theme` attribute on HTML

## Color System
Semantic color names backed by CSS variables:
- **primary / primary-content** — brand primary
- **secondary / secondary-content** — brand secondary
- **accent / accent-content** — brand accent
- **neutral / neutral-content** — neutral gray
- **base-100 / base-200 / base-300 / base-content** — surface colors
- **info / info-content** — informational
- **success / success-content** — positive feedback
- **warning / warning-content** — caution
- **error / error-content** — destructive/danger

Each color auto-generates a `-content` color for text contrast.

## Framework Independence
- **Pure CSS** — no JavaScript dependency
- "Pure CSS, No JS dependency" stated on homepage
- Components are HTML classes: `<button class="btn btn-primary">`
- Works with any server-rendered HTML (Jinja2, PHP, Rails, etc.)

## Component List (from homepage/docs)
Buttons, Cards, Navbar, Drawer, Modal, Dropdown, Menu, Table, Badge, Alert, Toast, Tabs, Accordion, Steps, Progress, Stats, Avatar, Breadcrumb, Pagination, Toggle, Checkbox, Radio, Select, Textarea, Range, Rating, Tooltip, Collapse, Join, Indicator, Swap, Loading, Diff, Chat Bubble, Timeline, Browser Mockup, Phone Mockup, Code Mockup, Divider, Footer, Hero, Stack, Artboard, Mask

## Accessibility Notes
- Built-in themes enforce color contrast
- Focus indicators via Tailwind's `focus-visible` utilities
- No built-in ARIA role management
- Keyboard navigation depends on HTML structure (developer responsibility)
- The project should add its own ARIA layer via Jinja2 macros
