import logging

from click import progressbar

from evernote_backup.cli_app_util import (
    DatabaseCorruptError,
    DatabaseEmptyError,
    get_progress_output,
)
from evernote_backup.note_storage import SqliteStorage

logger = logging.getLogger(__name__)


class NoteChecker:
    def __init__(
        self,
        storage: SqliteStorage,
        mark_corrupt: bool,
    ) -> None:
        self.storage = storage
        self.mark_corrupt = mark_corrupt

    def check_notes(self) -> None:
        db_integrity_report = self.storage.integrity_check()

        if db_integrity_report != "ok":
            logger.warning("Database integrity check reported following errors:")
            logger.warning(db_integrity_report)
            logger.warning("To recover your database run this command:")
            logger.warning(
                'sqlite3 en_backup.db ".recover" | sqlite3 en_backup_recovered.db'
            )
            raise DatabaseCorruptError

        count_notes = self.storage.notes.get_notes_count()
        count_trash = self.storage.notes.get_notes_count(is_active=False)

        logger.info(f"Notes: {count_notes}")
        logger.info(f"Trashed notes: {count_trash}")

        if count_notes == 0 and count_trash == 0:
            raise DatabaseEmptyError

        notes_source = self.storage.notes.check_notes(self.mark_corrupt)

        logger.info("Checking notes...")

        with progressbar(
            notes_source,
            length=count_notes + count_trash,
            show_pos=True,
            file=get_progress_output(),
        ) as notebooks_bar:
            count_processed_notes = sum(1 for _ in notebooks_bar)

        logger.info(f"Checked notes: {count_processed_notes}")
