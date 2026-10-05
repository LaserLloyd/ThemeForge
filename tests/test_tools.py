"""Tests for the repository tools. Standard library only:

    python -m unittest discover -s tests -v

They read the repository and write only to temporary folders.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = load("sync_theme")
contrast = load("check_contrast")
update = load("update")
lint = load("lint_colors")


def quiet(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue() + err.getvalue()


def repo_tarball(files: dict, top: str = "ThemeForge-1.0.0", extra: list | None = None) -> bytes:
    """A GitHub-style repository archive holding ui-theme/ (and anything in extra)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        def add(name, data):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        add(f"{top}/README.md", b"repo readme")
        for rel, text in files.items():
            add(f"{top}/ui-theme/{rel}", text.encode("utf-8") if isinstance(text, str) else text)
        for member, data in extra or []:
            if isinstance(member, tarfile.TarInfo):
                tar.addfile(member, io.BytesIO(data) if data is not None else None)
            else:
                add(member, data)
    return buf.getvalue()


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = sync.load_registry()
        self.bundle = sync.bundle_files(self.data)

    def test_generated_files_are_current(self):
        code, out = quiet(sync.main, ["check"])
        self.assertEqual(code, 0, out)

    def test_bundle_is_deterministic(self):
        self.assertEqual(self.bundle, sync.bundle_files(self.data))

    def test_version_and_manifest(self):
        name, version, digest = self.bundle["VERSION"].split()
        self.assertEqual((name, version), ("ThemeForge", self.data["version"]))
        manifest = json.loads(self.bundle["files.json"])
        self.assertEqual(manifest["hash"], digest)
        self.assertEqual(set(manifest["files"]), set(self.bundle) - {"files.json"})
        for rel, h in manifest["files"].items():
            self.assertEqual(hashlib.sha256(self.bundle[rel].encode("utf-8")).hexdigest(), h, rel)

    def test_runtime_carries_registry_and_version(self):
        js = self.bundle["ui-theme.js"]
        self.assertIn(f"version: /*@version*/'{self.data['version']}'", js)
        self.assertIn('"slug": "night-red"', js)
        self.assertNotIn("UI_THEME_MANIFEST =", js)

    def test_public_registry_has_no_private_fields(self):
        registry = json.loads(self.bundle["themes.json"])
        allowed = {"slug", "name", "family", "ground", "colorScheme", "themeColor", "set", "swatch",
                   "fonts", "contrastProfile", "description"}
        for theme in registry["themes"]:
            self.assertLessEqual(set(theme), allowed, theme["slug"])

    def test_shipped_javascript_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        for rel in sorted(r for r in self.bundle if r.endswith(".js")):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / Path(rel).name
                path.write_text(self.bundle[rel], encoding="utf-8")
                result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{rel}: {result.stderr}")

    def test_every_file_is_lf(self):
        for rel, text in self.bundle.items():
            self.assertNotIn("\r", text, rel)

    def test_tokens_are_dtcg_shaped(self):
        tokens = sync.token_files(self.data)
        doc = json.loads(tokens["glacier.json"])
        colour = doc["surfaces"]["surface-0"]
        self.assertEqual(colour["$type"], "color")
        self.assertEqual(colour["$value"]["colorSpace"], "srgb")
        self.assertEqual(colour["$value"]["hex"], "#000000")
        self.assertEqual(doc["geometry"]["radius-md"], {"$type": "dimension", "$value": {"value": 12, "unit": "px"}})
        self.assertTrue(doc["component-tokens"]["slider-color"]["$value"].startswith("{"))
        self.assertIn("--accent-rgb", doc["$extensions"]["com.laserlloyd.themeforge"]["css"])


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.registry = self.base / "registry"
        (self.registry / "overlays").mkdir(parents=True)
        (self.registry / "overlays" / "legacy.css").write_text(":root { --legacy: var(--accent); }\n", encoding="utf-8")
        (self.registry / "overlays" / "extra.css").write_text(".app-well { padding: 1px; }\n", encoding="utf-8")
        self.app = self.base / "app"
        (self.app / "static").mkdir(parents=True)
        (self.registry / "demo.json").write_text(json.dumps({
            "app": "demo", "repo": str(self.app), "bundle_dir": "static/ui-theme",
            "extra_files": {"adapters/legacy.css": "overlays/legacy.css",
                            "adapters/quasar.css": {"append": "overlays/extra.css"}},
        }), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_then_check_with_overlays(self):
        code, out = quiet(sync.main, ["install", "--apps", str(self.registry), "--quiet"])
        self.assertEqual(code, 0, out)
        copy = self.app / "static" / "ui-theme"
        self.assertTrue((copy / "adapters" / "legacy.css").is_file())
        self.assertIn(".app-well", (copy / "adapters" / "quasar.css").read_text(encoding="utf-8"))
        code, out = quiet(sync.main, ["check", "--apps", str(self.registry)])
        self.assertEqual(code, 0, out)
        (copy / "ui-theme.css").write_text("x", encoding="utf-8")
        code, out = quiet(sync.main, ["check", "--apps", str(self.registry)])
        self.assertEqual(code, 1)
        self.assertIn("stale", out)

    def test_install_to_folder(self):
        target = self.base / "plain" / "ui-theme"
        code, out = quiet(sync.main, ["install", "--to", str(target), "--quiet"])
        self.assertEqual(code, 0, out)
        self.assertEqual(sync.folder_drift(target, sync.bundle_files(sync.load_registry())), [])

    def test_bad_extra_file_source(self):
        (self.registry / "bad.json").write_text(json.dumps({
            "app": "bad", "repo": str(self.app), "bundle_dir": "static/x",
            "extra_files": {"adapters/nope.css": "overlays/missing.css"}}), encoding="utf-8")
        with self.assertRaises(sync.SyncError):
            sync.load_manifest(self.registry, "bad")

    def test_install_refuses_a_folder_that_is_not_a_bundle(self):
        static = self.base / "site" / "static"
        static.mkdir(parents=True)
        (static / "index.html").write_text("<p>app</p>", encoding="utf-8")
        code, out = quiet(sync.main, ["install", "--to", str(static), "--quiet"])
        self.assertEqual(code, 2)
        self.assertIn("not a copy of ui-theme", out)
        self.assertTrue((static / "index.html").is_file())

    def test_install_needs_a_target(self):
        code, out = quiet(sync.main, ["install"])
        self.assertEqual(code, 2)


class ContrastTests(unittest.TestCase):
    def test_every_theme_passes(self):
        _report, summary = contrast.build_report(None)
        self.assertEqual({r["slug"]: r["failures"] for r in summary if r["failures"]}, {})

    def test_color_mix(self):
        mixed = contrast.parse_color("color-mix(in srgb, #ffffff 50%, #000000)")
        self.assertEqual([round(c) for c in mixed[:3]], [128, 128, 128])
        self.assertEqual(mixed[3], 1.0)
        self.assertIsNone(contrast.parse_color("color-mix(in oklch, #fff, #000)"))

    def test_state_step_ignores_profile_floors(self):
        checks = contrast.apply_profile(contrast.build_checks({}), "night")
        step = [c for c in checks if c["label"].startswith("text-secondary vs text-disabled")]
        self.assertEqual([c["floor"] for c in step], [1.5])


class LintTests(unittest.TestCase):
    def test_self_test(self):
        code, out = quiet(lint.main, ["--self-test"])
        self.assertEqual(code, 0, out)

    def test_shipped_and_example_files_have_no_raw_colours(self):
        paths = [str(ROOT / "ui-theme" / "ui-components.css"), str(ROOT / "ui-theme" / "ui-components.js"),
                 str(ROOT / "specimen"), str(ROOT / "examples")]
        code, out = quiet(lint.main, [p for p in paths if Path(p).exists()] + ["--quiet"])
        self.assertEqual(code, 0, out)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bundle = sync.bundle_files(sync.load_registry())
        self.archive = self.base / "repo.tar.gz"
        self.archive.write_bytes(repo_tarball(self.bundle))
        self.dest = self.base / "app" / "static" / "ui-theme"

    def tearDown(self):
        self.tmp.cleanup()

    def run_update(self, *extra):
        return quiet(update.main, ["--source", str(self.archive), "--dest", str(self.dest), *extra])

    def test_first_install_and_rerun(self):
        code, out = self.run_update()
        self.assertEqual(code, 0, out)
        self.assertEqual(sync.folder_drift(self.dest, self.bundle), [])
        code, out = self.run_update()
        self.assertEqual(code, 0)
        self.assertIn("already up to date", out)

    def test_crlf_copy_is_not_an_edit(self):
        self.run_update()
        css = self.dest / "ui-theme.css"
        css.write_bytes(css.read_bytes().replace(b"\n", b"\r\n"))
        code, out = self.run_update()
        self.assertEqual(code, 0, out)
        self.assertNotIn("edited by hand", out)

    def test_hand_edit_is_refused_then_forced(self):
        self.run_update()
        (self.dest / "ui-theme.css").write_text("/* mine */", encoding="utf-8")
        code, out = self.run_update()
        self.assertEqual(code, 1)
        self.assertIn("edited by hand", out)
        code, out = self.run_update("--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(sync.folder_drift(self.dest, self.bundle), [])

    def test_foreign_files_are_kept_and_old_files_removed(self):
        self.run_update()
        (self.dest / "adapters" / "mine.css").write_text(".x{}", encoding="utf-8")
        manifest = json.loads((self.dest / "files.json").read_text(encoding="utf-8"))
        old = self.dest / "adapters" / "old-adapter.css"
        old.write_text("old", encoding="utf-8")
        manifest["files"]["adapters/old-adapter.css"] = update.digest(b"old")
        manifest["hash"] = "000000000000"
        (self.dest / "files.json").write_text(json.dumps(manifest), encoding="utf-8")
        code, out = self.run_update()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.dest / "adapters" / "mine.css").is_file())
        self.assertFalse(old.exists())

    def test_copy_without_manifest_is_upgraded(self):
        self.dest.mkdir(parents=True)
        (self.dest / "VERSION").write_text("ThemeForge 0.9.0 abc\n", encoding="utf-8")
        (self.dest / "adapters").mkdir()
        (self.dest / "adapters" / "app-only.css").write_text(".x{}", encoding="utf-8")
        code, out = self.run_update()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.dest / "adapters" / "app-only.css").is_file())
        self.assertTrue((self.dest / "files.json").is_file())

    def test_copy_under_the_old_name_is_upgraded(self):
        """ThemeForge shipped as unifyingTheme: such a copy is still this bundle."""
        self.dest.mkdir(parents=True)
        (self.dest / "VERSION").write_text("unifyingTheme 0.9.0 abc\n", encoding="utf-8")
        (self.dest / "ui-theme.css").write_text("/* old */", encoding="utf-8")
        code, out = self.run_update()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.dest / "VERSION").read_text(encoding="utf-8").startswith("ThemeForge "))

    def test_unrelated_folder_is_refused(self):
        self.dest.mkdir(parents=True)
        (self.dest / "index.html").write_text("<p>app</p>", encoding="utf-8")
        code, out = self.run_update()
        self.assertEqual(code, 2)
        self.assertIn("not a ui-theme folder", out)

    def test_corrupt_download_is_refused(self):
        bad = dict(self.bundle)
        bad["ui-theme.css"] = bad["ui-theme.css"] + "tampered"
        self.archive.write_bytes(repo_tarball(bad))
        code, out = self.run_update()
        self.assertEqual(code, 2)
        self.assertIn("corrupt ui-theme.css", out)
        self.assertFalse(self.dest.exists())

    def test_unsafe_archive_members_are_refused(self):
        self.archive.write_bytes(repo_tarball(self.bundle, extra=[("ThemeForge-1.0.0/ui-theme/../../evil.txt", b"x")]))
        self.assertEqual(self.run_update()[0], 2)
        link = tarfile.TarInfo("ThemeForge-1.0.0/ui-theme/link.css")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        self.archive.write_bytes(repo_tarball(self.bundle, extra=[(link, None)]))
        code, out = self.run_update()
        self.assertEqual(code, 2)
        self.assertIn("link", out)

    def test_interrupted_update_resumes(self):
        self.run_update()
        newer = dict(self.bundle)
        for rel in ("ui-theme.css", "ui-components.css", "ui-theme-base.css"):
            newer[rel] = newer[rel] + "/* newer */\n"
        manifest = json.loads(newer["files.json"])
        for rel in newer:
            if rel != "files.json":
                manifest["files"][rel] = update.digest(newer[rel].encode("utf-8"))
        manifest["hash"] = "111111111111"
        newer["files.json"] = json.dumps(manifest)
        self.archive.write_bytes(repo_tarball(newer))
        real_write, calls = update.write_file, []

        def flaky(path, data):
            calls.append(path)
            if len(calls) == 2:
                raise PermissionError("held open")
            real_write(path, data)

        update.write_file = flaky
        try:
            code, out = self.run_update()
        finally:
            update.write_file = real_write
        self.assertEqual(code, 2, out)
        self.assertIn("resumes", out)
        code, out = self.run_update()
        self.assertEqual(code, 0, out)
        self.assertNotIn("edited by hand", out)
        expected = {k: v.encode("utf-8") if isinstance(v, str) else v for k, v in newer.items()}
        for rel, data in expected.items():
            self.assertEqual((self.dest / rel).read_bytes(), data, rel)

    def test_bootstrap_without_dest_is_a_clear_error(self):
        source = (ROOT / "tools" / "update.py").read_bytes()
        err = io.StringIO()
        namespace = {"__name__": "bootstrap"}
        exec(compile(source, "update.py", "exec"), namespace)
        namespace.pop("__file__", None)
        with contextlib.redirect_stderr(err):
            code = namespace["main"]([])
        self.assertEqual(code, 2)
        self.assertIn("--dest", err.getvalue())

    def test_check_with_source(self):
        self.run_update()
        code, out = self.run_update("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("up to date", out)



class ExampleTests(unittest.TestCase):
    """The FastAPI example renders and serves the theme (skipped without FastAPI)."""

    def test_fastapi_example(self):
        try:
            from fastapi.testclient import TestClient  # noqa: F401
        except ImportError:
            self.skipTest("fastapi not installed")
        import sys
        sys.path.insert(0, str(ROOT / "examples" / "fastapi-jinja"))
        try:
            spec = importlib.util.spec_from_file_location("example_app", ROOT / "examples" / "fastapi-jinja" / "app.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        client = TestClient(module.app)
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertLess(page.text.index("ui-theme.js"), page.text.index("ui-theme-base.css"))
        self.assertLess(page.text.index("app.css"), page.text.index("ui-theme/ui-theme.css"))
        script = client.get("/static/ui-theme/ui-theme.js")
        self.assertEqual(script.headers.get("cache-control"), "no-cache")


if __name__ == "__main__":
    unittest.main()
