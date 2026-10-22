#!/usr/bin/env python3
"""Screenshot the specimen and rebuild every image the README shows.

    python tools/screenshots.py [--browser PATH] [--out DIR]

Writes docs/images/specimen-<theme>.png (the README's whole-board shots, 1440x900, header
and picker included) and docs/images/gallery.png (the states and form controls of every
theme, two columns). The per-theme shots behind the gallery (1280x1150, header hidden) go
to --out (default: screenshots/, ignored by git). Needs a Chromium-based browser (as
tests/run_browser_tests.py finds one) and Pillow (pip install pillow). Run it after a
change to how the specimen looks, with the web fonts the themes name installed: Inter,
JetBrains Mono and Space Grotesk, which CI's `screenshots` job installs (Electric
Yellow's Archivo is not installed there, so that theme shows its fallback face).
Exits 1 if any shot failed. Maintainers only.
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

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is needed to crop the shots: pip install pillow")

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "docs" / "images"
# The README's whole-board shots: Glacier (a dark theme), High Contrast (its dark half) and
# Slate (the neutral grey-blue one).
README_THEMES = ("glacier", "high-contrast", "slate")
README_SIZE = (1440, 900)
GALLERY_SIZE = (1280, 1150)
# What the gallery keeps of each GALLERY_SIZE shot. With the header hidden (&shot) the
# states section starts at the top of <main> in every theme; this box runs from just above
# its heading to just below the form hints.
GALLERY_CROP = (60, 8, 1220, 518)
CHROME = ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1"]
# Headless Chrome lays the page out in the window minus a strip at the bottom that it never
# paints (87px in Chromium 141 on Linux), yet --screenshot saves the whole window, so a shot
# taken at the size wanted ends in a blank band. The strip differs by build and the page cannot
# report it reliably (Chrome stable gives outerHeight - innerHeight = -513), so every window is
# opened this much taller and only its top is kept. The specimen lays out from the top and has no
# viewport-height rules, so the taller window changes nothing above the cut.
FRAME_MARGIN = 300


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def find_browser(explicit):
    spec = importlib.util.spec_from_file_location("runner", ROOT / "tests" / "run_browser_tests.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner.find_browser(explicit)


def shoot(browser: str, url: str, target: Path, size: tuple[int, int]) -> bool:
    """Save a width x height image of the page at `url` to `target`; False if the browser failed."""
    width, height = size
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.png"
        try:
            # The window is FRAME_MARGIN taller than the shot and the unpainted strip at its
            # bottom is cropped off with the rest of the margin. The virtual time budget has Chrome run
            # the page's timers for 3 s of virtual time (no real wait) before it captures, so
            # anything the page does late is in the shot.
            subprocess.run([browser, *CHROME, f"--window-size={width},{height + FRAME_MARGIN}",
                            f"--user-data-dir={tmp}/profile", "--virtual-time-budget=3000",
                            f"--screenshot={raw}", url],
                           capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            return False
        if not raw.is_file():
            return False
        with Image.open(raw) as image:
            if image.width < width or image.height < height:
                return False
            image.crop((0, 0, width, height)).save(target, optimize=True)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser")
    parser.add_argument("--out", default=str(ROOT / "screenshots"))
    args = parser.parse_args(argv)
    browser = find_browser(args.browser)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    themes = [t["slug"] for t in json.loads((ROOT / "src" / "themes.json").read_text(encoding="utf-8"))["themes"]]

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/specimen/index.html"
    shots = []
    failed = []
    try:
        for slug in README_THEMES:
            target = IMAGES / f"specimen-{slug}.png"
            ok = shoot(browser, f"{base}?theme={slug}", target, README_SIZE)
            print(target.relative_to(ROOT), "ok" if ok else "FAILED")
            if not ok:
                failed.append(target.name)
        for slug in themes:
            target = out / f"{slug}.png"
            ok = shoot(browser, f"{base}?theme={slug}&shot", target, GALLERY_SIZE)
            print(slug, "ok" if ok else "FAILED")
            if ok:
                shots.append(target)
            else:
                failed.append(target.name)
    finally:
        server.shutdown()
    if failed:
        print("failed: " + ", ".join(failed) + "; gallery not built", file=sys.stderr)
        return 1

    crops = []
    for path in shots:
        with Image.open(path) as image:
            crops.append(image.crop(GALLERY_CROP))
    w, h = crops[0].size
    cols = 2
    rows = (len(crops) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows))
    for i, crop in enumerate(crops):
        sheet.paste(crop, ((i % cols) * w, (i // cols) * h))
    sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    gallery = IMAGES / "gallery.png"
    sheet.save(gallery, optimize=True)
    print(f"wrote {gallery.relative_to(ROOT)} {sheet.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
