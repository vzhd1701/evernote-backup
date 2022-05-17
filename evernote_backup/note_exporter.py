# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Union

from click import progressbar
from evernote.edam.type.ttypes import Note, Notebook

from evernote_backup.cli_app_util import get_progress_output
from evernote_backup.log_util import log_format_note, log_format_notebook
from evernote_backup.note_exporter_util import SafePath
from evernote_backup.note_formatter import NoteFormatter
from evernote_backup.note_storage import SqliteStorage

logger = logging.getLogger(__name__)

ENEX_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">
"""
ENEX_TAIL = "</en-export>"


class NothingToExportError(Exception):
    """Raise when database is empty"""


class NoteExporter(object):
    def __init__(
        self,
        storage: SqliteStorage,
        target_dir: Path,
        single_notes: bool,
        export_trash: bool,
        no_export_date: bool,
        overwrite: bool,
    ) -> None:
        self.storage = storage
        self.safe_paths = SafePath(target_dir, overwrite)

        self.single_notes = single_notes
        self.export_trash = export_trash
        self.no_export_date = no_export_date

    def export_notebooks(self) -> None:
        count_notes = self.storage.notes.get_notes_count()
        count_trash = self.storage.notes.get_notes_count(is_active=False)

        if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
            logger.debug(f"Notes to export: {count_notes}")
            logger.debug(f"Trashed notes: {count_trash}")
            if self.single_notes:
                logger.debug("Export mode: single notes")
            else:
                logger.debug("Export mode: notebooks")

        if count_notes == 0 and count_trash == 0:
            raise NothingToExportError

        if count_notes > 0:
            logger.info("Exporting notes...")

            self._export_active()

        if count_trash > 0 and self.export_trash:
            logger.info("Exporting trash...")

            self._export_trash()

    def _export_active(self) -> None:
        notebooks = tuple(self.storage.notebooks.iter_notebooks())

        with progressbar(
            notebooks,
            show_pos=True,
            file=get_progress_output(),
        ) as notebooks_bar:
            for nb in notebooks_bar:
                if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
                    nb_info = log_format_notebook(nb)
                    logger.debug(f"Exporting notebook {nb_info}")

                if self.storage.notebooks.get_notebook_notes_count(nb.guid) == 0:
                    logger.debug("Notebook is empty, skip")
                    continue

                self._export_notes(nb)

    def _export_notes(self, notebook: Notebook) -> None:
        parent_dir = [notebook.stack] if notebook.stack else []

        notes_source = self.storage.notes.iter_notes(notebook.guid)

        if self.single_notes:
            parent_dir.append(notebook.name)
            self._output_single_notes(parent_dir, notes_source)
        else:
            self._output_notebook(parent_dir, notebook.name, notes_source)

    def _export_trash(self) -> None:
        notes_source = self.storage.notes.iter_notes_trash()

        if self.single_notes:
            self._output_single_notes(["Trash"], notes_source)
        else:
            self._output_notebook([], "Trash", notes_source)

    def _output_single_notes(
        self, parent_dir: List[str], notes_source: Iterable[Note]
    ) -> None:
        for note in notes_source:
            note_path = self.safe_paths.get_file(*parent_dir, f"{note.title}.enex")

            _write_export_file(note_path, note, self.no_export_date)

    def _output_notebook(
        self, parent_dir: List[str], notebook_name: str, notes_source: Iterable[Note]
    ) -> None:
        notebook_path = self.safe_paths.get_file(*parent_dir, f"{notebook_name}.enex")

        _write_export_file(notebook_path, notes_source, self.no_export_date)


def _write_export_file(
    file_path: Path, note_source: Union[Iterable[Note], Note], no_export_date: bool
) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        logger.debug(f"Writing file {file_path}")

        f.write(ENEX_HEAD)

        if no_export_date:
            f.write('<en-export application="Evernote" version="10.10.5">')
        else:
            now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            f.write(
                f'<en-export export-date="{now}"'
                f' application="Evernote" version="10.10.5">'
            )

        note_formatter = NoteFormatter()

        if isinstance(note_source, Note):
            if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
                n_info = log_format_note(note_source)
                logger.debug(f"Exporting note {n_info}")
            f.write(note_formatter.format_note(note_source))
        else:
            for note in note_source:  # noqa: WPS440
                if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
                    n_info = log_format_note(note)
                    logger.debug(f"Exporting note {n_info}")
                f.write(note_formatter.format_note(note))

        f.write(ENEX_TAIL)
