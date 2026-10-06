# FavoriteFilesNemo

A Sublime Text 4 package for Linux Mint (Cinnamon) that works like
[FavoriteFiles](https://github.com/facelessuser/FavoriteFiles) and **also lists the files you have favorited in
Nemo**, the same way xed does.

This is a fork of [facelessuser/FavoriteFiles](https://github.com/facelessuser/FavoriteFiles) by Isaac Muse. Adding,
removing and opening favorites, groups, aliases and per-project lists all behave as they do upstream; the Nemo
integration is what this fork adds.

## How Nemo favorites are found

Choosing *Add to Favorites* on a file in Nemo stores it in GSettings (`org.x.apps.favorites`, key `list`), as
entries like `file:///home/me/notes.md::text/markdown`. xed builds its *File → Favorites* menu from that list and
keeps only entries whose MIME type is a kind of `text/plain`. This package reads the same list with the same rule, so
it shows the same files xed shows: plain text, Markdown, shell, Python and C sources, JSON, YAML and so on.

Skipped entries: folders, images, PDFs and other non-text files, remote favorites (`sftp://`, `smb://`), and files
that no longer exist.

In **Open File(s)**, your Sublime favorites come first, then the Nemo ones tagged `Nemo`. The list is read each time
the picker opens, so a file favorited in Nemo appears immediately. A file in both lists is shown once, as your Sublime
favorite. Nemo favorites are read-only here: add and remove them in Nemo. *Remove File(s)* and *Edit File Alias* only
deal with Sublime favorites.

## Install

Clone the repository into your Sublime Text `Packages` folder. The folder must be named `FavoriteFilesNemo`:

```
git clone https://github.com/papelblume/FavoriteFilesNemo.git ~/.config/sublime-text/Packages/FavoriteFilesNemo
```

Then remove the original `FavoriteFiles` package if you have it installed, so the command palette doesn't show two
sets of entries. Your existing favorites carry over because this package uses the same list file
(`Packages/User/favorite_files_list.json`). To update later, run `git pull` in that folder.

Commands are in the command palette as **Favorite Files (Nemo): …** and under *File → Favorite Files (Nemo)*.

## Settings

*Preferences → Package Settings → FavoriteFilesNemo → Settings*

| Setting | Default | Meaning |
|---|---|---|
| `nemo_favorites` | `true` | Include Nemo favorites in *Open File(s)*. |
| `nemo_favorites_mime_types` | `["text/plain"]` | Keep Nemo favorites that are a kind of one of these MIME types. `[]` shows every favorited local file; wildcards such as `"image/*"` work. |
| `enable_per_projects` | `true` | Same as upstream. |
| `always_ask_alias` | `false` | Same as upstream. |

Settings live in `favorite_files_nemo.sublime-settings`, separate from the upstream package's
`favorite_files.sublime-settings`, so copy across any overrides you had.

## Requirements and limits

- Sublime Text 4, build 4107 or newer (Python 3.8 plugin host).
- `gsettings` on the `PATH` (standard on Linux Mint) and libxapp installed (it is wherever Nemo has Favorites).
  `dconf read` is used as a fallback. If neither works, one line is logged to the Sublime console and the package
  behaves like plain FavoriteFiles.
- A normal desktop install of Sublime Text. A Flatpak or Snap build can't see the host's GSettings.

## Differences from upstream

- **Added:** Nemo/XApp favorites (`nemo_favorites.py`), the `Nemo` tag in the picker, and the two settings above.
- **Renamed:** commands are `favorite_files_nemo_*`, the menu and palette entries say "(Nemo)", and imports are
  relative so the folder name doesn't matter to the code.
- **Removed:** the SubNotify integration (messages now use the status bar and error dialogs), the *Support Info*,
  *Changelog* and *Documentation* menu entries together with the `mdpopups` dependency, the Sublime Text 3 upgrade
  notice, the MkDocs documentation site, and upstream's CI and funding configuration.

To pull in upstream changes:

```
git remote add upstream https://github.com/facelessuser/FavoriteFiles.git
git fetch upstream
git merge upstream/master
```

Expect conflicts in `favorite_files.py`, `favorites.py` and `lib/notify.py`, which this fork changed.

## Tests

The tests run outside Sublime, with a stubbed Sublime API for the command tests. They cover the MIME rule against the
real shared-mime-info data, reading real `gsettings` output (including awkward filenames), and the merged Open
picker. Run them from the folder that contains the package:

```
cd ~/.config/sublime-text/Packages
python3 -m unittest FavoriteFilesNemo.tests.test_nemo_favorites FavoriteFilesNemo.tests.test_integration
```

They do not replace trying the package inside Sublime Text.

## License

MIT. Original work copyright (c) Isaac Muse; see [LICENSE.md](LICENSE.md). The Nemo additions are released under the
same license.

---

Written with AI assistance (Claude).
