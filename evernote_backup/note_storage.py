# -*- coding: utf-8 -*-

import lzma
import os
import pickle
import sqlite3
from typing import Iterator, List, Tuple, Union

from evernote.edam.type.ttypes import Note, Notebook

DB_SCHEMA = """create table notebooks(
                        guid TEXT PRIMARY KEY,
                        name TEXT,
                        stack TEXT
                    );
                    create table notes(
                        guid TEXT PRIMARY KEY,
                        title TEXT,
                        notebook_guid TEXT,
                        is_active BOOLEAN,
                        raw_note BLOB
                    );
                    create table config(
                        name TEXT PRIMARY KEY,
                        value TEXT
                    );
                    CREATE INDEX idx_notes ON notes(notebook_guid, is_active);"""


def initialize_db(filename: str, force: bool = False) -> None:
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
    def __init__(self, database: Union[str, sqlite3.Connection]) -> None:
        if isinstance(database, sqlite3.Connection):
            self.db = database
        else:
            if not os.path.exists(database):
                raise FileNotFoundError("Database file does not exist.")

            self.db = sqlite3.connect(database)
            self.db.row_factory = sqlite3.Row

    @property
    def config(self) -> "ConfigStorage":
        return ConfigStorage(self.db)

    @property
    def notes(self) -> "NoteStorage":
        return NoteStorage(self.db)

    @property
    def notebooks(self) -> "NoteBookStorage":
        return NoteBookStorage(self.db)


class NoteBookStorage(SqliteStorage):
    def add_notebooks(self, notebooks: List[Notebook]) -> None:
        with self.db as con:
            con.executemany(
                "replace into notebooks(guid, name, stack)" " values (?, ?, ?)",
                ((nb.guid, nb.name, nb.stack) for nb in notebooks),
            )

    def iter_notebooks(self) -> Iterator[Notebook]:
        with self.db as con:
            cur = con.execute(
                "select guid, name, stack from notebooks",
            )

            yield from (
                Notebook(
                    guid=row["guid"],
                    name=row["name"],
                    stack=row["stack"],
                )
                for row in cur
            )

    def get_notebook_notes_count(self, notebook_guid: str) -> int:
        with self.db as con:
            cur = con.execute(
                "select COUNT(guid) from notes"
                " where notebook_guid=? and is_active=1",
                (notebook_guid,),
            )

            return int(cur.fetchone()[0])

    def expunge_notebooks(self, guids: List[str]) -> None:
        with self.db as con:
            con.executemany("delete from notebooks where guid=?", ((g,) for g in guids))


class NoteStorage(SqliteStorage):
    def add_notes_for_sync(self, notes: List[Note]) -> None:
        with self.db as con:
            con.executemany(
                "replace into notes(guid, title) values (?, ?)",
                ((n.guid, n.title) for n in notes),
            )

    def add_note(self, note: Note) -> None:
        note_deflated = lzma.compress(pickle.dumps(note))

        with self.db as con:
            con.execute(
                "replace into notes(guid, title, notebook_guid, is_active, raw_note)"
                " values (?, ?, ?, ?, ?)",
                (
                    note.guid,
                    note.title,
                    note.notebookGuid,
                    note.active,
                    note_deflated,
                ),
            )

    def iter_notes(self, notebook_guid: str) -> Iterator[Note]:
        with self.db as con:
            cur = con.execute(
                "select raw_note"
                " from notes where notebook_guid=? and is_active=1"
                " order by title",
                (notebook_guid,),
            )

            yield from (pickle.loads(lzma.decompress(row["raw_note"])) for row in cur)

    def iter_notes_trash(self) -> Iterator[Note]:
        with self.db as con:
            cur = con.execute(
                "select raw_note" " from notes where is_active=0" " order by title",
            )

            yield from (pickle.loads(lzma.decompress(row["raw_note"])) for row in cur)

    def get_notes_for_sync(self) -> Tuple[Tuple[str, str], ...]:
        with self.db as con:
            cur = con.execute("select guid, title from notes where raw_note is NULL")

            notes = ((row["guid"], row["title"]) for row in cur.fetchall())

            return tuple(notes)

    def expunge_notes(self, guids: str) -> None:
        with self.db as con:
            con.executemany("delete from notes where guid=?", ((g,) for g in guids))

    def get_notes_count(self, is_active: bool = True):
        with self.db as con:
            cur = con.execute(
                "select COUNT(guid) from notes where is_active=?", (is_active,)
            )

            return int(cur.fetchone()[0])


class ConfigStorage(SqliteStorage):
    def set_config_value(self, name: str, config_value: str) -> None:
        with self.db as con:
            con.execute(
                "replace into config(name, value) values (?, ?)",
                (name, config_value),
            )

    def get_config_value(self, name: str) -> str:
        with self.db as con:
            cur = con.execute("select value from config where name=?", (name,))
            res = cur.fetchone()

            if not res:
                raise KeyError(f"Config ID {name} not found in database!")

            return res[0]
