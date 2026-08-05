import logging
from collections.abc import Iterable

from evernote.edam.type.ttypes import Note

from evernote_backup.evernote_client_util import require
from evernote_backup.note_storage import SqliteStorage

logger = logging.getLogger(__name__)


class NoteLister:
    def __init__(
        self,
        storage: SqliteStorage,
        notebook: str | None,
        is_list_all: bool,
    ) -> None:
        self.storage = storage
        self.notebook = notebook
        self.is_list_all = is_list_all

    def list_notebooks(self) -> None:
        notebooks = sorted(
            self.storage.notebooks.iter_notebooks(),
            key=lambda n: require(n.name).lower(),
        )

        logger.info("Listing notebooks in database...")
        logger.info("---")

        for nb in notebooks:
            name = require(nb.name)
            if self.notebook and name != self.notebook:
                continue

            logger.info(name)

            if self.is_list_all or self.notebook:
                notes = _sorted_note_titles(
                    self.storage.notes.iter_notes(require(nb.guid))
                )
                for n in notes:
                    logger.info(f"- '{n}'")

        if self.is_list_all:
            trash_notes = _sorted_note_titles(self.storage.notes.iter_notes_trash())

            if trash_notes:
                logger.info("---")
                logger.info("Trash")

                for n in trash_notes:
                    logger.info(f"- '{n}'")


def _sorted_note_titles(notes_source: Iterable[Note]) -> list[str]:
    return sorted(
        (require(n.title) for n in notes_source),
        key=lambda t: t.lower(),
    )
