#!/usr/bin/env python3
"""Self-test `python -m forgeui vendor` on the examples' forgeui.json manifests.

    python tools/selftest_forgeui.py                       use this checkout's forgeui/ package
    python tools/selftest_forgeui.py --wheel dist/forgeui-1.2.0-py3-none-any.whl
                                                           install the built wheel into a throwaway
                                                           virtual environment and test THAT

For every examples/*/forgeui.json it copies the example to a temporary folder and checks that:

  1. `vendor --check` fails before anything is vendored (exit 1),
  2. `vendor` writes the copy (exit 0) and `vendor --check` then passes (exit 0),
  3. a second `vendor` changes nothing,
  4. a hand edit to a bundle file makes `--check` fail (exit 1) and `vendor` refuse (exit 1),
     and `vendor --force` restores it (exit 0), after which `--check` passes again,
  5. with a wheel, the interpreter really imported the installed package, not this checkout.

CI runs the wheel form after `python -m build`, so a wheel that lost its bundle (or a manifest
the tool cannot read) fails the build. Exits 0 when everything passes. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(python: str, args: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str]:
    proc = subprocess.run([python, "-m", "forgeui", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def make_venv(wheel: Path, base: Path) -> str:
    venv = base / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True, timeout=300)
    python = str(venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))
    subprocess.run([python, "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", str(wheel)],
                   check=True, capture_output=True, timeout=300)
    return python


def check_example(python: str, example: Path, work: Path, env: dict | None) -> list[str]:
    problems: list[str] = []
    app = work / example.name
    shutil.copytree(example, app)
    manifest = json.loads((app / "forgeui.json").read_text(encoding="utf-8"))
    dest = app / manifest["dest"]

    def expect(label: str, got: tuple[int, str], code: int) -> None:
        if got[0] != code:
            problems.append(f"{example.name}: {label}: exit {got[0]}, wanted {code}\n{got[1].rstrip()}")

    expect("--check before vendoring", run(python, ["vendor", "--check"], app, env), 1)
    expect("vendor", run(python, ["vendor"], app, env), 0)
    expect("--check after vendoring", run(python, ["vendor", "--check"], app, env), 0)
    code, out = run(python, ["vendor"], app, env)
    if code != 0 or "already up to date" not in out:
        problems.append(f"{example.name}: a second vendor should change nothing:\n{out.rstrip()}")
    victim = dest / "ui-theme.css"
    original = victim.read_bytes()
    victim.write_bytes(original + b"\n/* edited by hand */\n")
    expect("--check after a hand edit", run(python, ["vendor", "--check"], app, env), 1)
    expect("vendor over a hand edit", run(python, ["vendor"], app, env), 1)
    if b"edited by hand" not in victim.read_bytes():
        problems.append(f"{example.name}: a refused vendor must not touch the edited file")
    expect("vendor --force", run(python, ["vendor", "--force"], app, env), 0)
    if victim.read_bytes().replace(b"\r\n", b"\n") != original.replace(b"\r\n", b"\n"):
        problems.append(f"{example.name}: --force did not restore ui-theme.css")
    expect("--check after --force", run(python, ["vendor", "--check"], app, env), 0)
    if (dest / "VERSION").read_text(encoding="utf-8") != (ROOT / "ui-theme" / "VERSION").read_text(encoding="utf-8"):
        problems.append(f"{example.name}: the vendored VERSION is not this checkout's")
    return problems


def main(argv: list[str] | None = None) -> int:
    try:  # a default-codepage Windows console can otherwise choke on non-ASCII text
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wheel", help="a built forgeui wheel to install into a throwaway venv and test")
    parser.add_argument("--examples", default=str(ROOT / "examples"), help="folder holding the examples")
    args = parser.parse_args(argv)
    examples = sorted(p.parent for p in Path(args.examples).glob("*/forgeui.json"))
    if not examples:
        print(f"no examples/*/forgeui.json under {args.examples}", file=sys.stderr)
        return 2
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        env = None
        if args.wheel:
            wheel = Path(args.wheel)
            if not wheel.is_file():
                print(f"wheel {wheel} not found", file=sys.stderr)
                return 2
            python = make_venv(wheel, base)
            work = base / "work"
            work.mkdir()
            code, out = run(python, ["path"], work)
            if code != 0 or Path(ROOT) in Path(out.strip()).parents or "site-packages" not in out:
                problems.append(f"the wheel's package did not import from site-packages: {out.strip()}")
        else:
            import os
            python = sys.executable
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            work = base / "work"
            work.mkdir()
        for example in examples:
            found = check_example(python, example, work, env)
            print(f"{example.name}: {'ok' if not found else 'FAILED'}")
            problems += found
    for p in problems:
        print("FAIL", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
