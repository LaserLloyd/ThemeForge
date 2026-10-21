"""``python -m forgeui icons``: find the emoji and Material icon names an app should draw with the bundle's icons.

    python -m forgeui icons PATH...            report what to replace, exit 0
    python -m forgeui icons PATH... --check    exit 1 when anything replaceable is found (CI)
    python -m forgeui icons PATH... --json     machine-readable report on stdout
    python -m forgeui icons PATH... --all      also list emoji that have no icon (fine as content)
    python -m forgeui icons --folder DIR ...   read icons.json from a vendored copy, not the package

Each finding is one line, ``path:line: what -> icon``:

    src/app.js:12: 🗑 -> trash
    src/ui.py:40: delete_forever -> trash (forgeui.quasar_icon('delete_forever'))
    src/ui.py:41: account_tree (no ThemeForge icon)

What it looks for, per line:

* Emoji, looked up the way ``UIComponents.iconFor()`` does (variation selectors and skin tones
  dropped; a ZWJ sequence falls back to its first emoji). A pictograph (⚙ 🗑 📁 ✅) is reported
  wherever it stands. Arrows and symbols that are not pictographs (→ ✓ ✕ ▸ ▾ ☰ … ×) are common in
  prose, so they are reported only as the whole text of a string ('✕', "▸", `…`) or of an element
  (>✕<, whitespace allowed). Pictographs without an icon are listed only with --all.
* Material Icons names in NiceGUI/Quasar code: icon="name", ui.icon("name"), 'icon': 'name',
  props('... icon=name') and <q-icon name="name">. Values that start with svguse: or img: are
  already converted, and so are the bundle's own icon names (trash). A Material name with no icon
  is listed too, and never fails --check.

A line holding ``forgeui: allow-icons`` is skipped, so an app can keep an emoji on purpose.

Files with the suffixes .html .htm .js .mjs .jsx .ts .tsx .vue .svelte .jinja .j2 .py .css are read
(and .json inside a folder named locales, locale, i18n or lang) as UTF-8. node_modules, vendor, dist,
build, .git, __pycache__, .venv, venv and copies of the ThemeForge bundle are skipped. A file named on
the command line is always read.

Exit codes: 0 ok (or nothing replaceable), 1 with --check and something to replace, 2 usage error.
Standard library only; Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import bisect
import dataclasses
import functools
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, FrozenSet, Iterable, Iterator, List, Optional, Set, Tuple

from . import _stamp, static_dir

MARKER = "forgeui: allow-icons"
SUFFIXES = frozenset((".html", ".htm", ".js", ".mjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".jinja",
                      ".j2", ".py", ".css"))
LOCALE_DIRS = frozenset(("locales", "locale", "i18n", "lang"))
SKIP_DIRS = frozenset((".git", "node_modules", "vendor", "dist", "build", "__pycache__", ".venv", "venv"))

# ---------------------------------------------------------------- finding emoji

# Where emoji and symbols live. Pictographs sit in U+1F000-1FAFF (the skin tones U+1F3FB-1F3FF only
# modify the character before them), the rest are dingbats, arrows, shapes and technical symbols.
_RANGES = (r"\U0001F000-\U0001F3FA\U0001F400-\U0001FAFF"
           r"☀-➿⬀-⯿⌀-⏿←-⇿■-◿℀-⅏"
           r"〰〽㊗㊙×")
_TONES = r"\U0001F3FB-\U0001F3FF"
_FLAG = r"[\U0001F1E6-\U0001F1FF]{2}"
_KEYCAP = r"[#*0-9]️?⃣"
_STRIP = re.compile("[︎️\U0001F3FB-\U0001F3FF]")  # emojiKey() in src/ui-components.js

# The BMP characters Unicode lists as emoji, outside the blocks of plain arrows, shapes and letters:
# these are pictures and are reported wherever they stand. The rest of _RANGES (→ ✓ ✕ ▸ ☰ ...) is
# punctuation of a kind prose uses, and counts only alone, unless a U+FE0F asks for the emoji look.
_PICTOGRAPHS = (
    (0x2139, 0x2139), (0x231A, 0x231B), (0x2328, 0x2328), (0x23CF, 0x23CF), (0x23E9, 0x23F3),
    (0x23F8, 0x23FA), (0x25FD, 0x25FE), (0x2600, 0x2604), (0x260E, 0x260E), (0x2611, 0x2611),
    (0x2614, 0x2615), (0x2618, 0x2618), (0x261D, 0x261D), (0x2620, 0x2620), (0x2622, 0x2623),
    (0x2626, 0x2626), (0x262A, 0x262A), (0x262E, 0x262F), (0x2638, 0x263A), (0x2640, 0x2640),
    (0x2642, 0x2642), (0x2648, 0x2653), (0x265F, 0x2660), (0x2663, 0x2663), (0x2665, 0x2666),
    (0x2668, 0x2668), (0x267B, 0x267B), (0x267E, 0x267F), (0x2692, 0x2697), (0x2699, 0x2699),
    (0x269B, 0x269C), (0x26A0, 0x26A1), (0x26A7, 0x26A7), (0x26AA, 0x26AB), (0x26B0, 0x26B1),
    (0x26BD, 0x26BE), (0x26C4, 0x26C5), (0x26C8, 0x26C8), (0x26CE, 0x26CF), (0x26D1, 0x26D1),
    (0x26D3, 0x26D4), (0x26E9, 0x26EA), (0x26F0, 0x26F5), (0x26F7, 0x26FA), (0x26FD, 0x26FD),
    (0x2702, 0x2702), (0x2705, 0x2705), (0x2708, 0x270D), (0x270F, 0x270F), (0x2712, 0x2712),
    (0x2714, 0x2714), (0x2716, 0x2716), (0x271D, 0x271D), (0x2721, 0x2721), (0x2728, 0x2728),
    (0x2733, 0x2734), (0x2744, 0x2744), (0x2747, 0x2747), (0x274C, 0x274C), (0x274E, 0x274E),
    (0x2753, 0x2755), (0x2757, 0x2757), (0x2763, 0x2764), (0x2795, 0x2797), (0x27A1, 0x27A1),
    (0x27B0, 0x27B0), (0x27BF, 0x27BF), (0x2B1B, 0x2B1C), (0x2B50, 0x2B50), (0x2B55, 0x2B55),
    (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297), (0x3299, 0x3299),
)


def _sequence_pattern(extras: Iterable[str] = ()) -> str:
    """One emoji: a flag, a keycap, or a character with its variation selector and skin tone, joined
    by ZWJ. ``extras`` are mapped symbols outside _RANGES (… ⋮ ⠿ ⟳ ＋ and the like), tried first."""
    atoms = [re.escape(e) for e in extras] + ["[" + _RANGES + "]"]
    unit = "(?:" + "|".join(atoms) + ")[︎️]?[" + _TONES + "]?"
    return _FLAG + "|" + _KEYCAP + "|" + unit + "(?:‍" + unit + ")*"


_BASE_EMOJI = re.compile(_sequence_pattern())


def _is_pictograph(text: str) -> bool:
    """True when the match is a picture wherever it stands, not a symbol prose also uses."""
    if "️" in text or "‍" in text or "⃣" in text or re.search("[" + _TONES + "]", text):
        return True
    first = ord(text[0])
    if first >= 0x1F000:
        return True
    return any(lo <= first <= hi for lo, hi in _PICTOGRAPHS)


def _alone(text: str, start: int, end: int) -> bool:
    """The match is the whole text of a string ('✕', "▸", `…`) or of an element (>✕<, whitespace allowed)."""
    if start > 0 and end < len(text) and text[start - 1] in "'\"`" and text[end] == text[start - 1]:
        return True
    before, after = start, end
    while before > 0 and text[before - 1].isspace():
        before -= 1
    while after < len(text) and text[after].isspace():
        after += 1
    return before > 0 and after < len(text) and text[before - 1] == ">" and text[after] == "<"


# ---------------------------------------------------------------- finding Material names

_NAME = r"""(?P<q>["'])(?P<name>[^"'\s]+)(?P=q)"""
_MATERIAL_RULES = (
    # icon="name", icon='name' (and icon-right), but not :icon="expr", prepend-icon= or my_icon=
    re.compile(r"(?<![\w:@-])icon(?:-right)?\s*=\s*" + _NAME),
    # ui.icon("name"
    re.compile(r"\bui\.icon\(\s*(?:name\s*=\s*)?" + _NAME),
    # 'icon': 'name', "icon": "name", { icon: 'name' }
    re.compile(r"""(?P<k>["']?)\bicon(?P=k)\s*:\s*""" + _NAME),
    # <q-icon name="name"
    re.compile(r"<(?:q-icon|QIcon)\b[^>]*?(?<![\w:-])name\s*=\s*" + _NAME),
)
_PROPS = re.compile(r"""\bprops\(\s*(?P<q>["'])(?P<body>.*?)(?P=q)""")  # props('flat icon=name')
_PROP_ICON = re.compile(r"""(?<![\w:@-])icon(?:-right)?=["']?(?P<name>[^\s"']+)""")
_MATERIAL_NAME = re.compile(r"[a-z](?:[a-z0-9_]*[a-z0-9])?")  # a Material name, not mdi-x, fa-x or a path


# ---------------------------------------------------------------- the icon catalog


@dataclass
class Catalog:
    """What icons.json maps: emoji -> icon (as ``iconFor``), Material names -> icon (what
    ``quasar_icon`` takes), the icons' own names, and the pattern that finds an emoji or a mapped
    symbol in text."""
    emoji: Dict[str, str]
    material: Dict[str, str]
    icons: FrozenSet[str]
    pattern: "re.Pattern[str]"

    def icon_for(self, text: str) -> Optional[str]:
        """``UIComponents.iconFor(text)``: the icon an emoji stands for, or None."""
        key = _STRIP.sub("", text.strip())
        found = self.emoji.get(key)
        if found is None and "‍" in key:
            found = self.emoji.get(key.split("‍")[0])
        return found


def load_catalog(folder: Optional[Path] = None) -> Catalog:
    """The catalog of ``folder/icons.json``, or of the installed bundle."""
    folder = Path(folder) if folder else static_dir()
    if not (folder / "icons.json").is_file():
        raise ValueError(f"{folder} has no icons.json (point --folder at a ui-theme copy)")
    return _catalog_at(str(folder), _stamp(folder / "icons.json"))


@functools.lru_cache(maxsize=8)
def _catalog_at(folder: str, stamp: int) -> Catalog:
    path = Path(folder) / "icons.json"
    try:
        icons = json.loads(path.read_text(encoding="utf-8"))["icons"]
        emoji: Dict[str, str] = {}
        material: Dict[str, str] = {}
        for name, entry in icons.items():
            for symbol in entry.get("emoji", []):
                emoji[_STRIP.sub("", symbol)] = name
            for label in entry.get("material", []):
                material[label] = name
    except (KeyError, TypeError, AttributeError):
        raise ValueError(f"{path} is not a ThemeForge icons.json (no icons)") from None
    extras = sorted({s for s in emoji if not _BASE_EMOJI.fullmatch(s)}, key=lambda s: (-len(s), s))
    return Catalog(emoji=emoji, material=material, icons=frozenset(icons),
                   pattern=re.compile(_sequence_pattern(extras)))


# ---------------------------------------------------------------- scanning


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    text: str              # the emoji as written, or the Material name
    kind: str              # "emoji" or "material"
    icon: Optional[str]    # the icon that replaces it; None when no icon means it

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}: "
        if self.kind == "emoji":
            if self.icon:
                return f"{where}{self.text} -> {self.icon}"
            return f"{where}{self.text} (no icon; fine as content)"
        if self.icon:
            return f"{where}{self.text} -> {self.icon} (forgeui.quasar_icon('{self.text}'))"
        return f"{where}{self.text} (no ThemeForge icon)"


def scan_text(text: str, catalog: Catalog, path: str = "", show_all: bool = False) -> List[Finding]:
    """The findings in one file's text, in line order. ``show_all`` keeps pictographs with no icon."""
    lines = text.split("\n")
    skipped: Set[int] = {n for n, line in enumerate(lines, 1) if MARKER in line} if MARKER in text else set()
    starts = [0]
    for line in lines[:-1]:
        starts.append(starts[-1] + len(line) + 1)
    found: List[Finding] = []
    seen: Set[Tuple[int, str, str]] = set()

    def add(line: int, what: str, kind: str, icon: Optional[str]) -> None:
        if line not in skipped and (line, kind, what) not in seen:
            seen.add((line, kind, what))
            found.append(Finding(path, line, what, kind, icon))

    for match in catalog.pattern.finditer(text):
        symbol = match.group()
        icon = catalog.icon_for(symbol)
        if icon is None and not show_all:
            continue
        if not _is_pictograph(symbol) and not _alone(text, match.start(), match.end()):
            continue
        add(bisect.bisect_right(starts, match.start()), symbol, "emoji", icon)

    for number, line in enumerate(lines, 1):
        if number in skipped or ("icon" not in line and "Icon" not in line):
            continue
        names = [m.group("name") for rule in _MATERIAL_RULES for m in rule.finditer(line)]
        for props in _PROPS.finditer(line):
            names += [m.group("name") for m in _PROP_ICON.finditer(props.group("body"))]
        for name in names:
            if name.startswith(("svguse:", "img:")):
                continue  # already drawn from the bundle (or an image)
            icon = catalog.material.get(name)
            if icon is None and (name in catalog.icons or not _MATERIAL_NAME.fullmatch(name)):
                continue  # one of the bundle's own names (not a Material name), or another icon font
            add(number, name, "material", icon)

    found.sort(key=lambda f: f.line)
    return found


def _is_bundle_copy(folder: Path) -> bool:
    return (folder / "files.json").is_file() and (folder / "VERSION").is_file()


def _walk(root: Path) -> Iterator[Path]:
    root_name = root.resolve().name.lower()
    for here, dirs, files in os.walk(root):
        here_path = Path(here)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not _is_bundle_copy(here_path / d))
        names = {root_name} | {part.lower() for part in here_path.relative_to(root).parts}
        in_locales = bool(names & LOCALE_DIRS)
        for name in sorted(files):
            suffix = os.path.splitext(name)[1].lower()
            if suffix in SUFFIXES or (suffix == ".json" and in_locales):
                yield here_path / name


def iter_files(paths: Iterable[str]) -> Iterator[Path]:
    """The files to read for these paths: a file is read as named, a folder is searched."""
    seen: Set[Path] = set()
    for raw in paths:
        root = Path(raw)
        if root.is_file():
            candidates: Iterable[Path] = [root]
        elif _is_bundle_copy(root):
            print(f"note: {raw} is a ThemeForge bundle copy; skipped", file=sys.stderr)
            candidates = []
        else:
            candidates = _walk(root)
        for path in candidates:
            real = path.resolve()
            if real not in seen:
                seen.add(real)
                yield path


def summarize(findings: List[Finding], files: int) -> dict:
    emoji = sum(1 for f in findings if f.kind == "emoji" and f.icon)
    material = sum(1 for f in findings if f.kind == "material" and f.icon)
    return {"to_replace": emoji + material, "emoji": emoji, "material": material,
            "material_no_icon": sum(1 for f in findings if f.kind == "material" and not f.icon),
            "emoji_no_icon": sum(1 for f in findings if f.kind == "emoji" and not f.icon), "files": files}


def summary_line(summary: dict) -> str:
    line = f"{summary['to_replace']} to replace ({summary['emoji']} emoji, {summary['material']} Material)"
    n = summary["material_no_icon"]
    if n:
        line += f", {n} Material {'name' if n == 1 else 'names'} with no icon"
    if summary["emoji_no_icon"]:
        line += f", {summary['emoji_no_icon']} emoji with no icon"
    return line


# ---------------------------------------------------------------- the command


def run(paths: List[str], *, folder: Optional[str] = None, check: bool = False, as_json: bool = False,
        show_all: bool = False, out: Callable[[str], object] = print) -> int:
    """0 ok, 1 with ``check`` and something to replace, 2 on a usage error."""
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        print(f"error: no such file or folder: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        catalog = load_catalog(Path(folder) if folder else None)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    findings: List[Finding] = []
    count = 0
    for path in iter_files(paths):
        try:
            text = path.read_bytes().decode("utf-8", errors="ignore")
        except OSError as exc:
            print(f"warning: could not read {path}: {exc}", file=sys.stderr)
            continue
        count += 1
        findings += scan_text(text, catalog, path.as_posix(), show_all)
    findings.sort(key=lambda f: (f.path, f.line))
    summary = summarize(findings, count)

    if as_json:
        out(json.dumps({"findings": [f.as_dict() for f in findings], "summary": summary}, ensure_ascii=False,
                       indent=2))
    else:
        for finding in findings:
            out(str(finding))
        out(summary_line(summary))
    return 1 if check and summary["to_replace"] else 0


def build_parser(sub: Optional[argparse.ArgumentParser] = None) -> argparse.ArgumentParser:
    parser = sub or argparse.ArgumentParser(prog="forgeui icons", description=__doc__,
                                            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", metavar="PATH", help="a file, or a folder searched recursively")
    parser.add_argument("--check", action="store_true", help="exit 1 when anything replaceable is found")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print the report as JSON")
    parser.add_argument("--all", action="store_true", dest="show_all",
                        help="also list emoji that have no icon (fine as content)")
    parser.add_argument("--folder", metavar="DIR",
                        help="read icons.json from this ui-theme copy instead of the installed package")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    return run(args.paths, folder=args.folder, check=args.check, as_json=args.as_json, show_all=args.show_all)


if __name__ == "__main__":
    sys.exit(main())
