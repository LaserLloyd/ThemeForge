#!/usr/bin/env python3
"""Run tests/runtime.html in a headless Chromium browser and report the result.

    python tests/run_browser_tests.py [--browser PATH]

Serves the repository over http://127.0.0.1 on a free port, loads the test
page in headless Chrome, Chromium or Edge (found on PATH or in the usual
install folders; UI_THEME_BROWSER or --browser overrides), and reads the
page title, which the harness sets to "PASS n/n passed" or "FAIL ...". Exits 0
only on PASS. Standard library only.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_browser(explicit: str | None) -> str:
    for name in [explicit, os.environ.get("UI_THEME_BROWSER")] + CANDIDATES:
        if not name:
            continue
        path = shutil.which(name) or (name if Path(name).is_file() else None)
        if path:
            return path
    raise SystemExit("no Chrome, Chromium or Edge found; pass --browser PATH")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", help="path to a Chromium-based browser")
    parser.add_argument("--page", default="tests/runtime.html", help="page to run, relative to the repo root")
    args = parser.parse_args(argv)
    browser = find_browser(args.browser)

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/{args.page}"
    try:
        with tempfile.TemporaryDirectory() as profile:
            result = subprocess.run(
                [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                 f"--user-data-dir={profile}", "--virtual-time-budget=30000", "--dump-dom", url],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    finally:
        server.shutdown()
    dom = result.stdout
    title = re.search(r"<title>(.*?)</title>", dom, re.S)
    summary = re.search(r'<p id="summary">(.*?)</p>', dom, re.S)
    failures = re.findall(r'<li class="fail">(.*?)</li>', dom, re.S)
    print(f"{args.page}: {title.group(1).strip() if title else '(no title)'}")
    for item in failures:
        print("  FAIL", re.sub(r"<[^>]+>", "", item))
    if not title or not title.group(1).startswith("PASS"):
        if summary:
            print("  ", re.sub(r"<[^>]+>", "", summary.group(1)))
        if not dom.strip():
            print(result.stderr[-2000:], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
