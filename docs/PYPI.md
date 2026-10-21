# ThemeForge

ThemeForge is a drop-in CSS theme system for web apps: thirteen colour themes (dark, OLED
black, light and a high-contrast pair, with automatic dark mode), a theme picker, design tokens,
a base element layer, ready-made components and 105 outline icons that take the theme's colours.
Plain CSS and a small script in one folder, `ui-theme/`. No build step, any framework.

This package, the `themeforge` distribution, carries that folder as package data, plus the
`forgeui` Python module (the import name) with a vendoring tool and web-framework helpers.
It has no dependencies and needs Python 3.9 or newer.

## Install

```
pip install themeforge
```

Or straight from a release tag, which is what the repository documents and pins:

```
pip install "themeforge @ git+https://github.com/LaserLloyd/ThemeForge@v1.5.0"
```

## Use

Copy the theme folder into your app from a manifest (`forgeui.json`, written by `init`), and
check in CI that the copy has not drifted:

```
python -m forgeui init --dest static/ui-theme    # writes forgeui.json; edit the themes in it
python -m forgeui vendor                         # copies the folder, every file verified
python -m forgeui vendor --check                 # exit 1 if the copy drifted
```

`forgeui` and `themeforge` are the same command, so `themeforge vendor` works too. The main
helpers, from Python:

```python
import forgeui

forgeui.static_dir()                                   # the bundle folder inside the package
forgeui.head_html(themes=["slate", "paper"], default="slate", storage_key="myapp.theme")
forgeui.head_html_from_manifest("forgeui.json", prefix="/static/ui-theme")   # the <head> tags
forgeui.mount(app, "/static/ui-theme", folder="static/ui-theme")             # FastAPI or NiceGUI
forgeui.quasar_icon("trash")                           # an icon for NiceGUI's icon=
```

## Links

- Source, releases and issues: https://github.com/LaserLloyd/ThemeForge
- Add it to an app, step by step: https://github.com/LaserLloyd/ThemeForge/blob/main/AGENTS.md
- Contract, versioning and the `forgeui.json` manifest: https://github.com/LaserLloyd/ThemeForge/blob/main/docs/THEME_SYSTEM.md
- Components: https://github.com/LaserLloyd/ThemeForge/blob/main/docs/COMPONENTS.md
- Updating and pinning: https://github.com/LaserLloyd/ThemeForge/blob/main/docs/UPDATING.md
- Changelog: https://github.com/LaserLloyd/ThemeForge/blob/main/CHANGELOG.md

## License

MIT-0 (MIT No Attribution): use it any way you like, with nothing to credit or keep. The themes,
the code and the icons are all ThemeForge's own.
