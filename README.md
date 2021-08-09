# evernote-backup

[![PyPI version](https://img.shields.io/pypi/v/evernote-backup?label=version)](https://pypi.python.org/pypi/evernote-backup)
[![Python Version](https://img.shields.io/pypi/pyversions/evernote-backup.svg)](https://pypi.org/project/evernote-backup/)
[![tests](https://github.com/vzhd1701/evernote-backup/actions/workflows/test.yml/badge.svg)](https://github.com/vzhd1701/evernote-backup/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/vzhd1701/evernote-backup/branch/master/graph/badge.svg)](https://codecov.io/gh/vzhd1701/evernote-backup)

Backup your notes & notebooks from Evernote locally and export them at any time!

## Features

- Quickly sync all your notes into the SQLite database for backup.
- Export all backed up notes in `*.enex` format, as **notebooks** or **single notes**.
- Support for both [Evernote](https://evernote.com/) and [Yinxiang (印象笔记)](https://yinxiang.com/).

## Installation

[**Download the latest release**](https://github.com/vzhd1701/evernote-backup/releases/latest) for your OS.

### With PIP

```bash
$ pip install evernote-backup
```

Or, since **evernote-backup** is a standalone tool, it might be more convenient to install it using [**pipx**](https://github.com/pipxproject/pipx):

```bash
$ pipx install evernote-backup
```

### With Docker

```bash
$ docker run --rm -t -v "$PWD":/tmp ghcr.io/vzhd1701/evernote-backup:latest
```

To log in to Evernote using OAuth with Docker, you'll have to forward port 10500 for a callback:

```bash
$ docker run --rm -t -v "$PWD":/tmp -p 10500:10500 ghcr.io/vzhd1701/evernote-backup:latest init-db --oauth
```

## Usage

### Step 1. Database initialization

To start you need to initialize your database.

```console
$ evernote-backup init-db
Username or Email: user@example.com
Password:
Logging in to Evernote...
Enter one-time code: 120917
Authorizing auth token, evernote backend...
Successfully authenticated as user!
Current login will expire at 2022-03-10 10:22:00.
Initializing database en_backup.db...
Reading database en_backup.db...
Successfully initialized database for user!
```

By default, it will prompt you to enter your account credentials. You can provide them beforehand with `--user` and `--password` options.

If you log in to Evernote with Google or Apple accounts, you must use the `--oauth` option.

To connect to **Yinxiang** instead of Evernote, use `--backend china` option. Unfortunately, OAuth is not supported for **Yinxiang** yet.

### Step 2. Downloading Evernote data

Then you will be able to sync your account data.

```console
$ evernote-backup sync
Reading database en_backup.db...
Authorizing auth token, evernote backend...
Successfully authenticated as user!
Current login will expire at 2022-03-10 10:22:00.
Syncing latest changes...
  [####################################]  6763/6763
566 notes to download...
  [####################################]  566/566
Updated or added notebooks: 23
Updated or added notes: 566
Expunged notebooks: 0
Expunged notes: 0
Synchronization completed!
```

You can interrupt this process at any point. It will continue from where it's left off when you will rerun `evernote-backup sync`.

**evernote-backup** keeps track of the sync state and downloads only new changes that have been made since the last run. So every sync will go pretty fast, but you'll have to wait for a bit on the first run if you have a lot of notes in your account.

### Step 3. Exporting `*.enex` files

Finally, you can export your data into specified **output directory**

```console
$ evernote-backup export output_dir/
Reading database en_backup.db...
Exporting notes...
  [####################################]  23/23
All notes have been exported!
```

By default, **evernote-backup** will export notes by packing them into notebooks, one `*.enex` file each. If you want to extract notes as **separate files**, use the `--single-notes` flag.

To also include **trashed** notes in export, use the `--include-trash` flag.

That's it! So to export all your Evernote data, you will have to run three commands:

```console
$ evernote-backup init-db
$ evernote-backup sync
$ evernote-backup export output_dir/
```

After first initialization, you can schedule `evernote-backup sync` command to keep your local database always up-to-date.

### How to refresh expired token

In case your auth token that you initialized your database with expires, you have an option to re-authorize it by running the `evernote-backup reauth` command. It has the same options as the `init-db` command.

## Dependencies

- [evernote3](https://github.com/evernote/evernote-sdk-python3) - to access Evernote API
- [oauth2](https://github.com/joestump/python-oauth2) - to perform OAuth authentication
- [xmltodict](https://github.com/martinblech/xmltodict) - to convert Evernote internal representation of notes into XML
- [click](https://github.com/pallets/click) - to create a CLI interface
- [click-option-group](https://github.com/click-contrib/click-option-group) - to add mutually exclusive options in сlick

## Alternative tools

**evernote-backup** is basically a clone of Evernote's original **ENScript** but simplified and stripped of its other functions. If you prefer to export your notes using Evernote's original tool, then you will need to take hold of [Evernote's legacy client](https://help.evernote.com/hc/en-us/articles/360052560314-Install-an-older-version-of-Evernote) and run the following commands:

```console
ENScript.exe syncDatabase /d backup.ebx /u your@email.com /p your_password
ENScript.exe exportDatabase /d backup.ebx /f output_dir
```

### Further reading

- [How to export Notebooks in new Evernote client](https://help.evernote.com/hc/en-us/articles/360053159414-Export-notebooks)
- [Backing up and restoring Evernote data (Reference article) (requires registration)](https://discussion.evernote.com/forums/topic/86152-backing-up-and-restoring-evernote-data-reference-article/?tab=comments#comment-367110)
- [Migrating Your Notes from Evernote to Obsidian](https://www.dmuth.org/migrating-from-evernote-to-obisidian/)
- https://github.com/davidedc/A-thousand-notes

## Similar projects

I've also combined a [bigger list](https://github.com/vzhd1701/evernote-backup/blob/master/SIMILAR_PROJECTS.md) where I included all adjacent projects that I could find.

### Export

Project                                                                |  Description                                                                                                      |  Language    |  Stars  |  Last commit
-----------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|--------------|---------|-------------
[ExportAllEverNote](https://github.com/dong-s/ExportAllEverNote)       |  Export notes in ENEX format driectly from your account                                                           |  Python      |  13     |  2020
[evernote2](https://github.com/JackonYang/evernote2)                   |  Improved version of standard Evernote SDK. Also provides a tool for exporting notes driectly from your account  |  Python      |  1      |  2020
[evernote-to-sqlite](https://github.com/dogsheep/evernote-to-sqlite)   |  Converts ENEX files into SQLite database                                                                         |  Python      |  20     |  2021
[enote](https://github.com/tkjacobsen/enote)                           |  Utility that can backup Evernote notes and notebooks                                                             |  Python      |  12     |  2017
[evernote-exporter](https://github.com/shawndaniel/evernote-exporter)  |  Export notes from old Evernote local database .exb format                                                        |  Python      |  28     |  2016

### Export / Sync

Project                                                                |  Description                                                                                                      |  Language    |  Stars  |  Last commit
-----------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|--------------|---------|-------------
[SyncToGit](https://github.com/KostyaEsmukov/SyncToGit)                |  Syncs your notes with their resources to the git repository in HTML format                                       |  Python      |  3      |  2020
[evermark](https://github.com/akuma/evermark)                          |  A command line tool for syncing markdown notes to Evernote                                                       |  JavaScript  |  72     |  2018
[eversync](https://github.com/yejianye/eversync)                       |  Sync your local directories with evernote notebooks                                                              |  Python      |  44     |  2017
[EverMark](https://github.com/liuwons/EverMark)                        |  A tool that can sync local markdown/text notes to Evernote                                                       |  Python      |  50     |  2016
[LocalEvernote](https://github.com/lwabish/LocalEvernote)              |  Syncs local directory containing notes in Markdown format with Evernote                                          |  Python      |  0      |  2021
