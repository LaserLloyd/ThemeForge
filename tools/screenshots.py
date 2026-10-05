#!/usr/bin/env python3
"""Screenshot the specimen in every theme and build docs/images/gallery.png.

    python tools/screenshots.py [--browser PATH] [--out DIR]

Needs a Chromium-based browser (as tests/run_browser_tests.py finds one) and,
for the gallery sheet, Pillow (pip install pillow). Individual screenshots go
to --out (default: screenshots/, ignored by git). Maintainers only.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_browser(explicit):
    spec = importlib.util.spec_from_file_location("runner", ROOT / "tests" / "run_browser_tests.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner.find_browser(explicit)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser")
    parser.add_argument("--out", default=str(ROOT / "screenshots"))
    args = parser.parse_args(argv)
    browser = find_browser(args.browser)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    themes = [t["slug"] for t in json.loads((ROOT / "src" / "themes.json").read_text(encoding="utf-8"))["themes"]]

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/specimen/index.html"
    shots = []
    try:
        for slug in themes:
            target = out / f"{slug}.png"
            with tempfile.TemporaryDirectory() as profile:
                subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                "--window-size=1280,1150", "--force-device-scale-factor=1",
                                f"--user-data-dir={profile}", "--virtual-time-budget=3000",
                                f"--screenshot={target}", f"{base}?theme={slug}"],
                               capture_output=True, timeout=120)
            print(slug, "ok" if target.is_file() else "FAILED")
            shots.append(target)
    finally:
        server.shutdown()

    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed: screenshots written, gallery not built", file=sys.stderr)
        return 0
    crops = [Image.open(p).crop((60, 100, 1220, 610)) for p in shots if p.is_file()]
    w, h = crops[0].size
    cols = 2
    rows = (len(crops) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows))
    for i, crop in enumerate(crops):
        sheet.paste(crop, ((i % cols) * w, (i // cols) * h))
    sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    gallery = ROOT / "docs" / "images" / "gallery.png"
    sheet.save(gallery, optimize=True)
    print(f"wrote {gallery.relative_to(ROOT)} {sheet.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
