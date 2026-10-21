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
        wheel = Path(self.tmp.name) / "forgeui-x-py3-none-any.whl"
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
        self.assertIn(forgeui.__version__, out)
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
