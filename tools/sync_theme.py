#!/usr/bin/env python3
"""Build the drop-in theme bundle, and keep copies of it current.

    python tools/sync_theme.py build      regenerate ui-theme/, tokens/ and the generated docs
    python tools/sync_theme.py check      exit 1 if any generated file is stale (and check app copies)
    python tools/sync_theme.py install --to DIR
                                          copy ui-theme/ into DIR (a folder in your app)
    python tools/sync_theme.py install [<app> ...] --apps REGISTRY [--dest REPO]
                                          copy ui-theme/ into apps listed in a registry
    python tools/sync_theme.py list       themes, and apps when a registry is given

Everything an app needs is ONE folder, ui-theme/ at the repository root. It
is generated from src/ and adapters/ and is the same bytes for every app;
each app sets its own options (themes, default, storage key) as data-*
attributes on the <script> tag that loads ui-theme.js. So an update is a new
copy of the folder: `ui-theme/update.py` inside any copy pulls one from
GitHub, and `install` copies this checkout's folder into apps on this machine.

What build writes into ui-theme/:
  ui-theme.js         the runtime with the theme registry; a blocking <script> in <head>
  ui-theme-base.css   element layer (src/css/theme-base.css section C) + text standard (text.css)
  ui-components.css   component classes (src/css/components.css)
  ui-components.js    dialog and toast helpers (src/ui-components.js)
  ui-theme.d.ts       TypeScript declarations for the two globals (src/ui-theme.d.ts)
  ui-theme.css        tokens: Purple's :root, every theme block, locale overrides
  adapters/           framework adapters (adapters/*.css, *.js)
  themes.json         the registry, for server-side pickers
  update.py           the installer/updater (tools/update.py)
  README.md           how to use the folder (src/bundle-README.md)
  VERSION             "ThemeForge <version> <hash>"
  files.json          sha256 of every file above (LF line endings), read by update.py

App registry (optional; for people who keep several apps on one machine):
a folder of <app>.json files, OUTSIDE this repository, named with --apps or
the UI_THEME_APPS environment variable. Each file:

    {"app": "myapp",
     "repo": "C:/code/myapp",                  absolute, or relative to the registry folder
     "bundle_dir": "static/ui-theme",          where the app keeps its copy, relative to repo
     "extra_files": {                          optional: files only this app's copy carries
       "adapters/legacy.css": "overlays/myapp-legacy.css",          copied in
       "adapters/quasar.css": {"append": "overlays/myapp-extra.css"} appended to a bundle file
     }}

Source paths in extra_files are relative to the registry folder. --dest
replaces a manifest's repo root (e.g. a git worktree). Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CSS = SRC / "css"
ADAPTERS = ROOT / "adapters"
BUNDLE = ROOT / "ui-theme"
TOKENS = ROOT / "tokens"
DOCS = ROOT / "docs"

NAME = "ThemeForge"
REPO = "LaserLloyd/ThemeForge"
BASE_SLUG = "purple"
GROUNDS = {"oled", "dark", "light"}
SETS = {"core", "opt-in"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
REGISTRY_RE = re.compile(r"/\*@registry\*/.*?/\*@end-registry\*/", re.S)
VERSION_RE = re.compile(r"/\*@version\*/'[^']*'")
SECTION_C = "C. THEME-AGNOSTIC LAYER"
LOCALE_START = "/* ---- Locale overrides"
LOCALE_END = "/* ---- highlight.js 11 mapping"
MANIFEST = "files.json"
APPS_ENV = "UI_THEME_APPS"


class SyncError(Exception):
    pass


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def lf(text: str) -> str:
    return text.replace("\r\n", "\n")


# ---------------------------------------------------------------- registry


def load_registry() -> dict:
    data = json.loads(read(SRC / "themes.json"))
    if not SEMVER.match(str(data.get("version", ""))):
        raise SyncError("themes.json: version must be semver, e.g. 1.0.0")
    seen = set()
    for t in data["themes"]:
        for key in ("slug", "name", "family", "ground", "colorScheme", "themeColor", "set", "swatch"):
            if not t.get(key):
                raise SyncError(f"themes.json: {t.get('slug', '?')} is missing {key}")
        if t["slug"] in seen:
            raise SyncError(f"themes.json: duplicate slug {t['slug']}")
        seen.add(t["slug"])
        if t["ground"] not in GROUNDS:
            raise SyncError(f"themes.json: {t['slug']} ground must be one of {sorted(GROUNDS)}")
        if t["set"] not in SETS:
            raise SyncError(f"themes.json: {t['slug']} set must be one of {sorted(SETS)}")
        if t["slug"] == BASE_SLUG:
            if t.get("css"):
                raise SyncError("themes.json: purple is the :root base and has no css file")
        elif not t.get("css") or not (CSS / t["css"]).is_file():
            raise SyncError(f"themes.json: {t['slug']} css file not found in src/css")
        elif f'[data-palette="{t["slug"]}"]' not in read(CSS / t["css"]):
            raise SyncError(f'{t["css"]} has no [data-palette="{t["slug"]}"] block')
    if BASE_SLUG not in seen:
        raise SyncError("themes.json: the purple base theme is required")
    return data


def runtime_registry(data: dict) -> list[dict]:
    keys = ("slug", "name", "family", "ground", "colorScheme", "themeColor", "set", "swatch", "fonts")
    return [{k: t.get(k, []) if k == "fonts" else t[k] for k in keys} for t in data["themes"]]


def render_runtime(data: dict) -> str:
    source = read(SRC / "ui-theme.js")
    if len(REGISTRY_RE.findall(source)) != 1 or len(VERSION_RE.findall(source)) != 1:
        raise SyncError("src/ui-theme.js needs exactly one /*@registry*/[]/*@end-registry*/ and one /*@version*/''")
    rows = ",\n    ".join(json.dumps(t, separators=(", ", ": ")) for t in runtime_registry(data))
    block = "/*@registry*/[\n    " + rows + "\n  ]/*@end-registry*/"
    source = REGISTRY_RE.sub(lambda _m: block, source)
    return VERSION_RE.sub(lambda _m: f"/*@version*/'{data['version']}'", source)


# ---------------------------------------------------------------- theme-base split


def split_base(text: str) -> tuple[str, str, str]:
    """Return (sections A+B, section C without locale, locale block)."""
    lines = text.splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if SECTION_C in line]
    if len(hits) != 1 or hits[0] == 0 or not lines[hits[0] - 1].lstrip().startswith("/* ===="):
        raise SyncError(f"theme-base.css: expected one '{SECTION_C}' banner")
    start = hits[0] - 1
    tokens = "".join(lines[:start])
    layer = "".join(lines[start:])
    a, b = layer.find(LOCALE_START), layer.find(LOCALE_END)
    if a < 0 or b < a:
        raise SyncError("theme-base.css: locale block markers not found in section C")
    return tokens, layer[:a] + layer[b:], layer[a:b]


# ---------------------------------------------------------------- design tokens (DTCG)
#
# tokens/<slug>.json follow the W3C Design Tokens Community Group format
# (Format Module 2025.10). Every theme file holds every token, Purple's values
# overlaid with the theme's own. A value the format has a type for is typed:
# colours as srgb components, px/rem dimensions, ms durations, cubic-bezier
# easings, font families, font weights, numbers and box shadows. A token whose
# whole value is var(--x) becomes an alias, {group.x}. Values the format has
# no type for (em letter spacing, gradients, filters, the comma triple
# --accent-rgb) are not tokens there: they are listed with their CSS text
# under $extensions["com.laserlloyd.themeforge"].css.

EXTENSION = "com.laserlloyd.themeforge"
COMMENT = re.compile(r"/\*.*?\*/", re.S)
DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]*);")
BANNER = re.compile(r"^\s*/\*\s*(?:-{2,}\s*)?([A-Z][^*:.(—]*?)\s*(?:[—(:.].*?)?(?:-{2,}\s*)?(?:\*/)?\s*$")
ALIAS = re.compile(r"^var\(\s*(--[\w-]+)\s*\)$")
DIMENSION = re.compile(r"^(-?\d*\.?\d+)(px|rem)$")
DURATION = re.compile(r"^(\d*\.?\d+)(ms|s)$")
NUMBER = re.compile(r"^-?\d*\.?\d+$")
CUBIC = re.compile(r"^cubic-bezier\(([^()]*)\)$")
SHADOW = re.compile(r"^(inset\s+)?(-?[\d.]+(?:px)?)\s+(-?[\d.]+(?:px)?)\s+([\d.]+(?:px)?)\s+(?:(-?[\d.]+px)\s+)?(\S.*)$")


def contrast_module():
    spec = importlib.util.spec_from_file_location("check_contrast", ROOT / "tools" / "check_contrast.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def root_blocks(css: str) -> list[str]:
    """The bodies of every `:root {` block, comments kept (they name the groups)."""
    out = []
    for m in re.finditer(r":root\s*\{", css):
        depth, i = 1, m.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return out


def token_groups(tokens_css: str) -> dict[str, str]:
    """token -> group, from the banner comments in theme-base.css's :root blocks
    (`/* ---- Surfaces ---- */`, `/* Geometry */`, ...): the banner's first
    words, up to any dash, colon, full stop or bracket."""
    groups: dict[str, str] = {}
    for body in root_blocks(tokens_css):
        group = "misc"
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("/*") and not DECLARATION.search(stripped):
                m = BANNER.match(line)
                if m and len(m.group(1).split()) <= 4:
                    group = re.sub(r"[^a-z0-9]+", "-", m.group(1).lower()).strip("-")
            for name, _value in DECLARATION.findall(COMMENT.sub("", line)):
                groups.setdefault(name, group)
    return groups


def declarations(body: str) -> dict[str, str]:
    return {n: " ".join(v.split()) for n, v in DECLARATION.findall(COMMENT.sub("", body))}


def dtcg_color(cc, value: str):
    rgba = cc.parse_color(value)
    if rgba is None:
        return None
    r, g, b, a = rgba
    hex_ = "#%02x%02x%02x" % (round(r), round(g), round(b))
    return {"colorSpace": "srgb", "components": [round(r / 255, 4), round(g / 255, 4), round(b / 255, 4)],
            "alpha": round(a, 4), "hex": hex_}


def dtcg_dimension(text: str):
    m = DIMENSION.match(text)
    if not m:
        return {"value": 0, "unit": "px"} if text == "0" else None
    number = float(m.group(1))
    return {"value": int(number) if number.is_integer() else number, "unit": m.group(2)}


def dtcg_shadow(cc, value: str):
    layers = []
    depth, start = 0, 0
    parts = []
    for i, ch in enumerate(value):
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append(value[start:i])
            start = i + 1
    parts.append(value[start:])
    for part in parts:
        m = SHADOW.match(part.strip())
        if not m:
            return None
        colour = dtcg_color(cc, m.group(6).strip())
        dims = [dtcg_dimension(x if x.endswith("px") or x == "0" else x + "px") for x in
                (m.group(2), m.group(3), m.group(4), m.group(5) or "0")]
        if colour is None or None in dims:
            return None
        layers.append({"color": colour, "offsetX": dims[0], "offsetY": dims[1], "blur": dims[2],
                       "spread": dims[3], "inset": bool(m.group(1))})
    return layers[0] if len(layers) == 1 else layers


def dtcg_token(cc, name: str, value: str):
    """(token or None). None means the format has no type for this value."""
    if name.startswith("--font-") and "," in value:
        return {"$type": "fontFamily", "$value": [p.strip().strip("'\"") for p in value.split(",")]}
    if name.startswith("--fw-") and NUMBER.match(value):
        return {"$type": "fontWeight", "$value": int(float(value))}
    duration = DURATION.match(value)
    if duration:
        number = float(duration.group(1))
        return {"$type": "duration", "$value": {"value": int(number) if number.is_integer() else number,
                                                "unit": duration.group(2)}}
    dimension = dtcg_dimension(value)
    if dimension:
        return {"$type": "dimension", "$value": dimension}
    cubic = CUBIC.match(value)
    if cubic:
        return {"$type": "cubicBezier", "$value": [float(x) for x in cubic.group(1).split(",")]}
    if NUMBER.match(value):
        return {"$type": "number", "$value": float(value) if "." in value else int(value)}
    if name.startswith("--shadow-") or name.startswith("--cta-shadow"):
        shadow = dtcg_shadow(cc, value)
        return {"$type": "shadow", "$value": shadow} if shadow else None
    colour = dtcg_color(cc, value) if "," not in value or value.lstrip().startswith(("rgb", "color-mix")) else None
    if colour:
        return {"$type": "color", "$value": colour}
    return None


def token_files(data: dict) -> dict[str, str]:
    cc = contrast_module()
    tokens_css, _layer, _locale = split_base(read(CSS / "theme-base.css"))
    groups = token_groups(tokens_css)
    base_props: dict[str, str] = {}
    for body in root_blocks(tokens_css):
        base_props.update(declarations(body))
    out = {}
    for t in data["themes"]:
        props = dict(base_props)
        if t.get("css"):
            props.update(cc.load_theme_own_props(read(CSS / t["css"]), t["slug"]))
            props = {k: " ".join(v.split()) for k, v in props.items()}
        resolved = {name: cc.resolve(name, props) or "" for name in props}
        typed: dict[str, dict] = {}
        untyped: dict[str, str] = {}
        for name in props:
            token = dtcg_token(cc, name, resolved[name])
            if token:
                typed[name] = token
            else:
                untyped[name] = resolved[name]
        doc: dict = {
            "$description": f"{t['name']}: {NAME} {data['version']} design tokens in the W3C DTCG format "
                            f"(Format Module 2025.10), generated from src/css. The CSS custom property for "
                            f"a token is --<token name>.",
            "$extensions": {EXTENSION: {
                "theme": {k: t[k] for k in ("slug", "name", "family", "ground", "colorScheme",
                                            "themeColor", "set")},
                "css": untyped,
            }},
        }
        for name, token in typed.items():
            alias = ALIAS.match(props[name])
            if alias and alias.group(1) in typed:
                target = alias.group(1)
                token = {"$type": typed[target]["$type"],
                         "$value": "{" + groups.get(target, "theme-specific") + "." + target[2:] + "}"}
            doc.setdefault(groups.get(name, "theme-specific"), {})[name[2:]] = token
        out[f"{t['slug']}.json"] = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    return out


# ---------------------------------------------------------------- the drop-in bundle


def header(kind: str, body: str, version: str) -> str:
    return (
        f"/* GENERATED {kind}: {NAME} {version}, drop-in bundle (ui-theme/).\n"
        f"   https://github.com/{REPO} . Do not edit this copy: update the whole\n"
        f"   folder (python ui-theme/update.py) and keep app styles in the app.\n"
        f"   body sha256: {sha(body)[:16]} */\n"
    )


def public_registry(data: dict) -> str:
    keep = ("slug", "name", "family", "ground", "colorScheme", "themeColor", "set", "swatch",
            "fonts", "contrastProfile", "description")
    themes = [{k: t[k] for k in keep if k in t} for t in data["themes"]]
    return json.dumps({"name": NAME, "version": data["version"], "themes": themes}, indent=2,
                      ensure_ascii=False) + "\n"


def bundle_files(data: dict) -> dict[str, str]:
    """Every file of the drop-in bundle, relative to ui-theme/."""
    version = data["version"]
    tokens, layer, locale = split_base(read(CSS / "theme-base.css"))
    themes_css = "".join("\n" + read(CSS / t["css"]) for t in data["themes"] if t.get("css"))
    runtime = render_runtime(data)
    base_body = layer + "\n" + read(CSS / "text.css")
    css_body = tokens + themes_css + "\n" + locale
    components = read(CSS / "components.css")
    files = {
        "ui-theme.js": header("theme runtime", runtime, version) + runtime,
        "ui-theme-base.css": header("base layer", base_body, version) + base_body,
        "ui-components.css": header("component layer", components, version) + components,
        "ui-theme.css": header("theme tokens", css_body, version) + css_body,
        "themes.json": public_registry(data),
        "README.md": read(SRC / "bundle-README.md").replace("{version}", version).replace("{repo}", REPO),
        "update.py": read(ROOT / "tools" / "update.py").replace('REPO = "LaserLloyd/ThemeForge"', f'REPO = "{REPO}"'),
    }
    if (SRC / "ui-theme.d.ts").is_file():
        files["ui-theme.d.ts"] = read(SRC / "ui-theme.d.ts")
    if (SRC / "ui-components.js").is_file():
        helpers = read(SRC / "ui-components.js")
        files["ui-components.js"] = header("component helpers", helpers, version) + helpers
    for path in sorted(ADAPTERS.iterdir()):
        if path.is_file() and path.suffix in (".css", ".js"):
            body = read(path)
            files[f"adapters/{path.name}"] = header(f"adapter {path.name}", body, version) + body
    files = {k: lf(v) for k, v in files.items()}
    digest = sha("".join(f"{k}\0{v}\0" for k, v in sorted(files.items())))[:12]
    files["VERSION"] = f"{NAME} {version} {digest}\n"
    manifest = {"name": NAME, "version": version, "hash": digest, "repo": REPO,
                "files": {k: sha(v) for k, v in sorted(files.items())}}
    files[MANIFEST] = json.dumps(manifest, indent=2) + "\n"
    return files


# ---------------------------------------------------------------- generated docs

GROUP_NOTES = {
    "surfaces": ("core", "Grounds, from the page (`--surface-0`) up through nav (1), cards (2), hover (3) and active (4); `--surface-sunken` for inset wells, `--surface-overlay` for menus and popovers, `--glass-*` for translucent panes, `--code-bg` for code."),
    "text": ("core", "Text tiers (primary, secondary, tertiary, disabled), links, and the label colour for each kind of fill (`--on-accent`, `--on-danger`, ...). Quieter text is a lower tier, never opacity."),
    "accent": ("core", "The brand accent: fills for primary actions, with `--on-accent` for labels on them. Accent-coloured text uses `--text-link` instead."),
    "call-to-action": ("core", "A stronger action plate for marketing-style calls to action, and the highlight colour for tips and marks."),
    "lines": ("core", "Borders, dividers, the focus ring, glass strokes. `--border-strong` is the edge of a form control (3:1)."),
    "control-states": ("core", "On, checked, pressed and current (`--selected`, with `--on-selected` on it), and the off outline (`--unselected-border`, `--unselected-fg`). Measured at 3:1 or better on every surface in every theme."),
    "status": ("core: success, warning, danger, info. extension: live, idle, offline, heartbeat", "Each status has a fill, a hover, a `-subtle` tint, a `-text` colour and a `-border`, plus an `--on-<status>` label colour for the solid fill. live, idle, offline and heartbeat (scheduled or ambient activity) are presence states for apps that show them."),
    "overlays": ("core", "Scrims behind dialogs and over media, the backdrop blur, and `--media-filter` for images marked `.ui-media`."),
    "chat-and-content": ("extension", "Chat bubbles, the quote bar, `<mark>`, the markdown emphasis colours (`--md-*`), narrative text roles (`--rp-*`: speech, action, thought, whisper, out-of-character, shout, critical) for chat, fiction and transcript views, and diff colours."),
    "syntax": ("extension", "Code colours on `--syn-bg`, which is dark in every theme; the names follow highlight.js, which the base layer maps."),
    "code-block-chrome": ("extension", "The bar above a code block and its strokes, mixed from the syntax pair so they stay dark with the slab."),
    "categorical-data": ("extension", "Twelve series colours for charts and tags, at 3:1 on the page; chart grid and axis; and two ramps mixed from the theme: `--seq-1` ... `--seq-5` (low to high, for heatmaps) and `--div-1` ... `--div-5` (bad, neutral, good)."),
    "canvas": ("extension", "Overlays drawn on images in editors: mask, handles, guides, outlines."),
    "type-families": ("core", "Font stacks. They name Inter, JetBrains Mono and a few display faces, and fall back to system fonts."),
    "elevation": ("core", "Shadows from 1 (subtle) to 4 (dialogs), a glow and an inset highlight."),
    "browser": ("core", "Text selection and scrollbars."),
    "control-boundary-fill": ("core", "`--control-track`: the empty part of a slider (3:1 on the surfaces)."),
    "geometry": ("core, invariant", "Radii, the 4px spacing scale, strokes, control heights, touch target and shell metrics. Themes may change radii."),
    "component-tokens": ("core, invariant", "Slider, toggle and chip sizes and colours."),
    "type-scale": ("core, invariant", "Font sizes, weights, line heights and letter spacing."),
    "motion": ("core, invariant", "Easings and durations. The base layer shortens every animation under reduced motion."),
    "layers": ("core, fixed", "z-index layers. Fixed: themes and apps never change them."),
}


def tokens_doc(data: dict) -> str:
    cc = contrast_module()
    tokens_css, _layer, _locale = split_base(read(CSS / "theme-base.css"))
    groups = token_groups(tokens_css)
    base: dict[str, str] = {}
    for body in root_blocks(tokens_css):
        base.update(declarations(body))
    order: list[str] = []
    for name in base:
        group = groups.get(name, "misc")
        if group not in order:
            order.append(group)
    lines = [
        "# Tokens",
        "",
        f"Generated from `src/css/theme-base.css` by `tools/sync_theme.py build` ({NAME} {data['version']}).",
        "Every theme resolves every token below: a theme sets the colours, and the rest are",
        "shared or derived. The values shown are Purple's (the `:root` base).",
        "`tokens/<theme>.json` holds each theme's resolved values in the W3C design tokens format.",
        "",
        "Use a token with `var(--name)`. Never redeclare one in app CSS; give app variables an",
        "app prefix (`--myapp-sidebar-w`) or alias a token (`--myapp-brand: var(--accent)`).",
        "Core groups are what most apps use; extension groups exist for apps that need them.",
        "",
        "Contrast floors every theme meets (`tools/check_contrast.py`; the night profile, used",
        "by Night Red, lowers the text floors as noted in [THEMES.md](THEMES.md)):",
        "",
        "| Pair | Floor |",
        "|---|---|",
        "| `--text-primary` on `--surface-0` and `--surface-2` | 7:1 |",
        "| `--text-secondary` on `--surface-2` | 6:1 |",
        "| `--text-primary`, `--text-secondary`, `--text-tertiary` on every surface | 4.5:1 |",
        "| `--text-disabled` on every surface | 3:1 |",
        "| `--on-accent` on `--accent` (and hover, pressed); every `--on-<status>` on its fill | 4.5:1 |",
        "| every `--<status>-text` on `--surface-2`, `--surface-3` and its own `-subtle` fill | 4.5:1 |",
        "| `--on-selected` on `--selected` | 4.5:1 |",
        "| `--selected`, `--unselected-border`, `--unselected-fg` on the surfaces | 3:1 |",
        "| `--border-strong`, `--control-track`, `--focus-ring` on the surfaces | 3:1 |",
        "| syntax colours on `--syn-bg` (comments 3.5:1) | 4.5:1 |",
        "| `--cat-1` ... `--cat-12` on `--surface-0` | 3:1 |",
        "",
    ]
    for group in order:
        kind, note = GROUP_NOTES.get(group, ("", ""))
        title = group.replace("-", " ").capitalize()
        lines += [f"## {title}", ""]
        if note:
            lines += [f"*{kind}.* {note}" if kind else note, ""]
        lines += ["| Token | Purple value |", "|---|---|"]
        for name, value in base.items():
            if groups.get(name, "misc") == group:
                shown = value.replace("|", "\\|")
                lines.append(f"| `{name}` | `{shown}` |")
        lines.append("")
    del cc
    return "\n".join(lines)


def theme_template(data: dict) -> str:
    tokens_css, _layer, _locale = split_base(read(CSS / "theme-base.css"))
    body = root_blocks(tokens_css)[0]
    body = "\n".join(line for line in body.splitlines()).strip("\n")
    return (
        "/* theme-<slug>.css — a new theme. Generated by `tools/sync_theme.py build`\n"
        "   from Purple's values in src/css/theme-base.css; copy it to\n"
        "   src/css/theme-<slug>.css, replace <slug>, and change the values.\n"
        "\n"
        "   Then add the theme to src/themes.json and run\n"
        "     python tools/check_contrast.py --theme <slug> --fail-on any\n"
        "   until it passes. The floors are listed in docs/TOKENS.md. Keep every\n"
        "   token: a theme that leaves one out inherits Purple's value. Tokens that\n"
        "   are var() references (the control states, the code chrome) usually need\n"
        "   no change; override one only if its contrast check fails.\n"
        "\n"
        "   Section B tokens (geometry, type scale, motion) are shared by every\n"
        "   theme; a theme may override radii and fonts, never the --z-* layers. */\n"
        "\n"
        "[data-palette=\"<slug>\"] {\n"
        f"{body}\n"
        "}\n"
    )


def swatch_svg(cc, props: dict[str, str], name: str) -> str:
    def colour(token: str) -> str:
        rgba = cc.parse_color(cc.resolve(token, props))
        if rgba is None:
            return "#000000"
        s0 = cc.parse_color(cc.resolve("--surface-0", props))
        r, g, b, _a = cc.over_surface0(rgba, s0) if rgba[3] < 1 else rgba
        return "#%02x%02x%02x" % (round(r), round(g), round(b))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="96" height="28" viewBox="0 0 96 28" role="img" aria-label="{name}">'
        f'<rect x="0.5" y="0.5" width="95" height="27" rx="6" fill="{colour("--surface-0")}" stroke="{colour("--border-strong")}"/>'
        f'<rect x="6" y="6" width="26" height="16" rx="4" fill="{colour("--surface-2")}"/>'
        f'<text x="19" y="18.5" font-family="sans-serif" font-size="11" font-weight="600" text-anchor="middle" fill="{colour("--text-primary")}">Aa</text>'
        f'<circle cx="46" cy="14" r="6" fill="{colour("--accent")}"/>'
        f'<circle cx="62" cy="14" r="6" fill="{colour("--selected")}"/>'
        f'<circle cx="78" cy="14" r="6" fill="{colour("--text-secondary")}"/>'
        "</svg>\n"
    )


def doc_files(data: dict) -> dict[str, str]:
    """Generated files under docs/, keyed by their path inside docs/."""
    cc = contrast_module()
    base_props = cc.load_base_props(read(CSS / "theme-base.css"))
    out = {"TOKENS.md": tokens_doc(data), "theme-template.css": theme_template(data),
           "contrast-report.md": cc.build_report(None)[0]}
    for t in data["themes"]:
        out[f"images/swatch-{t['slug']}.svg"] = swatch_svg(cc, cc.merged_props(t, base_props), t["name"])
    return out


INSTALL_BLOCK = re.compile(r"<!-- install:start -->.*?<!-- install:end -->", re.S)
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
PINNED = re.compile(r"ThemeForge@v(\d+\.\d+\.\d+)|/ThemeForge/v(\d+\.\d+\.\d+)/|ui-theme#v(\d+\.\d+\.\d+)")
REPO_SLUG = re.compile(r"github(?:usercontent)?\.com/([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?=[/@#)\s'\"]|\.git|$)")


def doc_consistency(data: dict) -> list[str]:
    """README and AGENTS.md carry the same install block; pinned versions in
    the docs are the current one; every GitHub link names this repository;
    the changelog has an entry for the current version."""
    problems = []
    blocks = {name: INSTALL_BLOCK.findall(read(ROOT / name)) for name in ("README.md", "AGENTS.md")}
    if any(len(b) != 1 for b in blocks.values()) or blocks["README.md"] != blocks["AGENTS.md"]:
        problems.append("README.md and AGENTS.md must hold one identical <!-- install:start/end --> block")
    docs = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md", SRC / "bundle-README.md",
            *sorted((ROOT / "docs").glob("*.md")), *sorted((ROOT / "examples").rglob("*.md"))]
    for path in docs:
        if not path.is_file():
            continue
        text = read(path)
        rel = path.relative_to(ROOT).as_posix()
        for m in PINNED.finditer(text):
            pinned = m.group(1) or m.group(2) or m.group(3)
            if pinned != data["version"]:
                problems.append(f"{rel}: pins v{pinned}, the version is {data['version']}")
        for slug in REPO_SLUG.findall(text):
            slug = slug.rstrip(".")
            if slug.lower().startswith("laserlloyd/") and slug != REPO:
                problems.append(f"{rel}: links {slug}, the repository is {REPO}")
    for path in docs + [ROOT / "CHANGELOG.md", ROOT / "CLAUDE.md"]:
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        for target in MD_LINK.findall(read(path)):
            target = target.split("#")[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).exists():
                problems.append(f"{rel}: broken link {target}")
    if f"## {data['version']}" not in read(ROOT / "CHANGELOG.md"):
        problems.append(f"CHANGELOG.md has no '## {data['version']}' entry")
    return problems


# ---------------------------------------------------------------- app registry


def registry_dir(args) -> Path | None:
    value = getattr(args, "apps", None) or os.environ.get(APPS_ENV)
    if not value:
        return None
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise SyncError(f"app registry {path} is not a folder")
    return path


def load_manifest(registry: Path, name: str) -> dict:
    path = registry / f"{name}.json"
    if not path.is_file():
        raise SyncError(f"no manifest {path}")
    m = json.loads(read(path))
    m.setdefault("app", name)
    rel = m.get("bundle_dir")
    if not rel:
        raise SyncError(f"{name}: bundle_dir is required (where the app keeps its copy of ui-theme/)")
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise SyncError(f"{name}: bundle_dir must be relative to the app's repo root")
    for target, source in (m.get("extra_files") or {}).items():
        if Path(target).is_absolute() or ".." in Path(target).parts:
            raise SyncError(f"{name}: extra_files target {target} must stay inside the bundle folder")
        src = source.get("append") if isinstance(source, dict) else source
        if not src or not (registry / src).is_file():
            raise SyncError(f"{name}: extra_files source {src} not found in {registry}")
    return m


def repo_root(registry: Path, m: dict, dest: str | None) -> Path:
    if dest:
        return Path(dest).resolve()
    if not m.get("repo"):
        raise SyncError(f"{m['app']}: manifest has no repo; pass --dest")
    return (registry / m["repo"]).resolve()


def app_copy(registry: Path, m: dict, bundle: dict[str, str]) -> dict[str, str]:
    """The exact files this app's copy should hold: the bundle plus its extra_files."""
    files = dict(bundle)
    for target, source in (m.get("extra_files") or {}).items():
        if isinstance(source, dict):
            if target not in files:
                raise SyncError(f"{m['app']}: cannot append to {target}: not a bundle file")
            extra = lf(read(registry / source["append"]))
            files[target] = files[target].rstrip("\n") + "\n\n" + extra
        else:
            files[target] = lf(read(registry / source))
    return files


def app_names(registry: Path, names: list[str], dest: str | None) -> list[str]:
    if dest and len(names) != 1:
        raise SyncError("--dest needs exactly one app name (it replaces that app's repo root)")
    return names or sorted(p.stem for p in registry.glob("*.json"))


# ---------------------------------------------------------------- io


def write_all(root: Path, files: dict[str, str], quiet: bool = False) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        if not quiet:
            print(f"  wrote {rel}  ({len(text.encode('utf-8'))} bytes)")


def text_of(path: Path) -> str | None:
    """The file as LF-normalised text, or None for a binary file."""
    try:
        return lf(path.read_bytes().decode("utf-8"))
    except UnicodeDecodeError:
        return None


def listing(folder: Path) -> dict[str, str | None]:
    """Every file under folder keyed by its posix path: its LF-normalised text,
    or None for a binary file (an image under docs/)."""
    if not folder.is_dir():
        return {}
    return {p.relative_to(folder).as_posix(): text_of(p)
            for p in sorted(folder.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def folder_drift(folder: Path, expected: dict[str, str]) -> list[str]:
    """A generated folder must hold exactly the expected files. Line endings are
    ignored, so a checkout with autocrlf still compares clean."""
    have = listing(folder)
    bad = [f"missing {rel}" for rel in expected if rel not in have]
    bad += [f"stale   {rel}" for rel in expected if rel in have and have[rel] != expected[rel]]
    bad += [f"extra   {rel}" for rel in have if rel not in expected]
    return bad


def require_bundle_folder(folder: Path) -> None:
    """Refuse to write into a non-empty folder that is not a copy of the bundle
    (no VERSION naming it), so a mistyped path never loses an app's files."""
    if not folder.is_dir() or not any(folder.iterdir()):
        return
    version = folder / "VERSION"
    if not (version.is_file() and version.read_text(encoding="utf-8", errors="replace").startswith(NAME + " ")):
        raise SyncError(f"{folder} is not empty and is not a copy of ui-theme/ (no VERSION); "
                        "point --to / bundle_dir at the ui-theme folder itself, e.g. static/ui-theme")


def mirror(folder: Path, files: dict[str, str], quiet: bool = False) -> None:
    for rel in listing(folder):
        if rel not in files:
            (folder / rel).unlink()
            if not quiet:
                print(f"  removed {rel}")
    write_all(folder, files, quiet)


# ---------------------------------------------------------------- commands


def generated(data: dict) -> list[tuple[str, Path, dict[str, str], bool]]:
    """(label, folder, files, owned). An owned folder holds nothing but
    generated files and is mirrored; docs/ also holds hand-written pages."""
    return [("ui-theme/", BUNDLE, bundle_files(data), True),
            ("tokens/", TOKENS, token_files(data), True),
            ("docs/", DOCS, doc_files(data), False)]


def cmd_build(args) -> int:
    data = load_registry()
    for label, folder, files, owned in generated(data):
        print(f"{label} ({len(files)} generated files)")
        if owned:
            mirror(folder, files, args.quiet)
        else:
            for rel in listing(folder / "images"):
                if rel.startswith("swatch-") and f"images/{rel}" not in files:
                    (folder / "images" / rel).unlink()
            write_all(folder, files, args.quiet)
    for problem in doc_consistency(data):
        print("WARN", problem)
    print(open(BUNDLE / "VERSION", encoding="utf-8").read().strip())
    return 0


def cmd_install(args) -> int:
    """Copy the bundle folder, as build would write it, into a folder or into
    registered apps. Refuses a stale ui-theme/ so nothing receives a bundle
    that build would not produce."""
    data = load_registry()
    expected = bundle_files(data)
    stale = folder_drift(BUNDLE, expected)
    if stale:
        for p in stale:
            print("STALE ui-theme/", p)
        print("ui-theme/ is out of date with src/: run `python tools/sync_theme.py build` first.")
        return 1
    if args.to:
        target = Path(args.to).resolve()
        require_bundle_folder(target)
        print(f"-> {target}")
        mirror(target, expected, args.quiet)
        print(f"installed {expected['VERSION'].strip()}")
        return 0
    registry = registry_dir(args)
    if registry is None:
        raise SyncError(f"install needs --to DIR, or an app registry (--apps DIR or {APPS_ENV})")
    skipped = []
    for name in app_names(registry, args.names, args.dest):
        m = load_manifest(registry, name)
        target = repo_root(registry, m, args.dest) / m["bundle_dir"]
        if not target.parent.is_dir():
            print(f"SKIP {name}: {target.parent} not found")
            skipped.append(name)
            continue
        require_bundle_folder(target)
        print(f"{name} -> {target}")
        mirror(target, app_copy(registry, m, expected), args.quiet)
    print(f"installed {expected['VERSION'].strip()}" + (f"; skipped {', '.join(skipped)}" if skipped else ""))
    return 1 if skipped else 0


def cmd_check(args) -> int:
    data = load_registry()
    failures = []
    for label, folder, files, owned in generated(data):
        if owned:
            failures += [f"{label}: {p}" for p in folder_drift(folder, files)]
            continue
        have = listing(folder)
        failures += [f"{label}: {'missing' if rel not in have else 'stale  '} {rel} (run build)"
                     for rel in files if have.get(rel) != files[rel]]
        failures += [f"{label}: extra   {rel}" for rel in have
                     if rel.startswith("images/swatch-") and rel not in files]
    failures += [f"docs: {p}" for p in doc_consistency(data)]
    registry = registry_dir(args)
    if registry is not None:
        expected = bundle_files(data)
        for name in app_names(registry, args.names, args.dest):
            m = load_manifest(registry, name)
            target = repo_root(registry, m, args.dest) / m["bundle_dir"]
            if not target.parent.is_dir():
                failures.append(f"{name}: {target.parent} not found")
                continue
            failures += [f"{name}: {p}" for p in folder_drift(target, app_copy(registry, m, expected))]
    for f in failures:
        print("DRIFT", f)
    print("ok" if not failures else f"{len(failures)} problem(s)")
    return 1 if failures else 0


def cmd_list(args) -> int:
    data = load_registry()
    print(f"{NAME} {data['version']}")
    print("themes:")
    for t in data["themes"]:
        print(f"  {t['slug']:<17} {t['name']:<17} {t['set']:<7} ground={t['ground']:<5} family={t['family']}")
    registry = registry_dir(args)
    if registry is not None:
        print(f"apps ({registry}):")
        for path in sorted(registry.glob("*.json")):
            m = json.loads(read(path))
            extras = ",".join(m.get("extra_files") or {}) or "-"
            print(f"  {path.stem:<12} {m.get('bundle_dir')}  extra_files={extras}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:  # a default-codepage Windows console can otherwise choke on em dashes
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build", help="regenerate ui-theme/, tokens/ and docs/contrast-report.md")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_build)
    p = sub.add_parser("install", help="copy ui-theme/ into a ui-theme folder (--to) or into registered apps; "
                                       "the folder becomes an exact copy")
    p.add_argument("names", nargs="*", help="app names in the registry (default: all)")
    p.add_argument("--to", help="the folder to copy ui-theme/ into, e.g. myapp/static/ui-theme")
    p.add_argument("--apps", help=f"app registry folder (default: ${APPS_ENV})")
    p.add_argument("--dest", help="repo root for the one named app (e.g. a git worktree)")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_install)
    p = sub.add_parser("check", help="exit 1 if generated files or registered app copies are stale")
    p.add_argument("names", nargs="*")
    p.add_argument("--apps", help=f"app registry folder (default: ${APPS_ENV})")
    p.add_argument("--dest", help="repo root for the one named app")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("list", help="list themes, and apps when a registry is given")
    p.add_argument("--apps", help=f"app registry folder (default: ${APPS_ENV})")
    p.set_defaults(func=cmd_list)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
