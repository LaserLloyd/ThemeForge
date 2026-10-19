#!/usr/bin/env python3
"""Build the drop-in theme bundle, and keep copies of it current.

    python tools/sync_theme.py build      regenerate ui-theme/, tokens/ and the generated docs
    python tools/sync_theme.py check      exit 1 if any generated file is stale (and check app copies)
    python tools/sync_theme.py install --to DIR      DEPRECATED, see below
    python tools/sync_theme.py install [<app> ...] --apps REGISTRY [--dest REPO]   DEPRECATED
    python tools/sync_theme.py list       themes, and apps when a registry is given

DEPRECATED: `install` (to a folder, or to apps in a machine-local registry) is replaced by
`python -m forgeui vendor`, driven by a forgeui.json manifest that lives in each app's own
repository (docs/THEME_SYSTEM.md). The old command still works and prints a deprecation
message; it will be removed in the next major version.

Everything an app needs is ONE folder, ui-theme/ at the repository root. It
is generated from src/ and adapters/ and is the same bytes for every app;
each app sets its own options (themes, default, storage key) as data-*
attributes on the <script> tag that loads ui-theme.js. So an update is a new
copy of the folder: `ui-theme/update.py` inside any copy pulls one from
GitHub, and `python -m forgeui vendor` copies it into an app repository from a manifest.

What build writes into ui-theme/:
  ui-theme.js         the runtime with the theme registry; a blocking <script> in <head>
  ui-theme-base.css   element layer (src/css/theme-base.css section C) + text standard (text.css)
  ui-components.css   component classes (src/css/components.css)
  ui-components.js    dialog, toast and icon helpers (src/ui-components.js + the emoji map)
  ui-theme.d.ts       TypeScript declarations for the two globals (src/ui-theme.d.ts + icon names)
  icons.svg           the icon sprite, one <symbol> per icon (src/icons)
  icons.json          the icon names, labels and the emoji each stands for
  icons-LICENSE.txt   the icons' license (Lucide, ISC)
  ui-theme.css        tokens: Purple's :root, every theme block, locale overrides
  adapters/           framework adapters (adapters/*.css, *.js)
  locales/            words ui-components.js puts on the page, one JSON file per language (src/locales)
  themes.json         the registry, for server-side pickers
  update.py           the installer/updater (tools/update.py)
  README.md           how to use the folder (src/bundle-README.md)
  VERSION             "ThemeForge <version> <hash>"
  files.json          sha256 of every file above (LF line endings), read by update.py

App registry (DEPRECATED; use forgeui.json and `python -m forgeui vendor`):
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
#: Names this bundle shipped under before; a copy whose VERSION carries one is still
#: this bundle (ThemeForge was released as unifyingTheme, and before that the drop-in
#: folder stamped "ui-theme <date> <hash>"). Same list as tools/update.py.
LEGACY_NAMES = ("unifyingTheme", "ui-theme")
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
    keys = ("slug", "name", "family", "ground", "colorScheme", "themeColor", "set", "swatch", "fonts",
            "contrastProfile")
    defaults = {"fonts": [], "contrastProfile": "standard"}
    return [{k: t.get(k, defaults[k]) if k in defaults else t[k] for k in keys} for t in data["themes"]]


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


# ---------------------------------------------------------------- icons
#
# src/icons/icons.json lists the icon set; src/icons/lucide/<name>.svg is each
# icon's source, copied unchanged from the Lucide package the file names. The
# build writes one sprite (ui-theme/icons.svg, a <symbol id="<name>"> per icon)
# and puts the emoji each icon stands for into ui-components.js.

ICONS = SRC / "icons"
#: A curated set, not a library: each icon is one an app draws. The cap keeps it that way.
ICON_LIMIT = 120
ICON_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ICON_GROUPS = ("actions", "navigation", "status", "areas", "people", "system", "media", "reactions")
ICONS_RE = re.compile(r"/\*@icons\*/.*?/\*@end-icons\*/", re.S)
MATERIAL_NAME = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
ICON_NAMES_RE = re.compile(r"/\*@icon-names\*/.*?/\*@end-icon-names\*/", re.S)
SVG_ROOT = re.compile(r"<svg\b([^>]*)>(.*)</svg>", re.S)
XML_COMMENT = re.compile(r"<!--.*?-->", re.S)
#: What every source icon's root element must say: the shape the sprite and .ui-icon assume.
LUCIDE_ROOT = {"viewBox": "0 0 24 24", "fill": "none", "stroke": "currentColor", "stroke-width": "2",
               "stroke-linecap": "round", "stroke-linejoin": "round"}


def emoji_key(text: str) -> str:
    """An emoji as icons.json and UIComponents.iconFor() compare it: no variation
    selectors, no skin tone."""
    return re.sub("[︎️\U0001F3FB-\U0001F3FF]", "", text)


def load_icons() -> dict:
    data = json.loads(read(ICONS / "icons.json"))
    icons = data.get("icons") or {}
    if not icons or len(icons) > ICON_LIMIT:
        raise SyncError(f"src/icons/icons.json: the set holds {len(icons)} icons; keep it between 1 and {ICON_LIMIT}")
    owner: dict[str, str] = {}
    for name, entry in icons.items():
        if not ICON_NAME.match(name):
            raise SyncError(f"src/icons/icons.json: {name!r} is not a lower-case-kebab icon name")
        if not (ICONS / "lucide" / f"{name}.svg").is_file():
            raise SyncError(f"src/icons/icons.json: {name} has no source file src/icons/lucide/{name}.svg")
        if entry.get("group") not in ICON_GROUPS or not entry.get("label") or not entry.get("use"):
            raise SyncError(f"src/icons/icons.json: {name} needs a group ({', '.join(ICON_GROUPS)}), a label and a use")
        for emoji in entry.get("emoji", []):
            key = emoji_key(emoji)
            if not key or key in owner:
                raise SyncError(f"src/icons/icons.json: {emoji} is listed under {owner.get(key, '?')} and {name}")
            owner[key] = name
        for material in entry.get("material", []):
            if not MATERIAL_NAME.match(material):
                raise SyncError(f"src/icons/icons.json: {name}: {material!r} is not a Material Icons name")
            if material in icons and material != name:
                raise SyncError(f"src/icons/icons.json: Material name {material} under {name} is the name of "
                                f"another icon; leave it out (forgeui.quasar_icon() takes either kind of name)")
            if "material:" + material in owner:
                raise SyncError(f"src/icons/icons.json: Material name {material} is listed under "
                                f"{owner['material:' + material]} and {name}")
            owner["material:" + material] = name
    extra = sorted(p.stem for p in (ICONS / "lucide").glob("*.svg") if p.stem not in icons)
    if extra:
        raise SyncError(f"src/icons/lucide/ holds {', '.join(extra)}, which icons.json does not list")
    return data


def icon_symbol(name: str) -> str:
    """One icon as a sprite <symbol>: the source's shapes, its root attributes
    moved onto the symbol, and the stroke weight read from --icon-stroke (a custom
    property inherits into a <use>, so every theme can set its own)."""
    text = XML_COMMENT.sub("", read(ICONS / "lucide" / f"{name}.svg"))
    m = SVG_ROOT.search(text)
    attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1))) if m else {}
    wrong = [k for k, v in LUCIDE_ROOT.items() if attrs.get(k) != v]
    if not m or wrong:
        raise SyncError(f"src/icons/lucide/{name}.svg: not a Lucide 24px outline icon ({', '.join(wrong) or 'no <svg>'})")
    body = re.sub(r"\s+/>", "/>", re.sub(r">\s+<", "><", m.group(2).strip()))
    if re.search(r"<(?!/?(?:path|circle|rect|line|polyline|polygon|ellipse)\b)", body) or "style=" in body:
        raise SyncError(f"src/icons/lucide/{name}.svg: only plain shapes are allowed in an icon")
    return (f'<symbol id="{name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" '
            f'stroke-linejoin="round" style="stroke-width:var(--icon-stroke,2)">{body}</symbol>')


def icon_sprite(icons: dict, version: str) -> str:
    src = icons["source"]
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg">',
             f"<!-- GENERATED: {NAME} {version} icons ({len(icons['icons'])}), from {src['name']} {src['version']} "
             f"({src['license']}; notice in icons-LICENSE.txt). Use: <svg class=\"ui-icon\"><use href=\"icons.svg#name\"/></svg> -->"]
    lines += [icon_symbol(name) for name in icons["icons"]]
    return "\n".join(lines) + "\n</svg>\n"


def icon_registry(icons: dict, version: str) -> str:
    out = {"name": NAME, "version": version, "sprite": "icons.svg", "source": icons["source"],
           "icons": {n: {k: e[k] for k in ("group", "label", "use", "emoji", "material") if k in e} for n, e in icons["icons"].items()}}
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


def icon_license(icons: dict) -> str:
    src = icons["source"]
    return (f"The icons in icons.svg are {src['name']} icons ({src['url']}), from the {src['package']} "
            f"{src['version']} package, used under the license below.\n\n" + read(ICONS / "LICENSE"))


def render_components(icons: dict) -> str:
    source = read(SRC / "ui-components.js")
    if len(ICONS_RE.findall(source)) != 1:
        raise SyncError("src/ui-components.js needs exactly one /*@icons*/{}/*@end-icons*/")
    table = {n: e.get("emoji", []) for n, e in icons["icons"].items()}
    # ASCII only (\u escapes), so the file reads the same whatever charset a server declares.
    block = "/*@icons*/" + json.dumps(table, ensure_ascii=True, separators=(",", ":")) + "/*@end-icons*/"
    return ICONS_RE.sub(lambda _m: block, source)


def render_types(icons: dict) -> str:
    source = read(SRC / "ui-theme.d.ts")
    if len(ICON_NAMES_RE.findall(source)) != 1:
        raise SyncError("src/ui-theme.d.ts needs exactly one /*@icon-names*/string/*@end-icon-names*/")
    names = " | ".join(f"'{n}'" for n in icons["icons"])
    return ICON_NAMES_RE.sub(lambda _m: f"/*@icon-names*/{names}/*@end-icon-names*/", source)


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
    icons = load_icons()
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
    files["ui-theme.d.ts"] = render_types(icons)
    helpers = render_components(icons)
    files["ui-components.js"] = header("component helpers", helpers, version) + helpers
    files["icons.svg"] = icon_sprite(icons, version)
    files["icons.json"] = icon_registry(icons, version)
    files["icons-LICENSE.txt"] = icon_license(icons)
    for path in sorted((SRC / "locales").glob("*.json")):
        files[f"locales/{path.name}"] = read(path)
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
    "notification": ("core", "The unread indicator, solved as a pair: `--notify` is the one colour whose job is to be noticed (4.5:1 on `--surface-0` and `--surface-1`), `--notify-idle` marks the same spot when nothing is waiting (at most 3:1), and the two are at least 3:1 apart. Pair it with a size change; colour alone is not enough."),
    "overlays": ("core", "Scrims behind dialogs and over media, the backdrop blur, and `--media-filter` for images marked `.ui-media`."),
    "chat-and-content": ("extension", "Chat bubbles, the quote bar, `<mark>`, the markdown emphasis colours (`--md-*`), narrative text roles (`--rp-*`: speech, action, thought, whisper, out-of-character, shout, critical) for chat, fiction and transcript views, and diff colours."),
    "syntax": ("extension", "Code colours on `--syn-bg`, which is dark in every theme; the names follow highlight.js, which the base layer maps."),
    "code-block-chrome": ("extension", "The bar above a code block and its strokes, mixed from the syntax pair so they stay dark with the slab."),
    "categorical-data": ("extension", "Twelve series colours for charts and tags, at 3:1 on the page; chart grid and axis; and two ramps mixed from the theme: `--seq-1` ... `--seq-5` (low to high, for heatmaps) and `--div-1` ... `--div-5` (bad, neutral, good)."),
    "canvas": ("extension", "Overlays drawn on images in editors: mask, handles, guides, outlines."),
    "type-families": ("core", "Font stacks. They name Inter, JetBrains Mono and a few display faces, and fall back to system fonts. `--font-emoji` draws typed emoji in the text colour (`.ui-emoji`)."),
    "elevation": ("core", "Shadows from 1 (subtle) to 4 (dialogs), a glow and an inset highlight."),
    "browser": ("core", "Text selection and scrollbars."),
    "control-boundary-fill": ("core", "`--control-track`: the empty part of a slider (3:1 on the surfaces)."),
    "geometry": ("core, invariant", "Radii, the 4px spacing scale, strokes, control heights, touch target and shell metrics. Themes may change radii."),
    "icons": ("core", "The stroke weight of `ui-theme/icons.svg` in units of its 24px grid. Themes may change it; the high-contrast pair and `prefers-contrast: more` draw 2.5. See [ICONS.md](ICONS.md)."),
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
        "by Night Red, lowers the text floors, and the high profile, used by the High Contrast pair,",
        "raises them to 7:1 for every text colour and 4.5:1 for edges and indicators, as noted in",
        "[THEMES.md](THEMES.md)):",
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
        "| `--notify` on `--surface-0` and `--surface-1`; `--notify` vs `--notify-idle` | 4.5:1; 3:1 |",
        "| `--notify-idle` on `--surface-0` and `--surface-1` | at most 3:1 |",
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


def icons_preview(icons: dict) -> str:
    """docs/images/icons.svg: every icon with its name, for choosing one on GitHub."""
    names = list(icons["icons"])
    cols, w, h = 8, 140, 64
    rows = -(-len(names) // cols)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{cols * w}" height="{rows * h}" '
           f'viewBox="0 0 {cols * w} {rows * h}" role="img" aria-label="{NAME} icons">',
           f'<rect width="{cols * w}" height="{rows * h}" rx="8" fill="#ffffff"/>']
    out += [icon_symbol(n) for n in names]
    for i, n in enumerate(names):
        x, y = (i % cols) * w, (i // cols) * h
        out.append(f'<use href="#{n}" x="{x + w / 2 - 12:g}" y="{y + 10}" width="24" height="24" color="#1f2328"/>'
                   f'<text x="{x + w / 2:g}" y="{y + 52}" font-family="ui-monospace,monospace" font-size="11" '
                   f'text-anchor="middle" fill="#57606a">{n}</text>')
    return "\n".join(out) + "\n</svg>\n"


def icons_doc(data: dict, icons: dict) -> str:
    src = icons["source"]
    v = data["version"]
    lines = [
        "# Icons",
        "",
        f"Generated from `src/icons/icons.json` by `tools/sync_theme.py build` ({NAME} {v}).",
        "",
        f"{len(icons['icons'])} outline icons for app chrome, one sprite (`ui-theme/icons.svg`). They draw in",
        "`currentColor` with the theme's `--icon-stroke`, so every theme colours them and the",
        "high-contrast pair draws them heavier. They are not decoration: use them where an app",
        "would otherwise put an emoji in a button, tab, menu or status line. The set is what the",
        "LaserLloyd apps draw, not a library; each icon lists the emoji and the Material Icons names",
        "it replaces, so moving an app over is a lookup.",
        "",
        "![The icon set](images/icons.svg)",
        "",
        "## Use",
        "",
        "Markup (any page; the path is wherever the app serves `ui-theme/`):",
        "",
        "```html",
        '<svg class="ui-icon" aria-hidden="true"><use href="/static/ui-theme/icons.svg#settings"/></svg>',
        '<button class="ui-btn"><svg class="ui-icon" aria-hidden="true"><use href="/static/ui-theme/icons.svg#trash"/></svg>Delete</button>',
        '<button class="ui-btn ui-btn--icon" aria-label="Close"><svg class="ui-icon" aria-hidden="true"><use href="/static/ui-theme/icons.svg#x"/></svg></button>',
        "```",
        "",
        "Script (with `ui-components.js` loaded, which finds `icons.svg` next to itself, and inlines it",
        "when it is on another origin such as the CDN, where `<use>` cannot reach):",
        "",
        "```js",
        "button.append(UIComponents.icon('trash'));                 // decorative",
        "UIComponents.icon('bell', { label: 'Notifications', size: 'sm' });  // an image with a name",
        "UIComponents.iconFor('🗑️');                               // 'trash'; null when no icon means it",
        "UIComponents.icons();                                      // every name",
        "```",
        "",
        "NiceGUI and Quasar: Quasar draws a sprite icon from `svguse:<url>#<name>`, so any `icon=` takes",
        "one. `forgeui.quasar_icon()` writes that string, from an icon name or the Material name the app",
        "uses today:",
        "",
        "```python",
        "import forgeui",
        "forgeui.mount(app)                                          # the bundle at /theme",
        "ui.button(icon=forgeui.quasar_icon('trash'))                # 'svguse:/theme/icons.svg#trash'",
        "ui.icon(forgeui.quasar_icon('delete_forever'))              # a Material name maps to trash too",
        "```",
        "",
        "Size: `1.25em` (it follows the text), or `.ui-icon--sm` (16px), `--md` (20px), `--lg` (24px), or",
        "`--ui-icon-size` on the element. Colour: the text colour, or `.ui-icon--muted`, `--accent`,",
        "`--success`, `--warning`, `--danger`, `--info`. Weight: `--icon-stroke` (2; 2.5 in the",
        "high-contrast themes and when the system asks for more contrast).",
        "",
        "## Emoji, three ways",
        "",
        "| Style | Class | For |",
        "|---|---|---|",
        "| icon | `.ui-icon` | An emoji in app chrome (⚙ 🗑 📁 ✕). It becomes the outline icon the table below names. |",
        "| text | `.ui-emoji` | An emoji someone typed (chat, notes), drawn in the text colour. |",
        "| colour | `.ui-emoji--color` | An emoji whose colours are the point (reactions), toned by the theme's `--media-filter` (Night Red keeps it red). |",
        "",
        "`UIComponents.emojify(element, 'icon' | 'text' | 'color')` applies one to an element's text, and",
        "`data-ui-emoji=\"icon\"` (or `text`, `color`) on an element does it on load. In `icon` style an",
        "emoji with no icon falls back to `text`; a text node that is nothing but one mapped symbol",
        "(a button reading `⚙` or `✕`) becomes its icon; arrows and symbols inside sentences are left",
        "alone. The emoji stays in the page, visually hidden, so copy, find and screen readers keep it.",
        "",
        "System fonts draw faces (😀) only in colour. For monochrome faces in `text` style, load the",
        "Noto Emoji web font, which `--font-emoji` names first, e.g.",
        "`data-fonts-href=\"https://fonts.googleapis.com/css2?family=Noto+Emoji&display=swap\"` on the",
        "`ui-theme.js` tag.",
        "",
        "## The set",
        "",
        "| Icon | Label | Use for | Emoji and symbols it replaces | Material Icons names |",
        "|---|---|---|---|---|",
    ]
    for group in ICON_GROUPS:
        for name, e in icons["icons"].items():
            if e["group"] == group:
                material = ", ".join(f"`{m}`" for m in e.get("material", []))
                lines.append(f"| `{name}` | {e['label']} | {e['use']} | {' '.join(e.get('emoji', []))} | {material} |")
    lines += [
        "",
        "## Adding an icon",
        "",
        f"The set holds what the apps draw, and the build refuses more than {ICON_LIMIT}: add an icon when an app",
        "needs one and nothing here means the same thing (a Material name or an emoji can usually join an",
        "existing icon instead). To add one, copy the icon's file from the",
        f"`{src['package']}` {src['version']} package (`icons/<name>.svg`, unchanged) into `src/icons/lucide/`, add",
        "an entry to `src/icons/icons.json`, and run `python tools/sync_theme.py build`. Icon names are public",
        "API, like token names: never rename or remove one in a minor release.",
        "",
        "## License",
        "",
        f"The icons are [{src['name']}]({src['url']}) {src['version']}, {src['license']} license (some derived from",
        "Feather, MIT). The notice ships beside the sprite as `ui-theme/icons-LICENSE.txt`; keep it with any copy.",
        "",
    ]
    return "\n".join(lines)


def doc_files(data: dict) -> dict[str, str]:
    """Generated files under docs/, keyed by their path inside docs/."""
    cc = contrast_module()
    base_props = cc.load_base_props(read(CSS / "theme-base.css"))
    icons = load_icons()
    out = {"TOKENS.md": tokens_doc(data), "theme-template.css": theme_template(data),
           "contrast-report.md": cc.build_report(None)[0],
           "ICONS.md": icons_doc(data, icons), "images/icons.svg": icons_preview(icons)}
    for t in data["themes"]:
        out[f"images/swatch-{t['slug']}.svg"] = swatch_svg(cc, cc.merged_props(t, base_props), t["name"])
    return out


INSTALL_BLOCK = re.compile(r"<!-- install:start -->.*?<!-- install:end -->", re.S)
THEME_SYSTEM = "THEME_SYSTEM.md"
THEMES_BLOCK = re.compile(r"<!-- themes:start -->.*?<!-- themes:end -->", re.S)
GROUND_LABEL = {"oled": "OLED", "dark": "dark", "light": "light"}
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
PINNED = re.compile(r"ThemeForge@v(\d+\.\d+\.\d+)|/ThemeForge/v(\d+\.\d+\.\d+)/|ui-theme#v(\d+\.\d+\.\d+)")
USED_BY = re.compile(r"^#{2,3}\s+Used by\s*$.*?(?=^#{1,3}\s|\Z)", re.S | re.M)
#: Repositories that are never a valid link target, even in a "Used by" list.
DEAD_SLUGS = {"laserlloyd/unifyingtheme"}
REPO_SLUG = re.compile(r"github(?:usercontent)?\.com/([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?=[/@#)\s'\"]|\.git|$)")


def theme_system_block(data: dict) -> str:
    """The generated theme list inside docs/THEME_SYSTEM.md: one row per theme in
    src/themes.json, so the index can never name a theme the registry lacks."""
    themes = data["themes"]
    cc = contrast_module()
    base = cc.load_base_props(read(CSS / "theme-base.css"))
    lines = ["<!-- themes:start -->",
             f"Release **{data['version']}**: {len(themes)} themes sharing {len(base)} tokens "
             "(the contract, counting the shared geometry, type and motion tokens).",
             "",
             "| Slug | Name | Ground | Set | Family | Contrast profile |",
             "|---|---|---|---|---|---|"]
    for t in themes:
        lines.append(f"| `{t['slug']}` | {t['name']} | {GROUND_LABEL[t['ground']]} | {t['set']} | `{t['family']}` | "
                     f"{t.get('contrastProfile', 'standard')} |")
    lines.append("<!-- themes:end -->")
    return "\n".join(lines)


def refresh_theme_system(data: dict) -> bool:
    """Rewrite the generated block of docs/THEME_SYSTEM.md. True when the file changed."""
    path = DOCS / THEME_SYSTEM
    if not path.is_file():
        return False
    text = read(path)
    if len(THEMES_BLOCK.findall(text)) != 1:
        return False
    new = THEMES_BLOCK.sub(lambda _m: theme_system_block(data), text)
    if lf(new) == lf(text):
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(lf(new))
    return True


def theme_system_problems(data: dict) -> list[str]:
    """docs/THEME_SYSTEM.md must exist and its theme list must equal src/themes.json."""
    path = DOCS / THEME_SYSTEM
    rel = f"docs/{THEME_SYSTEM}"
    if not path.is_file():
        return [f"{rel} is missing (the index of the token contract, the themes and the vendoring procedure)"]
    text = lf(read(path))
    blocks = THEMES_BLOCK.findall(text)
    if len(blocks) != 1:
        return [f"{rel} must hold one <!-- themes:start/end --> block"]
    listed = re.findall(r"^\| `([a-z0-9-]+)` \|", blocks[0], re.M)
    wanted = [t["slug"] for t in data["themes"]]
    problems = []
    if listed != wanted:
        missing = [x for x in wanted if x not in listed]
        extra = [x for x in listed if x not in wanted]
        problems.append(f"{rel}: theme list differs from src/themes.json"
                        + (f" (missing {', '.join(missing)})" if missing else "")
                        + (f" (not in the registry: {', '.join(extra)})" if extra else "")
                        + (" (order differs)" if not missing and not extra else "")
                        + "; run `python tools/sync_theme.py build`")
    elif blocks[0] != theme_system_block(data):
        problems.append(f"{rel}: the generated theme block is stale; run `python tools/sync_theme.py build`")
    return problems


def repo_link_problems(text: str, rel: str) -> list[str]:
    """Every GitHub link to a LaserLloyd repository must name this one. A
    "Used by" section is the exception: it names sibling products on purpose,
    so links there are allowed, except to a repository that no longer exists."""
    problems = []
    for slug in REPO_SLUG.findall(USED_BY.sub("", text)):
        slug = slug.rstrip(".")
        if slug.lower().startswith("laserlloyd/") and slug != REPO:
            problems.append(f"{rel}: links {slug}, the repository is {REPO}")
    for slug in REPO_SLUG.findall("".join(USED_BY.findall(text))):
        if slug.rstrip(".").lower() in DEAD_SLUGS:
            problems.append(f"{rel}: 'Used by' links {slug.rstrip('.')}, which is archived")
    return problems


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
        problems += repo_link_problems(text, rel)
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
    problems += theme_system_problems(data)
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
    """Write every file, VERSION last: a copy's VERSION line is what `check`
    and update.py trust, so a copy that failed partway must never carry the
    new version over old files."""
    for rel in sorted(files, key=lambda r: (r == "VERSION", r)):
        text = files[rel]
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
    names = tuple(n + " " for n in (NAME, *LEGACY_NAMES))
    if not (version.is_file() and version.read_text(encoding="utf-8", errors="replace").startswith(names)):
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


def forgeui_files(data: dict) -> dict[str, str]:
    """The one generated file of the forgeui/ package: its version, which hatchling reads."""
    lines = ['"""Generated by tools/sync_theme.py build from src/themes.json. Do not edit."""',
             "", f'__version__ = "{data["version"]}"', ""]
    return {"_version.py": "\n".join(lines)}


def generated(data: dict) -> list[tuple[str, Path, dict[str, str], bool]]:
    """(label, folder, files, owned). An owned folder holds nothing but
    generated files and is mirrored; docs/ and forgeui/ also hold hand-written files."""
    return [("ui-theme/", BUNDLE, bundle_files(data), True),
            ("tokens/", TOKENS, token_files(data), True),
            ("docs/", DOCS, doc_files(data), False),
            ("forgeui/", ROOT / "forgeui", forgeui_files(data), False)]


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
    if refresh_theme_system(data):
        print(f"docs/{THEME_SYSTEM} (theme list refreshed)")
    for problem in doc_consistency(data):
        print("WARN", problem)
    print(open(BUNDLE / "VERSION", encoding="utf-8").read().strip())
    return 0


DEPRECATION = ("deprecated: `sync_theme.py install` is replaced by `python -m forgeui vendor`, which reads a "
               "forgeui.json kept in each app's own repository (no machine-local registry, overlays never "
               "appended into bundle files). See docs/THEME_SYSTEM.md. This command still works.")


def cmd_install(args) -> int:
    """Copy the bundle folder, as build would write it, into a folder or into
    registered apps. Refuses a stale ui-theme/ so nothing receives a bundle
    that build would not produce. Deprecated: use `python -m forgeui vendor`."""
    print(DEPRECATION, file=sys.stderr)
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
    skipped: list[str] = []
    installed: list[str] = []
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
        installed.append(name)
    if not installed:
        # Every app was skipped: "installed" here would be a success report for a run that wrote nothing.
        print(f"installed {expected['VERSION'].strip()} into 0 apps (every app skipped)")
        return 1
    print(f"installed {expected['VERSION'].strip()} into {len(installed)} app(s): {', '.join(installed)}"
          + (f"; skipped {', '.join(skipped)}" if skipped else ""))
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
