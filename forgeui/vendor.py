"""``python -m forgeui vendor``: copy the ui-theme bundle into a consumer repository.

The consumer keeps a ``forgeui.json`` manifest at its repository root:

    {
      "dest": "frontend/static/ui-theme",        where the repo keeps its copy (relative)
      "version": "1.2",                          accepted bundle version: 1.2.3, 1.2 or 1
      "adapters": ["quasar"],                    adapters to ship; omit for all, [] for none
      "extra_files": {                           app-owned overlays, copied beside the bundle
        "adapters/myapp-extra.css": "frontend/overlays/myapp-extra.css"
      },
      "settings": {                              the one place the app's theme choice lives
        "themes": ["glacier", "paper", "daylight"],
        "default": "glacier",
        "storage_key": "myapp.theme"
      }
    }

    python -m forgeui vendor                     write/update the copy from the installed package
    python -m forgeui vendor --check             exit 1 when the copy drifted (CI, a unit test)
    python -m forgeui vendor --source X.zip      from a release zip, wheel, archive or folder
    python -m forgeui vendor --version 1.2       assert the source is 1.2.x (overrides the manifest)
    python -m forgeui vendor --force             overwrite files that were edited by hand

What it guarantees, the same model as ``ui-theme/update.py``:

* The source is verified against its ``files.json`` (complete, unaltered) before
  anything is written.
* A bundle file edited by hand in the copy is never overwritten without ``--force``.
  The bundle is replaced whole; app styles belong in an overlay.
* Overlays (``extra_files``) live under app-owned names and are written as files of their
  own. They are never appended to a bundle file, so ``files.json`` keeps proving the bundle.
* ``VERSION`` is written last: a copy that failed part way never claims the new version.
* ``--check`` exits 1 on any drift: a different version, a stale, edited or missing file, a
  missing or changed overlay, or settings that name a theme the bundle does not have.

Standard library only; Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

MANIFEST_NAME = "forgeui.json"
FILES = "files.json"
VERSION = "VERSION"
#: Names a copy's VERSION line may carry: the bundle's stamp, and the names it shipped under.
KNOWN_NAMES = ("ThemeForge", "ForgeUI", "unifyingTheme", "ui-theme")
MANIFEST_KEYS = {"dest", "version", "adapters", "extra_files", "settings", "comment", "$comment"}
SETTINGS_KEYS = {"themes", "default", "default_dark", "default_light", "storage_key"}


class VendorError(Exception):
    """A problem the user can fix: a bad manifest, a bad source, a refusal."""


def digest(data: bytes) -> str:
    """sha256 over LF line endings, as the bundle's files.json is computed."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _safe_rel(text: str, what: str) -> str:
    path = PurePosixPath(text.replace("\\", "/"))
    if not text or path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", text):
        raise VendorError(f"{what} {text!r} must be a relative path that stays inside its folder")
    return path.as_posix()


# ---------------------------------------------------------------- the manifest


@dataclass
class Manifest:
    path: Path
    dest: Path
    version: Optional[str] = None
    adapters: Optional[List[str]] = None
    extra_files: Dict[str, Path] = field(default_factory=dict)
    settings: dict = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return self.path.parent


def load_manifest(path: Path) -> Manifest:
    path = Path(path)
    if not path.is_file():
        raise VendorError(f"no {path.name} at {path.parent}: create one (python -m forgeui init --dest "
                          "<folder>) or pass --manifest")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise VendorError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise VendorError(f"{path} must hold a JSON object")
    unknown = sorted(set(data) - MANIFEST_KEYS)
    if unknown:
        raise VendorError(f"{path.name}: unknown key(s) {unknown}; allowed: dest, version, adapters, "
                          "extra_files, settings")
    if not isinstance(data.get("dest"), str) or not data["dest"].strip("./\\"):
        raise VendorError(f"{path.name}: dest is required (the folder that holds the copy, e.g. "
                          "static/ui-theme)")
    root = path.resolve().parent
    dest = root / _safe_rel(data["dest"], "dest")
    version = data.get("version")
    if version is not None:
        if not isinstance(version, str):
            raise VendorError(f"{path.name}: version must be a string such as \"1.2\"")
        parse_constraint(version)
    adapters = data.get("adapters")
    if adapters is not None and (not isinstance(adapters, list) or not all(isinstance(a, str) for a in adapters)):
        raise VendorError(f"{path.name}: adapters must be a list of adapter names, e.g. [\"quasar\"]")
    extras: Dict[str, Path] = {}
    raw = data.get("extra_files") or {}
    if not isinstance(raw, dict):
        raise VendorError(f"{path.name}: extra_files must map a target path to a source file")
    for target, source in raw.items():
        target = _safe_rel(target, "extra_files target")
        if isinstance(source, dict):
            raise VendorError(
                f"{path.name}: extra_files[{target!r}] uses the old 'append' form. Overlays are never "
                "appended into bundle files (that makes files.json unverifiable): give the overlay an "
                "app-owned name such as adapters/<app>-extra.css and load it after the adapter")
        if not isinstance(source, str):
            raise VendorError(f"{path.name}: extra_files[{target!r}] must be a source file path")
        src = (root / _safe_rel(source, "extra_files source")).resolve()
        if not src.is_file():
            raise VendorError(f"{path.name}: extra_files source {source} not found")
        if target in (FILES, VERSION):
            raise VendorError(f"{path.name}: {target} cannot be an overlay")
        extras[target] = src
    settings = data.get("settings") or {}
    if not isinstance(settings, dict) or set(settings) - SETTINGS_KEYS:
        raise VendorError(f"{path.name}: settings may hold only {sorted(SETTINGS_KEYS)}")
    return Manifest(path=path.resolve(), dest=dest, version=version, adapters=adapters, extra_files=extras,
                    settings=settings)


def init_manifest(path: Path, dest: str, force: bool = False) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise VendorError(f"{path} already exists (use --force to overwrite)")
    _safe_rel(dest, "dest")
    data = {"dest": dest, "version": "1.2", "adapters": [], "extra_files": {},
            "settings": {"themes": ["purple", "midnight-gold", "glacier", "forest", "paper", "daylight"],
                         "default": "auto", "storage_key": "myapp.theme"}}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- versions


def split_version(text: str) -> Tuple[int, ...]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?$", text.strip())
    if not m:
        raise VendorError(f"{text!r} is not a version like 1.2.0")
    return tuple(int(x) for x in m.groups())


def parse_constraint(text: str):
    """'1.2.3' exact, '1.2' any 1.2.x, '1' any 1.x, '*' or 'latest' anything.
    Returns a predicate over a full version string."""
    text = text.strip()
    if text in ("*", "latest", ""):
        return lambda _v: True
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-[0-9A-Za-z.-]+)?$", text)
    if not m:
        raise VendorError(f"version {text!r} must look like 1.2.3, 1.2, 1 (or * for any)")
    want = tuple(int(x) for x in m.groups() if x is not None)
    return lambda v: split_version(v)[:len(want)] == want


# ---------------------------------------------------------------- reading a source


@dataclass
class Source:
    files: Dict[str, bytes]
    manifest: dict
    origin: str

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", ""))


def _from_folder(folder: Path) -> Dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def _bundle_root(names: List[str]) -> str:
    """The folder prefix inside an archive that holds files.json next to VERSION and
    ui-theme.js: the shallowest such folder."""
    found = []
    for name in names:
        p = PurePosixPath(name)
        if p.name == FILES:
            prefix = p.parent.as_posix()
            prefix = "" if prefix == "." else prefix + "/"
            if (prefix + VERSION) in names and (prefix + "ui-theme.js") in names:
                found.append(prefix)
    if not found:
        raise VendorError("the source has no ui-theme bundle (no folder holding files.json, VERSION "
                          "and ui-theme.js)")
    return min(found, key=lambda s: s.count("/"))


def _from_archive(data: bytes, name: str) -> Dict[str, bytes]:
    members: Dict[str, bytes] = {}
    if name.lower().endswith((".tar.gz", ".tgz", ".tar")):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
            for m in tar.getmembers():
                if m.isdir():
                    continue
                if not m.isfile():
                    raise VendorError(f"unexpected link or device in archive: {m.name}")
                members[m.name] = tar.extractfile(m).read()  # type: ignore[union-attr]
    else:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                members[info.filename] = zf.read(info)
    for member in members:
        p = PurePosixPath(member)
        if p.is_absolute() or ".." in p.parts or "\\" in member:
            raise VendorError(f"unsafe path in archive: {member}")
    prefix = _bundle_root(list(members))
    return {k[len(prefix):]: v for k, v in members.items() if k.startswith(prefix)}


def verify(files: Dict[str, bytes]) -> dict:
    """The bundle's files.json must list every file, and every hash must match."""
    if FILES not in files:
        raise VendorError(f"the source has no {FILES}")
    try:
        manifest = json.loads(files[FILES].decode("utf-8"))
    except ValueError as exc:
        raise VendorError(f"the source's {FILES} is not valid JSON: {exc}") from exc
    listed = manifest.get("files")
    if not isinstance(listed, dict) or not listed:
        raise VendorError(f"the source's {FILES} has no files table")
    for rel in listed:
        _safe_rel(rel, f"{FILES} path")
    problems = [f"missing {rel}" for rel in listed if rel not in files]
    problems += [f"corrupt {rel}" for rel, h in listed.items() if rel in files and digest(files[rel]) != h]
    problems += [f"unlisted {rel}" for rel in files if rel not in listed and rel != FILES]
    if problems:
        raise VendorError("the source failed verification: " + "; ".join(problems))
    return manifest


def load_source(spec: Optional[str]) -> Source:
    """The installed package's bundle, or ``spec``: a folder (the bundle, or a checkout
    holding ui-theme/), or a .zip/.whl/.tar.gz archive."""
    if spec is None:
        from . import static_dir
        folder = static_dir()
        files, origin = _from_folder(folder), f"installed forgeui at {folder}"
    else:
        path = Path(spec)
        if path.is_dir():
            for candidate in (path, path / "ui-theme", path / "forgeui" / "ui-theme"):
                if (candidate / FILES).is_file():
                    files, origin = _from_folder(candidate), str(candidate)
                    break
            else:
                raise VendorError(f"{path} holds no ui-theme bundle (no {FILES})")
        elif path.is_file():
            try:
                files, origin = _from_archive(path.read_bytes(), path.name), str(path)
            except (zipfile.BadZipFile, tarfile.TarError) as exc:
                raise VendorError(f"{path} is not a readable archive: {exc}") from exc
        else:
            raise VendorError(f"source {spec} not found")
    return Source(files=files, manifest=verify(files), origin=origin)


# ---------------------------------------------------------------- planning


def adapter_name(rel: str) -> Optional[str]:
    parts = PurePosixPath(rel).parts
    if len(parts) == 2 and parts[0] == "adapters":
        return parts[1].split(".")[0]
    return None


def selected_files(source: Source, adapters: Optional[List[str]]) -> Dict[str, bytes]:
    """The bundle files a copy carries: everything, or everything except the
    adapters the manifest did not ask for."""
    if adapters is None:
        return dict(source.files)
    available = sorted({a for a in map(adapter_name, source.files) if a})
    unknown = [a for a in adapters if a not in available]
    if unknown:
        raise VendorError(f"unknown adapter(s) {unknown}; the bundle has {available}")
    wanted = set(adapters)
    return {rel: data for rel, data in source.files.items()
            if adapter_name(rel) is None or adapter_name(rel) in wanted}


def dest_manifest_text(source: Source, chosen: Dict[str, bytes], adapters: Optional[List[str]]) -> str:
    """The copy's files.json: the source's verbatim for a whole bundle, else the
    same table limited to the files the copy carries."""
    if adapters is None:
        return source.files[FILES].decode("utf-8")
    manifest = dict(source.manifest)
    manifest["files"] = {k: v for k, v in source.manifest["files"].items() if k in chosen}
    manifest["subset"] = {"adapters": sorted(adapters)}
    return json.dumps(manifest, indent=2) + "\n"


def read_installed(dest: Path) -> Optional[dict]:
    path = dest / FILES
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise VendorError(f"{path} is not valid JSON: {exc}") from exc
    return data if isinstance(data.get("files"), dict) else None


def listing(dest: Path) -> List[str]:
    if not dest.is_dir():
        return []
    return sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts)


def is_bundle_copy(dest: Path) -> bool:
    version = dest / VERSION
    if not version.is_file():
        return False
    text = version.read_text(encoding="utf-8", errors="replace")
    return text.startswith(tuple(n + " " for n in KNOWN_NAMES))


@dataclass
class State:
    """What a copy holds compared with the source it should match."""
    missing: List[str] = field(default_factory=list)
    stale: List[str] = field(default_factory=list)       # an older bundle's content, untouched
    edited: List[str] = field(default_factory=list)      # matches neither the old nor the new bundle
    overlays: List[str] = field(default_factory=list)    # missing or changed overlay files
    foreign: List[str] = field(default_factory=list)     # not ours: left alone
    removable: List[str] = field(default_factory=list)   # owned by the old bundle, dropped by the new
    installed: Optional[dict] = None


def inspect(manifest: Manifest, source: Source, chosen: Dict[str, bytes]) -> State:
    dest = manifest.dest
    state = State(installed=read_installed(dest))
    if dest.exists() and state.installed is None and not is_bundle_copy(dest):
        # Neither files.json nor a VERSION naming the bundle. That is still ours if a first
        # run was interrupted (everything present is a bundle file); anything else is not.
        known = set(source.files) | set(manifest.extra_files)
        strangers = [rel for rel in listing(dest) if rel not in known and not _leftover_temp(rel, known)]
        if strangers:
            raise VendorError(f"{dest} is not empty and is not a copy of the ui-theme bundle (no "
                              f"{FILES}/{VERSION}); point dest at the folder itself, e.g. static/ui-theme")
    old = (state.installed or {}).get("files", {})
    for rel, data in chosen.items():
        if rel == FILES:
            continue
        path = dest / rel
        if not path.is_file():
            state.missing.append(rel)
            continue
        have = digest(path.read_bytes())
        if have == digest(data):
            continue
        if rel in old and have != old[rel]:
            state.edited.append(rel)
        elif rel in old:
            state.stale.append(rel)
        else:  # no files.json to compare with: a copy from before files.json existed
            state.stale.append(rel)
    for rel, expected in old.items():
        if rel not in chosen and (dest / rel).is_file():
            if digest((dest / rel).read_bytes()) != expected:
                state.edited.append(rel)
            state.removable.append(rel)
    for target, src in manifest.extra_files.items():
        path = dest / target
        if target in chosen:
            raise VendorError(f"extra_files target {target} is a file of the bundle; give the overlay an "
                              "app-owned name such as adapters/<app>-extra.css")
        if not path.is_file() or digest(path.read_bytes()) != digest(src.read_bytes()):
            state.overlays.append(target)
    owned = set(chosen) | set(old) | set(manifest.extra_files) | {FILES}
    state.foreign = [rel for rel in listing(dest) if rel not in owned and not _leftover_temp(rel, owned)]
    return state


TEMP_NAME = re.compile(r"^\.(.+)\.[A-Za-z0-9_]{8}$")


def _leftover_temp(rel: str, owned: set) -> bool:
    path = PurePosixPath(rel)
    m = TEMP_NAME.match(path.name)
    return bool(m) and (path.parent / m.group(1)).as_posix() in owned


def settings_problems(manifest: Manifest, source: Source) -> List[str]:
    """The app's theme choice must name themes the bundle has."""
    s = manifest.settings
    known = {t["slug"] for t in json.loads(source.files["themes.json"].decode("utf-8"))["themes"]}
    problems = []
    themes = s.get("themes")
    if themes is not None:
        if not isinstance(themes, list) or not themes or not all(isinstance(t, str) for t in themes):
            problems.append("settings.themes must be a non-empty list of theme slugs")
        else:
            problems += [f"settings.themes names {t!r}, which the bundle does not have" for t in themes
                         if t not in known]
    for key in ("default", "default_dark", "default_light"):
        value = s.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or (value != "auto" or key != "default") and value not in known:
            problems.append(f"settings.{key} {value!r} is not a theme of the bundle")
        elif isinstance(themes, list) and value != "auto" and value not in themes and key == "default":
            problems.append(f"settings.default {value!r} is not in settings.themes")
    if "storage_key" in s and not (isinstance(s["storage_key"], str) and s["storage_key"].strip()):
        problems.append("settings.storage_key must be a non-empty string")
    return problems


def version_problem(manifest: Manifest, source: Source, override: Optional[str]) -> Optional[str]:
    wanted = override if override is not None else manifest.version
    if wanted is None:
        return None
    if not parse_constraint(wanted)(source.version):
        return (f"the source is {source.version} but {'--version' if override is not None else MANIFEST_NAME}"
                f" asks for {wanted} ({source.origin})")
    return None


# ---------------------------------------------------------------- writing


def write_file(path: Path, data: bytes) -> None:
    """Atomic: a temporary file beside the target, then a rename (retried, since a
    file held open on Windows refuses it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data.replace(b"\r\n", b"\n"))
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.2 * (attempt + 1))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def describe(manifest: Optional[dict]) -> str:
    if not manifest:
        return "(nothing installed)"
    return f"{manifest.get('name', 'ThemeForge')} {manifest.get('version', '?')} {manifest.get('hash', '')}".strip()


def apply(manifest: Manifest, source: Source, chosen: Dict[str, bytes], state: State) -> List[str]:
    """Write every changed file (VERSION last), remove what the old bundle owned and
    the new one dropped. Returns the changed paths."""
    dest = manifest.dest
    changed: List[str] = []
    for path in (dest.rglob(".*") if dest.exists() else []):
        rel = path.relative_to(dest).as_posix()
        if path.is_file() and _leftover_temp(rel, set(chosen) | set(manifest.extra_files)):
            path.unlink()
    for rel in sorted(chosen):
        if rel in (FILES, VERSION):
            continue
        target = dest / rel
        if target.is_file() and digest(target.read_bytes()) == digest(chosen[rel]):
            continue
        write_file(target, chosen[rel])
        changed.append(rel)
    for target, src in sorted(manifest.extra_files.items()):
        path = dest / target
        data = src.read_bytes()
        if not path.is_file() or digest(path.read_bytes()) != digest(data):
            write_file(path, data)
            changed.append(f"{target} (overlay)")
    for rel in sorted(state.removable):
        (dest / rel).unlink()
        changed.append(f"{rel} (removed)")
    write_file(dest / FILES, dest_manifest_text(source, chosen, manifest.adapters).encode("utf-8"))
    version = dest / VERSION
    if not version.is_file() or digest(version.read_bytes()) != digest(chosen[VERSION]):
        changed.append(VERSION)
    write_file(version, chosen[VERSION])
    return changed


# ---------------------------------------------------------------- the command


def run(manifest_path: Path, *, source: Optional[str] = None, version: Optional[str] = None,
        check: bool = False, force: bool = False, out=print) -> int:
    """0 ok, 1 drift or refused, 2 error."""
    try:
        manifest = load_manifest(manifest_path)
        src = load_source(source)
        chosen = selected_files(src, manifest.adapters)
        problem = version_problem(manifest, src, version)
        if problem:
            out(f"error: {problem}")
            return 2
        bad = settings_problems(manifest, src)
        state = inspect(manifest, src, chosen)
    except (VendorError, OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
        out(f"error: {exc}")
        return 2

    rel_dest = os.path.relpath(manifest.dest, manifest.root).replace("\\", "/")
    out(f"{rel_dest}")
    out(f"  installed: {describe(state.installed)}")
    out(f"  source:    {describe(src.manifest)}  ({src.origin})")
    if state.foreign:
        out("  not part of the bundle (left alone): " + ", ".join(state.foreign))

    if check:
        drift = [f"missing {r}" for r in state.missing]
        drift += [f"stale   {r} (differs from {src.version})" for r in state.stale]
        drift += [f"edited  {r} (changed by hand: move the change to an overlay)" for r in state.edited]
        drift += [f"overlay {r} (missing or changed: run vendor)" for r in state.overlays]
        drift += [f"removed-upstream {r}" for r in state.removable if r not in state.edited]
        installed_version = (state.installed or {}).get("version")
        if state.installed is None and not manifest.dest.exists():
            drift.append("the folder does not exist: run python -m forgeui vendor")
        elif installed_version != src.version and not drift:
            drift.append(f"version {installed_version} differs from the source {src.version}")
        drift += [f"settings: {p}" for p in bad]
        for line in drift:
            out(f"DRIFT {line}")
        out("ok" if not drift else f"{len(drift)} problem(s)")
        return 1 if drift else 0

    if bad:
        for p in bad:
            out(f"error: {p}")
        return 2
    if state.edited and not force:
        out("error: refusing to overwrite files edited by hand: " + ", ".join(state.edited))
        out("  The bundle is replaced whole on every vendor. Move the changes into an app-owned overlay "
            "(extra_files, e.g. adapters/<app>-extra.css), or pass --force.")
        return 1
    try:
        changed = apply(manifest, src, chosen, state)
    except OSError as exc:
        out(f"error: could not write {manifest.dest}: {exc}. Close anything holding the files and rerun: "
            "it resumes where it stopped.")
        return 2
    if changed:
        out(f"  updated -> {describe(src.manifest)}")
        out("  changed: " + ", ".join(changed))
    else:
        out("  already up to date")
    return 0


def build_parser(sub=None) -> argparse.ArgumentParser:
    parser = sub or argparse.ArgumentParser(prog="forgeui vendor", description=__doc__,
                                            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=MANIFEST_NAME, help=f"the consumer's manifest (default: ./{MANIFEST_NAME})")
    parser.add_argument("--source", help="a release zip, wheel, .tar.gz or folder instead of the installed package")
    parser.add_argument("--version", help="require the source to be this version (1.2.3, 1.2 or 1); "
                                          "overrides the manifest's version")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when the copy drifted")
    parser.add_argument("--force", action="store_true", help="overwrite bundle files that were edited by hand")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    return run(Path(args.manifest), source=args.source, version=args.version, check=args.check, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
