# evernote-backup

[![PyPI version](https://img.shields.io/pypi/v/evernote-backup?label=version)](https://pypi.python.org/pypi/evernote-backup)
[![Python Version](https://img.shields.io/pypi/pyversions/evernote-backup.svg)](https://pypi.org/project/evernote-backup/)
[![Tests Status](https://github.com/vzhd1701/evernote-backup/workflows/tests/badge.svg?branch=master&event=push)](https://github.com/vzhd1701/evernote-backup/actions?query=workflow%3Atests+branch%3Amaster+event%3Apush)
[![codecov](https://codecov.io/gh/vzhd1701/evernote-backup/branch/master/graph/badge.svg)](https://codecov.io/gh/vzhd1701/evernote-backup)

Backup your notes & notebooks from Evernote locally and export them at any time!

## Features

- Quickly sync all your notes into the SQLite database for backup.
- Export all backed up notes in `*.enex` format, as **notebooks** or **single notes**.

## Installation

```bash
$ pip install evernote-backup
```

Or, since **evernote-backup** is a standalone tool, it might be more convenient to install it using [**pipx**](https://github.com/pipxproject/pipx):

```bash
$ pipx install evernote-backup
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

If you want to connect to **Yinxiang** instead of Evernote, use `--backend china` option.

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

- `evernote3` - to access Evernote API
- `xmltodict` - to convert Evernote internal representation of notes into XML
- `click` - to create a CLI interface
