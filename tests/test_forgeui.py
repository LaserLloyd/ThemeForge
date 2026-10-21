"""Tests for the forgeui package: static_dir, head_html, mount and `forgeui vendor`.

    python -m unittest discover -s tests -v

Everything runs against temporary folders; the repository's own ui-theme/ is only read.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import forgeui  # noqa: E402
from forgeui import icons as iconlint  # noqa: E402
from forgeui import vendor  # noqa: E402
from forgeui import __main__ as cli  # noqa: E402

BUNDLE = ROOT / "ui-theme"


def run_vendor(*argv: str, cwd: Path):
    lines: list[str] = []
    manifest = cwd / "forgeui.json"
    args = vendor.build_parser().parse_args(["--manifest", str(manifest), *argv])
    code = vendor.run(manifest, source=args.source, version=args.version, check=args.check, force=args.force,
                      out=lines.append)
    return code, "\n".join(lines)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "app"
        self.repo.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, **overrides):
        data = {"dest": "static/ui-theme", "version": forgeui.bundle_version().rsplit(".", 1)[0]}
        data.update(overrides)
        (self.repo / "forgeui.json").write_text(json.dumps(data), encoding="utf-8")
        return data

    @property
    def dest(self) -> Path:
        return self.repo / "static" / "ui-theme"


class PackageTests(Base):
    def test_static_dir_is_the_bundle(self):
        self.assertEqual(forgeui.static_dir(), BUNDLE)
        self.assertTrue((forgeui.static_dir() / "ui-theme.js").is_file())

    def test_version_matches_the_bundle(self):
        self.assertEqual(forgeui.__version__, forgeui.bundle_version())
        self.assertEqual(forgeui.__version__, forgeui.registry()["version"])

    def test_core_themes_come_from_the_registry(self):
        core = forgeui.core_themes()
        self.assertIn("purple", core)
        self.assertNotIn("night-red", core)

    def test_quasar_icon_takes_icon_and_material_names(self):
        self.assertEqual(forgeui.quasar_icon("trash"), "svguse:/theme/icons.svg#trash")
        self.assertEqual(forgeui.quasar_icon("delete_forever"), "svguse:/theme/icons.svg#trash")
        self.assertEqual(forgeui.quasar_icon("settings", prefix="/static/ui-theme/"),
                         "svguse:/static/ui-theme/icons.svg#settings")
        self.assertEqual(forgeui.quasar_icon("menu", prefix=""), "svguse:/icons.svg#menu")
        with self.assertRaises(ValueError):
            forgeui.quasar_icon("no_such_icon")
        sprite = (forgeui.static_dir() / "icons.svg").read_text(encoding="utf-8")
        icons = json.loads((forgeui.static_dir() / "icons.json").read_text(encoding="utf-8"))["icons"]
        for entry in icons.values():
            for material in entry.get("material", []):
                drawn = forgeui.quasar_icon(material).rsplit("#", 1)[1]
                self.assertIn(f'<symbol id="{drawn}"', sprite, material)

    def test_head_html_order_and_attributes(self):
        head = forgeui.head_html(themes=["glacier", "paper"], default="glacier", storage_key="x.theme")
        lines = head.strip().splitlines()
        self.assertTrue(lines[0].startswith('<script src="/theme/ui-theme.js?v='), lines[0])
        self.assertIn('data-themes="glacier,paper"', lines[0])
        self.assertIn('data-default="glacier"', lines[0])
        self.assertIn('data-storage-key="x.theme"', lines[0])
        self.assertEqual([("ui-theme-base.css" in l, "ui-theme.css" in l) for l in lines[1:]],
                         [(True, False), (False, True)])

    def test_head_html_versions_urls_by_content_hash(self):
        head = forgeui.head_html()
        want = json.loads((BUNDLE / "files.json").read_text(encoding="utf-8"))["files"]["ui-theme.css"][:10]
        self.assertIn(f"/theme/ui-theme.css?v={want}", head)
        self.assertNotIn("?v=", forgeui.head_html(version_query=False))

    def test_head_html_sees_a_copy_vendored_again_under_a_running_process(self):
        copy = Path(self.tmp.name) / "copy"
        shutil.copytree(BUNDLE, copy)
        first = forgeui.head_html(folder=copy)
        manifest = json.loads((copy / "files.json").read_text(encoding="utf-8"))
        manifest["files"]["ui-theme.css"] = "f" * 64
        (copy / "files.json").write_text(json.dumps(manifest), encoding="utf-8")
        stat = (copy / "files.json").stat()
        os.utime(copy / "files.json", ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        second = forgeui.head_html(folder=copy)
        self.assertNotIn("ui-theme.css?v=ffffffffff", first)
        self.assertIn("ui-theme.css?v=ffffffffff", second)

    def test_quasar_icon_sees_a_copy_vendored_again_under_a_running_process(self):
        copy = Path(self.tmp.name) / "copy"
        shutil.copytree(BUNDLE, copy)
        self.assertEqual(forgeui.quasar_icon("trash", folder=copy), "svguse:/theme/icons.svg#trash")
        with self.assertRaises(ValueError):
            forgeui.quasar_icon("delete_sweep_zz", folder=copy)
        path = copy / "icons.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["icons"]["trash"]["material"].append("delete_sweep_zz")
        path.write_text(json.dumps(data), encoding="utf-8")
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        self.assertEqual(forgeui.quasar_icon("delete_sweep_zz", folder=copy), "svguse:/theme/icons.svg#trash")

    def test_head_html_adapters_components_and_overlays(self):
        head = forgeui.head_html(themes=["glacier"], adapters=["quasar"], components=True,
                                 extra_css=["adapters/app-extra.css"], app_css=["/static/app.css"],
                                 prefix="/sf-theme/", nonce="abc")
        lines = head.strip().splitlines()
        order = [("ui-theme.js", "ui-theme.js" in lines[0])]
        names = [re.search(r'(?:src|href)="([^"]+)"', l).group(1).split("?")[0] for l in lines]
        self.assertEqual(names, ["/sf-theme/ui-theme.js", "/sf-theme/adapters/quasar.js",
                                 "/sf-theme/ui-theme-base.css", "/sf-theme/ui-components.css",
                                 "/static/app.css", "/sf-theme/ui-theme.css", "/sf-theme/adapters/quasar.css",
                                 "/sf-theme/ui-components.js", "/sf-theme/adapters/app-extra.css"])
        self.assertTrue(all('nonce="abc"' in l for l in lines))
        self.assertTrue(order[0][1])

    def test_head_html_rejects_unknown_things(self):
        with self.assertRaises(ValueError):
            forgeui.head_html(themes=["nope"])
        with self.assertRaises(ValueError):
            forgeui.head_html(themes=["glacier"], default="nope")
        with self.assertRaises(ValueError):
            forgeui.head_html(adapters=["nope"])
        with self.assertRaises(ValueError):
            forgeui.head_html(storage_key="")

    def test_head_html_escapes_attribute_values(self):
        head = forgeui.head_html(themes=["glacier"], storage_key='a"b<c')
        self.assertIn('data-storage-key="a&quot;b&lt;c"', head)

    def test_head_from_manifest_uses_the_apps_own_copy(self):
        self.manifest(adapters=["quasar"], settings={"themes": ["glacier", "paper"], "default": "paper",
                                                     "storage_key": "m.theme"},
                      extra_files={"adapters/m-extra.css": "overlay.css"})
        (self.repo / "overlay.css").write_text(".m { padding: 1px; }\n", encoding="utf-8")
        code, _ = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0)
        head = forgeui.head_html_from_manifest(self.repo / "forgeui.json", prefix="/static/ui-theme")
        self.assertIn('data-default="paper"', head)
        self.assertIn("/static/ui-theme/adapters/m-extra.css?v=", head)
        self.assertTrue(head.strip().splitlines()[-1].find("m-extra.css") > 0)

    def test_mount_nicegui_style_app(self):
        calls = []

        class Fake:
            def add_static_files(self, url, directory, **kw):
                calls.append((url, Path(directory), kw))

        self.assertEqual(forgeui.mount(Fake(), "theme"), "/theme")
        self.assertEqual(calls, [("/theme", BUNDLE, {"max_cache_age": 0})])

    def test_mount_serves_the_vendored_copy_that_head_from_manifest_names(self):
        # The documented pair: vendor (with an overlay), head_html_from_manifest, mount. The head
        # names the overlay, which exists only in the vendored copy, so mount must serve that copy.
        self.manifest(extra_files={"adapters/m-extra.css": "overlay.css"})
        (self.repo / "overlay.css").write_text(".m { padding: 1px; }\n", encoding="utf-8")
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        head = forgeui.head_html_from_manifest(self.repo / "forgeui.json", prefix="/static/ui-theme")
        self.assertIn("/static/ui-theme/adapters/m-extra.css", head)
        self.assertFalse((BUNDLE / "adapters" / "m-extra.css").exists(), "the package copy has no overlay")
        calls = []

        class Fake:
            def add_static_files(self, url, directory, **kw):
                calls.append((url, Path(directory)))

        forgeui.mount(Fake(), "/static/ui-theme", folder=self.dest)
        self.assertEqual(calls, [("/static/ui-theme", self.dest.resolve())])
        self.assertTrue((calls[0][1] / "adapters" / "m-extra.css").is_file())
        with self.assertRaises(FileNotFoundError):
            forgeui.mount(Fake(), "/x", folder=self.repo / "nowhere")

    def test_mount_old_nicegui_without_cache_argument(self):
        calls = []

        class Old:
            def add_static_files(self, url, directory):
                calls.append(url)

        forgeui.mount(Old(), "/t/")
        self.assertEqual(calls, ["/t"])

    def test_mount_rejects_other_objects(self):
        with self.assertRaises(TypeError):
            forgeui.mount(object())

    def test_mount_fastapi_serves_the_bundle_uncached(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not installed")
        app = FastAPI()
        forgeui.mount(app, "/t")
        res = TestClient(app).get("/t/ui-theme.js")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["cache-control"], "no-cache")
        self.assertEqual(res.content.decode("utf-8").replace("\r\n", "\n"),
                         (BUNDLE / "ui-theme.js").read_text(encoding="utf-8").replace("\r\n", "\n"))


class VendorTests(Base):
    def test_first_vendor_then_check_then_idempotent(self):
        self.manifest()
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("changed:", out)
        self.assertEqual((self.dest / "VERSION").read_text(encoding="utf-8"),
                         (BUNDLE / "VERSION").read_text(encoding="utf-8"))
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual((code, out.splitlines()[-1]), (0, "ok"), out)
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("already up to date", out)

    def test_copy_is_byte_identical_to_update_py_output(self):
        self.manifest()
        run_vendor(cwd=self.repo)
        for rel in json.loads((BUNDLE / "files.json").read_text(encoding="utf-8"))["files"]:
            self.assertEqual((self.dest / rel).read_bytes(), (BUNDLE / rel).read_bytes(), rel)
        self.assertEqual((self.dest / "files.json").read_bytes(), (BUNDLE / "files.json").read_bytes())

    def test_check_fails_when_nothing_is_vendored(self):
        self.manifest()
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 1, out)
        self.assertIn("DRIFT", out)

    def test_check_detects_a_missing_file_and_an_edit(self):
        self.manifest()
        run_vendor(cwd=self.repo)
        (self.dest / "ui-components.css").unlink()
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertIn("missing ui-components.css", out)
        run_vendor(cwd=self.repo)
        with open(self.dest / "ui-theme.css", "a", encoding="utf-8") as fh:
            fh.write("/* hand edit */\n")
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertIn("edited  ui-theme.css", out)

    def test_hand_edit_is_refused_then_forced(self):
        self.manifest()
        run_vendor(cwd=self.repo)
        target = self.dest / "adapters" / "quasar.css"
        target.write_text(target.read_text(encoding="utf-8") + "\n.mine { color: red; }\n", encoding="utf-8")
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 1, out)
        self.assertIn("adapters/quasar.css", out)
        self.assertIn(".mine", target.read_text(encoding="utf-8"), "a refused run must not write")
        code, out = run_vendor("--force", cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn(".mine", target.read_text(encoding="utf-8"))

    def test_crlf_copy_is_not_an_edit(self):
        self.manifest()
        run_vendor(cwd=self.repo)
        path = self.dest / "ui-theme.css"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 0, out)

    def test_old_version_is_updated_and_stale_files_are_not_edits(self):
        self.manifest()
        run_vendor(cwd=self.repo)
        older = Path(self.tmp.name) / "older"
        shutil.copytree(BUNDLE, older)
        (older / "ui-theme.css").write_text("/* older */\n", encoding="utf-8")
        manifest = json.loads((older / "files.json").read_text(encoding="utf-8"))
        manifest["version"] = "1.1.0"
        manifest["files"]["ui-theme.css"] = vendor.digest(b"/* older */\n")
        (older / "files.json").write_text(json.dumps(manifest), encoding="utf-8")
        # install the older one by hand, as a previous vendor would have
        shutil.copy(older / "ui-theme.css", self.dest / "ui-theme.css")
        shutil.copy(older / "files.json", self.dest / "files.json")
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertIn("stale   ui-theme.css", out)
        self.assertNotIn("edited", out)
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)

    def test_version_is_written_last(self):
        self.manifest()
        order = []
        real = vendor.write_file

        def spy(path, data):
            order.append(path.name)
            real(path, data)

        vendor.write_file = spy
        try:
            run_vendor(cwd=self.repo)
        finally:
            vendor.write_file = real
        self.assertEqual(order[-1], "VERSION")
        self.assertEqual(order[-2], "files.json")

    def test_interrupted_run_leaves_the_old_version_and_resumes(self):
        self.manifest()
        real = vendor.write_file
        seen = []

        def flaky(path, data):
            seen.append(path.name)
            if path.name == "ui-theme.css":
                raise PermissionError("locked")
            real(path, data)

        vendor.write_file = flaky
        try:
            code, out = run_vendor(cwd=self.repo)
        finally:
            vendor.write_file = real
        self.assertEqual(code, 2, out)
        self.assertIn("resumes", out)
        self.assertFalse((self.dest / "VERSION").exists(), "VERSION must not be written by a failed run")
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)

    def test_overlays_are_separate_files_and_checked(self):
        (self.repo / "overlays").mkdir()
        (self.repo / "overlays" / "app-extra.css").write_text(".app-well { padding: 1px; }\n", encoding="utf-8")
        self.manifest(extra_files={"adapters/app-extra.css": "overlays/app-extra.css"})
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual((self.dest / "adapters" / "app-extra.css").read_text(encoding="utf-8"),
                         ".app-well { padding: 1px; }\n")
        self.assertEqual((self.dest / "adapters" / "quasar.css").read_bytes(),
                         (BUNDLE / "adapters" / "quasar.css").read_bytes(), "overlays never touch bundle files")
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)
        (self.dest / "adapters" / "app-extra.css").write_text("x", encoding="utf-8")
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertIn("overlay adapters/app-extra.css", out)
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)

    def test_append_form_and_bundle_collisions_are_refused(self):
        (self.repo / "o.css").write_text("x", encoding="utf-8")
        self.manifest(extra_files={"adapters/quasar.css": {"append": "o.css"}})
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("never appended", out)
        self.manifest(extra_files={"adapters/quasar.css": "o.css"})
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("file of the bundle", out)
        self.manifest(extra_files={"VERSION": "o.css"})
        self.assertEqual(run_vendor(cwd=self.repo)[0], 2)

    def test_unsafe_paths_are_refused(self):
        for dest in ("../out", "/abs/path", "C:/x", "a/../../b"):
            self.manifest(dest=dest)
            code, out = run_vendor(cwd=self.repo)
            self.assertEqual(code, 2, dest)
        (self.repo / "o.css").write_text("x", encoding="utf-8")
        self.manifest(extra_files={"../escape.css": "o.css"})
        self.assertEqual(run_vendor(cwd=self.repo)[0], 2)
        self.manifest(extra_files={"adapters/a-extra.css": "../o.css"})
        self.assertEqual(run_vendor(cwd=self.repo)[0], 2)

    def test_tampered_copy_files_json_cannot_delete_outside_the_copy(self):
        # The copy's files.json is committed in the consumer's repository; its entries decide
        # what vendor removes, so a crafted entry must not reach outside the copy.
        self.manifest()
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        victim = self.repo / "pyproject.toml"
        victim.write_text("keep", encoding="utf-8")
        table = json.loads((self.dest / "files.json").read_text(encoding="utf-8"))
        table["files"]["../../pyproject.toml"] = vendor.digest(b"keep")
        (self.dest / "files.json").write_text(json.dumps(table), encoding="utf-8")
        for flags in ((), ("--force",)):
            code, out = run_vendor(*flags, cwd=self.repo)
            self.assertEqual(code, 2, out)
            self.assertIn("pyproject.toml", out)
            self.assertTrue(victim.is_file(), flags)
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 2)

    def _symlink(self, link: Path, target: Path, is_dir: bool = False) -> None:
        try:
            link.symlink_to(target, target_is_directory=is_dir)
        except (OSError, NotImplementedError) as exc:  # Windows without developer mode
            self.skipTest(f"cannot create symlinks here: {exc}")

    def test_overlay_source_linking_outside_the_repo_is_refused(self):
        secret = Path(self.tmp.name) / "secret.env"
        secret.write_text("TOKEN=1\n", encoding="utf-8")
        self._symlink(self.repo / "overlay.css", secret)
        self.manifest(extra_files={"adapters/app-extra.css": "overlay.css"})
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2, out)
        self.assertIn("outside", out)
        self.assertFalse((self.dest / "adapters" / "app-extra.css").exists())

    def test_a_linked_subfolder_of_the_copy_is_not_written_through(self):
        self.manifest()
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        elsewhere = Path(self.tmp.name) / "elsewhere"
        elsewhere.mkdir()
        shutil.rmtree(self.dest / "adapters")
        self._symlink(self.dest / "adapters", elsewhere, is_dir=True)
        code, out = run_vendor("--force", cwd=self.repo)
        self.assertEqual(code, 2, out)
        self.assertIn("outside", out)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_an_app_file_named_like_a_new_bundle_file_is_not_overwritten(self):
        # A copy from a release without locales/ja.json; the app had put its own file there.
        self.manifest()
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        table = json.loads((self.dest / "files.json").read_text(encoding="utf-8"))
        del table["files"]["locales/ja.json"]
        (self.dest / "files.json").write_text(json.dumps(table), encoding="utf-8")
        own = self.dest / "locales" / "ja.json"
        own.write_text('{"cancel": "mine"}\n', encoding="utf-8")
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 1, out)
        self.assertIn("locales/ja.json", out)
        self.assertEqual(own.read_text(encoding="utf-8"), '{"cancel": "mine"}\n')
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 1)
        self.assertEqual(run_vendor("--force", cwd=self.repo)[0], 0)
        self.assertEqual(own.read_bytes(), (BUNDLE / "locales" / "ja.json").read_bytes().replace(b"\r\n", b"\n"))

    @unittest.skipIf(sys.platform == "win32", "POSIX permission bits")
    def test_written_files_are_readable_by_other_users(self):
        # mkstemp creates 0600 files; a copy served by nginx or another user must stay readable.
        old = os.umask(0o022)
        try:
            self.manifest()
            self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        finally:
            os.umask(old)
        for rel in ("ui-theme.css", "VERSION", "files.json", "locales/en.json"):
            self.assertEqual((self.dest / rel).stat().st_mode & 0o777, 0o644, rel)
        (self.dest / "ui-theme.css").chmod(0o640)
        (self.dest / "ui-theme.css").write_text("/* stale */\n", encoding="utf-8")
        self.assertEqual(run_vendor("--force", cwd=self.repo)[0], 0)
        self.assertEqual((self.dest / "ui-theme.css").stat().st_mode & 0o777, 0o640, "an existing mode is kept")

    def test_unknown_manifest_key_is_a_typo_error(self):
        self.manifest(extras_files={})
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("extras_files", out)

    def test_adapters_subset(self):
        self.manifest(adapters=["quasar"])
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertTrue((self.dest / "adapters" / "quasar.css").is_file())
        self.assertFalse((self.dest / "adapters" / "tailwind.css").exists())
        files = json.loads((self.dest / "files.json").read_text(encoding="utf-8"))
        self.assertNotIn("adapters/tailwind.css", files["files"])
        self.assertEqual(files["subset"], {"adapters": ["quasar"]})
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)

    def test_no_adapters_and_unknown_adapter(self):
        self.manifest(adapters=[])
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        self.assertFalse((self.dest / "adapters").exists())
        self.manifest(adapters=["bogus"])
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("bogus", out)

    def test_narrowing_adapters_removes_the_dropped_ones(self):
        self.manifest()
        run_vendor(cwd=self.repo)
        self.assertTrue((self.dest / "adapters" / "tailwind.css").is_file())
        self.manifest(adapters=["quasar"])
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("(removed)", out)
        self.assertFalse((self.dest / "adapters" / "tailwind.css").exists())

    def test_foreign_files_are_left_alone(self):
        self.manifest()
        run_vendor(cwd=self.repo)
        (self.dest / "mine.txt").write_text("keep", encoding="utf-8")
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("mine.txt", out)
        run_vendor("--force", cwd=self.repo)
        self.assertEqual((self.dest / "mine.txt").read_text(encoding="utf-8"), "keep")

    def test_a_folder_that_is_not_a_bundle_is_refused(self):
        self.manifest()
        self.dest.mkdir(parents=True)
        (self.dest / "precious.txt").write_text("keep", encoding="utf-8")
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("not a copy", out)
        self.assertTrue((self.dest / "precious.txt").exists())

    def test_pre_release_stamp_copy_without_files_json_is_upgraded(self):
        self.manifest()
        self.dest.mkdir(parents=True)
        (self.dest / "VERSION").write_text("ui-theme 2026-09-24 638060cc7dc6\n", encoding="utf-8")
        (self.dest / "ui-theme.css").write_text("/* old */\n", encoding="utf-8")
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)

    def test_version_constraints(self):
        have = forgeui.bundle_version()
        major, minor, _patch = have.split(".")
        self.manifest(version=f"{major}.{minor}")
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        self.manifest(version=f"{major}")
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)
        self.manifest(version=have)
        self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0)
        self.manifest(version=f"{major}.{int(minor) + 1}")
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 2, out)
        self.assertIn("asks for", out)
        code, out = run_vendor("--version", f"{int(major) + 1}", "--check", cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("--version", out)

    def test_version_flag_overrides_the_manifest(self):
        have = forgeui.bundle_version()
        major, minor, _ = have.split(".")
        self.manifest(version=f"{major}.{int(minor) + 5}")
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2, out)
        code, out = run_vendor("--version", f"{major}.{minor}", cwd=self.repo)
        self.assertEqual(code, 0, out)

    def test_bad_version_syntax(self):
        self.manifest(version="one.two")
        self.assertEqual(run_vendor(cwd=self.repo)[0], 2)

    def test_settings_must_name_real_themes(self):
        self.manifest(settings={"themes": ["glacier", "nope"], "default": "glacier", "storage_key": "k"})
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2, out)
        self.assertIn("nope", out)
        code, out = run_vendor("--check", cwd=self.repo)
        self.assertEqual(code, 1)
        self.assertIn("settings:", out)
        self.manifest(settings={"themes": ["glacier"], "default": "paper", "storage_key": "k"})
        self.assertEqual(run_vendor(cwd=self.repo)[0], 2)
        self.manifest(settings={"themes": ["glacier", "paper"], "default": "auto", "storage_key": "k"})
        self.assertEqual(run_vendor(cwd=self.repo)[0], 0)
        self.manifest(settings={"storage_key": " "})
        self.assertEqual(run_vendor(cwd=self.repo)[0], 2)
        self.manifest(settings={"bogus": 1})
        self.assertEqual(run_vendor(cwd=self.repo)[0], 2)

    def test_source_folder_zip_wheel_and_tarball(self):
        self.manifest()
        # a folder: the bundle itself, and a checkout holding ui-theme/
        self.assertEqual(run_vendor("--source", str(BUNDLE), cwd=self.repo)[0], 0)
        self.assertEqual(run_vendor("--check", "--source", str(ROOT), cwd=self.repo)[0], 0)
        files = sorted(p for p in BUNDLE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        zpath = Path(self.tmp.name) / "forgeui-x.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            for p in files:
                zf.write(p, f"ui-theme/{p.relative_to(BUNDLE).as_posix()}")
        wheel = Path(self.tmp.name) / "themeforge-x-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as zf:
            zf.writestr("forgeui-x.dist-info/METADATA", "Name: forgeui\n")
            for p in files:
                zf.write(p, f"forgeui/ui-theme/{p.relative_to(BUNDLE).as_posix()}")
        tgz = Path(self.tmp.name) / "repo.tar.gz"
        with tarfile.open(tgz, "w:gz") as tar:
            for p in files:
                tar.add(p, f"ThemeForge-x/ui-theme/{p.relative_to(BUNDLE).as_posix()}")
            tar.add(ROOT / "README.md", "ThemeForge-x/README.md")
        for source in (zpath, wheel, tgz):
            shutil.rmtree(self.dest)
            code, out = run_vendor("--source", str(source), cwd=self.repo)
            self.assertEqual(code, 0, f"{source.name}: {out}")
            self.assertEqual(run_vendor("--check", cwd=self.repo)[0], 0, source.name)

    def test_corrupt_source_is_refused_before_anything_is_written(self):
        self.manifest()
        broken = Path(self.tmp.name) / "broken"
        shutil.copytree(BUNDLE, broken)
        (broken / "ui-theme.css").write_text("tampered", encoding="utf-8")
        code, out = run_vendor("--source", str(broken), cwd=self.repo)
        self.assertEqual(code, 2, out)
        self.assertIn("corrupt ui-theme.css", out)
        self.assertFalse(self.dest.exists())
        (broken / "ui-theme.css").write_bytes((BUNDLE / "ui-theme.css").read_bytes())
        (broken / "extra.txt").write_text("x", encoding="utf-8")
        self.assertIn("unlisted extra.txt", run_vendor("--source", str(broken), cwd=self.repo)[1])

    def test_unsafe_archive_members_are_refused(self):
        self.manifest()
        zpath = Path(self.tmp.name) / "evil.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("../evil.txt", "x")
            zf.writestr("ui-theme/files.json", "{}")
        code, out = run_vendor("--source", str(zpath), cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("unsafe", out)

    def test_missing_manifest_and_source(self):
        code, out = run_vendor(cwd=self.repo)
        self.assertEqual(code, 2)
        self.assertIn("forgeui.json", out)
        self.manifest()
        self.assertEqual(run_vendor("--source", str(self.repo / "nope"), cwd=self.repo)[0], 2)

    def test_hash_checks_in_check_mode_do_not_write(self):
        self.manifest()
        run_vendor("--check", cwd=self.repo)
        self.assertFalse(self.dest.exists())


class CliTests(Base):
    def call(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(argv))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue() + err.getvalue()

    def test_version_and_path(self):
        code, out = self.call("--version")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f"themeforge {forgeui.__version__} (bundle {forgeui.bundle_version()})")
        code, out = self.call("path")
        self.assertEqual((code, out.strip()), (0, str(BUNDLE)))

    def test_init_vendor_check_head(self):
        manifest = self.repo / "forgeui.json"
        code, out = self.call("init", "--dest", "static/ui-theme", "--manifest", str(manifest))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.call("init", "--dest", "x", "--manifest", str(manifest))[0], 2)
        self.assertEqual(self.call("vendor", "--manifest", str(manifest))[0], 0)
        self.assertEqual(self.call("vendor", "--check", "--manifest", str(manifest))[0], 0)
        code, out = self.call("head", "--manifest", str(manifest), "--prefix", "/static/ui-theme")
        self.assertEqual(code, 0, out)
        self.assertIn('data-storage-key="myapp.theme"', out)

    def test_help_and_version_survive_a_missing_bundle(self):
        def gone(*_a, **_k):
            raise FileNotFoundError("no bundle")
        real = cli.bundle_version
        cli.bundle_version = gone
        try:
            code, out = self.call("--version")
            help_code, _ = self.call("--help")
        finally:
            cli.bundle_version = real
        self.assertEqual((code, help_code), (0, 0), out)
        self.assertIn("bundle missing", out)

    def test_python_dash_m_runs(self):
        import subprocess
        proc = subprocess.run([sys.executable, "-m", "forgeui", "path"], cwd=ROOT, capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(Path(proc.stdout.strip()), BUNDLE)


class IconLintTests(Base):
    """``python -m forgeui icons``: emoji and Material names an app should draw with the bundle's icons."""

    FILES = {
        "templates/index.html": (
            '<button class="ui-btn">\u2699\ufe0f Settings</button>\n'
            "<p>Go from A \u2192 B, then C \u2026 D.</p>\n"
            "<button>\u2715</button>\n"
            "<span>\U0001f98a fox</span>\n"
            "<span>\U0001f5d1 kept</span> <!-- forgeui: allow-icons -->\n"),
        "static/app.js": "const close = '\u2715';\nconst sentence = \"A \u2192 B\";\n",
        "static/locales/en.json": '{"close": "\u2715", "sentence": "A \u2192 B"}\n',
        "app.py": ("from nicegui import ui\n"
                   "ui.button(icon='delete_forever')\n"
                   "ui.button(icon='account_tree')\n"
                   "ui.button(icon=forgeui.quasar_icon('trash'))\n"
                   "ui.icon('home')  # forgeui: allow-icons\n"),
        "node_modules/x.js": "const a = '\U0001f5d1';\n",
        "static/ui-theme/ui-components.js": "const a = '\U0001f5d1';\n",
        "static/ui-theme/files.json": "{}\n",
        "static/ui-theme/VERSION": "ThemeForge 1.0.0\n",
        "data/other.json": '{"x": "\U0001f5d1"}\n',
        "notes.md": "\U0001f5d1\n",
    }

    def setUp(self):
        super().setUp()
        for rel, text in self.FILES.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        self.catalog = iconlint.load_catalog()

    def call(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(["icons", *argv])
            except SystemExit as exc:
                code = exc.code
        here = self.repo.as_posix() + "/"
        return code, out.getvalue().replace(here, ""), err.getvalue().replace(here, "")

    def tree(self, files):
        """Write ``files`` (relative path -> text) under a fresh folder inside the repo; return the folder."""
        root = self.repo / "case"
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        return root

    def scan(self, text, **kwargs):
        return [(f.line, f.text, f.icon) for f in iconlint.scan_text(text, self.catalog, **kwargs)]

    def test_text_report(self):
        code, out, err = self.call(str(self.repo))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), [
            "app.py:2: delete_forever -> trash (forgeui.quasar_icon('delete_forever'))",
            "app.py:3: account_tree (no ThemeForge icon)",
            "static/app.js:1: \u2715 -> x",
            "static/locales/en.json:1: \u2715 -> x",
            "templates/index.html:1: \u2699\ufe0f -> settings",
            "templates/index.html:3: \u2715 -> x",
            "5 to replace (4 emoji, 1 Material), 1 Material name with no icon",
        ])

    def test_prose_markers_and_skipped_folders_are_left_alone(self):
        out = self.call(str(self.repo))[1]
        self.assertNotIn("\u2192", out)                       # A -> B, in a sentence and in a string
        self.assertNotIn("index.html:2", out)                 # the ellipsis inside a sentence
        self.assertNotIn("index.html:5", out)                 # forgeui: allow-icons
        self.assertNotIn("app.py:5", out)
        self.assertNotIn("app.py:4", out)                     # already forgeui.quasar_icon(...)
        for skipped in ("node_modules", "ui-theme", "other.json", "notes.md"):
            self.assertNotIn(skipped, out)

    def test_check_exit_codes(self):
        self.assertEqual(self.call(str(self.repo), "--check")[0], 1)
        self.assertEqual(self.call(str(self.repo))[0], 0)
        # Material names with no icon and emoji with no icon never fail --check.
        quiet = self.repo / "quiet"
        quiet.mkdir()
        (quiet / "a.py").write_text("ui.icon('account_tree')\nx = '\U0001f98a'\n", encoding="utf-8")
        code, out, _ = self.call(str(quiet), "--check", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("0 to replace (0 emoji, 0 Material), 1 Material name with no icon, 1 emoji with no icon", out)
        (quiet / "a.py").write_text("print('hello')\n", encoding="utf-8")
        self.assertEqual(self.call(str(quiet), "--check")[0], 0)

    def test_all_lists_emoji_without_an_icon(self):
        fox = "templates/index.html:4: \U0001f98a (no icon; fine as content)"
        self.assertNotIn(fox, self.call(str(self.repo))[1])
        code, out, _ = self.call(str(self.repo), "--all")
        self.assertEqual(code, 0)
        self.assertIn(fox, out.splitlines())

    def test_json_report(self):
        code, out, err = self.call(str(self.repo), "--json", "--check")
        self.assertEqual((code, err), (1, ""))                # still honours --check
        report = json.loads(out)
        self.assertEqual(set(report), {"findings", "skipped", "summary"})
        self.assertEqual(report["skipped"], [])
        self.assertEqual([(f["path"], f["line"], f["text"], f["kind"], f["icon"]) for f in report["findings"]], [
            ("app.py", 2, "delete_forever", "material", "trash"),
            ("app.py", 3, "account_tree", "material", None),
            ("static/app.js", 1, "\u2715", "emoji", "x"),
            ("static/locales/en.json", 1, "\u2715", "emoji", "x"),
            ("templates/index.html", 1, "\u2699\ufe0f", "emoji", "settings"),
            ("templates/index.html", 3, "\u2715", "emoji", "x"),
        ])
        self.assertEqual({k: report["summary"][k] for k in ("to_replace", "emoji", "material", "material_no_icon")},
                         {"to_replace": 5, "emoji": 4, "material": 1, "material_no_icon": 1})
        self.assertEqual(self.call(str(self.repo), "--json")[0], 0)

    def test_usage_errors_exit_2(self):
        code, out, err = self.call(str(self.repo / "nope"))
        self.assertEqual(code, 2)
        self.assertIn("nope", err)
        self.assertEqual(out, "")
        self.assertEqual(self.call()[0], 2)                   # no PATH
        self.assertEqual(self.call(str(self.repo), "--folder", str(self.repo / "nope"))[0], 2)

    def test_folder_reads_a_vendored_icons_json(self):
        folder = self.repo / "copy"
        folder.mkdir()
        (folder / "icons.json").write_text(
            json.dumps({"icons": {"fox": {"emoji": ["\U0001f98a"], "material": ["pets"]}}}), encoding="utf-8")
        code, out, _ = self.call(str(self.repo / "templates"), "--folder", str(folder))
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["templates/index.html:4: \U0001f98a -> fox",
                                            "1 to replace (1 emoji, 0 Material)"])

    def test_a_file_named_twice_is_read_once_and_a_named_file_is_always_read(self):
        page = str(self.repo / "templates" / "index.html")
        out = self.call(page, str(self.repo / "templates"))[1]
        self.assertEqual(out.count("index.html:1:"), 1)
        out = self.call(str(self.repo / "notes.md"))[1]
        self.assertIn("notes.md:1: \U0001f5d1 -> trash", out)

    def test_tests_and_build_folders_are_skipped_with_a_note(self):
        gear = "<b>\u2699</b>\n"
        root = self.tree({
            "app/ui.html": gear,
            # Tests sits in another folder from tests: on Windows and macOS they would be one folder.
            "app/tests/t.html": gear, "app/pkg/Tests/t.html": gear, "app/test/t.html": gear,
            "app/__tests__/t.js": gear,
            "app/pkg/build/b.html": gear, "app/pkg/vendor/v.html": gear, "app/dist/d.html": gear,
            # skipped without a word
            "app/.hidden/h.html": gear, "app/node_modules/n.html": gear, "app/__pycache__/p.html": gear,
            "app/venv/v.html": gear, "app/copy/files.json": "{}", "app/copy/VERSION": "ThemeForge 1.0.0\n",
            "app/copy/c.html": gear,
        })
        code, out, err = self.call(str(root / "app"))
        self.assertEqual(code, 0)
        self.assertEqual([line.split(" ")[0] for line in out.splitlines()[:-1]], ["case/app/ui.html:1:"])
        self.assertEqual(err.splitlines(), [
            "note: skipped case/app/__tests__", "note: skipped case/app/dist", "note: skipped case/app/pkg/Tests",
            "note: skipped case/app/pkg/build", "note: skipped case/app/pkg/vendor", "note: skipped case/app/test",
            "note: skipped case/app/tests"])
        code, out, err = self.call(str(root / "app"), "--json")
        report = json.loads(out)
        self.assertEqual(report["skipped"], [line.split("skipped ")[1] for line in err.splitlines()])
        self.assertEqual([f["path"] for f in report["findings"]], ["case/app/ui.html"])

    def test_a_folder_named_on_the_command_line_is_always_read(self):
        gear = "<b>\u2699</b>\n"
        root = self.tree({"app/tests/t.html": gear, "app/tests/build/b.html": gear, "app/pkg/build/b.html": gear,
                          "app/pkg/ui.html": gear})
        for named in ("app/tests", "app/pkg/build"):
            code, out, err = self.call(str(root / named))
            self.assertEqual(out.count("\u2699 -> settings"), 1, (named, out))
        # what is skipped below it is still said once, even when two named folders reach it
        code, out, err = self.call(str(root / "app" / "tests"), str(root / "app" / "tests"))
        self.assertEqual(err.splitlines(), ["note: skipped case/app/tests/build"])
        code, out, err = self.call(str(root / "app"), str(root / "app" / "pkg"))
        self.assertEqual(err.splitlines(), ["note: skipped case/app/pkg/build", "note: skipped case/app/tests"])
        self.assertEqual(out.count("\u2699 -> settings"), 1, out)

    def test_python_dash_m_prints_utf8(self):
        import subprocess
        proc = subprocess.run([sys.executable, "-m", "forgeui", "icons", str(self.repo / "static"), "--check"],
                              cwd=ROOT, capture_output=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("\u2715 -> x", proc.stdout)

    # -- the emoji lookup, as UIComponents.iconFor()

    def test_every_mapped_symbol_is_found_and_maps_to_its_icon(self):
        icons = json.loads((BUNDLE / "icons.json").read_text(encoding="utf-8"))["icons"]
        expected = {}
        for name, entry in icons.items():
            for symbol in entry["emoji"]:
                expected[symbol] = name
        self.assertGreater(len(expected), 200)
        for symbol, name in expected.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(self.scan("<b>%s</b>\n" % symbol), [(1, symbol, name)])

    def test_variation_selectors_skin_tones_and_zwj_sequences(self):
        self.assertEqual(self.scan("\U0001f5d1\ufe0f"), [(1, "\U0001f5d1\ufe0f", "trash")])
        self.assertEqual(self.scan("a \U0001f44d\U0001f3fd b"), [(1, "\U0001f44d\U0001f3fd", "thumbs-up")])
        self.assertEqual(self.scan("\U0001f9d1\u200d\U0001f4bb"), [(1, "\U0001f9d1\u200d\U0001f4bb", "user")])
        rainbow = "\U0001f3f3\ufe0f\u200d\U0001f308"
        self.assertEqual(self.scan(rainbow), [(1, rainbow, "flag")])
        flag = "\U0001f1fa\U0001f1f8"                          # a flag is one emoji, with no icon
        self.assertEqual(self.scan(flag), [])
        self.assertEqual(self.scan(flag, show_all=True), [(1, flag, None)])
        self.assertEqual(self.scan("1\ufe0f\u20e3", show_all=True), [(1, "1\ufe0f\u20e3", None)])

    def test_pictographs_count_anywhere_but_symbols_only_alone(self):
        self.assertEqual(self.scan("Saved \u2705 just now"), [(1, "\u2705", "circle-check")])
        self.assertEqual(self.scan("\u2699 Settings"), [(1, "\u2699", "settings")])
        self.assertEqual(self.scan("Open \u2197\ufe0f in a tab"), [(1, "\u2197\ufe0f", "external-link")])
        prose = "A \u2192 B \u2713 ok \u2026 more \u25b8 \u25be \u2630 3 \u00d7 4 \u21d2 \u2122"
        self.assertEqual(self.scan(prose), [])
        self.assertEqual(self.scan(prose, show_all=True), [])  # not alone, so not even listed
        for alone in ("'\u2192'", '"\u25b8"', "`\u2715`", "<b>\u2713</b>", "<i> \u2630 </i>", "<b>\u2026</b>"):
            with self.subTest(alone=alone):
                self.assertEqual(len(self.scan(alone)), 1)
        self.assertEqual(self.scan("<button>\n  \u2715\n</button>"), [(2, "\u2715", "x")])
        self.assertEqual(self.scan("<button>\u00d7</button>"), [(1, "\u00d7", "x")])  # the usual close glyph

    def test_ellipsis_and_times_count_only_as_an_element(self):
        # A truncation suffix and a multiplication sign are text, whatever the quotes around them.
        for text in ('snippet = snippet[:57] + "\u2026"', "label = w + '\u00d7' + h", "assert out.endswith('\u2026')",
                     "const times = `\u00d7`;", "{ text: '\u00d7' }", "('\u2026', '...')"):
            with self.subTest(text=text):
                self.assertEqual(self.scan(text), [])
        self.assertEqual(self.scan("<span>\u2026</span>"), [(1, "\u2026", "ellipsis")])
        self.assertEqual(self.scan("<button>\n  \u00d7\n</button>"), [(2, "\u00d7", "x")])
        # the other symbols that count only alone still count as a string
        self.assertEqual(self.scan("{ text: '\u2715' }"), [(1, "\u2715", "x")])

    def test_comment_lines_are_skipped_by_file_type(self):
        gear = "\u2699"
        for path, text in [
            ("a.py", "# {g}"), ("a.py", "x = 1\n    # {g}"), ("a.sh", "# {g}"), ("a.yml", "# {g}"),
            ("a.js", "// {g}"), ("a.ts", "  // {g}"), ("a.py", "// {g}"),
            ("a.js", "/* {g} */"), ("a.js", "/**\n * {g}\n */"), ("a.js", "run(); /* opened late\n * {g}\n */"),
            ("a.css", "/*\n  {g} a block comment whose lines do not start with a star\n*/"),
            ("a.css", "/* {g}\n   {g} */"), ("a.css", "/**/\n/* x */ /* {g} */"),
            ("a.html", "<!-- {g} -->"), ("a.html", "<!--\n  {g}\n-->"), ("a.vue", "<!-- {g} -->"),
        ]:
            with self.subTest(path=path, text=text):
                self.assertEqual(self.scan(text.format(g=gear), path=path), [])
        # # starts a colour or an id in CSS and HTML; a comment that ends is followed by code again
        for path, text, line in [
            ("a.css", "#app::before {{ content: '{g}' }}", 1), ("a.html", "# {g}", 1), ("a.js", "# {g}", 1),
            ("a.py", "x = 1  # {g}", 1), ("a.js", "run();  // {g}", 1), ("a.py", "* {g}", 1),
            ("a.css", "/* a */\n<b>{g}</b>", 2), ("a.html", "<!-- a -->\n<b>{g}</b>", 2),
            ("a.css", "/* a\nb */\n<b>{g}</b>", 3), ("a.md", "* {g} item\n// {g}", 1), ("", "// {g}", 1),
        ]:
            with self.subTest(path=path, text=text):
                found = self.scan(text.format(g=gear), path=path)
                self.assertEqual([f[0] for f in found][:1], [line])

    def test_python_docstrings_are_skipped_but_other_strings_are_read(self):
        lines = [
            '"""Module {g}',
            'over two lines {g}"""',
            "import x",
            "class A:",
            '    """Class {g}."""',
            "    def f(self):",
            "        '''Method {g}'''",
            '        return x.html("""<b>{g}</b>""")  # READ: NiceGUI html with an emoji in it',
            "async def g():",
            '    """Async {g}"""',
            "def h():",
            "    y = 1",
            '    """Not a docstring {g}"""  # READ: it is not the first statement',
            "NOTE = '''{g}'''  # READ: a module-level string that is not the docstring",
        ]
        text = "\n".join(lines).format(g="\u2699")
        hits = [n for n, line in enumerate(text.split("\n"), 1) if "READ" in line]
        self.assertEqual(len(hits), 3)
        self.assertEqual([f[0] for f in self.scan(text, path="app.py")], hits)
        # Not Python, or Python that does not parse: nothing is a docstring.
        self.assertEqual(len(self.scan('"""Module \u2699"""\n', path="app.js")), 1)
        self.assertEqual(len(self.scan('"""Module \u2699"""\ndef broken(:\n', path="app.py")), 1)
        self.assertEqual(len(self.scan('\ufeff"""Module \u2699"""\n', path="app.py")), 0)  # a BOM is fine

    def test_reading_python_raises_no_syntax_warnings(self):
        import warnings
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.scan('"""Docstring"""\nx = re.compile("\\d+ \\.")\ny = "\\d"\n', path="app.py")
        self.assertEqual([str(w.message) for w in caught], [])

    def test_material_name_forms(self):
        text = "\n".join([
            "ui.button(icon='delete_forever')",
            'ui.button("Go", icon="refresh")',
            "ui.icon('settings', size='sm')",
            "ui.button('x').props('flat round icon=close')",
            "ui.button('x').props(\"icon='delete'\")",
            "tabs = [{'icon': 'folder_open', 'label': 'Files'}, {\"icon\": \"account_tree\"}]",
            '<q-icon name="delete_outline" size="sm" />',
            '<q-btn icon="mic" icon-right="close" />',
        ])
        expected = [
            (1, "delete_forever", "trash"), (2, "refresh", "refresh-cw"), (3, "settings", "settings"),
            (4, "close", "x"), (5, "delete", "trash"), (6, "folder_open", "folder"),
            (6, "account_tree", None), (7, "delete_outline", "trash"), (8, "mic", "mic"), (8, "close", "x")]
        self.assertEqual(self.scan(text, path="app.py"), expected)

    def test_the_bundles_own_icon_names_depend_on_the_file_type(self):
        # Quasar draws icon="name" from its font, so even trash draws a missing glyph in NiceGUI and Vue.
        quasar = "\n".join([
            "ui.button(icon='trash')",
            "ui.icon('circle-check')",
            "tabs = [{'icon': 'search'}, {'icon': 'mail'}]",
            "ui.button(icon='mdi-delete')",
            "ui.button(icon='svguse:/theme/icons.svg#trash')",
        ])
        self.assertEqual(self.scan(quasar, path="app.py"), [
            (1, "trash", "trash"), (2, "circle-check", "circle-check"), (3, "search", "search"),
            (3, "mail", "mail")])
        self.assertEqual(self.scan('<q-btn icon="trash" />\n<q-icon name="mail" />', path="Page.vue"),
                         [(1, "trash", "trash"), (2, "mail", "mail")])
        # Elsewhere they already name sprite icons, mail and search being Material names too.
        script = "\n".join([
            "const tabs = [{ icon: 'mail' }, { icon: 'trash' }, { icon: 'search' }, { icon: 'circle-check' }];",
            "const more = [{ icon: 'delete_forever' }, { icon: 'account_tree' }];",
        ])
        for path in ("app.js", "app.ts", "app.jsx", "app.tsx", "index.html", "app.svelte", "app.css", ""):
            with self.subTest(path=path):
                self.assertEqual(self.scan(script, path=path),
                                 [(2, "delete_forever", "trash"), (2, "account_tree", None)])

    def test_material_lookalikes_are_left_alone(self):
        text = "\n".join([
            "ui.button(icon='svguse:/theme/icons.svg#trash')",
            "ui.button(icon='img:/static/logo.png')",
            "ui.button(icon=forgeui.quasar_icon('delete_forever'))",
            "ui.button(icon=icon_name)",
            "ui.button(icon='mdi-delete')",
            "ui.button(icon='fa-solid fa-trash')",
            "<q-btn :icon=\"expr\" prepend-icon=\"close\" my_icon=\"close\">",
            "{'icon': 'trash', 'label': 'Delete'}",             # one of the bundle's own names (not in .py)
            "ui.button(icon='delete_forever')  # forgeui: allow-icons",
            "if icon == 'close': pass",
        ])
        self.assertEqual(self.scan(text, path="app.js"), [])

    def test_the_module_stays_python_39_syntax(self):
        import ast
        source = (ROOT / "forgeui" / "icons.py").read_text(encoding="utf-8")
        ast.parse(source, feature_version=(3, 9))


class ExamplesSelfTest(unittest.TestCase):
    """The examples' forgeui.json manifests vendor, check and refuse hand edits (tools/selftest_forgeui.py)."""

    def test_examples_vendor_and_check(self):
        import subprocess
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / "selftest_forgeui.py")], cwd=ROOT,
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("fastapi-jinja: ok", proc.stdout)
        self.assertIn("static-html: ok", proc.stdout)

    def test_every_example_manifest_accepts_this_release(self):
        have = forgeui.bundle_version()
        for path in sorted((ROOT / "examples").glob("*/forgeui.json")):
            wanted = json.loads(path.read_text(encoding="utf-8"))["version"]
            self.assertTrue(vendor.parse_constraint(wanted)(have), f"{path.parent.name} wants {wanted}, bundle is {have}")


if __name__ == "__main__":
    unittest.main()
