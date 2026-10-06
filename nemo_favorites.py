"""
Nemo (XApp) favorites support for FavoriteFilesNemo.

Nemo's "Favorites" feature is implemented by libxapp.  The list lives in GSettings:

    schema: org.x.apps.favorites
    key:    list   (as)  -- entries look like  "file:///home/me/notes.md::text/markdown"

xed builds its File -> Favorites menu from that list, keeping only entries whose cached
MIME type is a kind of "text/plain" (g_content_type_is_mime_type).  This module does the
same thing so Sublime Text can show exactly the files xed would.

This module deliberately does not import ``sublime`` so it can be tested on its own.

Licensed under MIT.
"""
import ast
import os
import subprocess
from urllib.parse import unquote, urlparse

SCHEMA = "org.x.apps.favorites"
KEY = "list"
DELIMITER = "::"

# Same filter xed uses.  Anything that shared-mime-info declares as a kind of
# text/plain (markdown, shell scripts, python, json, yaml, ...) matches.
DEFAULT_MIME_TYPES = ["text/plain"]

_TIMEOUT = 3  # seconds to wait for gsettings/dconf

_tables = None  # lazily loaded (aliases, parents)


# --------------------------------------------------------------------------------------
# MIME hierarchy (mirrors glib's xdgmime _xdg_mime_mime_type_subclass)
# --------------------------------------------------------------------------------------

def _data_dirs():
    """Return the XDG data directories, most specific first."""

    home = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [home] + [d for d in system.split(":") if d]


def load_mime_tables(data_dirs=None):
    """
    Load shared-mime-info ``aliases`` and ``subclasses`` files.

    Returns ``(aliases, parents)`` where ``aliases`` maps alias -> canonical type and
    ``parents`` maps type -> list of direct parent types.
    """

    aliases = {}
    parents = {}

    for directory in (data_dirs if data_dirs is not None else _data_dirs()):
        for name, handler in (("aliases", aliases), ("subclasses", parents)):
            path = os.path.join(directory, "mime", name)
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    lines = handle.read().splitlines()
            except OSError:
                continue
            for line in lines:
                parts = line.split()
                if len(parts) != 2 or line.lstrip().startswith("#"):
                    continue
                if name == "aliases":
                    aliases[parts[0]] = parts[1]
                else:
                    handler.setdefault(parts[0], [])
                    if parts[1] not in handler[parts[0]]:
                        handler[parts[0]].append(parts[1])
    return aliases, parents


def _get_tables():
    """Return cached MIME tables."""

    global _tables
    if _tables is None:
        _tables = load_mime_tables()
    return _tables


def reset_cache():
    """Drop cached MIME tables (they are re-read on next use)."""

    global _tables
    _tables = None


def is_mime_type(mime, base, tables=None):
    """
    Return True if ``mime`` is ``base`` or a kind of ``base``.

    Mirrors glib's ``g_content_type_is_mime_type`` on Linux, including its special cases:
    every ``text/*`` type is a kind of ``text/plain``, and everything except ``inode/*``
    is a kind of ``application/octet-stream``.
    """

    aliases, parents = tables if tables is not None else _get_tables()

    def unalias(value):
        return aliases.get(value, value)

    base = unalias(base)
    seen = set()

    def walk(current):
        current = unalias(current)
        if current == base:
            return True
        if base.endswith("/*") and current.split("/")[0] == base.split("/")[0]:
            return True
        if base == "text/plain" and current.startswith("text/"):
            return True
        if base == "application/octet-stream" and not current.startswith("inode/"):
            return True
        for parent in parents.get(current, ()):
            if parent in seen:
                continue
            seen.add(parent)
            if walk(parent):
                return True
        return False

    return walk(mime)


# --------------------------------------------------------------------------------------
# Reading the favorites list
# --------------------------------------------------------------------------------------

def _run(cmd):
    """Run a command and return its stdout (decoded) or None on any failure."""

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except OSError:
        return None

    try:
        out, _ = proc.communicate(timeout=_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return None

    if proc.returncode != 0:
        return None
    return out.decode("utf-8", "replace")


def parse_string_array(text):
    """
    Parse the GVariant text form of an ``as`` value, e.g. ``['a', 'b']`` or ``@as []``.

    Returns a list of strings, or None if the text isn't a string array.
    """

    text = text.strip()
    if text.startswith("@as"):
        text = text[3:].strip()
    if not text:
        # dconf prints nothing when a key is unset (i.e. still the empty default)
        return []
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def read_raw_entries():
    """
    Return the raw ``uri::mimetype`` strings from GSettings.

    Returns None when the list cannot be read at all (no gsettings/dconf, schema missing).
    """

    for cmd in (
        ["gsettings", "get", SCHEMA, KEY],
        ["dconf", "read", "/org/x/apps/favorites/" + KEY]
    ):
        out = _run(cmd)
        if out is not None:
            entries = parse_string_array(out)
            if entries is not None:
                return entries
    return None


def parse_entry(entry):
    """Split a stored entry into ``(uri, mimetype)``; mimetype may be None."""

    parts = entry.split(DELIMITER, 1)
    return parts[0], (parts[1] if len(parts) > 1 and parts[1] else None)


def uri_to_path(uri):
    """Convert a local ``file://`` URI to a filesystem path, or None for anything else."""

    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    path = unquote(parsed.path)
    return path or None


def get_favorites(mime_types=None, check_exists=True, raw_entries=None, tables=None):
    """
    Return Nemo favorites as a list of ``(name, path)`` tuples, sorted by name.

    :param mime_types: keep entries that are a kind of any of these types
        (default ``["text/plain"]``, the same as xed).  An empty list keeps everything.
    :param check_exists: drop entries whose file is gone.
    :param raw_entries: override the GSettings read (used by tests).
    :param tables: override the MIME tables (used by tests).

    Returns None if the favorites list could not be read.
    """

    if mime_types is None:
        mime_types = DEFAULT_MIME_TYPES

    if raw_entries is None:
        raw_entries = read_raw_entries()
        if raw_entries is None:
            return None

    results = []
    seen = set()

    for entry in raw_entries:
        uri, mime = parse_entry(entry)
        path = uri_to_path(uri)
        if path is None or path in seen:
            continue
        if mime_types:
            if mime is None or not any(is_mime_type(mime, m, tables) for m in mime_types):
                continue
        if check_exists and not os.path.isfile(path):
            continue
        seen.add(path)
        results.append((os.path.basename(path), path))

    results.sort(key=lambda item: (item[0].lower(), item[1]))
    return results
