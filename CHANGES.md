# FavoriteFiles

## Unreleased (FavoriteFilesNemo fork)

-   **NEW**: List files favorited in Nemo (read from GSettings `org.x.apps.favorites`), filtered by MIME type
    the same way xed does. Shown in *Open File(s)* with a `Nemo` tag.
-   **NEW**: `nemo_favorites` and `nemo_favorites_mime_types` settings.
-   **NEW**: Tests for the MIME rule, real `gsettings` parsing and the Open command.
-   **NEW**: Commands renamed to `favorite_files_nemo_*`; settings moved to `favorite_files_nemo.sublime-settings`.
-   **REMOVED**: SubNotify support, support/changelog/documentation commands, `mdpopups` dependency,
    Sublime Text 3 upgrade notice and the MkDocs site.

## 1.7.0

-   **NEW**: Changes to support Python 3.13 on ST 4201+.

## 1.6.1

-   **FIX**: Ensure `typing` dependency for Python 3.3.

## 1.6.0

-   **NEW**: Add alias support.
-   **NEW**: Commands were renamed internally to be prefixed with `FavoriteFiles`.
-   **FIX**: General internal bugs.

## 1.5.0

-   **NEW**: Support commands.
-   **FIX**: Fix error message bug.
