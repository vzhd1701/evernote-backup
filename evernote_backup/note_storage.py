# -*- coding: utf-8 -*-

import logging
import lzma
import os
import pickle
import sqlite3
from typing import Iterable, Iterator, NamedTuple, Optional, Tuple, Union

from evernote.edam.type.ttypes import LinkedNotebook, Note, Notebook

from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.log_util import log_format_note, log_format_notebook

logger = logging.getLogger(__name__)


class NoteForSync(NamedTuple):
    guid: str
    title: str
    linked_notebook_guid: Optional[str]


DB_SCHEMA = """CREATE TABLE IF NOT EXISTS notebooks(
                        guid TEXT PRIMARY KEY,
                        name TEXT,
                        stack TEXT
                    );
                    CREATE TABLE IF NOT EXISTS notebooks_linked(
                        guid TEXT PRIMARY KEY,
                        notebook_guid TEXT,
                        usn INT DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS notes(
                        guid TEXT PRIMARY KEY,
                        title TEXT,
                        notebook_guid TEXT,
                        is_active BOOLEAN,
                        raw_note BLOB
                    );
                    CREATE TABLE IF NOT EXISTS config(
                        name TEXT PRIMARY KEY,
                        value TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_notes
                     ON notes(notebook_guid, is_active);
                    CREATE INDEX IF NOT EXISTS idx_notes_title
                     ON notes(title COLLATE NOCASE);
                    CREATE INDEX IF NOT EXISTS idx_notebooks_linked
                     ON notebooks_linked(guid, notebook_guid);
"""


class DatabaseResyncRequiredError(Exception):
    """Raise when database update requires resync"""


def initialize_db(filename: str) -> None:
    if os.path.exists(filename):
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

    def check_version(self) -> None:
        try:
            db_version = int(self.config.get_config_value("DB_VERSION"))
        except KeyError:
            db_version = 0

        if db_version != CURRENT_DB_VERSION:
            self.upgrade_db(db_version)

    def upgrade_db(self, db_version: int) -> None:
        need_resync = False

        if db_version == 0:
            need_resync = True
            with self.db as con1:
                con1.execute("DROP TABLE notebooks;")
                con1.execute("DROP TABLE notes;")

                con1.executescript(DB_SCHEMA)

        if db_version < 3:
            with self.db as con2:
                con2.execute(
                    "CREATE INDEX IF NOT EXISTS idx_notes_title"
                    " ON notes(title COLLATE NOCASE);"
                )

        if db_version < 4:
            with self.db as con3:
                con3.execute(
                    "CREATE TABLE IF NOT EXISTS notebooks_linked("
                    " guid TEXT PRIMARY KEY,"
                    " notebook_guid TEXT,"
                    " usn INT DEFAULT 0"
                    " );"
                )
                con3.execute(
                    "CREATE INDEX IF NOT EXISTS idx_notebooks_linked"
                    " ON notebooks_linked(guid, notebook_guid);"
                )

        self.config.set_config_value("DB_VERSION", str(CURRENT_DB_VERSION))

        if need_resync:
            self.config.set_config_value("USN", "0")
            raise DatabaseResyncRequiredError


class NoteBookStorage(SqliteStorage):  # noqa: WPS214
    def add_notebooks(self, notebooks: Iterable[Notebook]) -> None:
        if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
            for nb in notebooks:
                nb_info = log_format_notebook(nb)
                logger.debug(f"Adding/updating notebook {nb_info}")

        with self.db as con:
            con.executemany(
                "replace into notebooks(guid, name, stack) values (?, ?, ?)",
                ((nb.guid, nb.name, nb.stack) for nb in notebooks),  # noqa: WPS441
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

    def expunge_notebooks(self, guids: Iterable[str]) -> None:
        with self.db as con:
            con.executemany("delete from notebooks where guid=?", ((g,) for g in guids))

    def add_linked_notebook(
        self, l_notebook: LinkedNotebook, notebook: Notebook
    ) -> None:
        if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
            logger.debug(
                f"Adding/updating linked notebook {l_notebook.shareName}"
                " [{l_notebook.guid}] -> [{notebook.guid}]"
            )

        with self.db as con:
            con.execute(
                "replace into notebooks_linked(guid, notebook_guid) values (?, ?)",
                (l_notebook.guid, notebook.guid),
            )

    def get_notebook_by_linked_guid(self, l_notebook_guid: str) -> Optional[Notebook]:
        with self.db as con:
            cur = con.execute(
                "select notebooks.guid, notebooks.name, notebooks.stack"
                " from notebooks_linked"
                " join notebooks"
                " on notebooks.guid=notebooks_linked.notebook_guid"
                " where notebooks_linked.guid=?",
                (l_notebook_guid,),
            )

            row = cur.fetchone()

            if row is None:
                return None

            return Notebook(
                guid=row["guid"],
                name=row["name"],
                stack=row["stack"],
            )

    def get_linked_notebook_usn(self, l_notebook_guid: str) -> int:
        with self.db as con:
            cur = con.execute(
                "select usn from notebooks_linked where guid=?",
                (l_notebook_guid,),
            )

            res = cur.fetchone()

            if res is None:
                return 0

            return int(res[0])

    def set_linked_notebook_usn(self, l_notebook_guid: str, usn: int) -> None:
        with self.db as con:
            con.execute(
                "update notebooks_linked set usn=? where guid=?",
                (usn, l_notebook_guid),
            )

    def expunge_linked_notebooks(self, guids: Iterable[str]) -> None:
        with self.db as con:
            con.executemany(
                "delete from notebooks_linked where guid=?", ((g,) for g in guids)
            )


class NoteStorage(SqliteStorage):  # noqa: WPS214
    def add_notes_for_sync(self, notes: Iterable[Note]) -> None:
        if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
            for note in notes:
                n_info = log_format_note(note)
                logger.debug(f"Scheduling note for sync {n_info}")

        with self.db as con:
            con.executemany(
                "replace into notes(guid, title, notebook_guid) values (?, ?, ?)",
                ((n.guid, n.title, n.notebookGuid) for n in notes),
            )

    def add_note(self, note: Note) -> None:
        if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
            n_info = log_format_note(note)
            logger.debug(f"Adding/updating note {n_info}")

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
                " order by title COLLATE NOCASE",
                (notebook_guid,),
            )

            yield from (pickle.loads(lzma.decompress(row["raw_note"])) for row in cur)

    def iter_notes_trash(self) -> Iterator[Note]:
        with self.db as con:
            cur = con.execute(
                "select raw_note"
                " from notes where is_active=0"
                " order by title COLLATE NOCASE",
            )

            yield from (pickle.loads(lzma.decompress(row["raw_note"])) for row in cur)

    def get_notes_for_sync(self) -> Tuple[NoteForSync, ...]:
        with self.db as con:
            cur = con.execute(
                "select notes.guid, title, notebooks_linked.guid as l_notebook"
                " from notes"
                " left join notebooks_linked"
                " using (notebook_guid)"
                " where raw_note is NULL"
            )

            notes = (
                NoteForSync(
                    guid=row["guid"],
                    title=row["title"],
                    linked_notebook_guid=row["l_notebook"],
                )
                for row in cur.fetchall()
            )

            return tuple(notes)

    def expunge_notes(self, guids: Iterable[str]) -> None:
        with self.db as con:
            con.executemany("delete from notes where guid=?", ((g,) for g in guids))

    def expunge_notes_by_notebook(self, notebook_guid: str) -> None:
        with self.db as con:
            con.execute("delete from notes where notebook_guid=?", (notebook_guid,))

    def get_notes_count(self, is_active: bool = True) -> int:
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

            return str(res[0])
