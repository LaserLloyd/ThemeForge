# Changelog

Versions follow [Semantic Versioning](https://semver.org/). A release is a git tag `vX.Y.Z`;
`ui-theme/VERSION` and `UITheme.version` carry the same number. Token names are the public
API: removing or renaming one is a major version.

## 1.0.0

First public release.

- **Ten themes:** Purple (the base), Midnight Gold, Glacier, Forest, Paper and Daylight
  (core); Electric Yellow, LaserLloyd, LaserLloyd Light and Night Red (opt-in). Every theme
  passes `tools/check_contrast.py` with no failures.
- **The drop-in bundle `ui-theme/`:** runtime, base layer with the text standard, component
  layer, tokens, adapters, `themes.json`, `update.py`, and `files.json` checksums.
- **Runtime:** `data-default="auto"` follows the OS light/dark preference until the visitor
  picks (with `data-default-dark` / `data-default-light`); `UITheme.reset()`; the picker
  offers "Match system" in auto mode; pickers and toggles a framework renders after load
  mount themselves; `window.UI_THEME_MANIFEST` takes `themes` as an array or a comma string;
  another tab's `localStorage.clear()` repaints the default.
- **TypeScript:** `ui-theme.d.ts` declares `window.UITheme`, `window.UIComponents` and the
  `ui-theme-change` event.
- **Control states:** new tokens `--selected`, `--on-selected`, `--unselected-border` and
  `--unselected-fg`. On, checked, pressed and current read by fill and shape in every theme
  (an accent "on" beside a grey "off" was 1.0-1.6:1 in most themes); disabled controls are
  dashed and unfilled. Native checkboxes and radios take `--selected` as their accent colour.
- **Component layer `ui-components.css`:** buttons, fields, checkbox, radio and switch (with
  on/off marks and an optional On/Off label), cards, wells, stats, badges, counts, dots,
  callouts, tabs, segmented controls, tables, lists, dialog, menu, tooltip, toasts, progress,
  spinner, skeleton, code block, empty state, chat bubbles, an app shell and layout helpers.
  Logical properties throughout (works right-to-left); forced-colours safe.
- **More components:** breadcrumbs, pagination, avatar, chips (removable and selectable),
  disclosure/accordion (`<details>`), drawer (side sheet on `<dialog>`), fieldset, file input,
  sticky table header, a tooltip that opens below. Counts are neutral by default (`--accent`,
  `--danger` variants); status dots use the status text colours.
- **Printing:** a dark theme prints in a light one (`data-print-theme`), and print hides the
  side nav, toasts, menus, drawers and tooltips.
- **High contrast:** under `prefers-contrast: more` every theme raises its lines to the
  control-edge strength and its tertiary text to the secondary tier.
- **Chart ramps:** `--seq-1` ... `--seq-5` and `--div-1` ... `--div-5`, mixed from each theme.
- **`ui-components.js`:** themed `confirm()`, `alert()`, `prompt()` and `toast()`.
- **New tokens:** `--code-header-bg` and `--code-stroke` (code block chrome, dark in every
  theme), `--media-filter` (images marked `.ui-media`; Night Red turns them red).
- **Adapters:** NiceGUI/Quasar (toggles, checkboxes and radios use the control-state design;
  disabled controls are dashed at full opacity), Tailwind CSS v4 (`@theme inline` mapping)
  and a Tailwind v3 preset.
- **`update.py`:** installs and updates a copy from GitHub releases, verifies every file,
  replaces only the files it owns, refuses hand-edited files, and resumes a run that stopped
  half way (a file held open).
- **Design tokens:** `tokens/<theme>.json` in the W3C DTCG format, generated from the CSS.
- **Contrast fixes** carried into this release: Purple `--text-secondary` #a0a0bd,
  `--accent-hover` and `--cta-hover` #8250f0, `--border-strong` #6f6f9c; Paper
  `--text-secondary` #4a3722, `--success-text` #0e4a2e, `--warning-text` #5a3a00,
  `--danger-text` #8a1a15; Glacier and Forest slider fill on the highlight colour; Paper and
  Daylight `--unselected-border` on the tertiary ink.
- **Contrast checks for every pair the components render,** with the values they caught:
  `--rp-ooc` takes the tertiary ink in Purple, Paper, Electric Yellow and LaserLloyd Light;
  `--chart-axis` reaches 3:1 in Purple (#66668a), LaserLloyd Light (#788794) and Night Red
  (#bc0000); `--canvas-handle` is white in the three light themes (it sits on the dark mask);
  Paper's `--text-link` is #781a14 (4.5:1 on its darkest surface); Night Red's
  `--diff-remove-text` is #ff3000.
