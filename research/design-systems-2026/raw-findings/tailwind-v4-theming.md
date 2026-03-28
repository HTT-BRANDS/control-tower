# Tailwind v4 Native Theming — Raw Findings

**Source:** https://tailwindcss.com/docs/theme (Official docs, accessed 2026-03-27)
**Source credibility:** Tier 1 — Framework author documentation (Tailwind Labs)
**Version:** v4.2

## @theme Directive

### What it does
- Defines **theme variables** — special CSS variables that create corresponding utility classes
- `@theme { --color-mint-500: #4ade80; }` → generates `bg-mint-500`, `text-mint-500`, `border-mint-500`, etc.
- Replaces `tailwind.config.js` theme configuration from v3

### Why @theme instead of :root
- Theme variables aren't *just* CSS variables — they instruct Tailwind to create utility classes
- Must be top-level (not nested in selectors or media queries)
- `:root` is for CSS variables that don't need utility classes

### Theme Variable Namespaces
Variables map to utilities by prefix:
- `--color-*` → `bg-*`, `text-*`, `border-*`, `ring-*`, `outline-*`, `fill-*`, `stroke-*`, etc.
- `--font-*` → `font-*`
- `--spacing-*` → `p-*`, `m-*`, `gap-*`, `w-*`, `h-*`, etc.
- `--breakpoint-*` → responsive variants (`sm:*`, `md:*`, etc.)
- `--radius-*` → `rounded-*`
- `--shadow-*` → `shadow-*`
- `--animate-*` → `animate-*`

## Customizing Themes

### Extending the default theme
Add new variables alongside defaults:
```css
@theme {
  --font-script: Great Vibes, cursive;
  --color-midnight: #0f172a;
}
```

### Overriding defaults
Redefine within @theme:
```css
@theme {
  --breakpoint-sm: 30rem; /* Overrides default 40rem */
}
```

### Using a custom theme (clean slate)
Use `--color-*: initial` to clear all defaults:
```css
@theme {
  --color-*: initial;
  --color-dusk: #6b5b95;
  --color-dawn: #f7cac9;
}
```

## Referencing Other Variables

### ⚠️ Critical Caveat
When using `var()` inside `@theme`, CSS variable resolution happens at the **element level**, not at definition time.

Example of the problem:
```css
@theme {
  --font-sans: var(--font-inter), sans-serif;
}
```
If `--font-inter` is defined on a child element but not on the parent, `.font-sans` will resolve to `sans-serif` on the parent — the `var()` reference won't find `--font-inter`.

### Implication for this project
The pattern `@theme { --color-brand-primary: var(--brand-primary); }` works correctly because `--brand-primary` is defined on `:root` (the highest level). If `[data-brand]` is on `<html>` (which it is), this is safe. If `[data-brand]` were on a lower element, it would break.

### Using `inline` keyword
For theme variables that reference runtime CSS variables, use `inline` to avoid resolution issues:
```css
@theme inline {
  --color-primary: var(--color-primary);
}
```
The `inline` keyword tells Tailwind to generate `var()` references in utilities rather than resolving at build time.

## Dark Mode (v4)

### @custom-variant approach
```css
@custom-variant dark (&:where(.dark, .dark *));
```
- Replaces `darkMode: 'class'` from tailwind.config.js
- Can use data attributes: `@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));`
- System preference support available

## Generating All CSS Variables
```css
@theme {
  /* Theme variables are automatically output as CSS variables on :root */
}
```
All `@theme` variables are emitted as CSS custom properties, accessible via `var()` in custom CSS.

## Sharing Across Projects
Theme can be extracted to a shared CSS file and `@import`ed.
