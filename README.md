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

### Using portable binary

[**Download the latest release**](https://github.com/vzhd1701/evernote-backup/releases/latest) for your OS.

### With [Homebrew](https://brew.sh/) (Recommended for macOS)

```bash
$ brew install evernote-backup
```

### With [PIPX](https://github.com/pypa/pipx) (Recommended for Linux & Windows)

```shell
$ pipx install evernote-backup
```

### With PIP

```bash
$ pip install --user evernote-backup
```

**Python 3.8 or later required.**

### With [**Docker**](https://docs.docker.com/)

[![Docker Image Size (amd64)](<https://img.shields.io/docker/image-size/vzhd1701/evernote-backup?arch=amd64&label=image%20size%20(amd64)>)](https://hub.docker.com/r/vzhd1701/evernote-backup)
[![Docker Image Size (arm64)](<https://img.shields.io/docker/image-size/vzhd1701/evernote-backup?arch=arm64&label=image%20size%20(arm64)>)](https://hub.docker.com/r/vzhd1701/evernote-backup)

```bash
$ docker run --rm -t -v "$PWD":/tmp vzhd1701/evernote-backup:latest
```

To log in to Evernote using OAuth with Docker, you'll have to forward port 10500 for a callback:

```bash
$ docker run --rm -t -v "$PWD":/tmp -p 10500:10500 vzhd1701/evernote-backup:latest init-db
```

### From source

This project uses [poetry](https://python-poetry.org/) for dependency management and packaging. You will have to install it first. See [poetry official documentation](https://python-poetry.org/docs/) for instructions.

```shell
$ git clone https://github.com/vzhd1701/evernote-backup.git
$ cd evernote-backup/
$ poetry install
$ poetry run evernote-backup
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

If you log in to Evernote, it will prompt you to complete OAuth login using your browser.

To connect to **Yinxiang** instead of Evernote, use `--backend china` option. It will prompt you to enter your account credentials. You can provide them beforehand with `--user` and `--password` options. OAuth is not supported for **Yinxiang**.

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

**evernote-backup** keeps track of the sync state and downloads only new changes that have been made since the last run. So every sync will go pretty fast, but you'll have to wait for a bit on the first run if you have a lot of notes in your account. Syncing uses the Evernote Cloud API.

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

Exporting is performed wholly offline, and does not require access to the Evernote Cloud API to convert the notes.

That's it! So to export all your Evernote data, you will have to run three commands:

```console
$ evernote-backup init-db
$ evernote-backup sync
$ evernote-backup export output_dir/
```

After first initialization, you can schedule `evernote-backup sync` command to keep your local database always up-to-date. However, `evernote-backup export` will always re-export all notebooks to the specified output directory.

### Tasks

To sync tasks & reminders, you will need:

1. Get the official desktop app authentication token using [evertoken](https://github.com/vzhd1701/evertoken)
2. Use it with sync command like so: `evernote-backup sync --include-tasks --token "YOUR_TOKEN_HERE"`

Sorry for the extra steps, tasks and reminders are not accessible using current public API, so I had to use Evernote's new sync API which is not available for third party apps yet. I have placed a request to grant my app key access to the new API, but I have not received a response yet.

### How to refresh expired token

In case your auth token that you initialized your database with expires, you have an option to re-authorize it by running the `evernote-backup reauth` command. It has the same options as the `init-db` command.

## Getting help

If you found a bug or have a feature request, please [open a new issue](https://github.com/vzhd1701/evernote-backup/issues/new/choose).

If you have a question about the program or have difficulty using it, you are welcome to [the discussions page](https://github.com/vzhd1701/evernote-backup/discussions). You can also mail me directly, I'm always happy to help.

## Further reading

- [How to export Notebooks in new Evernote client](https://help.evernote.com/hc/en-us/articles/360053159414-Export-notebooks)
- [Backing up and restoring Evernote data (Reference article) (requires registration)](https://discussion.evernote.com/forums/topic/86152-backing-up-and-restoring-evernote-data-reference-article/?tab=comments#comment-367110)
- [Migrating Your Notes from Evernote to Obsidian](https://www.dmuth.org/migrating-from-evernote-to-obisidian/)
- https://github.com/davidedc/A-thousand-notes

## Similar projects

I've also combined a [bigger list](https://github.com/vzhd1701/evernote-backup/blob/master/SIMILAR_PROJECTS.md) where I included all adjacent projects that I could find.

### Export

Project                                                                |  Description                                                                                                      |  Language
-----------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|--------------
[ExportAllEverNote](https://github.com/dong-s/ExportAllEverNote)       |  Export notes in ENEX format driectly from your account                                                           |  Python
[evernote2](https://github.com/JackonYang/evernote2)                   |  Improved version of standard Evernote SDK. Also provides a tool for exporting notes driectly from your account   |  Python
[evernote-to-sqlite](https://github.com/dogsheep/evernote-to-sqlite)   |  Converts ENEX files into SQLite database                                                                         |  Python
[enote](https://github.com/tkjacobsen/enote)                           |  Utility that can backup Evernote notes and notebooks                                                             |  Python
[evernote-exporter](https://github.com/shawndaniel/evernote-exporter)  |  Export notes from old Evernote local database .exb format                                                        |  Python

### Export / Sync

Project                                                                |  Description                                                                                                      |  Language
-----------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|--------------
[SyncToGit](https://github.com/KostyaEsmukov/SyncToGit)                |  Syncs your notes with their resources to the git repository in HTML format                                       |  Python
[evermark](https://github.com/akuma/evermark)                          |  A command line tool for syncing markdown notes to Evernote                                                       |  JavaScript
[eversync](https://github.com/yejianye/eversync)                       |  Sync your local directories with evernote notebooks                                                              |  Python
[EverMark](https://github.com/liuwons/EverMark)                        |  A tool that can sync local markdown/text notes to Evernote                                                       |  Python
[LocalEvernote](https://github.com/lwabish/LocalEvernote)              |  Syncs local directory containing notes in Markdown format with Evernote                                          |  Python
[gnsync](https://github.com/vitaly-zdanevich/geeknote)                 |  Part of Geeknote                                                                                                 |  Python
