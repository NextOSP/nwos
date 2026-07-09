# Web Carbon Theme — Design Principles

This addon restyles the whole web client (backend, login, portal, website) to
follow the [IBM Carbon Design System](https://carbondesignsystem.com/). It is
**token-driven** and **non-invasive**: it only prepends variable overrides and
adds component SCSS — no core file is modified, so it installs and uninstalls
cleanly.

## Principles

1. **Token-driven.** Every color, space and type value comes from the token
   layer in `static/src/scss/tokens/carbon_tokens.scss`. Never hardcode a hex
   outside that file. Component SCSS references `$carbon-*` (or the mapped
   `$o-*`) variables only.
2. **IBM Plex typography.** IBM Plex Sans for UI, IBM Plex Mono for code. The
   fixed *productive* type scale is used (base 14px), with semibold (600)
   headings. Fonts are bundled as woff2 under `static/src/fonts/`.
3. **2x Grid / 8px spacing.** Layout rhythm follows Carbon's spacing scale:
   2, 4, 8, 12, 16, 24, 32, 40, 48px (`$carbon-spacing-01…09`).
4. **Sharp corners.** Border-radius is `0` everywhere — Carbon's most
   recognizable trait (`$o-border-radius* : 0`).
5. **Accessible contrast (WCAG AA).** Text ≥ 4.5:1, UI ≥ 3:1. We use Carbon's
   precomputed token pairs, which already satisfy AA.
6. **Distinctive focus.** Every interactive element gets a 2px Blue 60
   (`#0f62fe`) focus ring, inset with a white companion border so it reads on
   both light and dark surfaces.
7. **Dark UI Shell.** The top navbar is Gray 100 (`#161616`) with Gray 10 text,
   white on hover, and Blue 60 accents — the Carbon UI Shell header.

## Token reference

| Role | Carbon token | Hex |
|---|---|---|
| Brand / interactive / focus / links | Blue 60 | `#0f62fe` |
| Interactive hover | Blue 70 | `#0043ce` |
| Highlight / selected bg | Blue 20 | `#d0e2ff` |
| Text primary / shell bg | Gray 100 | `#161616` |
| Text secondary / labels | Gray 70 | `#525252` |
| Layer / field / page-alt bg | Gray 10 | `#f4f4f4` |
| Subtle border | Gray 20 / 30 | `#e0e0e0` / `#c6c6c6` |
| Strong border / toggle-off | Gray 50 | `#8d8d8d` |
| Shell hover | Gray 80 | `#393939` |
| Background | White | `#ffffff` |
| Error | Red 60 | `#da1e28` |
| Success | Green 50 | `#24a148` |
| Warning | Yellow 30 | `#f1c21b` |

## Architecture

The theme hooks Odoo's SCSS bundle system (all core vars use `!default`, so a
prepended value wins):

- `web._assets_primary_variables` ← `carbon_tokens.scss` → `primary_variables.scss`
  → `navbar.variables.scss` → `frontend/primary_variables.scss`
- `web._assets_secondary_variables` ← `secondary_variables.scss`
- `web.assets_backend` ← `fonts.scss` + `components/*.scss`
- `web.assets_frontend` ← `fonts.scss` + `frontend/frontend.scss`

Setting the `$o-*` layer also flows through the base `bootstrap_overridden.scss`
bridge into Bootstrap's `$primary`, `$font-family-sans-serif`,
`$border-radius`, etc., so most Bootstrap components recolor for free. Component
SCSS only restyles elements whose Carbon *shape* differs (shell, buttons,
fields, controls).

## Files

```
static/src/
  fonts/                       IBM Plex Sans + Mono woff2
  scss/
    tokens/carbon_tokens.scss  the single source of truth
    primary_variables.scss     $carbon-* -> $o-*
    secondary_variables.scss   derived vars
    bootstrap ... (none)       handled via $o-* bridge + component SCSS
    fonts.scss                 @font-face
    components/*.scss           backend parity (shell, buttons, fields, …)
    frontend/*.scss            login / portal / website
  webclient/navbar/navbar.variables.scss   dark UI Shell
```

To extend: add a new `components/<name>.scss`, reference only `$carbon-*` /
`$o-*` tokens, and register it in `__manifest__.py` under `web.assets_backend`.
