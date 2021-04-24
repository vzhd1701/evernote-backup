# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from click import progressbar

from evernote_backup.cli_app_util import get_progress_output
from evernote_backup.note_exporter_util import SafePath

logger = logging.getLogger(__name__)

ENEX_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">
<en-export export-date="{export_date}" application="Evernote" version="10.10.5">
"""
ENEX_TAIL = "</en-export>"


class NothingToExportError(Exception):
    """Raise when database is empty"""


class NoteExporter(object):
    def __init__(self, storage, target_dir):
        self.storage = storage
        self.safe_paths = SafePath(target_dir)

    def export_notebooks(self, single_notes, export_trash):
        count_notes = self.storage.notes.get_notes_count()
        count_trash = self.storage.notes.get_notes_count(is_active=False)

        if count_notes == 0 and count_trash == 0:
            raise NothingToExportError

        if count_notes > 0:
            logger.info("Exporting notes...")

            self._export_active(single_notes)

        if count_trash > 0 and export_trash:
            logger.info("Exporting trash...")

            self._export_trash(single_notes)

    def _export_active(self, single_notes):
        notebooks = tuple(self.storage.notebooks.iter_notebooks())

        with progressbar(
            notebooks,
            item_show_func=lambda x: x.name if x else None,
            show_pos=True,
            file=get_progress_output(),
        ) as notebooks_bar:
            for notebook in notebooks_bar:
                if self.storage.notebooks.get_notebook_notes_count(notebook.guid) == 0:
                    continue

                self._export_notes(notebook, single_notes)

    def _export_notes(self, notebook, single_notes):
        parent_dir = [notebook.stack] if notebook.stack else []

        notes_source = self.storage.notes.iter_notes(notebook.guid)

        if single_notes:
            parent_dir.append(notebook.name)
            self._output_single_notes(parent_dir, notes_source)
        else:
            self._output_notebook(parent_dir, notebook.name, notes_source)

    def _export_trash(self, single_notes):
        notes_source = self.storage.notes.iter_notes_trash()

        if single_notes:
            self._output_single_notes(["Trash"], notes_source)
        else:
            self._output_notebook([], "Trash", notes_source)

    def _output_single_notes(self, parent_dir, notes_source):
        for note in notes_source:
            note_path = self.safe_paths.get_file(*parent_dir, f"{note.title}.enex")

            _write_export_file(note_path, note.body)

    def _output_notebook(self, parent_dir, notebook_name, notes_source):
        notebook_path = self.safe_paths.get_file(*parent_dir, f"{notebook_name}.enex")
        notes_content = (n.body for n in notes_source)

        _write_export_file(notebook_path, notes_content)


def _write_export_file(file_path, output):
    with open(file_path, "w", encoding="utf-8") as f:
        now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        f.write(ENEX_HEAD.format(export_date=now))

        if isinstance(output, str):
            f.write(output)
        else:
            for body in output:
                f.write(body)

        f.write(ENEX_TAIL)
