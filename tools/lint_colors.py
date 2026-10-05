#!/usr/bin/env python3
"""Flag raw colours living outside the theme files.

    python tools/lint_colors.py PATH... [--allow GLOB ...] [--quiet] [--strict]
    python tools/lint_colors.py --self-test

Walks .css .js .mjs .html .htm .jinja .j2 .py .vue .svelte files under each
PATH (file or directory) and flags:
  - hex colours:  #rgb  #rgba  #rrggbb  #rrggbbaa
  - function calls: rgb() rgba() hsl() hsla()
  - CSS named colours used as a declaration value (white, black, red, ... but
    never transparent, currentColor, inherit, initial, unset, none)

In a .css file (or a <style> block / style="..." attribute embedded in a
non-CSS file) a hit counts anywhere it looks like a value. In every other
file, a hit only counts inside a string literal (JS/Python string, or an
HTML/template attribute value) -- a bare word in a comment, e.g. a Python
"# deadbeef" note or a "#region" fold marker, is never inside a string and
so is never flagged. A handful of narrower look-alikes are always skipped:
URL fragments (href="#abc"), #id CSS selectors, HTML numeric entities
(&#39;), and any line containing the literal text "theme-lint: allow".

theme-*.css, ui-theme*.css and ui-theme*.js are themselves the theme system
(or its generated runtime) and are always allowed, as is anything under a
vendor/ or node_modules/ directory. `var(--x, #fff)`-style fallbacks are a
separate WARN category -- pass --strict to fail on those too.

Equivalent ripgrep one-liner (coarser: no context-awareness, no CSS named
colours, no var()-fallback distinction):

    rg -n --glob '!**/theme-*.css' --glob '!**/ui-theme*' --glob '!**/vendor/**' '#[0-9a-fA-F]{3,8}\\b|\\b(rgba?|hsla?)\\(' <dirs>

Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import re
import sys
import tempfile
import tokenize
from pathlib import Path

EXTENSIONS = {".css", ".js", ".mjs", ".html", ".htm", ".jinja", ".j2", ".py", ".vue", ".svelte"}
ALWAYS_ALLOW_NAME_GLOBS = ("theme-*.css", "ui-theme*.css", "ui-theme*.js")
ALWAYS_ALLOW_DIRS = {"vendor", "node_modules"}
ALLOW_LINE_MARKER = "theme-lint: allow"

RIPGREP_EQUIVALENT = (
    "rg -n --glob '!**/theme-*.css' --glob '!**/ui-theme*' --glob '!**/vendor/**' "
    "'#[0-9a-fA-F]{3,8}\\b|\\b(rgba?|hsla?)\\(' <dirs>"
)

NEVER_NAMED = {"transparent", "currentcolor", "inherit", "initial", "unset", "none"}

# The 147 CSS3/SVG extended colour keywords (rebeccapurple included), minus
# the always-safe keywords in NEVER_NAMED, which are never in this list.
CSS_NAMED_COLORS = sorted(
    {
        "aliceblue", "antiquewhite", "aqua", "aquamarine", "azure", "beige", "bisque", "black",
        "blanchedalmond", "blue", "blueviolet", "brown", "burlywood", "cadetblue", "chartreuse",
        "chocolate", "coral", "cornflowerblue", "cornsilk", "crimson", "cyan", "darkblue",
        "darkcyan", "darkgoldenrod", "darkgray", "darkgreen", "darkgrey", "darkkhaki",
        "darkmagenta", "darkolivegreen", "darkorange", "darkorchid", "darkred", "darksalmon",
        "darkseagreen", "darkslateblue", "darkslategray", "darkslategrey", "darkturquoise",
        "darkviolet", "deeppink", "deepskyblue", "dimgray", "dimgrey", "dodgerblue", "firebrick",
        "floralwhite", "forestgreen", "fuchsia", "gainsboro", "ghostwhite", "gold", "goldenrod",
        "gray", "green", "greenyellow", "grey", "honeydew", "hotpink", "indianred", "indigo",
        "ivory", "khaki", "lavender", "lavenderblush", "lawngreen", "lemonchiffon", "lightblue",
        "lightcoral", "lightcyan", "lightgoldenrodyellow", "lightgray", "lightgreen", "lightgrey",
        "lightpink", "lightsalmon", "lightseagreen", "lightskyblue", "lightslategray",
        "lightslategrey", "lightsteelblue", "lightyellow", "lime", "limegreen", "linen",
        "magenta", "maroon", "mediumaquamarine", "mediumblue", "mediumorchid", "mediumpurple",
        "mediumseagreen", "mediumslateblue", "mediumspringgreen", "mediumturquoise",
        "mediumvioletred", "midnightblue", "mintcream", "mistyrose", "moccasin", "navajowhite",
        "navy", "oldlace", "olive", "olivedrab", "orange", "orangered", "orchid", "palegoldenrod",
        "palegreen", "paleturquoise", "palevioletred", "papayawhip", "peachpuff", "peru", "pink",
        "plum", "powderblue", "purple", "rebeccapurple", "red", "rosybrown", "royalblue",
        "saddlebrown", "salmon", "sandybrown", "seagreen", "seashell", "sienna", "silver",
        "skyblue", "slateblue", "slategray", "slategrey", "snow", "springgreen", "steelblue",
        "tan", "teal", "thistle", "tomato", "turquoise", "violet", "wheat", "white", "whitesmoke",
        "yellow", "yellowgreen",
    } - NEVER_NAMED,
    key=len,
    reverse=True,
)

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
FUNC_RE = re.compile(r"\b(rgba?|hsla?)\(", re.IGNORECASE)
NAMED_RE = re.compile(r"(?<![\w-])(" + "|".join(CSS_NAMED_COLORS) + r")(?![\w-])", re.IGNORECASE)
VAR_RE = re.compile(r"\bvar\(")


# ============================================================ offset <-> rc


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def offset_to_linecol(offsets: list[int], pos: int) -> tuple[int, int]:
    lo, hi = 0, len(offsets) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if offsets[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1, pos - offsets[lo] + 1


# ==================================================== region extraction


def find_matching_paren(text: str, open_idx: int, limit: int) -> int:
    depth = 0
    i = open_idx
    while i < limit:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def var_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Absolute (open, close) paren spans of every var(...) call in [start,end)."""
    spans = []
    for m in VAR_RE.finditer(text, start, end):
        open_idx = m.end() - 1
        close_idx = find_matching_paren(text, open_idx, end)
        if close_idx != -1:
            spans.append((open_idx, close_idx))
    return spans


def css_comment_complement(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """[start,end) minus every /* ... */ span -> the pieces actually holding values."""
    pieces = []
    i = start
    while i < end:
        j = text.find("/*", i, end)
        if j == -1:
            pieces.append((i, end))
            break
        if j > i:
            pieces.append((i, j))
        k = text.find("*/", j + 2, end)
        i = end if k == -1 else k + 2
    return pieces


def jslike_string_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Absolute spans of '...' "..." `...` string/template literals in [start,end),
    skipping over // and /* */ comments so a quote inside one can't fool this."""
    spans = []
    i = start
    while i < end:
        c = text[i]
        if c == "/" and i + 1 < end and text[i + 1] == "/":
            j = text.find("\n", i, end)
            i = end if j == -1 else j
        elif c == "/" and i + 1 < end and text[i + 1] == "*":
            j = text.find("*/", i + 2, end)
            i = end if j == -1 else j + 2
        elif c in ("'", '"', "`"):
            quote = c
            j = i + 1
            while j < end:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            spans.append((i, min(j, end)))
            i = j
        else:
            i += 1
    return spans


def python_string_spans(text: str) -> list[tuple[int, int]]:
    offsets = line_offsets(text)
    spans = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.STRING:
                srow, scol = tok.start
                erow, ecol = tok.end
                start = offsets[srow - 1] + scol
                end = offsets[erow - 1] + ecol
                spans.append((start, end))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return spans


ATTR_RE = re.compile(r'([a-zA-Z_:][\w:.-]*)\s*=\s*("([^"]*)"|\'([^\']*)\')')
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.I | re.S)
URL_ATTRS = {"href", "src", "action", "formaction", "poster", "cite", "background", "xlink:href", "manifest", "longdesc"}


def complement(end_of_file: int, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    spans = sorted(spans)
    pieces = []
    cur = 0
    for s, e in spans:
        if s > cur:
            pieces.append((cur, s))
        cur = max(cur, e)
    if cur < end_of_file:
        pieces.append((cur, end_of_file))
    return pieces


class Region:
    __slots__ = ("start", "end", "css_like", "url_attr")

    def __init__(self, start: int, end: int, css_like: bool, url_attr: bool = False):
        self.start, self.end, self.css_like, self.url_attr = start, end, css_like, url_attr


def regions_for(suffix: str, text: str) -> list[Region]:
    n = len(text)
    if suffix == ".css":
        return [Region(s, e, css_like=True) for s, e in css_comment_complement(text, 0, n)]

    if suffix in (".js", ".mjs"):
        return [Region(s, e, css_like=False) for s, e in jslike_string_spans(text, 0, n)]

    if suffix == ".py":
        return [Region(s, e, css_like=False) for s, e in python_string_spans(text)]

    # HTML-ish: .html .htm .jinja .j2 .vue .svelte
    regions: list[Region] = []
    consumed: list[tuple[int, int]] = []

    for m in STYLE_BLOCK_RE.finditer(text):
        s, e = m.start(1), m.end(1)
        consumed.append((m.start(), m.end()))
        regions.extend(Region(a, b, css_like=True) for a, b in css_comment_complement(text, s, e))

    for m in SCRIPT_BLOCK_RE.finditer(text):
        s, e = m.start(1), m.end(1)
        consumed.append((m.start(), m.end()))
        regions.extend(Region(a, b, css_like=False) for a, b in jslike_string_spans(text, s, e))

    for piece_start, piece_end in complement(n, consumed):
        chunk = text[piece_start:piece_end]
        for m in ATTR_RE.finditer(chunk):
            attr_name = m.group(1).lower()
            # group(2) is the quoted value including its quotes; value spans group(3)/(4)
            if m.group(3) is not None:
                vs, ve = m.start(3), m.end(3)
            else:
                vs, ve = m.start(4), m.end(4)
            css_like = attr_name == "style"
            regions.append(Region(piece_start + vs, piece_start + ve, css_like=css_like, url_attr=attr_name in URL_ATTRS))
    return regions


# ==================================================================== hits


def looks_like_selector(text: str, end_idx: int, limit: int) -> bool:
    i = end_idx
    while i < limit and text[i] in " \t\r\n":
        i += 1
    return i < limit and text[i] in "{,.:["


def is_html_entity(text: str, start_idx: int) -> bool:
    return start_idx > 0 and text[start_idx - 1] == "&"


def in_value_position(text: str, region_start: int, idx: int) -> bool:
    colon = text.rfind(":", region_start, idx)
    stop = max(text.rfind(c, region_start, idx) for c in ";{}")
    return colon != -1 and colon > stop


# Outside real CSS (JS/Python strings, non-style attributes) a colour word is
# usually prose ("gray skies", "cyan/green"). There it only counts when it is
# the value of a colour-bearing CSS property written inline, e.g.
# `el.style.cssText = "border: 1px solid white"`.
COLOR_PROP_BEFORE_RE = re.compile(
    r"(?:^|[\s;{\"'`])(?:color|background(?:-color)?|border(?:-(?:top|right|bottom|left))?(?:-color)?"
    r"|outline(?:-color)?|fill|stroke|(?:box|text)-shadow|accent-color|caret-color"
    r"|column-rule(?:-color)?|text-decoration(?:-color)?)\s*:\s*[\w#%().,\-\s]*$",
    re.IGNORECASE,
)


def in_inline_css_declaration(text: str, region_start: int, idx: int) -> bool:
    return bool(COLOR_PROP_BEFORE_RE.search(text[max(region_start, idx - 120):idx]))


def scan_region(text: str, region: Region, var_spans_all: list[tuple[int, int]]) -> list[dict]:
    hits = []
    start, end = region.start, region.end

    def is_var_fallback(pos: int) -> bool:
        return any(vs < pos < ve for vs, ve in var_spans_all)

    for m in HEX_RE.finditer(text, start, end):
        if is_html_entity(text, m.start()):
            continue
        if region.css_like and looks_like_selector(text, m.end(), end):
            continue
        if region.url_attr:
            continue  # href="#abc" and friends: a fragment, never a colour
        hits.append({"pos": m.start(), "end": m.end(), "literal": m.group(0), "kind": "hex", "warn": is_var_fallback(m.start())})

    for m in FUNC_RE.finditer(text, start, end):
        hits.append({"pos": m.start(), "end": m.end(), "literal": m.group(0), "kind": m.group(1).lower(), "warn": is_var_fallback(m.start())})

    for m in NAMED_RE.finditer(text, start, end):
        if not in_value_position(text, start, m.start()):
            continue
        if not region.css_like and not in_inline_css_declaration(text, start, m.start()):
            continue
        hits.append({"pos": m.start(), "end": m.end(), "literal": m.group(0), "kind": "named", "warn": is_var_fallback(m.start())})

    return hits


def is_always_allowed(path: Path, extra_allow: list[str]) -> bool:
    name = path.name
    if any(fnmatch.fnmatch(name, pat) for pat in ALWAYS_ALLOW_NAME_GLOBS):
        return True
    if any(part in ALWAYS_ALLOW_DIRS for part in path.parts):
        return True
    rel = path.as_posix()
    for pat in extra_allow:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat):
            return True
    return False


def lint_text(suffix: str, text: str) -> list[dict]:
    """Return raw hits (absolute offsets) for one file's already-read text."""
    regions = regions_for(suffix, text)
    vspans: list[tuple[int, int]] = []
    for r in regions:
        vspans.extend(var_spans(text, r.start, r.end))
    # var() can nest across region boundaries only in CSS-like text, where a
    # region is a whole comment-free slice, so scanning per region is enough.
    hits: list[dict] = []
    for r in regions:
        hits.extend(scan_region(text, r, vspans))
    return hits


def lint_file(path: Path, strict: bool) -> tuple[list[str], int, int]:
    """Return (formatted lines, error_count, warning_count) for one file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ([f"{path}: could not read ({exc})"], 1, 0)

    offsets = line_offsets(text)
    file_lines = text.splitlines()
    raw_hits = lint_text(path.suffix.lower(), text)
    raw_hits.sort(key=lambda h: h["pos"])

    lines, errors, warnings = [], 0, 0
    for h in raw_hits:
        line_no, col_no = offset_to_linecol(offsets, h["pos"])
        line_text = file_lines[line_no - 1] if 0 < line_no <= len(file_lines) else ""
        if ALLOW_LINE_MARKER in line_text:
            continue
        is_warn = h["warn"] and not strict
        if h["warn"]:
            kind = f"{h['kind']} warn"
        else:
            kind = h["kind"]
        if is_warn:
            warnings += 1
        else:
            errors += 1
        lines.append(f"{path}:{line_no}:{col_no}  {h['literal']}  ({kind})")
    return lines, errors, warnings


# =================================================================== walk


def iter_candidate_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            if p.suffix.lower() in EXTENSIONS:
                files.append(p)
            continue
        if not p.is_dir():
            continue
        for root, dirnames, filenames in _walk(p):
            for fn in filenames:
                fp = Path(root) / fn
                if fp.suffix.lower() in EXTENSIONS:
                    files.append(fp)
    return files


def _walk(root: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ALWAYS_ALLOW_DIRS and not d.startswith(".")]
        yield dirpath, dirnames, filenames


# ================================================================ self-test


def _selftest_case(name, filename, content, expect_literals, expect_absent):
    import os

    with tempfile.TemporaryDirectory(prefix="lint_colors_selftest_") as tmp:
        # tempfile.gettempdir() is outside this package by construction.
        path = Path(tmp) / filename
        path.write_text(content, encoding="utf-8")
        lines, errors, warnings = lint_file(path, strict=False)
        found = [ln.split("  ")[1] for ln in lines]
        ok = True
        for lit in expect_literals:
            if lit not in found:
                print(f"FAIL {name}: expected to flag {lit!r}, hits were {found!r}")
                ok = False
        for lit in expect_absent:
            if lit in found:
                print(f"FAIL {name}: {lit!r} should NOT have been flagged, hits were {found!r}")
                ok = False
        if ok:
            print(f"PASS {name}")
        return ok


def run_self_test() -> int:
    all_ok = True

    all_ok &= _selftest_case(
        "css selector vs value",
        "sample.css",
        "#main {\n  color: #ffffff;\n  background: rgb(1,2,3);\n}\n#a, #b { color: red; }\n.x { color: transparent; }\n",
        expect_literals=["#ffffff", "rgb(", "red"],
        expect_absent=["#main", "#a", "#b", "transparent"],
    )

    all_ok &= _selftest_case(
        "html href fragment vs style attr",
        "sample.html",
        '<a href="#top">top</a>\n<div style="color:#123456; border-color: navy;"></div>\n<a href="/page#deadbeef">x</a>\n',
        expect_literals=["#123456", "navy"],
        expect_absent=["#top", "#deadbeef"],
    )

    all_ok &= _selftest_case(
        "html entity and region comment",
        "sample.html",
        '<p>&#39;quoted&#39;</p>\n<script>\n// #region setup\nconst c = "#abcdef";\n</script>\n',
        expect_literals=["#abcdef"],
        expect_absent=["#39", "#region"],
    )

    all_ok &= _selftest_case(
        "python comment vs string",
        "sample.py",
        "# deadbeef is not a colour, it's a comment\nCOLOR = '#deadbe'\nOTHER = 'just some red text in prose'\n",
        expect_literals=["#deadbe"],
        expect_absent=["deadbeef"],
    )

    all_ok &= _selftest_case(
        "var fallback is a warning not an error",
        "sample.css",
        ".x { color: var(--text, #fff); border-color: #000000; }\n",
        expect_literals=["#fff", "#000000"],
        expect_absent=[],
    )
    with tempfile.TemporaryDirectory(prefix="lint_colors_selftest_") as tmp:
        path = Path(tmp) / "warn.css"
        path.write_text(".x { color: var(--text, #fff); }\n", encoding="utf-8")
        lines, errors, warnings = lint_file(path, strict=False)
        if errors == 0 and warnings == 1:
            print("PASS var-fallback severity (warn, not error)")
        else:
            print(f"FAIL var-fallback severity: errors={errors} warnings={warnings}")
            all_ok = False
        lines, errors, warnings = lint_file(path, strict=True)
        if errors == 1 and warnings == 0:
            print("PASS var-fallback severity under --strict (promoted to error)")
        else:
            print(f"FAIL var-fallback under --strict: errors={errors} warnings={warnings}")
            all_ok = False

    all_ok &= _selftest_case(
        "allow-line marker suppresses a real hit",
        "sample.css",
        ".x { color: #ff00ff; }  /* theme-lint: allow */\n.y { color: #00ff00; }\n",
        expect_literals=["#00ff00"],
        expect_absent=["#ff00ff"],
    )

    # Always-allowed filenames are skipped outright, even with real colours.
    with tempfile.TemporaryDirectory(prefix="lint_colors_selftest_") as tmp:
        for fn in ("theme-purple.css", "ui-theme.js", "ui-theme.custom.css"):
            (Path(tmp) / fn).write_text("body { color: #ff0000; }", encoding="utf-8")
        files = [f for f in iter_candidate_files([tmp]) if not is_always_allowed(f, [])]
        if files:
            print(f"FAIL always-allowed filenames were not skipped: {files}")
            all_ok = False
        else:
            print("PASS always-allowed filenames (theme-*.css, ui-theme*) are skipped")

    print("SELF-TEST " + ("PASS" if all_ok else "FAIL"))
    return 0 if all_ok else 1


# ======================================================================= IO


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Equivalent ripgrep one-liner:\n\n    " + RIPGREP_EQUIVALENT + "\n",
    )
    parser.add_argument("paths", nargs="*", metavar="PATH", help="files or directories to walk")
    parser.add_argument("--allow", action="append", default=[], metavar="GLOB", help="repeatable; extra paths/basenames to skip")
    parser.add_argument("--quiet", action="store_true", help="print only the summary")
    parser.add_argument("--strict", action="store_true", help="fail on var(--x, #fallback)-style hits too")
    parser.add_argument("--self-test", action="store_true", help="run the built-in self-test and exit")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.paths:
        parser.error("PATH... is required (or pass --self-test)")

    all_files = iter_candidate_files(args.paths)
    scanned, allowed = [], 0
    for f in all_files:
        if is_always_allowed(f, args.allow):
            allowed += 1
        else:
            scanned.append(f)

    total_errors = total_warnings = 0
    for f in sorted(scanned):
        lines, errors, warnings = lint_file(f, args.strict)
        total_errors += errors
        total_warnings += warnings
        if not args.quiet:
            for line in lines:
                print(line)

    print("--- summary ---")
    print(f"files scanned: {len(scanned)}  (allowed/skipped: {allowed})")
    print(f"errors: {total_errors}  warnings: {total_warnings}")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
