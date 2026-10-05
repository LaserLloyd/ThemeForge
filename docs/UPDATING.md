# Updating

An app holds a copy of `ui-theme/` and never edits it, so updating is replacing the copy.
`ui-theme/update.py` does that safely.

```
python3 static/ui-theme/update.py            # install the latest release
python3 static/ui-theme/update.py --check    # report only; exits 1 when an update exists
python3 static/ui-theme/update.py --ref v1.2.0   # a specific release (or a branch or commit)
```

(On Windows, `python` or `py` instead of `python3`.) It needs Python 3.9 or newer and nothing
else.

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
(`--ref v1.2.0`) and review the diff in your app's version control after updating, like any
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
- **degit:** `npx degit LaserLloyd/ThemeForge/ui-theme#v1.0.0 static/ui-theme --force`.
- **CDN:** apps that load the files from jsDelivr update by changing the pinned version in the
  URL: `https://cdn.jsdelivr.net/gh/LaserLloyd/ThemeForge@v1.0.0/ui-theme/ui-theme.css`.
  Never pin `@main`: the CDN caches it for up to 12 hours.
- **Offline:** copy a release archive (`.tar.gz`) to the machine and run
  `python3 update.py --source <archive> --dest static/ui-theme` with the `update.py` from the
  archive's `ui-theme/` folder; `--source` also takes an unpacked `ui-theme/` folder.

## Troubleshooting

| Message | Meaning |
|---|---|
| `edited by hand: ...` | A bundle file in the copy changed. Move the change into the app's own CSS, then rerun with `--force`. `--check` reports it as "updating needs --force". |
| `not a ui-theme folder` | `--dest` points at a folder with other files and no `VERSION`. Pick an empty or new folder. |
| `cannot verify HTTPS certificates` | A python.org build on macOS: run "Install Certificates.command" from its folder in Applications. |
| `HTTP 404` | Wrong `--ref`: no such tag, branch or commit. |
| `<urlopen error ...>` | No network access to github.com (proxy, firewall, offline). |
| `could not write ...` | A file is locked (an editor, a running server on Windows). Close it and rerun. |
