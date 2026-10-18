# ThemeForge

ThemeForge is a drop-in CSS theme system for web apps that an AI coding agent installs in
one step: thirteen colour themes (dark, OLED black, light, a neutral default and a high-contrast
pair, with automatic dark mode from the OS setting), a theme picker, design tokens, a base element layer, text standards and
ready-made component classes, MIT licensed. Plain CSS and a small script in one folder,
`ui-theme/`. No build step, no dependencies, any framework. The package is called **ForgeUI**
(a `pip`-installable wheel, `forgeui`); the repository, the `ui-theme/` folder and every token and class keep
the ThemeForge names, so nothing an app depends on changes with the name.

![On, off, selected and disabled controls in every theme](docs/images/gallery.png)

See every component in every theme in [`specimen/index.html`](specimen/index.html) (serve the
repository with `python3 -m http.server` and open `/specimen/`).

**Using an AI agent?** Point it at [`AGENTS.md`](AGENTS.md): "Add ThemeForge to this app
following AGENTS.md in https://github.com/LaserLloyd/ThemeForge".

## Quick start

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

Then, in every page's `<head>`:

```html
<script src="/static/ui-theme/ui-theme.js"
        data-themes="purple,midnight-gold,glacier,forest,paper,daylight"
        data-default="auto" data-default-dark="midnight-gold" data-default-light="daylight"
        data-storage-key="myapp.theme"></script>
<link rel="stylesheet" href="/static/ui-theme/ui-theme-base.css">
<link rel="stylesheet" href="/static/ui-theme/ui-components.css">
<!-- your stylesheets -->
<link rel="stylesheet" href="/static/ui-theme/ui-theme.css">
```

and a picker wherever you like: `<select data-ui-theme-picker aria-label="Theme"></select>`.
Build with tokens (`var(--surface-2)`, `var(--text-secondary)`) and classes
(`ui-btn ui-btn--primary`, `ui-card`, `ui-switch`). Full guide: [`AGENTS.md`](AGENTS.md).

Works in current Chrome, Edge, Firefox and Safari (2024 or newer).

### With pip (ForgeUI)

For Python apps (FastAPI, NiceGUI, Flask, Django) the folder is also a wheel, and a manifest in
your repository says which copy you hold, so the copy can be checked in CI:

```
pip install "forgeui @ git+https://github.com/LaserLloyd/ThemeForge@v1.2.0"   # from the release tag; see the note below
python -m forgeui init --dest static/ui-theme   # writes forgeui.json: your themes, default, storage key
python -m forgeui vendor                        # copies the folder, verified against its checksums
python -m forgeui vendor --check                # exit 1 when the copy drifted (CI, a unit test)
```

```python
import forgeui
forgeui.mount(app, "/static/ui-theme")          # FastAPI or NiceGUI: serves the folder, no-cache
head = forgeui.head_html_from_manifest("forgeui.json", prefix="/static/ui-theme")   # the <head> tags
```

How the manifest, versions and overlays work: [`docs/THEME_SYSTEM.md`](docs/THEME_SYSTEM.md).

The wheel is **not on PyPI**: the name `forgeui` there belongs to an unrelated project, so a bare
`pip install forgeui` installs the wrong package. Install from the release tag as above (pip builds
the wheel from the repository; it needs `git`), or from a wheel you built with `python -m build`.

Prefer not to install anything? For a prototype, load the files from jsDelivr:
`https://cdn.jsdelivr.net/gh/LaserLloyd/ThemeForge@v1.2.0/ui-theme/ui-theme.js` (and the
same path for each CSS file).

## Preview in Docker

ThemeForge is a CSS package you copy into your own app (see Quick start). The container only serves the
specimen page, so you can see every component in every theme without installing anything.

    git clone https://github.com/LaserLloyd/ThemeForge.git && cd ThemeForge    # or: git pull
    docker compose -f deploy/compose/compose.yml up -d
    # open http://127.0.0.1:8185/   (redirects to /specimen/)

| Port | What |
|---|---|
| 8185 (host) -> 8080 (container) | the specimen preview, published on 127.0.0.1 only by default |

Optional environment: `HOST_PORT` (8185), `BIND_ADDR` (127.0.0.1), `IMAGE`, `VERSION`, `MEM_LIMIT`, `CPU_LIMIT`.
The image is stateless (nginx-unprivileged, read-only root, no volumes), so there is nothing to back up and
`docker compose down -v` cannot lose anything. Theme edits need `up -d --build`. To use ThemeForge in an app,
follow Quick start instead; details are in [docs/deploy/docker.md](docs/deploy/docker.md).

## Themes

| | Theme | Kind | |
|---|---|---|---|
| ![](docs/images/swatch-purple.svg) | Purple | dark | Violet accent and soft lavender text on deep indigo. The base theme. |
| ![](docs/images/swatch-midnight-gold.svg) | Midnight Gold | OLED | Warm gold on true black. |
| ![](docs/images/swatch-glacier.svg) | Glacier | OLED | Ice-blue text on true black with a deep teal accent. |
| ![](docs/images/swatch-forest.svg) | Forest | OLED | Pale sage and lichen with bark browns on true black. |
| ![](docs/images/swatch-paper.svg) | Paper | light | Warm parchment, ink-brown text, a serif for prose. |
| ![](docs/images/swatch-daylight.svg) | Daylight | light | Clean white with a blue accent. |
| ![](docs/images/swatch-slate.svg) | Slate | dark | The neutral professional default: grey-blue, steel accent, dense but calm. |
| ![](docs/images/swatch-high-contrast.svg) | High Contrast | dark | White on black, yellow actions, 7:1 text, solid colours. |
| ![](docs/images/swatch-high-contrast-light.svg) | High Contrast Light | light | Black on white, blue actions, 7:1 text, solid colours. |
| ![](docs/images/swatch-electric-yellow.svg) | Electric Yellow | dark, opt-in | Acid yellow on graphite. |
| ![](docs/images/swatch-laserlloyd.svg) | LaserLloyd | dark, opt-in | Laser blue on graphite; pairs with LaserLloyd Light. |
| ![](docs/images/swatch-laserlloyd-light.svg) | LaserLloyd Light | light, opt-in | The light partner of LaserLloyd. |
| ![](docs/images/swatch-night-red.svg) | Night Red | OLED, opt-in | Low blue light: ember text on black, zero blue in any colour. |

The first nine are the core set an app offers by default; the opt-in four appear only when an
app lists them. Every theme passes a contrast audit
([`docs/contrast-report.md`](docs/contrast-report.md)): body text at 7:1, secondary text at
4.5:1 on every surface, control edges and on/off states at 3:1. On, selected and disabled
states read by shape as well as colour in every theme. More in
[`docs/THEMES.md`](docs/THEMES.md), including how to add your own theme.

## What is in the folder

| File | |
|---|---|
| `ui-theme.js` | the runtime: applies the saved theme before first paint, follows the OS light/dark setting with `data-default="auto"`, fills pickers, syncs tabs, exposes `window.UITheme` |
| `ui-theme-base.css` | element defaults, focus ring, scrollbars, reduced motion, text tiers, `.ui-markdown`, highlight.js colours |
| `ui-components.css` | buttons, fields, checkboxes, radios, switches, cards, badges, callouts, tabs, segmented controls, tables, dialogs, menus, tooltips, toasts, progress, code blocks, an app shell |
| `ui-theme.css` | the tokens of all thirteen themes (about 20 KB gzipped) |
| `ui-components.js` | optional: themed `confirm()`, `alert()`, `prompt()` and toasts, copy-to-clipboard, inline validation, settings rows, translatable words (`locales/`) |
| `locales/` | the words `ui-components.js` shows, in English and Japanese |
| `adapters/` | NiceGUI/Quasar, Tailwind CSS v4 and v3 |
| `update.py` | installs and updates the folder, checking every file (apps without pip); `python -m forgeui vendor` does the same from a manifest |
| `ui-theme.d.ts` | TypeScript declarations for `window.UITheme` and `window.UIComponents` |
| `themes.json`, `VERSION`, `files.json`, `README.md` | the theme list, version, checksums, and usage notes |

## Documentation

- [`AGENTS.md`](AGENTS.md): add the theme to an app, step by step (for agents and people)
- [`docs/THEME_SYSTEM.md`](docs/THEME_SYSTEM.md): the index: token contract rules, the themes, the versioning policy and how to vendor the folder
- [`docs/TOKENS.md`](docs/TOKENS.md): every token, by group
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md): every component class, with markup
- [`docs/TEXT.md`](docs/TEXT.md): text tiers and the markdown style
- [`docs/THEMES.md`](docs/THEMES.md): the themes, their design notes, and adding a theme
- [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md): Flask, FastAPI, Django, Vite, React/Next.js, Vue, Svelte, NiceGUI, Tailwind, Electron
- [`docs/UPDATING.md`](docs/UPDATING.md): updates, pinning, caching, what the checksums prove
- [`examples/`](examples/): a static page and a FastAPI + Jinja app
- [`tokens/`](tokens/): every theme's values as W3C design tokens (DTCG JSON), for design tools
- [`CONTRIBUTING.md`](CONTRIBUTING.md): working on the themes themselves

Open [`specimen/index.html`](specimen/index.html) through any local web server
(`python3 -m http.server`, then `/specimen/`) to see every component in every theme.

## Used by

- [StudioForge](https://github.com/LaserLloyd/StudioForge): a GPU LLM server over llama.cpp
  with an OpenAI-compatible API and a web dashboard
- [ClawForge](https://github.com/LaserLloyd/ClawForge): an image-generation gateway that puts
  a local ComfyUI behind an MCP server and a web GUI
- [DisPatch](https://github.com/LaserLloyd/DisPatch_Chat): self-hosted chat for a household
  and its AI agents

## Read more

- [ThemeForge: a drop-in CSS theme system an AI agent installs in one step](https://www.laserlloyd.com/projects/themeforge-a-drop-in-css-theme-system-an-ai-agent-installs-in-one-step/),
  the article on how it was built and why
- [laserlloyd.com](https://www.laserlloyd.com/): the other projects

## License

MIT, see [`LICENSE`](LICENSE). The font stacks name Inter, JetBrains Mono, Space Grotesk and
Archivo (all under the SIL Open Font License); none are bundled, and every stack falls back to
system fonts.
