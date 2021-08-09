# -*- coding: utf-8 -*-

import logging
from datetime import datetime
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
<en-export export-date="{export_date}" application="Evernote" version="10.10.5">
"""
ENEX_TAIL = "</en-export>"


class NothingToExportError(Exception):
    """Raise when database is empty"""


class NoteExporter(object):
    def __init__(self, storage: SqliteStorage, target_dir: str) -> None:
        self.storage = storage
        self.safe_paths = SafePath(target_dir)

    def export_notebooks(self, single_notes: bool, export_trash: bool) -> None:
        count_notes = self.storage.notes.get_notes_count()
        count_trash = self.storage.notes.get_notes_count(is_active=False)

        if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
            logger.debug(f"Notes to export: {count_notes}")
            logger.debug(f"Trashed notes: {count_trash}")
            if single_notes:
                logger.debug("Export mode: single notes")
            else:
                logger.debug("Export mode: notebooks")

        if count_notes == 0 and count_trash == 0:
            raise NothingToExportError

        if count_notes > 0:
            logger.info("Exporting notes...")

            self._export_active(single_notes)

        if count_trash > 0 and export_trash:
            logger.info("Exporting trash...")

            self._export_trash(single_notes)

    def _export_active(self, single_notes: bool) -> None:
        notebooks = tuple(self.storage.notebooks.iter_notebooks())

        with progressbar(
            notebooks,
            item_show_func=lambda x: str(x.name) if x else "",
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

                self._export_notes(nb, single_notes)

    def _export_notes(self, notebook: Notebook, single_notes: bool) -> None:
        parent_dir = [notebook.stack] if notebook.stack else []

        notes_source = self.storage.notes.iter_notes(notebook.guid)

        if single_notes:
            parent_dir.append(notebook.name)
            self._output_single_notes(parent_dir, notes_source)
        else:
            self._output_notebook(parent_dir, notebook.name, notes_source)

    def _export_trash(self, single_notes: bool) -> None:
        notes_source = self.storage.notes.iter_notes_trash()

        if single_notes:
            self._output_single_notes(["Trash"], notes_source)
        else:
            self._output_notebook([], "Trash", notes_source)

    def _output_single_notes(
        self,
        parent_dir: List[str],
        notes_source: Iterable[Note],
    ) -> None:
        for note in notes_source:
            note_path = self.safe_paths.get_file(*parent_dir, f"{note.title}.enex")

            _write_export_file(note_path, note)

    def _output_notebook(
        self,
        parent_dir: List[str],
        notebook_name: str,
        notes_source: Iterable[Note],
    ) -> None:
        notebook_path = self.safe_paths.get_file(*parent_dir, f"{notebook_name}.enex")

        _write_export_file(notebook_path, notes_source)


def _write_export_file(
    file_path: str, note_source: Union[Iterable[Note], Note]
) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        logger.debug(f"Writing file {file_path}")

        now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        f.write(ENEX_HEAD.format(export_date=now))

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
