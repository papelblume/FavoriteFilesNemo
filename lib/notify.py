"""
Favorite Files (Nemo) notifications.

Licensed under MIT
Copyright (c) 2012 - 2015 Isaac Muse <isaacmuse@gmail.com>
"""
import sublime

SETTINGS_FILE = "favorite_files_nemo.sublime-settings"
TITLE = "FavoriteFilesNemo"


def settings():
    """Return the plugin settings."""

    return sublime.load_settings(SETTINGS_FILE)


def notify(msg):
    """Show a non-blocking status bar message."""

    sublime.status_message("%s: %s" % (TITLE, msg))


def error(msg):
    """Show an error dialog."""

    sublime.error_message("%s:\n%s" % (TITLE, msg))
