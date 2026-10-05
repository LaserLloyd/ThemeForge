#!/usr/bin/env python3
"""Measure WCAG 2 contrast for every theme against the contract's floors.

    python tools/check_contrast.py [--theme SLUG ...] [--out FILE] [--fail-on {any,none}]

Reads src/themes.json, src/css/theme-base.css and each src/css/theme-<slug>.css.
Purple is every `:root { ... }` block in theme-base.css; every other theme is
Purple overlaid with its own `[data-palette="<slug>"] { ... }` block, the same
cascade the browser uses: a token a theme does not declare is inherited.

var(--x) and var(--x, fallback) resolve recursively against the theme's merged
tokens, and color-mix(in srgb, ...) is evaluated. A translucent foreground is
composited over its background; a translucent background is first composited
over --surface-0 unless a check names another ground (status callouts sit on
--surface-2, so their -subtle fills are composited over it).

What it checks, per theme:
  - every text tier on every surface the theme defines (text-primary 7:1,
    text-secondary 4.5:1 and 6:1 on surface-2, text-tertiary 4.5:1,
    text-disabled 3:1), and every status text on --surface-3 and on its own
    -subtle fill;
  - labels on fills: on-accent, on-cta and every on-<status> on its fill;
  - control boundaries (border-strong, control-track, focus-ring) at 3:1;
  - control states: on-selected on --selected, --selected against the
    surfaces, the off state (--unselected-border, --unselected-fg) against
    the surfaces, and a visible step from enabled (text-secondary) to
    disabled (text-disabled) text;
  - syntax colours on --syn-bg, syn-fg on --code-bg, the code bar label on
    --code-header-bg, categorical colours on --surface-0, md-bold, and the
    two chat bubbles against each other.

Contrast profiles: a theme may name one with "contrastProfile" in
src/themes.json. "standard" is the default. "night" is for red-on-black night
themes. With zero blue, text gains luminance only through the green channel,
which pulls it toward orange, so --text-primary's 7:1 would take the text out
of the red family. The night profile sets --text-primary 5.5:1, --text-secondary
4.5:1 everywhere, --text-tertiary 4:1, --text-disabled 2:1 and --md-bold 6:1,
and adds what a dim red theme needs most: outlines and strokes against the
surfaces they sit on, a visible surface step, a visible step between text
tiers, and colour separation between the accent, danger and body text,
measured both as a ratio and as CIEDE2000 (dE00). It also reports APCA Lc for
the text tiers (WCAG 2 overstates saturated light text on black) and runs a
zero-blue audit: every colour the theme ends up with must have a blue channel
of 0.

Output is one markdown table per theme plus a summary. --fail-on any (the
default) exits 1 when any check fails. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

BASE_SLUG = "purple"

STATUSES = ["success", "warning", "danger", "info", "live", "idle", "offline", "heartbeat"]

# Floors a theme opts into with "contrastProfile" in src/themes.json, keyed by
# the checked (foreground) token; a token not listed keeps the standard floor.
# "night": pure red tops out at 5.25:1 on black (see the module docstring).
CONTRAST_PROFILES: dict[str, dict] = {
    "standard": {"floors": {}, "zero_blue": False},
    "night": {
        "floors": {
            "text-primary": 5.5,
            "text-secondary": 4.5,
            "text-tertiary": 4.0,
            "text-disabled": 2.0,
            "md-bold": 6.0,
        },
        "zero_blue": True,
        "extra": True,
    },
}

# Night-profile structure, ladder and separation rows, appended
# after the profile's floors are applied so that a ladder row whose
# foreground is --text-primary keeps its own floor. Each row is (label, fg,
# bg, floor, mode). "normal" is a contrast ratio; "above" is the same ratio
# taken in one direction, (L_fg + .05) / (L_bg + .05), so an inverted
# ladder or a surface darker than the page falls below 1 and fails;
# "delta_e" is CIEDE2000 between the two resolved colours (translucent ones
# composited over --surface-0 first). A floor of 0 marks a reported row:
# measured and printed, never failed.
NIGHT_EXTRA: list[tuple[str, str, str, float, str]] = [
    ("border on surface-0 (card and panel outlines)", "border", "surface-0", 1.8, "normal"),
    ("border on surface-2 (card and panel outlines)", "border", "surface-2", 1.8, "normal"),
    ("border-subtle on surface-0", "border-subtle", "surface-0", 1.25, "normal"),
    ("border-subtle on surface-2", "border-subtle", "surface-2", 1.2, "normal"),
    ("divider on surface-2", "divider", "surface-2", 1.2, "normal"),
    ("glass-stroke on surface-0", "glass-stroke", "surface-0", 1.6, "normal"),
    ("glass-stroke on surface-2", "glass-stroke", "surface-2", 1.6, "normal"),
    ("glass-stroke-strong on surface-0", "glass-stroke-strong", "surface-0", 2.2, "normal"),
    ("scrollbar-thumb on surface-0", "scrollbar-thumb", "surface-0", 1.4, "normal"),
    ("surface-2 steps up from surface-0", "surface-2", "surface-0", 1.04, "above"),
    ("text ladder: primary above secondary", "text-primary", "text-secondary", 1.15, "above"),
    ("text ladder: secondary above tertiary", "text-secondary", "text-tertiary", 1.15, "above"),
    ("text ladder: tertiary above disabled", "text-tertiary", "text-disabled", 1.4, "above"),
    ("accent vs danger (Save vs Delete)", "accent", "danger", 1.3, "normal"),
    ("accent vs danger", "accent", "danger", 15, "delta_e"),
    ("danger-text vs text-primary (an error line stands out)", "danger-text", "text-primary", 10, "delta_e"),
    ("danger vs warning", "danger", "warning", 12, "delta_e"),
    ("warning vs info", "warning", "info", 12, "delta_e"),
    ("info vs success", "info", "success", 10, "delta_e"),
    ("md-bold vs danger-text (bold prose is not an error)", "md-bold", "danger-text", 10, "delta_e"),
    ("text-link vs warning-text (reported)", "text-link", "warning-text", 0, "delta_e"),
    ("text-secondary on bubble-user-bg (reported)", "text-secondary", "bubble-user-bg", 0, "normal"),
    ("text-tertiary on bubble-user-bg (reported)", "text-tertiary", "bubble-user-bg", 0, "normal"),
]

# Text tiers whose APCA Lc the night profile reports (not gated).
APCA_TOKENS = ["text-primary", "text-secondary", "text-tertiary", "text-disabled", "md-bold", "text-link", "danger-text"]
APCA_GROUNDS = ["surface-0", "surface-2"]

# Contract order (the Syntax group), syn-bg excluded — it is the ground,
# never checked against itself.
SYN_TOKENS_ORDER = [
    "syn-fg", "syn-comment", "syn-keyword", "syn-string", "syn-number",
    "syn-function", "syn-title", "syn-type", "syn-variable", "syn-attr",
    "syn-tag", "syn-builtin", "syn-literal", "syn-meta", "syn-operator",
    "syn-punctuation", "syn-deletion", "syn-addition",
]


# ============================================================== CSS parsing

COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
DECL_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;]+);")


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def find_blocks(text: str, selector_re: "re.Pattern[str]") -> list[str]:
    """Return the {...} body of every top-level match of selector_re (which
    must match through the opening brace)."""
    blocks = []
    for m in selector_re.finditer(text):
        depth = 1
        j = m.end()
        start = j
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        blocks.append(text[start : j - 1])
    return blocks


def parse_declarations(block_text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for m in DECL_RE.finditer(block_text):
        props[m.group(1)] = m.group(2).strip()
    return props


ROOT_RE = re.compile(r":root\s*\{")


def load_base_props(base_css_text: str) -> dict[str, str]:
    text = strip_comments(base_css_text)
    props: dict[str, str] = {}
    for block in find_blocks(text, ROOT_RE):
        props.update(parse_declarations(block))
    return props


def load_theme_own_props(theme_css_text: str, slug: str) -> dict[str, str]:
    text = strip_comments(theme_css_text)
    pattern = re.compile(re.escape(f'[data-palette="{slug}"]') + r"\s*\{")
    props: dict[str, str] = {}
    for block in find_blocks(text, pattern):
        props.update(parse_declarations(block))
    return props


# ========================================================== var() expansion


def _find_matching_paren(s: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_comma(s: str) -> tuple[str, str | None]:
    depth = 0
    for i, ch in enumerate(s):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            return s[:i], s[i + 1 :]
    return s, None


def expand(text: str | None, props: dict[str, str], stack: frozenset[str] = frozenset(), depth: int = 0) -> str:
    """Resolve every var(--x) / var(--x, fallback) in text, recursively."""
    if text is None:
        return ""
    if depth > 40:
        return text
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i : i + 4] == "var(":
            open_idx = i + 3
            close_idx = _find_matching_paren(text, open_idx)
            if close_idx == -1:
                out.append(text[i:])
                break
            inner = text[open_idx + 1 : close_idx]
            name_part, fallback_part = _split_top_comma(inner)
            name = name_part.strip()
            value = None if name in stack else props.get(name)
            if value is not None:
                out.append(expand(value, props, stack | {name}, depth + 1))
            elif fallback_part is not None:
                out.append(expand(fallback_part.strip(), props, stack, depth + 1))
            # else: unresolved and no fallback -> contributes nothing
            i = close_idx + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def resolve(name: str, props: dict[str, str]) -> str | None:
    raw = props.get(name)
    if raw is None:
        return None
    value = expand(raw, props, frozenset({name}))
    return eval_color_mix(value) if MIX_RE.search(value) else value


# ================================================================== colour

HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_FUNC_RE = re.compile(r"^rgba?\((.*)\)$", re.I)
COLOR_TOKEN_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", re.I)

RGBA = tuple[float, float, float, float]


MIX_RE = re.compile(r"color-mix\(", re.I)


def _mix_part(part: str) -> tuple[RGBA | None, float | None]:
    m = re.match(r"^(.*?)(?:\s+(\d*\.?\d+)%)?$", part.strip())
    colour = parse_color(m.group(1).strip())
    return colour, (float(m.group(2)) / 100 if m.group(2) else None)


def eval_color_mix(value: str) -> str:
    """Replace every color-mix(in srgb, A [p%], B [q%]) in value with rgba(),
    innermost first: premultiplied-alpha interpolation, as CSS Color 5 does."""
    while True:
        hits = list(MIX_RE.finditer(value))
        if not hits:
            return value
        m = hits[-1]
        close = _find_matching_paren(value, m.end() - 1)
        if close < 0:
            return value
        inner = value[m.end():close]
        space, rest = _split_top_comma(inner)
        a_part, b_part = _split_top_comma(rest or "")
        if space.strip().lower() != "in srgb" or b_part is None:
            return value
        (a, pa), (b, pb) = _mix_part(a_part), _mix_part(b_part)
        if a is None or b is None:
            return value
        if pa is None and pb is None:
            pa = pb = 0.5
        elif pa is None:
            pa = 1 - pb
        elif pb is None:
            pb = 1 - pa
        total = pa + pb
        pa, pb = pa / total, pb / total
        alpha = a[3] * pa + b[3] * pb
        if alpha <= 0:
            rgb = (0.0, 0.0, 0.0)
        else:
            rgb = tuple((a[i] * a[3] * pa + b[i] * b[3] * pb) / alpha for i in range(3))
        mixed = "rgba(%.4f,%.4f,%.4f,%.4f)" % (rgb[0], rgb[1], rgb[2], alpha * min(total, 1.0))
        value = value[:m.start()] + mixed + value[close + 1:]


def parse_color(value: str | None) -> RGBA | None:
    if value is None:
        return None
    v = value.strip()
    if v.lower() == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if MIX_RE.search(v):
        v = eval_color_mix(v)
    m = HEX_RE.match(v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            r, g, b = (int(c * 2, 16) for c in h)
            return (float(r), float(g), float(b), 1.0)
        if len(h) == 4:
            r, g, b, a = (int(c * 2, 16) for c in h)
            return (float(r), float(g), float(b), a / 255.0)
        if len(h) == 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (float(r), float(g), float(b), 1.0)
        if len(h) == 8:
            r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
            return (float(r), float(g), float(b), a / 255.0)
    m = RGB_FUNC_RE.match(v)
    if m:
        inner = m.group(1).strip()
        parts = [p.strip() for p in inner.split(",") if p.strip() != ""]
        if len(parts) < 3:
            parts = [p for p in re.split(r"[\s/]+", inner) if p]

        def num(p: str, is_alpha: bool) -> float:
            p = p.strip()
            if p.endswith("%"):
                frac = float(p[:-1]) / 100.0
                return frac if is_alpha else frac * 255.0
            return float(p)

        if len(parts) >= 3:
            r, g, b = num(parts[0], False), num(parts[1], False), num(parts[2], False)
            a = num(parts[3], True) if len(parts) > 3 else 1.0
            return (r, g, b, a)
    return None


def srgb_channel_to_linear(c: float) -> float:
    c = max(0.0, min(255.0, c)) / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.2126 * srgb_channel_to_linear(r) + 0.7152 * srgb_channel_to_linear(g) + 0.0722 * srgb_channel_to_linear(b)


def contrast_ratio(rgb1: tuple[float, float, float], rgb2: tuple[float, float, float]) -> float:
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def apca_lc(text_rgb: tuple[float, float, float], bg_rgb: tuple[float, float, float]) -> float:
    """APCA 0.0.98G-4g lightness contrast (Lc). Negative is light text on a
    dark ground. Reported only; no floor in this tool reads it."""

    def y(rgb):
        r, g, b = (max(0.0, min(255.0, c)) / 255.0 for c in rgb)
        return 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4

    def clamp(v):
        return v if v > 0.022 else v + (0.022 - v) ** 1.414

    yt, yb = clamp(y(text_rgb)), clamp(y(bg_rgb))
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:
        s = (yb ** 0.56 - yt ** 0.57) * 1.14
        return 0.0 if s < 0.1 else (s - 0.027) * 100
    s = (yb ** 0.65 - yt ** 0.62) * 1.14
    return 0.0 if s > -0.1 else (s + 0.027) * 100


def _lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (srgb_channel_to_linear(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    yy = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x), f(yy), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e00(rgb1: tuple[float, float, float], rgb2: tuple[float, float, float]) -> float:
    """CIEDE2000 colour difference (Sharma, Wu and Dalal, 2005)."""
    import math

    l1, a1, b1 = _lab(rgb1)
    l2, a2, b2 = _lab(rgb2)
    cbar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cbar ** 7 / (cbar ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dlp, dcp = l2 - l1, c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dhp_big = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp / 2))
    lbp, cbp = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    else:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dtheta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cbp ** 7 / (cbp ** 7 + 25 ** 7))
    sl = 1 + 0.015 * (lbp - 50) ** 2 / math.sqrt(20 + (lbp - 50) ** 2)
    sc = 1 + 0.045 * cbp
    sh = 1 + 0.015 * cbp * t
    rt = -math.sin(math.radians(2 * dtheta)) * rc
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp_big / sh) ** 2 + rt * (dcp / sc) * (dhp_big / sh))


def composite(fg: RGBA, bg_opaque: RGBA) -> RGBA:
    """Alpha-composite fg over an opaque background, rounding each channel to
    the nearest 8-bit value, as rendering onto an 8-bit canvas does."""
    a = max(0.0, min(1.0, fg[3]))
    r = round(fg[0] * a + bg_opaque[0] * (1 - a))
    g = round(fg[1] * a + bg_opaque[1] * (1 - a))
    b = round(fg[2] * a + bg_opaque[2] * (1 - a))
    return (float(r), float(g), float(b), 1.0)


def over_surface0(color: RGBA, surface0: RGBA) -> RGBA:
    return composite(color, surface0) if color[3] < 1.0 else color


def fmt_color(rgba: RGBA) -> str:
    r, g, b, a = rgba
    if a >= 1.0:
        return "#%02x%02x%02x" % (round(r), round(g), round(b))
    return "rgba(%d,%d,%d,%.3g)" % (round(r), round(g), round(b), a)


# ============================================================ check tables


def status_checks() -> list[tuple[str, str, str, float]]:
    out = []
    for s in STATUSES:
        out.append((f"{s}-text on surface-2", f"{s}-text", "surface-2", 4.5))
        out.append((f"on-{s} on {s}", f"on-{s}", s, 4.5))
    return out


# Grounds the "text on every ground" group iterates. --glass-3 is translucent
# in most themes and is composited over --surface-0 like any other background.
EVERY_GROUND = ["surface-0", "surface-1", "surface-2", "surface-3", "surface-4", "surface-sunken", "glass-3"]

# (token, floor, grounds already covered by a pre-existing, separately-tracked
# check in build_checks() and therefore skipped here so no pair is measured
# twice). text-primary keeps its surface-0/surface-2 rows at their existing 7:1
# floor; text-secondary keeps its surface-2 row at the contract's stricter 6:1
# promise. Both floors already match this group's own floor for those tokens
# except text-secondary/surface-2, which is intentionally stricter.
TEXT_TIERS: list[tuple[str, float, set[str]]] = [
    ("text-primary", 7, {"surface-0", "surface-2"}),
    ("text-secondary", 4.5, {"surface-2"}),
    ("text-tertiary", 4.5, set()),
    ("text-disabled", 3, set()),
    ("text-link", 4.5, set()),
]


def every_ground_checks(props: dict[str, str]) -> list[tuple[str, str, str, float]]:
    """Each text tier against every surface the theme defines, plus each
    status text against --surface-3 (zebra rows, tab bars). Generated from
    EVERY_GROUND/TEXT_TIERS/STATUSES, so a new surface is covered at once."""
    grounds = [g for g in EVERY_GROUND if resolve(f"--{g}", props) is not None]
    out = []
    for token, floor, already_covered in TEXT_TIERS:
        for g in grounds:
            if g in already_covered:
                continue
            out.append((f"{token} on {g}", token, g, floor))
    if "surface-3" in grounds:
        for s in STATUSES:
            out.append((f"{s}-text on surface-3 (zebra row, tab bar)", f"{s}-text", "surface-3", 4.5))
    return out


def status_subtle_checks() -> list[tuple[str, str, str, float]]:
    """Status text renders on its own --{status}-subtle fill in callouts and
    badges, so it is checked there too, composited over --surface-2."""
    return [(f"{s}-text on {s}-subtle (over surface-2)", f"{s}-text", f"{s}-subtle", 4.5) for s in STATUSES]


def syn_checks(props: dict[str, str]) -> list[tuple[str, str, str, float]]:
    order = list(SYN_TOKENS_ORDER)
    for key in props:
        if key.startswith("--syn-") and key != "--syn-bg" and key[2:] not in order:
            order.append(key[2:])
    return [(f"{tok} on syn-bg", tok, "syn-bg", 3.5 if tok == "syn-comment" else 4.5) for tok in order]


CAT_RE = re.compile(r"^--cat-(\d+)$")


def cat_checks(props: dict[str, str]) -> list[tuple[str, str, str, float]]:
    nums = sorted((int(m.group(1)) for k in props if (m := CAT_RE.match(k))))
    return [(f"cat-{n} on surface-0", f"cat-{n}", "surface-0", 3.0) for n in nums]


def build_checks(props: dict[str, str]) -> list[dict]:
    """Every (label, fg, bg, floor, mode) row for one theme's merged props."""
    checks: list[dict] = []

    def add(label, fg, bg, floor, mode="normal", base=None, fixed=False):
        checks.append({"label": label, "fg": fg, "bg": bg, "floor": floor, "mode": mode, "base": base,
                       "fixed": fixed})

    add("text-primary on surface-0", "text-primary", "surface-0", 7)
    add("text-primary on surface-2", "text-primary", "surface-2", 7)
    add("text-secondary on surface-2 — the contract's 6:1 promise", "text-secondary", "surface-2", 6)

    for label, fg, bg, floor in every_ground_checks(props):
        add(label, fg, bg, floor)

    add("on-accent on accent", "on-accent", "accent", 4.5)
    add("on-accent on accent-hover", "on-accent", "accent-hover", 4.5)
    add("on-accent on accent-pressed", "on-accent", "accent-pressed", 4.5)
    add("on-cta on cta", "on-cta", "cta", 4.5)

    for label, fg, bg, floor in status_checks():
        add(label, fg, bg, floor)
    for label, fg, bg, floor in status_subtle_checks():
        add(label, fg, bg, floor, base="surface-2")

    add("focus-ring on surface-0", "focus-ring", "surface-0", 3)
    add("focus-ring on surface-2", "focus-ring", "surface-2", 3)
    add("border-strong on surface-2", "border-strong", "surface-2", 3)
    add("border-strong on surface-0", "border-strong", "surface-0", 3)
    add("control-track on surface-2", "control-track", "surface-2", 3)
    add("control-track on surface-0", "control-track", "surface-0", 3)

    # Control states: what is on/checked/selected must read as such, the off
    # state must still be visible, and disabled text must sit visibly below
    # enabled text. (Shape carries the state too: see components.css.)
    add("on-selected on selected (tick, knob, pressed label)", "on-selected", "selected", 4.5)
    for g in ("surface-0", "surface-1", "surface-2", "surface-sunken"):
        add(f"selected on {g} (on/checked/current indicator)", "selected", g, 3)
    for g in ("surface-0", "surface-1", "surface-2"):
        add(f"unselected-border on {g} (off control outline)", "unselected-border", g, 3)
        add(f"unselected-fg on {g} (off switch knob)", "unselected-fg", g, 3)
    add("text-secondary vs text-disabled (enabled vs disabled)", "text-secondary", "text-disabled", 1.5,
        fixed=True)

    add("on-media on scrim-media (dark stop, over #ffffff)", "on-media", "scrim-media", 4.5, mode="media")

    for label, fg, bg, floor in syn_checks(props):
        add(label, fg, bg, floor)
    add("syn-fg on code-bg — markdown code blocks", "syn-fg", "code-bg", 4.5)
    add("syn-fg on code-header-bg — code bar buttons", "syn-fg", "code-header-bg", 4.5)
    add("syn-comment on code-header-bg — code bar label", "syn-comment", "code-header-bg", 3.5)
    for label, fg, bg, floor in cat_checks(props):
        add(label, fg, bg, floor)

    add("md-bold on surface-2", "md-bold", "surface-2", 7)

    # Pairs the component layer and the text standard render.
    add("bubble-user-text on bubble-user-bg", "bubble-user-text", "bubble-user-bg", 4.5)
    add("bubble-assistant-text on bubble-assistant-bg", "bubble-assistant-text", "bubble-assistant-bg", 4.5)
    for s in ("success", "warning", "danger", "info"):
        add(f"text-primary on {s}-subtle (status callout body, over surface-2)", "text-primary",
            f"{s}-subtle", 4.5, base="surface-2", fixed=True)
    for role in ("rp-speech", "rp-action", "rp-thought", "rp-whisper", "rp-ooc", "rp-shout", "rp-critical"):
        add(f"{role} on surface-2 (narrative text role)", role, "surface-2", 4.5)
    add("diff-add-text on diff-add-bg (over surface-2)", "diff-add-text", "diff-add-bg", 4.5, base="surface-2")
    add("diff-remove-text on diff-remove-bg (over surface-2)", "diff-remove-text", "diff-remove-bg", 4.5,
        base="surface-2")
    add("chart-axis on surface-0 (graphic)", "chart-axis", "surface-0", 3)
    add("seq-5 vs seq-1 (ramp ends apart)", "seq-5", "seq-1", 3, base="surface-2", fixed=True)
    add("seq-5 on surface-2 (graphic)", "seq-5", "surface-2", 3)
    add("div-1 on surface-2 (graphic)", "div-1", "surface-2", 3)
    add("div-5 on surface-2 (graphic)", "div-5", "surface-2", 3)
    add("canvas-handle on canvas-mask (graphic, over surface-0)", "canvas-handle", "canvas-mask", 3)
    add("canvas-outline on canvas-mask (graphic, over surface-0)", "canvas-outline", "canvas-mask", 3)
    add("bubble-user-bg vs bubble-assistant-bg", "bubble-user-bg", "bubble-assistant-bg", 1.3, mode="bubble")

    return checks


def apply_profile(checks: list[dict], profile_name: str) -> list[dict]:
    """Replace the floor of every check whose foreground token the profile
    lists. The label names the profile, so a row can't claim the standard
    promise (e.g. "the contract's 6:1 promise") at a different floor."""
    floors = CONTRAST_PROFILES[profile_name]["floors"]
    out = []
    for c in checks:
        new_floor = None if c.get("fixed") else floors.get(c["fg"])
        if new_floor is not None and new_floor != c["floor"]:
            c = dict(c, floor=new_floor, label=f"{c['fg']} on {c['bg']} ({profile_name} profile)")
        out.append(c)
    return out


def _colours_in(name: str, value: str) -> list[RGBA]:
    """Every colour literal in a resolved token value. --*-rgb tokens are a
    bare comma triple ("240,0,0"), read as an opaque colour."""
    if name.endswith("-rgb"):
        parts = [p.strip() for p in value.split(",")]
        if len(parts) == 3 and all(p.replace(".", "", 1).isdigit() for p in parts):
            return [(float(parts[0]), float(parts[1]), float(parts[2]), 1.0)]
        return []
    found = []
    for m in COLOR_TOKEN_RE.finditer(value):
        c = parse_color(m.group(0))
        if c is not None:
            found.append(c)
    return found


ALIAS_RE = re.compile(r"^\s*var\(--[\w-]+\)\s*$")
# Colour syntax parse_color() does not read. The audit can't prove a zero blue
# channel for these, so it fails them rather than passing them silently.
UNPARSED_FUNC_RE = re.compile(r"\b(?:hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(", re.I)
QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
CSS_NAMED_COLOURS = frozenset("""
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue
blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk
crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki
darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue
dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite
gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki
lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen
lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen
magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen
mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream
mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid
palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum
powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown
seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen
steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen
""".split())


def _unparsed_colour(value: str) -> bool:
    """True when a resolved value holds colour syntax the audit can't read:
    a colour function other than rgb()/rgba(), or a CSS named colour outside
    a quoted string (so a font called 'Crimson Pro' doesn't trip it)."""
    bare = QUOTED_RE.sub("", value)
    if UNPARSED_FUNC_RE.search(bare):
        return True
    return any(word.lower() in CSS_NAMED_COLOURS for word in re.findall(r"[A-Za-z]+", bare))


def zero_blue_audit(props: dict[str, str]) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """(tokens carrying any blue, tokens in colour syntax the audit can't
    read, tokens lighting green) over the merged props, each as (token,
    resolved value). A colour at alpha 0 emits nothing and is ignored. A bare
    alias (`--slider-color: var(--accent)`) is skipped: its target is audited
    under its own name, so counting it again would only inflate the lists."""
    blue, unparsed, green = [], [], []
    for name in sorted(props):
        if ALIAS_RE.match(props[name]):
            continue
        value = resolve(name, props) or ""
        if _unparsed_colour(value):
            unparsed.append((name, value))
            continue
        colours = [c for c in _colours_in(name, value) if c[3] > 0]
        if any(round(c[2]) > 0 for c in colours):
            blue.append((name, value))
        elif any(round(c[1]) > 0 for c in colours):
            green.append((name, value))
    return blue, unparsed, green


def render_zero_blue(blue: list[tuple[str, str]], unparsed: list[tuple[str, str]], green: list[tuple[str, str]]) -> str:
    lines = ["### Zero-blue audit (night profile)", ""]
    if blue or unparsed:
        lines.append(f"**FAIL**: {len(blue)} token(s) carry blue; {len(unparsed)} use colour syntax the audit can't read:")
        lines.append("")
        lines.append("| Token | Resolved value | Problem |")
        lines.append("|---|---|---|")
        lines.extend(f"| {n} | {v} | carries blue |" for n, v in blue)
        lines.extend(f"| {n} | {v} | unparsed colour |" for n, v in unparsed)
    else:
        lines.append("pass: no token carries any blue.")
    lines.append("")
    lines.append(f"Tokens that light the green channel ({len(green)}), the theme's non-red elements: "
                 + ", ".join(f"`{n}`" for n, _ in green) if green else "No token lights the green channel.")
    lines.append("")
    return "\n".join(lines)


def render_apca(props: dict[str, str], surface0: RGBA) -> str:
    """APCA Lc for the text tiers on the main grounds (night profile; reported,
    not gated). APCA's guidance for reading: about Lc 75 for body columns,
    60 for other content text, 45 for large or bold headings, 30 as the floor
    for any text at all. No zero-blue red reaches 60 on black: #ff9700 is the
    first to, and it is orange."""
    lines = ["### APCA lightness contrast (reported, not gated)", "",
             "| Token | " + " | ".join(APCA_GROUNDS) + " |", "|---|" + "---|" * len(APCA_GROUNDS)]
    for tok in APCA_TOKENS:
        fg = parse_color(resolve(f"--{tok}", props))
        if fg is None:
            continue
        cells = []
        for g in APCA_GROUNDS:
            bg = parse_color(resolve(f"--{g}", props))
            if bg is None:
                cells.append("n/a")
                continue
            bg_eff = over_surface0(bg, surface0)
            fg_eff = composite(fg, bg_eff) if fg[3] < 1.0 else fg
            cells.append(f"Lc {apca_lc(fg_eff[:3], bg_eff[:3]):.1f}")
        lines.append(f"| {tok} | " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def run_check(check: dict, props: dict[str, str], surface0: RGBA) -> dict:
    label, floor, mode = check["label"], check["floor"], check["mode"]
    fg_name, bg_name = check["fg"], check["bg"]

    if mode == "media":
        fg_raw = resolve(f"--{fg_name}", props)
        bg_raw = resolve(f"--{bg_name}", props)
        fg_color = parse_color(fg_raw)
        stop_match = COLOR_TOKEN_RE.search(bg_raw) if bg_raw else None
        stop = parse_color(stop_match.group(0)) if stop_match else None
        if fg_color is None or stop is None:
            return _error_row(label, fg_name, bg_name, fg_raw, bg_raw, floor)
        white: RGBA = (255.0, 255.0, 255.0, 1.0)
        bg_eff = composite(stop, white)
        fg_eff = composite(fg_color, bg_eff) if fg_color[3] < 1.0 else fg_color
        ratio = contrast_ratio(fg_eff[:3], bg_eff[:3])
        return _row(label, fg_name, bg_name, fg_raw, stop_match.group(0), ratio, floor)

    if mode == "delta_e":
        fg_raw = resolve(f"--{fg_name}", props)
        bg_raw = resolve(f"--{bg_name}", props)
        fg_color, bg_color = parse_color(fg_raw), parse_color(bg_raw)
        if fg_color is None or bg_color is None:
            return _error_row(label, fg_name, bg_name, fg_raw, bg_raw, floor)
        a = over_surface0(fg_color, surface0)
        b = over_surface0(bg_color, surface0)
        row = _row(label, fg_name, bg_name, fg_raw, bg_raw, delta_e00(a[:3], b[:3]), floor)
        row["unit"] = "dE00"
        return row

    if mode == "bubble":
        fg_raw = resolve(f"--{fg_name}", props)
        bg_raw = resolve(f"--{bg_name}", props)
        fg_color, bg_color = parse_color(fg_raw), parse_color(bg_raw)
        if fg_color is None or bg_color is None:
            return _error_row(label, fg_name, bg_name, fg_raw, bg_raw, floor)
        a = over_surface0(fg_color, surface0)
        b = over_surface0(bg_color, surface0)
        ratio = contrast_ratio(a[:3], b[:3])
        return _row(label, fg_name, bg_name, fg_raw, bg_raw, ratio, floor)

    # normal
    fg_raw = resolve(f"--{fg_name}", props)
    bg_raw = resolve(f"--{bg_name}", props)
    fg_color, bg_color = parse_color(fg_raw), parse_color(bg_raw)
    if fg_color is None or bg_color is None:
        return _error_row(label, fg_name, bg_name, fg_raw, bg_raw, floor)
    ground = surface0
    base_name = check.get("base")
    if base_name:
        # bg sits on a named ground (e.g. a status-subtle fill rendered over
        # --surface-2) rather than directly on --surface-0.
        base_color = parse_color(resolve(f"--{base_name}", props))
        if base_color is None:
            return _error_row(label, fg_name, bg_name, fg_raw, bg_raw, floor)
        ground = over_surface0(base_color, surface0)
    bg_eff = over_surface0(bg_color, ground)
    fg_eff = composite(fg_color, bg_eff) if fg_color[3] < 1.0 else fg_color
    if mode == "above":
        ratio = (relative_luminance(fg_eff[:3]) + 0.05) / (relative_luminance(bg_eff[:3]) + 0.05)
    else:
        ratio = contrast_ratio(fg_eff[:3], bg_eff[:3])
    return _row(label, fg_name, bg_name, fg_raw, bg_raw, ratio, floor)


def _fmt_raw(raw: str | None) -> str:
    return raw if raw is not None else "?"


def _row(label, fg_name, bg_name, fg_raw, bg_raw, ratio, floor) -> dict:
    return {
        "label": label,
        "fg_token": fg_name,
        "bg_token": bg_name,
        "fg_display": _fmt_raw(fg_raw),
        "bg_display": _fmt_raw(bg_raw),
        "ratio": ratio,
        "floor": floor,
        "pass": ratio >= floor - 1e-9,
        "error": None,
    }


def _error_row(label, fg_name, bg_name, fg_raw, bg_raw, floor) -> dict:
    return {
        "label": label,
        "fg_token": fg_name,
        "bg_token": bg_name,
        "fg_display": _fmt_raw(fg_raw),
        "bg_display": _fmt_raw(bg_raw),
        "ratio": None,
        "floor": floor,
        "pass": False,
        "error": "unparsed colour",
    }


# ======================================================================= IO


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_registry() -> list[dict]:
    data = json.loads(read(SRC / "themes.json"))
    return data["themes"]


def merged_props(theme: dict, base_props: dict[str, str]) -> dict[str, str]:
    if theme["slug"] == BASE_SLUG:
        return dict(base_props)
    css_text = read(SRC / "css" / theme["css"])
    own = load_theme_own_props(css_text, theme["slug"])
    return {**base_props, **own}


# =================================================================== report


def render_theme_section(theme: dict, rows: list[dict]) -> tuple[str, int]:
    profile = theme.get("contrastProfile", "standard")
    suffix = "" if profile == "standard" else f" · contrast profile {profile}"
    lines = [f"## {theme['slug']} — {theme['set']} · ground {theme['ground']}{suffix}", ""]
    lines.append("| Pair | fg | bg | Ratio | Floor | Result |")
    lines.append("|---|---|---|---|---|---|")
    failures = 0
    for r in rows:
        is_de = r.get("unit") == "dE00"
        floor_s = f"dE00 {r['floor']:g}" if is_de else f"{r['floor']:g}:1"
        if r["error"]:
            result = f"ERROR ({r['error']})"
            ratio_s = "n/a"
            failures += 1
        else:
            ratio_s = f"dE00 {r['ratio']:.1f}" if is_de else f"{r['ratio']:.2f}"
            if r["floor"] == 0:
                result = "reported"
                floor_s = "none"
            elif r["pass"]:
                result = "pass"
            else:
                failures += 1
                result = "**FAIL**"
        lines.append(f"| {r['label']} | {r['fg_display']} | {r['bg_display']} | {ratio_s} | {floor_s} | {result} |")
    lines.append("")
    return "\n".join(lines), failures


def build_report(slugs: list[str] | None) -> tuple[str, list[dict]]:
    """(markdown report, one summary row per theme). Raises ValueError on an
    unknown slug or a theme whose --surface-0 is not a colour."""
    registry = load_registry()
    by_slug = {t["slug"]: t for t in registry}
    if slugs:
        unknown = [x for x in slugs if x not in by_slug]
        if unknown:
            raise ValueError(f"unknown theme(s) {unknown}; known: {sorted(by_slug)}")
        selected = [by_slug[x] for x in slugs]
    else:
        selected = registry

    base_props = load_base_props(read(SRC / "css" / "theme-base.css"))
    out_lines = ["# Contrast report", "",
                 "Generated by `tools/check_contrast.py` (`python tools/sync_theme.py build` refreshes it).",
                 "WCAG 2 relative luminance; translucent colours are composited as described in the",
                 "tool's docstring. Every theme must pass every row of its contrast profile.", ""]
    summary_rows = []
    for theme in selected:
        props = merged_props(theme, base_props)
        surface0_raw = resolve("--surface-0", props)
        surface0 = parse_color(surface0_raw)
        if surface0 is None:
            raise ValueError(f"{theme['slug']}: --surface-0 did not resolve to a colour ({surface0_raw!r})")
        profile = theme.get("contrastProfile", "standard")
        if profile not in CONTRAST_PROFILES:
            raise ValueError(f"{theme['slug']}: unknown contrastProfile {profile!r}; known: {sorted(CONTRAST_PROFILES)}")
        checks = apply_profile(build_checks(props), profile)
        if CONTRAST_PROFILES[profile].get("extra"):
            checks += [{"label": label, "fg": fg, "bg": bg, "floor": floor, "mode": mode, "base": None}
                       for label, fg, bg, floor, mode in NIGHT_EXTRA]
        rows = [run_check(c, props, surface0) for c in checks]
        section, failures = render_theme_section(theme, rows)
        out_lines.append(section)
        if CONTRAST_PROFILES[profile].get("extra"):
            out_lines.append(render_apca(props, surface0))
        n_checks = len(rows)
        if CONTRAST_PROFILES[profile]["zero_blue"]:
            blue, unparsed, green = zero_blue_audit(props)
            out_lines.append(render_zero_blue(blue, unparsed, green))
            n_checks += 1
            failures += 1 if (blue or unparsed) else 0
        summary_rows.append({"slug": theme["slug"], "set": theme["set"], "profile": profile,
                             "checks": n_checks, "failures": failures})

    out_lines += ["## Summary", "", "| Theme | Set | Profile | Checks | Failures |", "|---|---|---|---|---|"]
    out_lines += [f"| {r['slug']} | {r['set']} | {r['profile']} | {r['checks']} | {r['failures']} |"
                  for r in summary_rows]
    out_lines.append("")
    return "\n".join(out_lines), summary_rows


def main(argv: list[str] | None = None) -> int:
    try:  # a default-codepage Windows console can otherwise choke on em dashes
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--theme", action="append", dest="themes", metavar="SLUG",
                        help="repeatable; default: every theme in src/themes.json")
    parser.add_argument("--out", metavar="FILE", help="write markdown to FILE instead of stdout")
    parser.add_argument("--fail-on", choices=["any", "none"], default="any",
                        help="any (default): exit 1 when any check fails; none: report only")
    args = parser.parse_args(argv)
    try:
        report, summary_rows = build_report(args.themes)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8", newline="\n")
        print(f"wrote {out_path} ({len(summary_rows)} theme(s))", file=sys.stderr)
    else:
        print(report)
    failing = [r for r in summary_rows if r["failures"]]
    for r in failing:
        print(f"FAIL {r['slug']}: {r['failures']} check(s)", file=sys.stderr)
    return 1 if failing and args.fail_on == "any" else 0


if __name__ == "__main__":
    sys.exit(main())
