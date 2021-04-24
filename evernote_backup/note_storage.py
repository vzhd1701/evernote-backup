# -*- coding: utf-8 -*-

import lzma
import os
import sqlite3
from dataclasses import dataclass

from evernote_backup.note_formatter import NoteFormatter

DB_SCHEMA = """create table notebooks(
                        guid TEXT PRIMARY KEY,
                        name TEXT,
                        stack TEXT
                    );
                    create table notes(
                        guid TEXT PRIMARY KEY,
                        title TEXT,
                        body BLOB,
                        notebook_guid TEXT,
                        is_active BOOLEAN
                    );
                    create table config(
                        name TEXT PRIMARY KEY,
                        value TEXT
                    );
                    CREATE INDEX idx_notes ON notes(notebook_guid, is_active);"""


@dataclass
class Note(object):
    guid: str
    title: str
    body: str
    notebook_guid: str
    is_active: bool


@dataclass
class NoteBook(object):
    guid: str
    name: str
    stack: str


def initialize_db(filename, force=False):
    if os.path.exists(filename):
        if force:
            if os.path.exists(filename) and force:
                os.remove(filename)
        else:
            raise FileExistsError

    db = sqlite3.connect(filename)

    with db as con:
        con.executescript(DB_SCHEMA)

    db.close()


class SqliteStorage(object):
    def __init__(self, database):
        if isinstance(database, sqlite3.Connection):
            self.db = database
        else:
            if not os.path.exists(database):
                raise FileNotFoundError("Database file does not exist.")

            self.db = sqlite3.connect(database)
            self.db.row_factory = sqlite3.Row

    @property
    def config(self):
        return ConfigStorage(self.db)

    @property
    def notes(self):
        return NoteStorage(self.db)

    @property
    def notebooks(self):
        return NoteBookStorage(self.db)


class NoteBookStorage(SqliteStorage):
    def add_notebooks(self, notebooks):
        with self.db as con:
            con.executemany(
                "replace into notebooks(guid, name, stack)" " values (?, ?, ?)",
                ((nb.guid, nb.name, nb.stack) for nb in notebooks),
            )

    def iter_notebooks(self):
        with self.db as con:
            cur = con.execute(
                "select guid, name, stack from notebooks",
            )

            yield from (
                NoteBook(
                    guid=row["guid"],
                    name=row["name"],
                    stack=row["stack"],
                )
                for row in cur
            )

    def get_notebook_notes_count(self, notebook_guid):
        with self.db as con:
            cur = con.execute(
                "select COUNT(guid) from notes"
                " where notebook_guid=? and is_active=1",
                (notebook_guid,),
            )

            return int(cur.fetchone()[0])

    def expunge_notebooks(self, guids):
        with self.db as con:
            con.executemany("delete from notebooks where guid=?", ((g,) for g in guids))


class NoteStorage(SqliteStorage):
    def add_notes_for_sync(self, notes):
        with self.db as con:
            con.executemany(
                "replace into notes(guid, title) values (?, ?)",
                ((n.guid, n.title) for n in notes),
            )

    def add_note(self, note: Note):
        note_formatter = NoteFormatter()
        note_body = note_formatter.format_note(note)
        note_body_deflated = lzma.compress(note_body.encode())

        with self.db as con:
            con.execute(
                "replace into notes(guid, title, body, notebook_guid, is_active)"
                " values (?, ?, ?, ?, ?)",
                (
                    note.guid,
                    note.title,
                    note_body_deflated,
                    note.notebookGuid,
                    note.active,
                ),
            )

    def iter_notes(self, notebook_guid):
        with self.db as con:
            cur = con.execute(
                "select guid, title, body, notebook_guid, is_active"
                " from notes where notebook_guid=? and is_active=1",
                (notebook_guid,),
            )

            for row in cur:
                body = lzma.decompress(row["body"]).decode()

                yield Note(
                    guid=row["guid"],
                    title=row["title"],
                    body=body,
                    notebook_guid=row["notebook_guid"],
                    is_active=row["is_active"],
                )

    def iter_notes_trash(self):
        with self.db as con:
            cur = con.execute(
                "select guid, title, body, notebook_guid, is_active"
                " from notes where is_active=0"
            )

            for row in cur:
                body = lzma.decompress(row["body"]).decode()

                yield Note(
                    guid=row["guid"],
                    title=row["title"],
                    body=body,
                    notebook_guid=row["notebook_guid"],
                    is_active=row["is_active"],
                )

    def get_notes_for_sync(self):
        with self.db as con:
            cur = con.execute("select guid, title from notes where body is NULL")

            notes = ((row["guid"], row["title"]) for row in cur.fetchall())

            return tuple(notes)

    def expunge_notes(self, guids):
        with self.db as con:
            con.executemany("delete from notes where guid=?", ((g,) for g in guids))

    def get_notes_count(self, is_active=True):
        with self.db as con:
            cur = con.execute(
                "select COUNT(guid) from notes where is_active=?", (is_active,)
            )

            return int(cur.fetchone()[0])


class ConfigStorage(SqliteStorage):
    def set_config_value(self, name, config_value):
        with self.db as con:
            con.execute(
                "replace into config(name, value) values (?, ?)",
                (name, config_value),
            )

    def get_config_value(self, name):
        with self.db as con:
            cur = con.execute("select value from config where name=?", (name,))
            res = cur.fetchone()

            if not res:
                raise KeyError(f"Config ID {name} not found in database!")

            return res[0]
