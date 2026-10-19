# CLAUDE.md

**Adding the theme to an app?** Read [`AGENTS.md`](AGENTS.md); it is the whole procedure.

**Working on this repository** (the themes, the runtime, the tools):

- Generated, never edited by hand: `ui-theme/`, `tokens/`, `forgeui/_version.py`, `docs/TOKENS.md`,
  `docs/ICONS.md`, `docs/contrast-report.md`, `docs/theme-template.css`, `docs/images/swatch-*.svg`,
  `docs/images/icons.svg`, and the theme block (between `<!-- themes:start/end -->`) of
  `docs/THEME_SYSTEM.md`. Edit `src/`,
  `adapters/`, `tools/update.py` or `GROUP_NOTES` in `tools/sync_theme.py`, then run
  `python tools/sync_theme.py build`.
- Before committing, all of these must pass:
  ```
  python tools/sync_theme.py check
  python tools/check_contrast.py --out contrast.tmp.md   (then delete the file)
  python -m unittest discover -s tests
  python tests/run_browser_tests.py
  python tools/lint_colors.py ui-theme src
  ```
  (CI also builds the wheel with `python -m build` and runs `tools/selftest_forgeui.py --wheel`.)
- A theme is `src/css/theme-<slug>.css` plus an entry in `src/themes.json`. Start from
  `docs/theme-template.css`. A new theme must pass every floor of its contrast profile.
- Components and the base layer use tokens only (no colour literals; `tools/lint_colors.py`
  checks) and never name a theme slug or `[data-palette]`.
- Never rename or remove a token or an icon in a minor release; their names are the public API.
- Icons: `src/icons/icons.json` plus the unchanged Lucide source in `src/icons/lucide/`. Keep the
  set under 50 (`build` refuses more); components never put emoji in chrome.
- Version: `src/themes.json` `version` is the single source; `build` stamps it everywhere.
  Add a `CHANGELOG.md` entry for every release, and keep pinned URLs in the docs on the
  current version (`check` fails otherwise). Merging a new version to `main` is the release:
  `.github/workflows/release.yml` tags it and publishes the zip and wheel.
- Apps vendor the bundle with `python -m forgeui vendor` (a `forgeui.json` in their own repo);
  `sync_theme.py install` and its machine-local registry are deprecated. Never run either against
  a folder you were not asked to change.
- `docs/THEME_SYSTEM.md` is the index and the contract rules; keep it true when the policy changes.
