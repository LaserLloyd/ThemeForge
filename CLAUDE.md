# CLAUDE.md

**Adding the theme to an app?** Read [`AGENTS.md`](AGENTS.md); it is the whole procedure.

**Working on this repository** (the themes, the runtime, the tools):

- Generated, never edited by hand: `ui-theme/`, `tokens/`, `docs/TOKENS.md`,
  `docs/contrast-report.md`, `docs/theme-template.css`, `docs/images/swatch-*.svg`. Edit `src/`,
  `adapters/`, `tools/update.py` or `GROUP_NOTES` in `tools/sync_theme.py`, then run
  `python tools/sync_theme.py build`.
- Before committing, all of these must pass:
  ```
  python tools/sync_theme.py check
  python tools/check_contrast.py --out contrast.tmp.md   (then delete the file)
  python -m unittest discover -s tests
  python tests/run_browser_tests.py
  ```
- A theme is `src/css/theme-<slug>.css` plus an entry in `src/themes.json`. Start from
  `docs/theme-template.css`. A new theme must pass every floor of its contrast profile.
- Components and the base layer use tokens only (no colour literals; `tools/lint_colors.py`
  checks) and never name a theme slug or `[data-palette]`.
- Never rename or remove a token in a minor release; the token names are the public API.
- Version: `src/themes.json` `version` is the single source; `build` stamps it everywhere.
  Add a `CHANGELOG.md` entry for every release, and keep pinned URLs in the docs on the
  current version (`check` fails otherwise).
- `install` copies the bundle into folders or registered apps on this machine; never run it
  against a folder you were not asked to change.
