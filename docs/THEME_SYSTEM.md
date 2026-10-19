# ForgeUI theme system

ForgeUI is the name of the package: design tokens, themes, components and a vendoring tool for
web UIs. The repository stays `LaserLloyd/ThemeForge`, and **the shipped contract is unchanged by
the name**: the `ui-theme/` folder, `window.UITheme`, every `--token` and every `ui-*` class keep
the names they have had since 1.0.0. This page is the index to all of it, and the place that
says which rules are law. It is the token source of truth in the sense that every other page
(and every consuming app) defers to the rules and sources named here.

## What is true where

When a page disagrees with the source in the second column, the source wins and the page is a bug.

| Fact | Source of truth | Where it is written up |
|---|---|---|
| The theme list, release version, each theme's ground, family, set and contrast profile | [`src/themes.json`](../src/themes.json) | the table below (generated), [THEMES.md](THEMES.md) |
| Token names, groups and Purple's values | [`src/css/theme-base.css`](../src/css/theme-base.css) | [TOKENS.md](TOKENS.md) (generated), [`tokens/*.json`](../tokens/) (W3C design tokens, generated) |
| What each theme sets | `src/css/theme-<slug>.css` | [THEMES.md](THEMES.md), `tokens/<slug>.json` |
| Contrast guarantees | [`tools/check_contrast.py`](../tools/check_contrast.py) | [contrast-report.md](contrast-report.md) (generated, every row of every theme) |
| The icon set, and the emoji each icon replaces | [`src/icons/icons.json`](../src/icons/icons.json) | [ICONS.md](ICONS.md) (generated) |
| Component classes and behaviour | [`src/css/components.css`](../src/css/components.css), [`src/ui-components.js`](../src/ui-components.js) | [COMPONENTS.md](COMPONENTS.md), the [specimen](../specimen/index.html) |
| The runtime and its API | [`src/ui-theme.js`](../src/ui-theme.js), [`src/ui-theme.d.ts`](../src/ui-theme.d.ts) | [INTEGRATIONS.md](INTEGRATIONS.md), [AGENTS.md](../AGENTS.md) |
| What an app receives | [`ui-theme/`](../ui-theme/) (generated, checksummed by `files.json`) | [UPDATING.md](UPDATING.md) |

## The themes

<!-- themes:start -->
Release **1.4.0**: 13 themes sharing 277 tokens (the contract, counting the shared geometry, type and motion tokens).

| Slug | Name | Ground | Set | Family | Contrast profile |
|---|---|---|---|---|---|
| `purple` | Purple | dark | core | `purple` | standard |
| `midnight-gold` | Midnight Gold | OLED | core | `midnight-gold` | standard |
| `glacier` | Glacier | OLED | core | `glacier` | standard |
| `forest` | Forest | OLED | core | `forest` | standard |
| `paper` | Paper | light | core | `paper` | standard |
| `daylight` | Daylight | light | core | `daylight` | standard |
| `slate` | Slate | dark | core | `slate` | standard |
| `high-contrast` | High Contrast | dark | core | `high-contrast` | high |
| `high-contrast-light` | High Contrast Light | light | core | `high-contrast` | high |
| `electric-yellow` | Electric Yellow | dark | opt-in | `electric-yellow` | standard |
| `laserlloyd` | LaserLloyd | dark | opt-in | `laserlloyd` | standard |
| `laserlloyd-light` | LaserLloyd Light | light | opt-in | `laserlloyd` | standard |
| `night-red` | Night Red | OLED | opt-in | `night-red` | night |
<!-- themes:end -->

*Ground* decides `<html data-theme>` (`oled` gives `amoled`). *Set*: core themes are what an app
offers when it does not choose; opt-in themes appear only when an app lists them in
`data-themes`. *Family* pairs a dark and a light theme for `UITheme.toggleFamily()` and for
printing. *Contrast profile* names the floors `check_contrast.py` enforces: `standard`, `high`
(the high-contrast pair: 7:1 text everywhere, solid colours) or `night` (Night Red). Design notes
for each theme, and how to add one, are in [THEMES.md](THEMES.md).

## Token contract rules

1. **Names are the public API.** A token is named for its role, not its look (`--surface-2`,
   `--text-secondary`, `--danger-text`), so a theme can change every value without touching a
   name. Adding a token is a minor release; renaming or removing one is a major release.
2. **Every theme defines every colour token.** A theme that leaves one out inherits Purple's
   value, which is almost never right. Non-colour tokens (spacing, type scale, motion, layers)
   are shared; a theme may set radii, control heights, shell metrics, font stacks and the icon
   stroke, and never a `--z-*` layer.
3. **Apps and components use tokens, never colour literals.** `color: var(--text-primary)`, not
   `#fff`. `tools/lint_colors.py` enforces it on the component layer, and the app checklist in
   [AGENTS.md](../AGENTS.md) enforces it on apps.
4. **Never redeclare a token in app CSS.** Name app variables with an app prefix
   (`--myapp-sidebar-w`); aliasing a token is fine (`--myapp-brand: var(--accent)`).
5. **Quieter text is a lower tier, never `opacity`.** The tiers (`--text-primary`, `-secondary`,
   `-tertiary`, `-disabled`) each carry a contrast floor in every theme; opacity does not.
6. **State reads by shape as well as colour.** On, checked, pressed and current are filled with
   `--selected` (label `--on-selected`); off is an outline; disabled is dashed and unfilled, even
   when on. State comes from native attributes (`disabled`, `checked`, `aria-pressed`,
   `aria-selected`, `aria-current`, `aria-invalid`, `aria-busy`), not from extra classes.
7. **Component CSS never names a theme.** No slug and no `[data-palette]`: Purple is the absence
   of `data-palette`, and a component must work in a theme that does not exist yet.
8. **Icons, not emoji, in app chrome.** A button, tab, menu or status line draws an icon from
   `ui-theme/icons.svg` (`currentColor`, so it takes the theme); emoji are for what people type.
   The set is what the apps draw (an icon is added when an app needs one and nothing already
   means it; the build caps it at 120); an icon name is public API like a token name.
9. **Contrast is a gate, not a goal.** Every theme passes every row of its profile in
   `check_contrast.py` before it ships; CI fails otherwise. The floors are listed at the top of
   [TOKENS.md](TOKENS.md).

### Accessibility and language

WCAG 2.2 AA is the baseline: contrast (above), a visible `:focus-visible` ring from tokens,
labels and ARIA on custom controls, `prefers-reduced-motion` honoured by every animation, a
24px minimum target (`--control-h-sm` is never smaller), and a dedicated high-contrast pair for
people who need more. The layer uses logical properties throughout, so it works right-to-left,
and `tests/runtime.html` checks a right-to-left page and long pseudo-translated words (at 320px
wide) for overflow. Every word the JavaScript helpers put on the page is in a string table
(`UIComponents.setStrings`, `loadLocale`, `data-ui-str-*`), with `locales/en.json` and
`locales/ja.json` shipped; see [COMPONENTS.md](COMPONENTS.md#words-and-languages).

### Microcopy rules

- **Buttons are verbs:** Save, Delete job, Copy, not OK or Submit. A destructive button names
  what it destroys.
- **No jargon in Basic settings.** Say what the setting does and what changes; keep terms of art
  for settings marked Advanced.
- **An error says what happened, why, and what to do:** "Could not save: the port 80 is in use.
  Pick another port or stop the program using it."
- **An empty state says what is missing and offers the next step** in its actions slot.
- **Sentence case, no trailing full stops on labels, and no text baked into images.**

## Public API and compatibility policy

The public API is everything an app can depend on:

- the `ui-theme/` folder and the names of its files, and `files.json` and `VERSION` (`ThemeForge
  <version> <hash>`);
- `window.UITheme` and `window.UIComponents` and their methods and options, the `ui-theme-change`
  event, and the `data-*` settings on the `ui-theme.js` and `ui-components.js` script tags;
- every `--token` of the contract, every `ui-*` class and its `__part` and `--variant` names, the
  state attributes components read (`data-level`, `data-source`, `data-default`, `data-state`,
  `data-copied`, ...), `[data-palette]`, `<html data-theme>` and `<html data-contrast-profile>`;
- theme slugs, icon names (the `<symbol>` ids of `icons.svg`), and the keys of `locales/*.json`;
- the `forgeui` Python package (`static_dir`, `head_html`, `head_html_from_manifest`, `mount`),
  the `python -m forgeui` commands and flags, and the `forgeui.json` schema.

Not public: the bytes of any generated file, the hash in a header, selectors that are not a
documented class, tokens a theme file defines outside the contract, and the internals of
`update.py` and `forgeui.vendor`.

Versions follow [Semantic Versioning](https://semver.org/):

| Release | What may change |
|---|---|
| **Major** | Renaming or removing a token, class, API, file, theme slug, icon or locale key; changing what a token means; an incompatible `forgeui.json` change; dropping a supported Python version. Also the point where deprecated things are removed, and where the `ThemeForge` stamp in `VERSION` may become `ForgeUI`. |
| **Minor** | Adding a token (defined in every theme), a theme, a component class, an icon, an emoji mapping, a string key, a command or flag, an adapter. Nothing an app uses changes. |
| **Patch** | Fixes, value tweaks that keep every contrast floor passing, documentation. |

Deprecations are announced in [CHANGELOG.md](../CHANGELOG.md) and, where there is a command, by a
message on stderr, and last at least one minor release before a major removes them
(`sync_theme.py install` is the current example: deprecated in 1.2.0, replaced by
`forgeui vendor`). The current major is the supported one. An app pins the bundle with the
`version` of its `forgeui.json` (`"1.2"` accepts 1.2.x), so a new minor is a deliberate change.

## Distribution and vendoring

One folder is the whole contract, so every route ends in "this folder, byte for byte, in the app":

| Route | For | How |
|---|---|---|
| **`forgeui` wheel** (primary) | Python apps (FastAPI, NiceGUI, Flask, Django) and any repo that can run `pip` in dev | `pip install` from a release tag (not PyPI; see Procedure); `python -m forgeui vendor` copies the folder into the repo; `forgeui.head_html()` and `forgeui.mount(app)` wire it |
| **Release zip** | AI agents, offline machines, CI caches | Every [GitHub release](https://github.com/LaserLloyd/ThemeForge/releases) carries `ThemeForge-<version>.zip` (the bundle, `AGENTS.md`, the docs, tokens and examples); [`releases/latest/download/ThemeForge.zip`](https://github.com/LaserLloyd/ThemeForge/releases/latest/download/ThemeForge.zip) is always the newest. `python -m forgeui vendor --source ThemeForge-1.4.0.zip` vendors from it (it also takes a wheel, a repo archive or an unpacked folder) |
| **`ui-theme/update.py`** | Apps with no `pip` | `python ui-theme/update.py` fetches the latest release from GitHub |
| **jsDelivr** | Prototypes, single HTML files | `https://cdn.jsdelivr.net/gh/LaserLloyd/ThemeForge@v1.4.0/ui-theme/ui-theme.css`, pinned, never `@main` |

There is no JavaScript build step in any route. Releasing is merging: when `src/themes.json` on
`main` names a version with no tag yet, `.github/workflows/release.yml` runs the checks, builds
the zip (`tools/release_zip.py`) and the wheel, and publishes the release, which creates the tag.

### The manifest: `forgeui.json`

Each consuming repository keeps a `forgeui.json` at its root. It is the only place the app's
theme choice lives (it replaces the same list copied into Python, HTML and JavaScript).

```json
{
  "dest": "frontend/static/ui-theme",
  "version": "1.2",
  "adapters": ["quasar"],
  "extra_files": { "adapters/myapp-extra.css": "frontend/overlays/myapp-extra.css" },
  "settings": { "themes": ["slate", "high-contrast", "high-contrast-light"], "default": "slate", "storage_key": "myapp.theme" }
}
```

| Key | Meaning |
|---|---|
| `dest` | Where the repo keeps its copy, relative to the manifest. Required. It must be the `ui-theme` folder itself, not its parent. |
| `version` | The bundle versions this app accepts: `1.2.3` exact, `1.2` any patch, `1` any minor. `--version` overrides it for one run. |
| `adapters` | Adapter families to ship (`quasar`, `tailwind`, `tailwind-v3`). Omit for all, `[]` for none. |
| `extra_files` | App-owned overlays copied beside the bundle: target inside `dest` to a source file in the repo. |
| `settings` | `themes`, `default` (a slug or `auto`), `default_dark`, `default_light`, `storage_key`. Checked against the bundle's theme list. |

### Procedure

1. Install: `pip install "forgeui @ git+https://github.com/LaserLloyd/ThemeForge@v1.4.0"` (a dev dependency is
   enough; pin it in the lockfile). The wheel is not on PyPI: the name `forgeui` there belongs to an
   unrelated project, so never run a bare `pip install forgeui`.
2. `python -m forgeui init --dest static/ui-theme`, then edit `forgeui.json`.
3. `python -m forgeui vendor`. It verifies every file against the bundle's `files.json` before it
   writes, replaces only files the bundle owns, removes files the new bundle dropped, leaves your
   own files alone, and writes `VERSION` last, so a copy that stopped half way never claims the new
   version. Commit the folder and the manifest.
4. Wire the page head: `forgeui.head_html_from_manifest("forgeui.json", prefix="/static/ui-theme")`
   returns the tags in the required order (runtime first and blocking, base and component layers,
   your CSS, then the tokens), or `python -m forgeui head` prints them for a static template. Serve the
   folder with `Cache-Control: no-cache`; `forgeui.mount(app, "/static/ui-theme", folder="static/ui-theme")` does
   this for FastAPI and NiceGUI (without `folder` it serves the installed package, which lacks your overlays).
5. Guard it: run `python -m forgeui vendor --check` in CI and in a unit test. It exits 1 when the
   version, a file or an overlay drifted, or when the settings name a theme the bundle lacks.
6. Update: raise the pin, `python -m forgeui vendor`, read the diff and the
   [CHANGELOG](../CHANGELOG.md), run the app's tests, commit.

Rules the tool enforces: a bundle file edited by hand is never overwritten without `--force`
(the bundle is replaced whole; move the edit into the app's own CSS first); overlays are files of
their own under app-owned names (`adapters/<app>-extra.css`) and are **never appended into a
bundle file**, which is what kept `files.json` from verifying a copy before 1.2.0; and a source
that fails verification is refused before anything is written.

### Migrating from the machine-local app registry

Before 1.2.0 `sync_theme.py install --apps <folder>` copied the bundle into apps listed in a
`<app>.json` registry kept outside every repository, which nobody else could reproduce. That
command still works and prints a deprecation message. To migrate an app once: copy its
`bundle_dir` to `dest`; give each `extra_files` entry a source file inside the app's repo (an
`append` entry becomes an overlay file of its own with an app-owned name, loaded after the adapter
it extended); move the app's theme list, default and storage key into `settings`; then run
`python -m forgeui vendor --force` once (the first run replaces a copy whose adapter was appended
to) and `--check` from then on.

## Where to read next

- [TOKENS.md](TOKENS.md): every token, by group, with the contrast floors (generated)
- [THEMES.md](THEMES.md): each theme's design, the high-contrast pair, making your own
- [COMPONENTS.md](COMPONENTS.md): every component with markup, the JavaScript helpers, words and languages
- [TEXT.md](TEXT.md): text tiers and the markdown style
- [INTEGRATIONS.md](INTEGRATIONS.md): Flask, FastAPI, Django, Vite, React, Vue, Svelte, NiceGUI, Tailwind, Electron
- [UPDATING.md](UPDATING.md): updating, pinning, caching, what the checksums prove
- [contrast-report.md](contrast-report.md): every contrast row of every theme (generated)
- [`tokens/`](../tokens/): every theme's values as W3C design tokens, for design tools
- [CONTRIBUTING.md](../CONTRIBUTING.md): working on the repository itself
