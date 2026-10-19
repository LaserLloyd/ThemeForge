#!/usr/bin/env python3
"""Build the release zip: everything an app, or an AI agent working on one, needs.

    python tools/release_zip.py [--out dist]     write dist/ThemeForge-<version>.zip and dist/ThemeForge.zip
    python tools/release_zip.py --notes          print this version's CHANGELOG section (the release notes)

The zip holds one folder, ThemeForge-<version>/, with AGENTS.md (the procedure: start
there), README.md, CHANGELOG.md, LICENSE, the ui-theme/ bundle, docs/, tokens/ and
examples/. Only files git tracks go in, so it is the tagged tree and nothing local, and no
screenshots (PNG): they are most of the bytes and no install needs them. The
same bytes are written twice: under the versioned name, and as ThemeForge.zip, which
https://github.com/LaserLloyd/ThemeForge/releases/latest/download/ThemeForge.zip always
serves for the newest release. Entries carry a fixed date, so a rebuild is identical.

Refuses to build when ui-theme/ does not match its files.json, or the CHANGELOG has no
entry for the version. Standard library only (and git).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ("AGENTS.md", "README.md", "CHANGELOG.md", "LICENSE", "ui-theme/", "docs/", "tokens/", "examples/")
STAMP = (2026, 1, 1, 0, 0, 0)


def version() -> str:
    return json.loads((ROOT / "src" / "themes.json").read_text(encoding="utf-8"))["version"]


def notes(v: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(v)}\b.*?$(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise SystemExit(f"CHANGELOG.md has no '## {v}' entry")
    return m.group(1).strip() + "\n"


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return sorted(p for p in out.decode("utf-8").split("\0")
                  if p and not p.endswith(".png") and any(p == i or (i.endswith("/") and p.startswith(i)) for i in INCLUDE))


def verify_bundle() -> None:
    manifest = json.loads((ROOT / "ui-theme" / "files.json").read_text(encoding="utf-8"))
    for rel, want in manifest["files"].items():
        data = (ROOT / "ui-theme" / rel).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != want:
            raise SystemExit(f"ui-theme/{rel} does not match files.json; run `python tools/sync_theme.py build`")


def build(out: Path) -> list[Path]:
    v = version()
    notes(v)
    verify_bundle()
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"ThemeForge-{v}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in tracked():
            info = zipfile.ZipInfo(f"ThemeForge-{v}/{rel}", STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (ROOT / rel).read_bytes())
    latest = out / "ThemeForge.zip"
    latest.write_bytes(target.read_bytes())
    return [target, latest]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="dist", help="folder to write the zips into (default: dist)")
    parser.add_argument("--notes", action="store_true", help="print the release notes and exit")
    args = parser.parse_args(argv)
    if args.notes:
        sys.stdout.write(notes(version()))
        return 0
    for path in build(Path(args.out)):
        print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
