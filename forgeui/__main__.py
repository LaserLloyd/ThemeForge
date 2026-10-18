"""``python -m forgeui``: vendor the bundle into a repository, print head tags, find the folder.

    python -m forgeui vendor [--check] [--force] [--version X] [--source S] [--manifest M]
    python -m forgeui init --dest static/ui-theme   write a starter forgeui.json
    python -m forgeui head [--manifest M] [--prefix /theme]   the <head> tags for the manifest's settings
    python -m forgeui path                          the folder inside the installed package
    python -m forgeui --version
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, bundle_version, head_html_from_manifest, static_dir
from . import vendor


def main(argv: Optional[List[str]] = None) -> int:
    try:  # a default-codepage Windows console can otherwise choke on non-ASCII text
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="python -m forgeui", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    try:
        bundle = bundle_version()
    except OSError:  # a damaged install: --help and --version still answer, and say so
        bundle = "missing"
    parser.add_argument("--version", action="version", version=f"forgeui {__version__} (bundle {bundle})")
    sub = parser.add_subparsers(dest="cmd", required=True)
    vendor.build_parser(sub.add_parser("vendor", help="copy the bundle into this repository, or check the copy",
                                       description=vendor.__doc__,
                                       formatter_class=argparse.RawDescriptionHelpFormatter))
    p = sub.add_parser("init", help="write a starter forgeui.json")
    p.add_argument("--dest", required=True, help="where the repo keeps its copy, e.g. static/ui-theme")
    p.add_argument("--manifest", default=vendor.MANIFEST_NAME)
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("head", help="print the <head> tags for the manifest's settings")
    p.add_argument("--manifest", default=vendor.MANIFEST_NAME)
    p.add_argument("--prefix", default="/theme", help="the URL the folder is served under")
    sub.add_parser("path", help="print the bundle folder inside the installed package")
    args = parser.parse_args(argv)

    if args.cmd == "vendor":
        return vendor.run(Path(args.manifest), source=args.source, version=args.version, check=args.check,
                          force=args.force)
    try:
        if args.cmd == "init":
            vendor.init_manifest(Path(args.manifest), args.dest, args.force)
            print(f"wrote {args.manifest}; edit it, then run: python -m forgeui vendor")
        elif args.cmd == "head":
            sys.stdout.write(head_html_from_manifest(args.manifest, prefix=args.prefix))
        elif args.cmd == "path":
            print(static_dir())
    except (vendor.VendorError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
