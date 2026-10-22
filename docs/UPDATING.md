# Updating

An app holds a copy of `ui-theme/` and never edits it, so updating is replacing the copy.
Two tools do that safely, with the same guarantees (verified files, no overwriting of hand edits):
`python -m forgeui vendor` for repositories that keep a `forgeui.json` (the `themeforge` package; see
[THEME_SYSTEM.md](THEME_SYSTEM.md)), and `ui-theme/update.py` for apps without pip.

## With the Python package

```
pip install --upgrade "themeforge @ git+https://github.com/LaserLloyd/ThemeForge@v2.0.1"   # the release your forgeui.json accepts (from the tag until it is on PyPI)
python -m forgeui vendor                      # write the new copy (VERSION last)
python -m forgeui vendor --check              # CI: exit 1 when the copy drifted
python -m forgeui vendor --source ThemeForge-2.0.1.zip   # offline: a release zip, wheel, archive or folder
```

`--check` fails on a different version, a stale, edited or missing file, a missing or changed
overlay, or settings that name a theme the bundle does not have. A hand-edited bundle file is
refused unless you pass `--force`: move the edit into an overlay (`extra_files`, e.g.
`adapters/<app>-extra.css`) first. Overlays are never appended into bundle files.

### Moving from 1.x to 2.0

The distribution is now `themeforge`, and two edits go together: the install requirement changes
its name from `forgeui @ git+…` to `themeforge @ git+…@v2.0.1`, and `"version"` in `forgeui.json`
changes to `"2.0"` (a `1.x` pin refuses a 2.0 bundle). Keep the old name with the new tag and pip
or uv refuses the tree:

```
uv:   Package metadata name 'themeforge' does not match given name 'forgeui'
pip:  .dist-info directory 'themeforge-2.0.0.dist-info' does not start with 'forgeui'
```

That error means "rename the requirement", not "the tag is broken". Swap the package once:
`pip uninstall forgeui`, then the install line above, then the `"version"` change and `vendor`.
Nothing in the bundle is renamed. `sync_theme.py install` is gone; an app it used to update gets a
`forgeui.json` (`python -m forgeui init --dest static/ui-theme`) or uses `update.py` below.

If `pip uninstall forgeui` ran after `themeforge` was installed, it deleted files both packages
share. Then `python -m forgeui` fails with `No module named forgeui.__main__` while `pip list` shows
`themeforge 2.0.0`. Recover with:

```
pip install --force-reinstall "themeforge @ git+https://github.com/LaserLloyd/ThemeForge@v2.0.1"
```

## With update.py

```
python3 static/ui-theme/update.py            # install the latest release
python3 static/ui-theme/update.py --check    # report only; exits 1 when an update exists
python3 static/ui-theme/update.py --ref v2.0.1   # a specific release (or a branch or commit)
```

(On Windows, `python` or `py` instead of `python3`.) It needs Python 3.9 or newer and nothing
else.

From 2.0, `update.py` with no `--ref` (and no `--source`) stops before a major release. It prints
`<old> -> <new> is a major release`, then says to read `CHANGELOG.md` and rerun with
`--ref v<new>`; `--check` reports the update as a major. An explicit `--ref` or `--source` is the
deliberate yes. This applies to copies that already carry 2.0's `update.py`. A copy still running
a 1.x `update.py` moves to 2.0 without a question, which is safe because 2.0 removes nothing from
the bundle; the guard protects the next major.

## What it does

1. Learns the newest version from the repository's `main` branch (one small file), then
   downloads that release tag's archive from GitHub. If that tag is not published yet it says
   so and stops (`--ref main` installs the development tree instead).
2. Reads only the archive's `ui-theme/` folder into memory. Links, devices and paths that
   would leave the folder are refused; nothing is extracted to disk.
3. Checks every file against the new `files.json` (SHA-256), and refuses an incomplete or
   altered download.
4. Compares the installed copy with its own `files.json`. A bundle file that was edited by hand
   stops the update, with the list of files, unless you pass `--force`. Line endings do not
   count: a checkout that turned the files into CRLF is still unedited.
5. Writes new and changed files (each one atomically), removes files an older version had and
   the new one does not, and leaves every other file in the folder alone, so an app's own file
   there survives.
6. Prints the old and new version and the changed files.

Run it again any time: it is safe to repeat, and an up-to-date copy is left untouched.

## What the checksums prove

`files.json` travels inside the download, so it proves the files arrived complete and
unaltered, and that the installed copy was not edited. It does not prove where they came
from: that rests on HTTPS to `github.com`. To fix exactly what you get, pin a release tag
(`--ref v2.0.1`) and review the diff in your app's version control after updating, like any
vendored code.

## After updating

- **Caching.** Pages pick up the new files on the next load only if the folder is served with
  `Cache-Control: no-cache` (or `max-age=0`), or if the URLs carry a content hash
  (`ui-theme.css?v=<hash>`). The most common "the update did nothing" is a cached file.
- **Read the changelog** ([`CHANGELOG.md`](../CHANGELOG.md)). Patch and minor releases never
  remove or rename a token; a major release may, and says which.
- **Commit the new copy** with the app.
- New themes in a release appear in an app's picker only when the app lists them in
  `data-themes`, except core themes when `data-themes` is omitted.

## Other ways

- **git:** clone this repository (`--depth 1`), copy `ui-theme/` over the app's copy.
- **degit:** `npx degit LaserLloyd/ThemeForge/ui-theme#v2.0.1 static/ui-theme --force`.
- **CDN:** apps that load the files from jsDelivr update by changing the pinned version in the
  URL: `https://cdn.jsdelivr.net/gh/LaserLloyd/ThemeForge@v2.0.1/ui-theme/ui-theme.css`.
  Never pin `@main`: the CDN caches it for up to 12 hours.
- **Offline:** copy a release archive (`.tar.gz`) to the machine and run
  `python3 update.py --source <archive> --dest static/ui-theme` with the `update.py` from the
  archive's `ui-theme/` folder; `--source` also takes an unpacked `ui-theme/` folder.

## Troubleshooting

| Message | Meaning |
|---|---|
| `edited by hand: ...` | A bundle file in the copy changed. Move the change into the app's own CSS, then rerun with `--force`. `--check` reports it as "updating needs --force". `forgeui vendor` says "refusing to overwrite files edited by hand" and `--check` prints `DRIFT edited ...`. |
| `asks for ...` (forgeui) | The source bundle's version is outside the manifest's `version` (or `--version`). Upgrade or pin `forgeui`, or change the manifest on purpose. |
| `the source failed verification` (forgeui) | The zip, wheel or folder given to `--source` is incomplete or altered; nothing was written. |
| `not a ui-theme folder` | `--dest` points at a folder with other files and no `VERSION`. Pick an empty or new folder. |
| `<old> -> <new> is a major release` | `update.py` stopped before a major release (2.0 and later). Read `CHANGELOG.md`, then rerun with `--ref v<new>`. |
| `does not match given name 'forgeui'` (uv), `does not start with 'forgeui'` (pip) | The requirement still says `forgeui` and the tag is 2.0. Rename it to `themeforge`; the tag is fine. See [Moving from 1.x to 2.0](#moving-from-1x-to-20). |
| `cannot verify HTTPS certificates` | A python.org build on macOS: run "Install Certificates.command" from its folder in Applications. |
| `HTTP 404` | Wrong `--ref`: no such tag, branch or commit. |
| `<urlopen error ...>` | No network access to github.com (proxy, firewall, offline). |
| `could not write ...` | A file is locked (an editor, a running server on Windows). Close it and rerun. |
