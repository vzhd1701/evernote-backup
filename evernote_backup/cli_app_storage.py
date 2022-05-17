import logging
from pathlib import Path

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.note_storage import (
    DatabaseResyncRequiredError,
    SqliteStorage,
    initialize_db,
)

logger = logging.getLogger(__name__)


def get_storage(database_path: Path) -> SqliteStorage:
    logger.info("Reading database {0}...".format(database_path.name))

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


def raise_on_existing_database(database_path: Path) -> None:
    if database_path.exists():
        raise ProgramTerminatedError(
            "Database already exists."
            " Use --force option to overwrite existing database file."
        )


def initialize_storage(database_path: Path, force: bool) -> SqliteStorage:
    logger.info("Initializing database {0}...".format(database_path.name))

    if force:
        if database_path.exists():
            database_path.unlink()
    else:
        raise_on_existing_database(database_path)

    initialize_db(database_path)

    return get_storage(database_path)
