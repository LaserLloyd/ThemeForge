# AGENTS.md — adding ThemeForge to an app

You are an AI coding agent and someone asked you to theme a web app, or to give it a theme
picker, dark mode or a consistent look. This file is everything you need: follow it top to
bottom. It takes about five minutes.

**Names.** Repository `LaserLloyd/ThemeForge` ("ThemeForge"). What you copy into the app
is one folder, `ui-theme/`. The script defines `window.UITheme`. Every component class starts
with `ui-` (the base layer also keeps a few unprefixed helpers for older apps, listed in
`docs/COMPONENTS.md`). There is no npm or pip package and no build step: plain CSS files and
two small scripts.

**What you get.** Ten colour themes and a picker; about 250 design tokens (colours, type,
spacing, radii, shadows, motion); an element base layer (body text, links, focus ring,
scrollbars); text tiers and a markdown style; component classes (buttons, form fields,
switches, cards, badges, callouts, tabs, tables, dialogs, menus, toasts, an app shell);
themed `confirm()`/`alert()`/`prompt()`; adapters for NiceGUI/Quasar and Tailwind.
**What you do not get:** icons, fonts (stacks fall back to system fonts; see
`docs/INTEGRATIONS.md` to load them), or framework components.

**Browsers:** current Chrome, Edge, Firefox and Safari (2024 or newer). The layer uses
`:has()`, `color-mix()` and the popover API; older browsers keep the colours, but some
component states and menus degrade.

## 1. Decide once

| Question | Default answer |
|---|---|
| Where does the folder go? | The app's static folder, served as-is: `static/ui-theme/` (Flask, FastAPI, Django), `public/ui-theme/` (Vite, Next.js, Create React App), `app/static/ui-theme/`, or next to `index.html` for a plain site. |
| Which themes? | The six core themes: `purple,midnight-gold,glacier,forest,paper,daylight`. Add an opt-in theme (`night-red`, `electric-yellow`, `laserlloyd`, `laserlloyd-light`) only if the user asked for it. |
| Default theme? | `auto`: follow the visitor's OS light/dark setting until they pick (`data-default-dark="midnight-gold"`, `data-default-light="daylight"`). |
| Storage key? | `<appname>.theme`, e.g. `notes.theme`. |

## 2. Install

<!-- install:start -->
Run from the app's root folder (Python 3.9 or newer; change `static/ui-theme` to the folder
you chose):

```
python3 -c "import urllib.request as u,sys;sys.argv=['update.py','--dest','static/ui-theme'];exec(u.urlopen('https://raw.githubusercontent.com/LaserLloyd/ThemeForge/main/ui-theme/update.py').read())"
```

On Windows use `python` (or `py`) instead of `python3`; the line is the same in PowerShell,
cmd and bash. It downloads the installer, which fetches the latest release from GitHub,
checks every file against its checksum list and writes the folder. Later updates are
`python3 static/ui-theme/update.py`. Offline: download a release archive (`.tar.gz`) elsewhere,
then run `python3 update.py --source <archive> --dest static/ui-theme` with the `update.py` from
its `ui-theme/` folder.
<!-- install:end -->

Other ways, if Python is not available:

- **git:** `git clone --depth 1 https://github.com/LaserLloyd/ThemeForge.git ut-tmp`, copy
  `ut-tmp/ui-theme` into the app, delete `ut-tmp`.
- **Node:** `npx degit LaserLloyd/ThemeForge/ui-theme#v1.0.0 static/ui-theme`.
- **No install (prototypes, single HTML files):** load the files from jsDelivr, pinned to a
  release: `https://cdn.jsdelivr.net/gh/LaserLloyd/ThemeForge@v1.0.0/ui-theme/ui-theme.js`
  (and the same path for each CSS file). Never pin `@main`; the CDN caches it for up to
  12 hours. A CDN page updates by changing the pinned version; `update.py` and steps 8.5, 9
  and 10 below do not apply to it.

## 3. Wire the page head

Every page's `<head>`, in this order (adjust the `/static/ui-theme/` prefix to where the
folder is served):

```html
<script src="/static/ui-theme/ui-theme.js"
        data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
        data-default="auto"
        data-default-dark="midnight-gold"
        data-default-light="daylight"
        data-storage-key="myapp.theme"></script>
<link rel="stylesheet" href="/static/ui-theme/ui-theme-base.css">
<link rel="stylesheet" href="/static/ui-theme/ui-components.css">
<!-- the app's own stylesheets go here -->
<link rel="stylesheet" href="/static/ui-theme/ui-theme.css">
<script src="/static/ui-theme/ui-components.js" defer></script>
```

Three rules, each for a reason:

1. **`ui-theme.js` is a classic, blocking script, first in `<head>`.** Never `type="module"`,
   `defer` or `async`, and never inject it from JavaScript: it reads its settings from its
   own tag (`document.currentScript`, which is null for module scripts) and sets the theme
   before the first paint, so there is no flash of the wrong theme.
2. **The base and component layers load before the app's CSS,** so the app's own rules win
   at equal specificity.
3. **`ui-theme.css` loads after the app's CSS,** so an old variable in the app can never
   shadow a theme token.

`ui-components.js` (dialogs and toasts) is optional and may be deferred; an app script that
uses `UIComponents` must come after it (both `defer`, or both at the end of `<body>`).

Framework notes (details and full examples in `docs/INTEGRATIONS.md`):

- **Jinja / Django / Flask / FastAPI:** put the block in the base template; serve the folder
  with `Cache-Control: no-cache` so updates show up (or add `?v=<file hash>` to each URL).
- **Vite, Vue, Svelte, SvelteKit:** put the block in `index.html` / `app.html`, not in a
  component. Files under `public/` are served from `/`, so the prefix is `/ui-theme/`.
- **React with Next.js:** in the root layout, render the block inside `<head>` as plain
  `<script>` and `<link>` elements (they are server-rendered, so the script runs before first
  paint; silence the `no-sync-scripts` lint rule for that line), and add
  `suppressHydrationWarning` to `<html>`, because the runtime sets attributes there before
  React hydrates.
- **NiceGUI / Quasar:** also load `adapters/quasar.js` right after `ui-theme.js` and
  `adapters/quasar.css` right after `ui-theme.css` (`ui.add_head_html`). Remove any
  `ui.dark_mode()`: the adapter switches Quasar's dark mode with the theme.
- **Tailwind CSS v4:** `@import "./<path>/ui-theme/adapters/tailwind.css";` after
  `@import "tailwindcss";` gives `bg-surface-2`, `text-fg`, `text-fg-muted`, `bg-accent`,
  `text-on-accent`, `border-line`... Tailwind v3: `presets: [require('./<path>/ui-theme/adapters/tailwind-v3.preset.js')]`.
  Text colours are `fg-*` because `text-*` sizes belong to Tailwind.
- **Another library reads `data-theme` on `<html>`** (daisyUI, Pico): the runtime writes
  `data-theme="amoled|dark|light"` there; check that this does not fight it.

## 4. Add the theme picker

Put this wherever settings live (header, settings page). It fills itself and stays in sync,
across tabs too:

```html
<label class="ui-field" style="max-width: 220px">
  <span class="ui-label">Theme</span>
  <select class="ui-select" data-ui-theme-picker></select>
</label>
```

With `data-default="auto"` the picker's first entry is "Match system". From script:
`UITheme.set('glacier')`, `UITheme.reset()` (back to the default), `UITheme.current()`,
`UITheme.list()`, `UITheme.onChange(fn)`.

A `<select data-ui-theme-picker>` that React, Vue or Svelte renders later is found and filled
automatically; leave it uncontrolled (no `value`/`onChange` from the framework). For a
fully custom control, build it from `UITheme.list()` and call `UITheme.set(slug)` /
`UITheme.reset()`. TypeScript: `ui-theme/ui-theme.d.ts` declares `window.UITheme` and
`window.UIComponents`; add it to `tsconfig.json`'s `include`.

## 5. Build the UI from tokens and classes

Never write a colour value. Use a token: `color: var(--text-primary)`. The tokens you need
almost every time:

| Need | Token |
|---|---|
| page, nav, card, hover, active grounds | `--surface-0`, `--surface-1`, `--surface-2`, `--surface-3`, `--surface-4` |
| inset well, menus and popovers | `--surface-sunken`, `--surface-overlay` |
| text, in tiers | `--text-primary`, `--text-secondary` (labels, descriptions), `--text-tertiary` (hints, timestamps), `--text-disabled` |
| links and accent-coloured text | `--text-link`, `--text-link-hover` |
| primary action fill | `--accent`, `--accent-hover`, label on it `--on-accent` |
| on / checked / selected / current | `--selected` (fill or indicator), `--on-selected` (on it) |
| lines | `--border`, `--border-subtle`, `--border-strong` (control edges), `--divider`, `--focus-ring` |
| status | `--success`, `--warning`, `--danger`, `--info` (dots, bars, fills); `--danger-text` etc. (text); `--danger-subtle` (tinted background); `--danger-border`; `--on-danger` (label on the solid fill) |
| shape, space, type | `--radius-sm`/`-md`/`-lg`/`-pill`, `--space-1`...`--space-8` (4-64px), `--fs-xs`...`--fs-2xl`, `--fw-medium`/`-semibold`, `--font-sans`, `--font-mono` |
| depth and layers | `--shadow-1`...`--shadow-4`, `--z-modal`, `--z-toast`, `--z-popover` |
| charts | `--cat-1`...`--cat-12` (series), `--seq-1`...`--seq-5` (low to high), `--div-1`...`--div-5` (bad, neutral, good), `--chart-grid`, `--chart-axis` |

Only elements with a `ui-` class are styled as components: a bare `<button>`, `<input>`,
`<select>` or `<table>` keeps the browser's default look, so give every control its class.
(The base layer only sets the page text, links, headings, code, focus ring and scrollbars.)
All states come from native attributes: `disabled`, `checked`, `aria-pressed`,
`aria-selected`, `aria-current`, `aria-invalid`, `aria-busy`. Markup for each component is in
`docs/COMPONENTS.md`; the common ones:

```html
<div class="ui-app">                                  <!-- app shell: header, side nav, main -->
  <header class="ui-app__header"><a class="ui-brand" href="/">Notes</a><span class="ui-spacer"></span>
    <select class="ui-select" data-ui-theme-picker style="width: auto"></select></header>
  <nav class="ui-app__nav ui-nav"><a class="ui-nav__item" href="/" aria-current="page">Inbox</a></nav>
  <main class="ui-app__main ui-stack">
    <h1 class="ui-title">Inbox</h1>
    <div class="ui-card">
      <label class="ui-field"><span class="ui-label">Title</span><input class="ui-input" name="title"></label>
      <label class="ui-check"><input type="checkbox" role="switch" class="ui-switch" checked> Pinned
        <span class="ui-switch-state" aria-hidden="true"></span></label>
      <div class="ui-row"><button class="ui-btn ui-btn--primary">Save</button><button class="ui-btn">Cancel</button></div>
    </div>
    <div class="ui-callout ui-callout--danger" role="alert"><strong class="ui-callout__title">Failed</strong> Try again.</div>
  </main>
</div>
```

Buttons `.ui-btn` + `--primary` `--ghost` `--outline` `--danger` `--cta` `--sm` `--lg`
`--icon` `--block`; fields `.ui-field` `.ui-label` `.ui-input` `.ui-select` `.ui-textarea`
`.ui-help` `.ui-error`; `.ui-check` with `.ui-checkbox` `.ui-radio` `.ui-switch`
`.ui-switch-state`; `.ui-card` (`__header` `__title` `__footer`) `.ui-well` `.ui-stat`;
`.ui-badge` (`--success` `--warning` `--danger` `--info` `--live` `--accent`...) `.ui-dot`
`.ui-count`; `.ui-callout` (`--info` `--success` `--warning` `--danger`); `.ui-tabs` +
`.ui-tab`; `.ui-segmented`; `.ui-table-wrap` + `.ui-table` (`--hover` `--compact`, `td.num`);
`.ui-dialog`; `.ui-drawer` (side sheet); `.ui-menu` + `.ui-menu__item`; `[data-ui-tooltip]`
(`data-ui-tooltip-side="bottom"` near the top); `.ui-progress` `.ui-spinner` `.ui-skeleton`;
`.ui-breadcrumbs`; `.ui-pagination`; `.ui-avatar`; `.ui-chip` (+ `__remove`); `.ui-details`
(accordion); `.ui-fieldset`; `.ui-codeblock` (a `<figure>` holding a
`<figcaption class="ui-codeblock__bar">` and a `<pre>`); `.ui-empty`; `.ui-bubble`; layout
`.ui-stack` `.ui-row` `.ui-grid` `.ui-container` `.ui-spacer` (set `--ui-gap` to change the
gap).

Text: use `.ui-text-secondary` / `.ui-text-tertiary` (or the tokens) for quieter text, and
put rendered markdown in an element with class `ui-markdown`.

Dialogs and toasts (with `ui-components.js` loaded), instead of the browser's unthemed ones:

```js
if (await UIComponents.confirm({ title: 'Delete note?', message: 'This cannot be undone.',
                                 confirmLabel: 'Delete', danger: true })) { /* delete */ }
UIComponents.toast('Saved', { kind: 'success' });   // info | success | warning | danger
const name = await UIComponents.prompt({ title: 'Rename', value: oldName });  // null if cancelled
```

## 6. Rules

Do:

- Build every colour from a token or a `ui-` class; write layout CSS freely.
- Use a lower text tier for quieter text. Labels on an accent fill use `--on-accent`;
  accent-coloured text uses `--text-link`.
- Show on/selected/current states with the classes or with `--selected` + `--on-selected`;
  disabled with `disabled` (the classes then draw a dashed, unfilled control).
- Give every interactive element a visible `:focus-visible` style (the base layer already
  does; do not remove it).
- Serve the folder with `Cache-Control: no-cache` (or content-hash `?v=`).

Do not:

- Write colour literals (`#fff`, `rgb()`, `white`) in the app's CSS or inline styles.
- Redeclare a theme token (`--accent: ...`) in the app. Name app variables with an app prefix
  (`--notes-sidebar-w: 280px`); aliasing a token is fine (`--notes-brand: var(--accent)`).
- Make text quieter with `opacity` or `color-mix()`; it becomes unreadable in the dim themes.
- Name a theme slug or `[data-palette]` in component CSS. Purple is the absence of
  `data-palette`, not a value of it.
- Change a `--z-*` value, or edit anything inside `ui-theme/` (it is replaced on update).
- Enable opt-in themes nobody asked for.

## 7. Charts, canvas and SVG

Canvas and chart libraries cannot read `var()`. Resolve the tokens to `rgb()` colours with
`UITheme.colors()` (or one with `UITheme.color()`) and redraw on change:

```js
function palette() { return UITheme.colors(['--cat-1', '--cat-2', '--cat-3', '--chart-grid', '--text-secondary']); }
chart.update(palette());
UITheme.onChange(() => chart.update(palette()));
```

Inline SVG icons: `fill="currentColor"` / `stroke="currentColor"` so they take the text tier
of their container.

## 8. Verify

1. View the page source: `ui-theme.js` is the first script in `<head>`, the base and
   component layers come before the app's CSS, `ui-theme.css` after it.
2. In the browser console: `UITheme.current()` returns a slug, and
   `UITheme.list().map(t => t.slug)` lists the themes you enabled.
3. Switch through every theme in the picker, including a light one (`paper`, `daylight`):
   no white flash on reload, no unreadable text, no hard-coded colour that stays put.
4. Search the app's own files for colour literals (works in every shell; list the app's CSS
   and template folders at the end):
   ```
   python3 -c "import re,sys,pathlib;[print(p,l.strip()) for a in sys.argv[1:] for p in pathlib.Path(a).rglob('*') if p.is_file() and 'ui-theme' not in p.parts and p.suffix in ('.css','.html','.js','.jsx','.tsx','.vue','.svelte','.jinja','.j2') for l in p.read_text(errors='ignore').splitlines() if re.search(r'#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(',l)]" static templates
   ```
   It should print nothing, or only comments. (`tools/lint_colors.py` in this repository is the
   thorough version.)
5. `python3 static/ui-theme/update.py --check` prints "up to date".

## 9. Keep the convention in the app

Add this line to the app's own `AGENTS.md` or `CLAUDE.md` (create one if missing), so the next
agent working on the app keeps using the theme:

```
UI styling uses ThemeForge 1.0.0 in static/ui-theme/ (read static/ui-theme/README.md before
writing CSS). Every page head carries the theme block from the base template: ui-theme.js first
and blocking, ui-theme-base.css + ui-components.css before the app's CSS, ui-theme.css after it.
Build from its tokens and ui-* classes, never write colour literals, never edit that folder;
update it with `python3 static/ui-theme/update.py`.
```

(Replace `static/ui-theme/` with the folder you used.)

## 10. Updating later

`python3 static/ui-theme/update.py` installs the latest release (`--check` only reports;
`--ref v1.2.0` pins a version). It replaces only the files it owns, leaves the app's own
files in the folder alone, and refuses to overwrite a file that was edited by hand (move the
edit into the app's CSS). Read `CHANGELOG.md` in this repository for what changed, then repeat
step 8. More in `docs/UPDATING.md`.

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Flash of the wrong theme on load | `ui-theme.js` is not first in `<head>`, or is `defer`/`async`/`module`. |
| `UITheme is not defined` | Wrong path, a module script, or code running before the tag. |
| `UIComponents is not defined` | Load `ui-components.js` before the script that uses it (both `defer`). |
| A control looks like a plain browser control | It has no `ui-` class (`ui-btn`, `ui-input`, ...). |
| Picker is empty | No `data-themes` on the script tag, or the `<select>` lacks `data-ui-theme-picker` (or call `UITheme.mountPicker(el)`). |
| A stored theme is ignored | Its slug is not in `data-themes`. |
| Old colours after an update | The folder is cached: serve it `no-cache` or version the URLs. |
| Hydration warning in Next.js | Add `suppressHydrationWarning` to `<html>`. |
| Tailwind `rounded-md` / `font-sans` changed | Expected: the theme defines `--radius-*` and `--font-*`, and its values win. |
| A library reacts to `data-theme` | The runtime sets `<html data-theme>`; see section 3. |
| `update.py` says "edited by hand" | Something changed a file in `ui-theme/`. Move the change into app CSS, then rerun with `--force`. |

## 12. Reference

- `window.UITheme`: `current()`, `theme([slug])`, `list()`, `set(slug)`, `reset()`,
  `onChange(fn)` (returns an unsubscribe; `detail.print` is true for the swap around printing),
  `token(name)`, `tokens(names)` (raw values),
  `color(name)`, `colors(names)` (resolved `rgb()` colours for canvas),
  `mountPicker(selectOrContainer)`, `partner()`, `toggleFamily()`, `version`. The
  `ui-theme-change` event on `document` carries `{slug, theme, previous}`.
- Script tag settings: `data-themes`, `data-default` (slug or `auto`), `data-default-dark`,
  `data-default-light`, `data-storage-key`, `data-families`, `data-print-theme` (`auto`:
  print a dark theme in a light one; a slug; or `none`), `data-legacy-key` + `data-legacy-map`
  (migrate an older setting once), `data-mirror-attr`, `data-fonts-href`.
- Also built in: printing switches to a light theme and hides navigation and toasts; when the
  system asks for more contrast (`prefers-contrast: more`) lines get stronger and the quietest
  text tier steps up; reduced motion stops loops and shortens animations.
- Docs: `docs/TOKENS.md` (every token), `docs/COMPONENTS.md`, `docs/TEXT.md` (text tiers and
  markdown), `docs/THEMES.md` (the themes, and making your own), `docs/INTEGRATIONS.md`,
  `docs/UPDATING.md`.
