import os

from evernote_backup.cli_app_util import ProgramTerminatedError, logger
from evernote_backup.note_storage import DatabaseResyncRequiredError, SqliteStorage


def get_storage(database_path: str) -> SqliteStorage:
    logger.info("Reading database {0}...".format(os.path.basename(database_path)))

    try:
        return SqliteStorage(database_path)
    except FileNotFoundError:
        raise ProgramTerminatedError(
            f"Database file {database_path} does not exist."
            f" Initialize database first!"
        )


def raise_on_old_database_version(storage: SqliteStorage) -> None:
    try:
        storage.check_version()
    except DatabaseResyncRequiredError:
        raise ProgramTerminatedError(
            "The database version has been updated. Full resync is required."
        )
