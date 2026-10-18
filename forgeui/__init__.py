"""ForgeUI: the ThemeForge design system as a pure-data Python package.

The wheel carries the drop-in ``ui-theme/`` bundle (tokens, themes, base and
component CSS, the runtime and the component helpers) as package data, plus
three helpers and a vendoring tool. Standard library only; FastAPI/Starlette
and NiceGUI are imported lazily by :func:`mount` when you call it.

    import forgeui

    forgeui.static_dir()                  # Path to the bundle folder
    forgeui.head_html(themes=["glacier", "paper"], default="glacier",
                      storage_key="myapp.theme")   # the <head> tags, in order
    forgeui.mount(app)                    # serve the bundle at /theme

    python -m forgeui vendor              # copy the bundle into this repo (forgeui.json)

The shipped contract is unchanged by the package name: the ``ui-theme/``
folder, ``window.UITheme``, the ``--token`` names and the ``ui-*`` classes are
the public API (docs/THEME_SYSTEM.md).
"""

from __future__ import annotations

import functools
import hashlib
import html
import json
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from ._version import __version__

__all__ = ["__version__", "static_dir", "bundle_version", "registry", "core_themes", "head_html",
           "head_html_from_manifest", "mount"]

#: The folder name the bundle has had since 1.0.0 (part of the public contract).
BUNDLE_DIR = "ui-theme"


def static_dir() -> Path:
    """The folder holding the bundle: inside an installed wheel, or the
    repository's own ``ui-theme/`` when running from a source checkout."""
    here = Path(__file__).resolve().parent
    for candidate in (here / BUNDLE_DIR, here.parent / BUNDLE_DIR):
        if (candidate / "files.json").is_file():
            return candidate
    raise FileNotFoundError(f"the ui-theme bundle was not found next to {here}")


def bundle_version(folder: Optional[Path] = None) -> str:
    """The bundle's version number, e.g. ``1.2.0`` (from its ``VERSION`` file)."""
    text = ((folder or static_dir()) / "VERSION").read_text(encoding="utf-8").split()
    return text[1] if len(text) > 1 else ""


def registry(folder: Optional[Path] = None) -> dict:
    """The bundle's ``themes.json`` (name, version, themes) as a dict."""
    return json.loads(((folder or static_dir()) / "themes.json").read_text(encoding="utf-8"))


def core_themes(folder: Optional[Path] = None) -> "list[str]":
    """The slugs of the core set: what an app offers when it does not choose."""
    return [t["slug"] for t in registry(folder)["themes"] if t.get("set") == "core"]


@functools.lru_cache(maxsize=None)
def _hashes(folder: str) -> "dict[str, str]":
    path = Path(folder) / "files.json"
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")).get("files", {}))
    except (OSError, ValueError):
        return {}


def _file_version(folder: Path, rel: str) -> str:
    """First 10 hex chars of the file's sha256 (from files.json), for cache busting."""
    known = _hashes(str(folder)).get(rel)
    if known:
        return known[:10]
    try:
        return hashlib.sha256((folder / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:10]
    except OSError:
        return "0" * 10


def _adapter_files(folder: Path, name: str, suffix: str) -> "list[str]":
    return sorted(p.relative_to(folder).as_posix() for p in (folder / "adapters").glob(f"{name}.*")
                  if p.suffix == suffix)


def head_html(themes: Optional[Sequence[str]] = None, default: Optional[str] = None,
              storage_key: str = "forgeui.theme", prefix: str = "/theme", version_query: bool = True,
              *, default_dark: Optional[str] = None, default_light: Optional[str] = None,
              adapters: Iterable[str] = (), components: bool = False, extra_css: Iterable[str] = (),
              extra_js: Iterable[str] = (), app_css: Iterable[str] = (), nonce: Optional[str] = None,
              folder: Optional[Path] = None) -> str:
    """The ``<head>`` tags that wire the bundle into a page, in the required order.

    ``themes``       slugs the picker offers, in order (default: the core set).
    ``default``      a slug, or ``"auto"`` to follow the OS light/dark setting until the
                     visitor picks (default: the first theme).
    ``storage_key``  localStorage key for the choice, e.g. ``"myapp.theme"``.
    ``prefix``       URL the bundle folder is served under (see :func:`mount`).
    ``version_query`` add ``?v=<hash>`` to every URL so an update shows on the next load.
    ``adapters``     adapter names to load: ``"quasar"`` (NiceGUI), ``"tailwind"``.
    ``components``   also load ``ui-components.css`` and ``ui-components.js``.
    ``extra_css`` / ``extra_js``  app-owned files inside the bundle folder (the overlays
                     listed in ``forgeui.json``, e.g. ``adapters/myapp-extra.css``); CSS goes
                     last so it wins ties.
    ``nonce``        a CSP nonce for the script and link tags.

    ``app_css``      URLs of the app's own stylesheets, emitted after the base and component
                     layers and before ``ui-theme.css`` (the tokens load last, so no old
                     variable of the app can shadow one).

    The order is the one the runtime needs: ``ui-theme.js`` first and blocking (it paints
    the theme before first paint), adapter scripts, the base and component layers, the
    app's CSS, ``ui-theme.css``, then adapter and overlay CSS."""
    folder = Path(folder) if folder else static_dir()
    known = {t["slug"]: t for t in registry(folder)["themes"]}
    chosen = list(themes) if themes else core_themes(folder)
    unknown = [s for s in chosen if s not in known]
    if unknown:
        raise ValueError(f"unknown theme(s) {unknown}; the bundle has {sorted(known)}")
    default = default or chosen[0]
    if default != "auto" and default not in known:
        raise ValueError(f"default {default!r} is not a theme of the bundle")
    for label, slug in (("default_dark", default_dark), ("default_light", default_light)):
        if slug and slug not in known:
            raise ValueError(f"{label} {slug!r} is not a theme of the bundle")
    if not storage_key:
        raise ValueError("storage_key must not be empty")
    base = "/" + prefix.strip("/") if prefix.strip("/") else ""

    def url(rel: str, owned: bool = True) -> str:
        # Bundle files must exist; an app-owned overlay may live only in the vendored copy.
        if owned and not (folder / rel).is_file():
            raise FileNotFoundError(f"{rel} is not in the bundle folder {folder}")
        present = (folder / rel).is_file()
        query = f"?v={_file_version(folder, rel)}" if version_query and present else ""
        return html.escape(f"{base}/{rel}{query}", quote=True)

    n = f' nonce="{html.escape(nonce, quote=True)}"' if nonce else ""
    attrs = {"data-themes": ",".join(chosen), "data-default": default, "data-default-dark": default_dark,
             "data-default-light": default_light, "data-storage-key": storage_key}
    attr_text = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in attrs.items() if v)

    def script(rel: str, extra: str = "", owned: bool = True) -> str:
        return f'<script src="{url(rel, owned)}"{extra}{n}></script>'

    def link(rel: str, owned: bool = True) -> str:
        return f'<link rel="stylesheet" href="{url(rel, owned)}"{n}>'

    adapter_names = list(adapters)
    for name in adapter_names:
        if not _adapter_files(folder, name, ".css") and not _adapter_files(folder, name, ".js"):
            raise ValueError(f"unknown adapter {name!r}")
    tags = [script("ui-theme.js", attr_text)]
    tags += [script(rel) for name in adapter_names for rel in _adapter_files(folder, name, ".js")
             if not rel.endswith(".preset.js")]
    tags.append(link("ui-theme-base.css"))
    if components:
        tags.append(link("ui-components.css"))
    tags += [f'<link rel="stylesheet" href="{html.escape(href, quote=True)}"{n}>' for href in app_css]
    tags.append(link("ui-theme.css"))
    tags += [link(rel) for name in adapter_names for rel in _adapter_files(folder, name, ".css")]
    if components:
        tags.append(script("ui-components.js", " defer"))
    tags += [script(rel, owned=False) for rel in extra_js]
    tags += [link(rel, owned=False) for rel in extra_css]
    return "\n".join(tags) + "\n"


def head_html_from_manifest(manifest: "str | Path" = "forgeui.json", **overrides: Any) -> str:
    """:func:`head_html` for the settings in a consumer's ``forgeui.json``
    (``settings.themes/default/storage_key``, ``adapters``, ``extra_files`` overlays).
    Keyword overrides win, e.g. ``prefix="/static/ui-theme"``."""
    path = Path(manifest)
    data = json.loads(path.read_text(encoding="utf-8"))
    served = path.resolve().parent / str(data.get("dest") or "")
    settings = dict(data.get("settings") or {})
    kwargs: "dict[str, Any]" = {
        "themes": settings.get("themes"), "default": settings.get("default"),
        "storage_key": settings.get("storage_key") or "forgeui.theme",
        "default_dark": settings.get("default_dark"), "default_light": settings.get("default_light"),
        "adapters": [a for a in data.get("adapters") or [] if a != "none"],
        "extra_css": [t for t in (data.get("extra_files") or {}) if t.endswith(".css")],
        "extra_js": [t for t in (data.get("extra_files") or {}) if t.endswith(".js")],
    }
    if data.get("dest") and (served / "files.json").is_file():
        kwargs["folder"] = served  # hashes and overlays come from the app's own copy
    kwargs.update(overrides)
    return head_html(**kwargs)


def mount(app: Any, prefix: str = "/theme", *, cache_control: str = "no-cache",
          name: str = "forgeui") -> str:
    """Serve the bundle folder at ``prefix`` on a FastAPI/Starlette app or NiceGUI's
    ``app`` and return the prefix. Files are served with ``Cache-Control: no-cache``
    so a new bundle shows on the next load (pair with ``head_html(version_query=True)``).

    FastAPI/Starlette is detected by ``app.mount``; NiceGUI by ``app.add_static_files``
    (checked first, since NiceGUI's app is a FastAPI subclass). Neither is imported until
    this function runs, and a missing Starlette is reported as an error you can act on."""
    prefix = "/" + prefix.strip("/")
    folder = static_dir()
    if hasattr(app, "add_static_files"):  # NiceGUI
        try:
            app.add_static_files(prefix, str(folder), max_cache_age=0)
        except TypeError:  # older NiceGUI without max_cache_age
            app.add_static_files(prefix, str(folder))
        return prefix
    if hasattr(app, "mount"):  # FastAPI / Starlette
        try:
            from starlette.staticfiles import StaticFiles
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise RuntimeError("forgeui.mount() needs Starlette (pip install fastapi) "
                               "for a FastAPI app") from exc

        class _Static(StaticFiles):
            async def get_response(self, path, scope):  # noqa: ANN001
                response = await super().get_response(path, scope)
                response.headers["Cache-Control"] = cache_control
                return response

        app.mount(prefix, _Static(directory=folder), name=name)
        return prefix
    raise TypeError("forgeui.mount() supports FastAPI/Starlette apps and NiceGUI's app "
                    f"(got {type(app).__name__})")
