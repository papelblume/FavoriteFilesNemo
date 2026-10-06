"""Tests for nemo_favorites (no Sublime required)."""
import os
import shutil
import subprocess
import tempfile
import unittest

from FavoriteFilesNemo import nemo_favorites as nf

SYSTEM_MIME = os.path.isfile("/usr/share/mime/subclasses")


def fake_tables():
    """Small hand-written hierarchy so the logic is tested independent of the host."""

    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "mime"))
    with open(os.path.join(tmp, "mime", "subclasses"), "w") as f:
        f.write("text/markdown text/plain\n")
        f.write("application/x-shellscript application/x-executable\n")
        f.write("application/x-executable text/plain\n")   # two-level chain
        f.write("application/json application/javascript\n")
        f.write("application/javascript text/plain\n")
        f.write("loop/a loop/b\nloop/b loop/a\n")           # buggy circular data must not hang
    with open(os.path.join(tmp, "mime", "aliases"), "w") as f:
        f.write("text/x-markdown text/markdown\n")
    try:
        return nf.load_mime_tables([tmp])
    finally:
        shutil.rmtree(tmp)


class TestMimeLogic(unittest.TestCase):
    """is_mime_type against synthetic tables."""

    def setUp(self):
        self.t = fake_tables()

    def check(self, mime, base, expected):
        self.assertEqual(nf.is_mime_type(mime, base, self.t), expected, "%s vs %s" % (mime, base))

    def test_exact_and_text_wildcard(self):
        self.check("text/plain", "text/plain", True)
        self.check("text/x-anything-unlisted", "text/plain", True)   # glib: every text/* is text/plain

    def test_subclass_chains(self):
        self.check("text/markdown", "text/plain", True)
        self.check("application/x-shellscript", "text/plain", True)  # two hops
        self.check("application/json", "text/plain", True)

    def test_alias(self):
        self.check("text/x-markdown", "text/plain", True)

    def test_negatives(self):
        self.check("image/png", "text/plain", False)
        self.check("inode/directory", "text/plain", False)
        self.check("application/unknown", "text/plain", False)
        self.check("application/octet-stream", "text/plain", False)

    def test_octet_stream_and_supertype(self):
        self.check("image/png", "application/octet-stream", True)
        self.check("inode/directory", "application/octet-stream", False)
        self.check("image/png", "image/*", True)
        self.check("text/plain", "image/*", False)

    def test_circular_data_terminates(self):
        self.check("loop/a", "text/plain", False)


@unittest.skipUnless(SYSTEM_MIME, "shared-mime-info not installed")
class TestRealMimeData(unittest.TestCase):
    """The same questions against the host's real shared-mime-info database."""

    def test_common_text_files(self):
        nf.reset_cache()
        for mime in ("text/plain", "text/markdown", "text/x-python", "text/x-csrc",
                     "application/x-shellscript", "application/json", "application/xml"):
            self.assertTrue(nf.is_mime_type(mime, "text/plain"), mime)

    def test_non_text(self):
        for mime in ("image/png", "application/pdf", "inode/directory", "application/zip"):
            self.assertFalse(nf.is_mime_type(mime, "text/plain"), mime)


class TestParsing(unittest.TestCase):
    """GVariant array parsing, entry splitting and URI conversion."""

    def test_parse_string_array(self):
        self.assertEqual(nf.parse_string_array("@as []\n"), [])
        self.assertEqual(nf.parse_string_array(""), [])  # dconf prints nothing for unset keys
        self.assertEqual(nf.parse_string_array("['a::b', 'c::d']\n"), ["a::b", "c::d"])
        self.assertEqual(nf.parse_string_array("[\"it's::x\"]"), ["it's::x"])
        self.assertIsNone(nf.parse_string_array("not a list"))
        self.assertIsNone(nf.parse_string_array("[1, 2]"))

    def test_parse_entry(self):
        self.assertEqual(nf.parse_entry("file:///a.md::text/markdown"), ("file:///a.md", "text/markdown"))
        self.assertEqual(nf.parse_entry("file:///a.md"), ("file:///a.md", None))
        # only the first delimiter splits (same as g_strsplit(..., "::", 2))
        self.assertEqual(nf.parse_entry("file:///a::b.md::text/plain"), ("file:///a", "b.md::text/plain"))

    def test_uri_to_path(self):
        self.assertEqual(nf.uri_to_path("file:///home/me/my%20notes%20%C3%A9.md"), "/home/me/my notes é.md")
        self.assertEqual(nf.uri_to_path("file://localhost/etc/hosts"), "/etc/hosts")
        self.assertIsNone(nf.uri_to_path("sftp://host/file.txt"))
        self.assertIsNone(nf.uri_to_path("smb://nas/share/file.txt"))
        self.assertIsNone(nf.uri_to_path("file://otherhost/file.txt"))


class TestGetFavorites(unittest.TestCase):
    """get_favorites with injected entries."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tables = fake_tables()
        self.md = self.mk("Notes.md")
        self.sh = self.mk("backup script.sh")
        self.png = self.mk("pic.png")
        self.a = self.mk("alpha.txt")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def mk(self, name):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write("x")
        return path

    def uri(self, path):
        from urllib.parse import quote
        return "file://" + quote(path)

    def test_filters_sorts_and_dedupes(self):
        raw = [
            self.uri(self.sh) + "::application/x-shellscript",
            self.uri(self.png) + "::image/png",
            self.uri(self.md) + "::text/markdown",
            self.uri(self.md) + "::text/markdown",                      # duplicate
            self.uri(self.tmp) + "::inode/directory",                    # a favorited folder
            self.uri(os.path.join(self.tmp, "gone.txt")) + "::text/plain",   # no longer exists
            "sftp://host/remote.txt::text/plain",                        # not local
            self.uri(self.a) + "::text/plain",
            self.uri(self.a + "x") + "::",                               # missing mime -> skipped
        ]
        result = nf.get_favorites(raw_entries=raw, tables=self.tables)
        self.assertEqual(
            result,
            [("alpha.txt", self.a), ("backup script.sh", self.sh), ("Notes.md", self.md)]
        )

    def test_empty_mime_list_keeps_everything_local(self):
        raw = [self.uri(self.png) + "::image/png", self.uri(self.md) + "::text/markdown"]
        result = nf.get_favorites(mime_types=[], raw_entries=raw, tables=self.tables)
        self.assertEqual([n for n, _ in result], ["Notes.md", "pic.png"])

    def test_custom_mime_type(self):
        raw = [self.uri(self.png) + "::image/png", self.uri(self.md) + "::text/markdown"]
        result = nf.get_favorites(mime_types=["image/*"], raw_entries=raw, tables=self.tables)
        self.assertEqual(result, [("pic.png", self.png)])

    def test_check_exists_off(self):
        raw = [self.uri(os.path.join(self.tmp, "gone.txt")) + "::text/plain"]
        result = nf.get_favorites(raw_entries=raw, tables=self.tables, check_exists=False)
        self.assertEqual(len(result), 1)


SCHEMA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<schemalist>
  <schema id="org.x.apps.favorites" path="/org/x/apps/favorites/">
    <key name="list" type="as"><default>[]</default><summary>favorites</summary></key>
  </schema>
</schemalist>
"""


@unittest.skipUnless(shutil.which("gsettings") and shutil.which("glib-compile-schemas"), "gsettings not available")
class TestRealGSettings(unittest.TestCase):
    """End to end against the real gsettings binary and real GVariant text output."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        schemas = os.path.join(self.tmp, "schemas")
        os.makedirs(schemas)
        with open(os.path.join(schemas, "org.x.apps.gschema.xml"), "w") as f:
            f.write(SCHEMA_XML)
        subprocess.check_call(["glib-compile-schemas", schemas])

        self.saved = dict(os.environ)
        os.environ["GSETTINGS_SCHEMA_DIR"] = schemas
        os.environ["GSETTINGS_BACKEND"] = "keyfile"
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.tmp, "config")
        os.makedirs(os.environ["XDG_CONFIG_HOME"])

        self.files = os.path.join(self.tmp, "files")
        os.makedirs(self.files)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.tmp)

    def mk(self, name):
        path = os.path.join(self.files, name)
        with open(path, "w") as f:
            f.write("x")
        return path

    def set_list(self, entries):
        from urllib.parse import quote
        value = "[" + ", ".join(
            "'" + ("file://" + quote(p) + "::" + m).replace("\\", "\\\\").replace("'", "\\'") + "'"
            for p, m in entries
        ) + "]"
        subprocess.check_call(["gsettings", "set", "org.x.apps.favorites", "list", value])

    def test_empty_default(self):
        self.assertEqual(nf.read_raw_entries(), [])
        self.assertEqual(nf.get_favorites(), [])

    def test_round_trip_with_awkward_names(self):
        tricky = self.mk("it's a \"test\" über 日本.md")
        plain = self.mk("plain.txt")
        image = self.mk("photo.png")
        self.set_list([
            (tricky, "text/markdown"),
            (plain, "text/plain"),
            (image, "image/png"),
        ])
        raw = nf.read_raw_entries()
        self.assertEqual(len(raw), 3)
        result = nf.get_favorites()
        self.assertEqual(sorted(p for _, p in result), sorted([tricky, plain]))

    def test_missing_schema_returns_none(self):
        os.environ["GSETTINGS_SCHEMA_DIR"] = os.path.join(self.tmp, "nowhere")
        self.assertIsNone(nf.read_raw_entries())
        self.assertIsNone(nf.get_favorites())


if __name__ == "__main__":
    unittest.main()
