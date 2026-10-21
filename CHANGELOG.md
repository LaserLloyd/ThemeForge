# Changelog

Versions follow [Semantic Versioning](https://semver.org/). A release is a git tag `vX.Y.Z`;
`ui-theme/VERSION` and `UITheme.version` carry the same number. Token names are the public
API: removing or renaming one is a major version.

## 1.5.0

**License: MIT-0.** ThemeForge is now [MIT No Attribution](LICENSE): apps can use, copy, change and
ship any of it with no conditions, and nothing has to be credited or kept. Up to 1.4.0 it was MIT,
which asks every copy to keep the notice, and 1.3.0 and 1.4.0 also carried Lucide's icons under ISC
(with a notice of its own and Feather's MIT notice for some icons).

- **The icons are ThemeForge's own.** All 105 are redrawn for ThemeForge on the same 24px grid with
  a 2px round stroke, under the same names, so every `icons.svg#name`, `UIComponents.icon()`,
  `iconFor()` and `forgeui.quasar_icon()` call keeps working; the drawings change, the API does not.
  The sources live in `src/icons/svg/`; the Lucide files are gone.
- `ui-theme/icons-LICENSE.txt` stays (it is a bundle file) and now says the icons are MIT-0 like the
  rest, with no conditions. `pyproject.toml` declares `MIT-0`, and the Docker image label too.
- A test fails the build if an icon source looks copied from another set, and `docs/ICONS.md` says
  how to draw a new one.

## 1.4.0

The icon set grows from 48 to 105 so it covers what the LaserLloyd apps draw today. An audit of
DisPatch (Chat and Voice), MailForge, StudioForge, ChatForge, CrucibleForge, ClawForge,
SpeechForge, InfoForge and TransForge found 57 icons they use (as emoji, Material Icons names or
hand-drawn SVG) that the set did not have. Nothing is removed or renamed.

- **57 icons added**, all Lucide 1.50.0: `activity` `archive` `arrow-down` `arrow-right`
  `arrow-up` `arrow-up-down` `ban` `book-open` `brain` `camera` `chevron-left` `chevron-up`
  `circle-question-mark` `clipboard-list` `clock` `cloud-off` `code` `cpu` `database`
  `ellipsis-vertical` `eraser` `eye` `eye-off` `flag` `flask-conical` `gauge` `grip-vertical`
  `history` `image-off` `inbox` `key` `life-buoy` `list` `list-checks` `lock-open` `mail`
  `mail-open` `maximize-2` `messages-square` `moon` `music` `pause` `pin` `power` `reply` `save`
  `shield` `shield-alert` `shield-check` `sliders-horizontal` `smartphone` `sun` `tag` `target`
  `undo-2` `unlink` `user-plus`. The sprite is 33 KB (5 KB gzipped).
- **Material Icons names:** every icon lists the Material names that mean it (223 in all), in
  `icons.json` and the table in [`docs/ICONS.md`](docs/ICONS.md), for the NiceGUI apps.
- **`forgeui.quasar_icon(name, prefix="/theme")`** returns Quasar's `svguse:` string for an icon,
  from its name or a Material name it lists: `ui.button(icon=forgeui.quasar_icon('delete_forever'))`
  draws `trash` from the sprite (checked against the Quasar that NiceGUI 3.18 ships).
- **Emoji map:** 263 emoji and symbols (from 164). These now name the closer new icon: ✉📧📨📩📮
  `mail` (was `send`), 📥📬 `inbox`, 📷📸 `camera` (was `image`), ⬆ ⬇ `arrow-up`/`arrow-down` (were
  `upload`/`download`), ◂◀‹❮ `chevron-left` (was `arrow-left`), ⋮ `ellipsis-vertical`, 🗄
  `database` and 🗃📦 `archive` (were `folder`/`puzzle`), 📋 `clipboard-list`, 📖📚 `book-open`,
  🔑🗝 `key` and 🛡 `shield` (were `lock`), 🎛🎚 `sliders-horizontal` (was `wrench`), ⛔🚫 `ban`
  (was `circle-x`).
- **Policy:** the set holds what the apps draw rather than a fixed count: an icon is added when an
  app needs one and no icon already means it, and the build refuses more than 120.

## 1.3.0

Icons, so apps stop using emoji as icons. Nothing is removed or renamed.

**Icons** ([`docs/ICONS.md`](docs/ICONS.md))

- **`ui-theme/icons.svg`**: 48 outline icons from [Lucide](https://lucide.dev) 1.50.0 (ISC; the
  notice ships as `ui-theme/icons-LICENSE.txt`), one sprite of 15 KB (3 KB gzipped). Use:
  `<svg class="ui-icon" aria-hidden="true"><use href="/static/ui-theme/icons.svg#settings"/></svg>`.
  They draw in `currentColor` with the theme's stroke weight, so every theme colours them. The set
  covers app chrome (actions, navigation, status, areas, people and AI, system, media,
  reactions) and stays under 50; icon names are public API like token names.
- **`.ui-icon`** (1.25em, or `--sm` 16px, `--md` 20px, `--lg` 24px, or `--ui-icon-size`) with colour
  modifiers `--muted`, `--accent`, `--success`, `--warning`, `--danger`, `--info`.
- **Emoji, three ways:** as an icon (an emoji in app chrome becomes the outline icon it stands
  for), as text (`.ui-emoji`: a typed emoji in the text colour, text presentation), or in colour
  (`.ui-emoji--color`: native colours, toned by the theme's `--media-filter`, so Night Red keeps
  them red).
- **`ui-components.js`:** `UIComponents.icon(name, { label, size })`, `UIComponents.iconFor('🗑️')`
  (the icon an emoji or symbol stands for: 164 mapped, e.g. ⚙ 🗑 📁 ✅ ❌ ✕ ▸ ☰),
  `UIComponents.icons()`, `UIComponents.emojify(element, 'icon' | 'text' | 'color')`, and
  `data-ui-emoji="..."` on an element to do it on load. The sprite is found next to the script
  (`data-icons` overrides); on another origin (the CDN) it is fetched once and inlined, because
  `<use>` cannot cross origins. `ui-theme.d.ts` types the icon names.
- **`ui-theme/icons.json`**: the names, labels, uses and emoji map, for server-side templates
  and agents.

**Tokens** (added in every theme)

- `--icon-stroke` (2; 2.5 in the high-contrast pair and under `prefers-contrast: more`).
- `--font-emoji`: a monochrome-first stack (Noto Emoji, then system symbol fonts) for `.ui-emoji`.

**Releases**

- **Merging a version bump to `main` is the release.** `.github/workflows/release.yml` checks the
  tree, builds the release zip and the wheel, and publishes a GitHub release with the tag, so
  `update.py`'s "latest" (the tag that `main` names) always exists.
- **`ThemeForge-<version>.zip`** (`tools/release_zip.py`): the bundle, `AGENTS.md`, the docs, tokens
  and examples, for handing to an AI agent or an offline machine.
  `https://github.com/LaserLloyd/ThemeForge/releases/latest/download/ThemeForge.zip` is always
  the newest.

## 1.2.0

The package is now called **ForgeUI** (the repository stays ThemeForge, and the shipped
contract is unchanged: the `ui-theme/` folder, `window.UITheme`, every `--token` and every
`ui-*` class keep their names, and `VERSION` still reads `ThemeForge <version> <hash>`).
Nothing is removed or renamed. The index of the rules is the new
[`docs/THEME_SYSTEM.md`](docs/THEME_SYSTEM.md).

**Distribution**

- **`forgeui` Python package** (`pyproject.toml`, a pure-data wheel, standard library only,
  Python 3.9 or newer): the `ui-theme/` bundle as package data, plus `forgeui.static_dir()`,
  `forgeui.head_html()` (the head tags in the required order, with `?v=` hashes, adapters,
  overlays and a CSP nonce), `forgeui.head_html_from_manifest()` and `forgeui.mount(app)` for
  FastAPI and NiceGUI. CI builds the wheel and sdist (`python -m build`, `twine check`) on Linux
  and Windows and vendors the examples with the built wheel. Not on PyPI yet: the name `forgeui`
  there belongs to an unrelated project, so the docs install from the release tag
  (`pip install "forgeui @ git+...ThemeForge@v1.2.0"`) until the distribution is renamed or published.
- **`python -m forgeui vendor [--version X] [--check] [--force] [--source <zip|folder>]`**, driven
  by a `forgeui.json` manifest kept in each app's own repository (`dest`, `version`, `adapters`,
  `extra_files`, `settings`): verifies `files.json` before writing, refuses to overwrite
  hand-edited files, writes `VERSION` last, and `--check` exits 1 on drift (version, stale,
  edited or missing files, changed overlays, settings that name a theme the bundle lacks).
  Overlays live under app-owned names and are never appended into bundle files. `init` writes a
  starter manifest and `head` prints the head tags.
- **Deprecated:** `sync_theme.py install` and its machine-local app registry (`--apps`,
  `UI_THEME_APPS`). Both still work and print a message; the next major version removes them.
  `update.py` is unchanged and still the route for apps without pip.

**Components** (CSS in `ui-components.css`, behaviour in `ui-components.js`)

- **Settings row** `.ui-settings` / `.ui-setting`: label, description, control, a reset-to-default
  button that appears only while the value differs, a Basic/Advanced marker
  (`data-level`, with `data-level-filter="basic"` on the group) and a "set by environment" badge
  that locks the control (`data-source="env"`). `UIComponents.setting(row, { default, onReset })`.
- **Copy field** `.ui-copy` and `UIComponents.copy(el | string)`: clipboard API on secure
  contexts, hidden-textarea `execCommand` fallback on plain `http://` pages, "Copied" feedback and
  a polite announcement. `.ui-codeblock__button` now copies the code too.
- **Inline validation** `UIComponents.validate(field, message, { focus, announce })`:
  `aria-invalid`, a `.ui-error` after the control, `aria-describedby` and a live-region
  announcement; an empty message clears it.
- **Progress with cancel** `.ui-progress-row` (label, value, detail and a cancel slot;
  `data-state` for how a finished row ended), and an **empty-state action slot**
  (`.ui-empty__actions`, `__desc`, `__icon`).
- `.ui-visually-hidden`, and `.ui-error:empty` is hidden.

**Themes**

- **`high-contrast` (dark) and `high-contrast-light`:** a dedicated pair with the new `high`
  contrast profile: 7:1 for every text colour (tiers, links and hover, status text, labels on
  fills, syntax, narrative roles), 4.5:1 for edges, the focus ring, state indicators and chart
  colours, 3:1 for every line, status hues far apart, and an opacity audit that fails any
  translucent colour token (the media scrim and canvas overlays are exempt). Surfaces, strokes,
  glows and the scrim are solid, shadows are zero-size and the focus ring is 3px.
- **`slate`:** a neutral grey-blue "professional default" with a steel accent, muted status
  colours and denser geometry (radii 3 to 12px, controls 26, 32 and 40px).
- All three are core themes; `<html data-contrast-profile>` can now be `high`
  (the TypeScript declarations list it).

**i18n and accessibility of the helpers**

- A string table for every word the JavaScript puts on the page (`UIComponents.setStrings`,
  `strings`, `t`, `resetStrings`), `loadLocale('ja')` and `data-locale="auto"` on the script tag,
  `data-ui-str-<key>` attribute overrides on any element, `{placeholder}` filling, and Intl
  `formatNumber` / `formatDate` in the page's language.
- `ui-theme/locales/en.json` and `ja.json`.
- `tests/runtime.html` now checks long pseudo-translated words at 800px and 320px for overflow,
  and a right-to-left page; unit tests check that every language has every key.

**Fixes**

- `python -m forgeui --help` and `--version` answer even when the bundle folder is missing (they
  say `bundle missing` instead of raising).
- `sync_theme.py check` (and two unit tests) no longer fail on a clean checkout: sibling
  `LaserLloyd/*` links are allowed in a "Used by" section (a link to the archived UnifyingTheme
  there, or a sibling link anywhere else, is still rejected).
- `check` now also verifies that `docs/THEME_SYSTEM.md` lists exactly the themes of
  `src/themes.json`, and `build` regenerates that list.

## 1.1.2

- Forest: `--cta-gradient` starts from a lighter step of its green accent and `--notify` is
  the pale lichen of its focus ring. 1.1.0 had carried the stops of an earlier brown Forest.

## 1.1.1

- `install` and `update.py` accept a copy whose `VERSION` reads `ui-theme <date> <hash>`, the
  stamp the drop-in folder carried before the first release, instead of refusing it as "not
  a ui-theme folder".

## 1.1.0

Three tokens every theme now defines, and the runtime says which contrast profile is on.
Nothing is removed or renamed.

- **`--cta-gradient`:** the gradient fill for a primary call to action, from the hover step
  to the resting step (a background image only; its label still uses `--on-cta`). Core
  themes carry the gradient DisPatch shipped with; opt-in themes derive theirs.
- **`--notify` and `--notify-idle`:** the unread indicator, solved as a pair against the
  rail and sidebar grounds: `--notify` at 4.5:1 or better on `--surface-0` and `--surface-1`,
  `--notify-idle` at no more than 3:1 there, and the two at least 3:1 apart. The contrast
  checker enforces all three (the idle rule is its first ceiling).
- **`<html data-contrast-profile="standard|night">`:** set by the runtime next to
  `data-theme`, so component CSS can adapt to a night theme without naming a slug;
  `UITheme.theme()` carries `contrastProfile` and the TypeScript declarations list it.
- **Mono font stacks:** `SFMono-Regular` and `Menlo` dropped from every `--font-mono`.
  `ui-monospace` already covers Apple, and on Linux fontconfig maps both names to a
  proportional sans, so code rendered proportionally there.
- **`sync_theme.py install`:** writes each copy's `VERSION` last, so a copy that failed
  partway never reads as current; when every registered app was skipped it says so and
  exits 1 instead of printing "installed" after writing nothing.

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
