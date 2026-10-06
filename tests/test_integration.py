"""
Integration tests for the Open command, run against a stubbed Sublime API.

This exercises the real favorites.py list handling and the real Open command code; only
``sublime`` / ``sublime_plugin`` themselves are faked.  It is not a substitute for trying the
plugin inside Sublime Text.
"""
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock


class FakeSettings(object):
    """Dict backed stand-in for sublime.Settings."""

    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)


class QuickPanelItem(object):
    """Stand-in for sublime.QuickPanelItem (ST4)."""

    def __init__(self, trigger, details="", annotation="", kind=None):
        self.trigger, self.details, self.annotation = trigger, details, annotation


class FakeWindow(object):
    """Captures what the commands ask the window to do."""

    def __init__(self):
        self.panels = []
        self.opened = []

    def id(self):
        return 1

    def active_group(self):
        return 0

    def show_quick_panel(self, items, on_select, *args, **kwargs):
        self.panels.append((items, on_select))

    def open_file(self, path):
        self.opened.append(path)
        return object()

    def set_view_index(self, *args):
        pass

    def focus_view(self, view):
        pass

    def run_command(self, *args):
        pass


def install_stubs(packages_dir, settings, panel_items=True):
    sublime = types.ModuleType("sublime")
    sublime.packages_path = lambda: packages_dir
    sublime.windows = lambda: []
    sublime.load_settings = lambda name: FakeSettings(settings)
    sublime.status_message = lambda msg: None
    sublime.error_message = mock.Mock()
    sublime.set_timeout = lambda fn, ms: None
    if panel_items:
        sublime.QuickPanelItem = QuickPanelItem
    plugin = types.ModuleType("sublime_plugin")

    class WindowCommand(object):
        def __init__(self, window):
            self.window = window

    plugin.WindowCommand = WindowCommand
    plugin.ApplicationCommand = object
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin
    return sublime


def fresh_import():
    for name in [m for m in sys.modules if m.startswith("FavoriteFilesNemo.") and "tests" not in m
                 or m == "FavoriteFilesNemo"]:
        if name != "FavoriteFilesNemo.nemo_favorites":
            del sys.modules[name]
    import importlib
    return importlib.import_module("FavoriteFilesNemo.favorite_files")


class OpenCommandBase(unittest.TestCase):
    panel_items = True

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.packages = os.path.join(self.tmp, "Packages")
        os.makedirs(os.path.join(self.packages, "User"))
        self.settings = {"nemo_favorites": True, "enable_per_projects": True}
        self.sublime = install_stubs(self.packages, self.settings, self.panel_items)
        self.ff = fresh_import()
        self.ff.plugin_loaded()  # builds the real Favorites object on a temp list file

        self.own = self.mk("own.txt")
        self.shared = self.mk("shared.md")        # in both lists
        self.nemo1 = self.mk("zeta.sh")
        self.nemo2 = self.mk("Alpha.md")
        self.ff.Favs.set(self.own)
        self.ff.Favs.set(self.shared)
        self.ff.Favs.add_group("Work")
        self.ff.Favs.set(self.own, group_name="Work")
        self.ff.Favs.save(True)

        self.nemo_result = [("Alpha.md", self.nemo2), ("shared.md", self.shared), ("zeta.sh", self.nemo1)]
        patcher = mock.patch.object(self.ff.nemo_favorites, "get_favorites", side_effect=self.fake_get)
        self.get_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.nemo_return = self.nemo_result

    def fake_get(self, **kwargs):
        return self.nemo_return

    def tearDown(self):
        shutil.rmtree(self.tmp)
        for name in ("sublime", "sublime_plugin"):
            sys.modules.pop(name, None)

    def mk(self, name):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write("x")
        return path

    def run_open(self):
        window = FakeWindow()
        cmd = self.ff.FavoriteFilesNemoOpenCommand(window)
        cmd.run()
        return window, cmd

    def rows(self, items):
        out = []
        for i in items:
            if isinstance(i, QuickPanelItem):
                out.append((i.trigger, i.details, i.annotation))
            else:
                out.append(tuple(i))
        return out


class TestOpenCommand(OpenCommandBase):

    def test_panel_merges_sources(self):
        window, _ = self.run_open()
        items, _cb = window.panels[0]
        self.assertEqual(self.rows(items), [
            ("own.txt", self.own, ""),
            ("shared.md", self.shared, ""),               # Sublime entry wins, no duplicate
            ("Alpha.md", self.nemo2, "Nemo"),
            ("zeta.sh", self.nemo1, "Nemo"),
            ("Group: Work", "1 files", ""),
        ])

    def test_selecting_nemo_entry_opens_it(self):
        window, cmd = self.run_open()
        cmd.open_file(2)
        self.assertEqual(window.opened, [self.nemo2])

    def test_selecting_own_entry_still_works(self):
        window, cmd = self.run_open()
        cmd.open_file(0)
        self.assertEqual(window.opened, [self.own])

    def test_group_descent_has_no_nemo_entries(self):
        window, cmd = self.run_open()
        cmd.open_file(4)  # "Group: Work"
        items, _ = window.panels[1]
        self.assertEqual(self.rows(items), [("Open Group", "", ""), ("own.txt", self.own, "")])

    def test_setting_off_hides_nemo(self):
        self.settings["nemo_favorites"] = False
        window, _ = self.run_open()
        names = [r[0] for r in self.rows(window.panels[0][0])]
        self.assertEqual(names, ["own.txt", "shared.md", "Group: Work"])
        self.get_mock.assert_not_called()

    def test_nemo_unavailable_still_shows_own(self):
        self.nemo_return = None
        window, _ = self.run_open()
        names = [r[0] for r in self.rows(window.panels[0][0])]
        self.assertEqual(names, ["own.txt", "shared.md", "Group: Work"])

    def test_nemo_exception_is_contained(self):
        self.get_mock.side_effect = RuntimeError("boom")
        window, _ = self.run_open()
        names = [r[0] for r in self.rows(window.panels[0][0])]
        self.assertEqual(names, ["own.txt", "shared.md", "Group: Work"])

    def test_only_nemo_favorites_no_own(self):
        self.ff.Favs.obj.files = {"version": 2, "files": [], "groups": {}}
        window, _ = self.run_open()
        names = [r[0] for r in self.rows(window.panels[0][0])]
        self.assertEqual(names, ["Alpha.md", "shared.md", "zeta.sh"])

    def test_nothing_anywhere_shows_message(self):
        self.ff.Favs.obj.files = {"version": 2, "files": [], "groups": {}}
        self.nemo_return = []
        window, _ = self.run_open()
        self.assertEqual(window.panels, [])
        self.sublime.error_message.assert_called_once()

    def test_mime_setting_is_passed_through(self):
        self.settings["nemo_favorites_mime_types"] = ["text/markdown"]
        self.run_open()
        self.get_mock.assert_called_with(mime_types=["text/markdown"])

    def test_default_mime_setting_is_text_plain(self):
        self.run_open()
        self.get_mock.assert_called_with(mime_types=["text/plain"])


class TestOpenCommandSt3Fallback(OpenCommandBase):
    panel_items = False

    def test_plain_list_rows(self):
        window, _ = self.run_open()
        items, _ = window.panels[0]
        self.assertTrue(all(isinstance(i, list) for i in items))
        self.assertEqual(items[2], ["Alpha.md  [Nemo]", self.nemo2])
        self.assertEqual(items[0], ["own.txt", self.own])


if __name__ == "__main__":
    unittest.main()
