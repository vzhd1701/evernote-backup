# -*- coding: utf-8 -*-

import logging
from typing import Optional

from evernote_backup.cli_app_auth import get_auth_token, get_sync_client
from evernote_backup.cli_app_storage import (
    get_storage,
    initialize_storage,
    raise_on_existing_database,
    raise_on_old_database_version,
)
from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.note_exporter import NoteExporter, NothingToExportError
from evernote_backup.note_synchronizer import NoteSynchronizer, WrongAuthUserError

logger = logging.getLogger(__name__)


def init_db(
    database: str,
    auth_user: Optional[str],
    auth_password: Optional[str],
    auth_is_oauth: bool,
    auth_oauth_port: int,
    auth_token: Optional[str],
    force: bool,
    backend: str,
    network_retry_count: int,
) -> None:
    if not force:
        raise_on_existing_database(database)

    if not auth_token:
        auth_token = get_auth_token(
            auth_user,
            auth_password,
            auth_is_oauth,
            auth_oauth_port,
            backend,
            network_retry_count,
        )

    note_client = get_sync_client(auth_token, backend, network_retry_count, 1)

    storage = initialize_storage(database, force)

    new_user = note_client.user

    storage.config.set_config_value("DB_VERSION", str(CURRENT_DB_VERSION))
    storage.config.set_config_value("USN", "0")
    storage.config.set_config_value("auth_token", auth_token)
    storage.config.set_config_value("user", new_user)
    storage.config.set_config_value("backend", backend)

    logger.info(f"Successfully initialized database for {new_user}!")


def reauth(
    database: str,
    auth_user: Optional[str],
    auth_password: Optional[str],
    auth_is_oauth: bool,
    auth_oauth_port: int,
    auth_token: Optional[str],
    network_retry_count: int,
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    backend = storage.config.get_config_value("backend")

    if not auth_token:
        auth_token = get_auth_token(
            auth_user,
            auth_password,
            auth_is_oauth,
            auth_oauth_port,
            backend,
            network_retry_count,
        )

    note_client = get_sync_client(auth_token, backend, network_retry_count, 1)

    local_user = storage.config.get_config_value("user")

    if local_user != note_client.user:
        raise ProgramTerminatedError(
            f"Current user of this database is {local_user}, not {note_client.user}!"
            " Each user must use a different database file."
        )

    storage.config.set_config_value("auth_token", auth_token)

    logger.info(f"Successfully refreshed auth token for {local_user}!")


def sync(
    database: str,
    max_chunk_results: int,
    max_download_workers: int,
    network_retry_count: int,
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    backend = storage.config.get_config_value("backend")
    auth_token = storage.config.get_config_value("auth_token")

    note_client = get_sync_client(
        auth_token, backend, network_retry_count, max_chunk_results
    )

    note_synchronizer = NoteSynchronizer(note_client, storage, max_download_workers)

    try:
        note_synchronizer.sync()
    except WrongAuthUserError as e:
        raise ProgramTerminatedError(
            f"Current user of this database is {e.local_user}, not {e.remote_user}!"
            " Each user must use a different database file."
        )

    logger.info("Synchronization completed!")


def export(
    database: str,
    single_notes: bool,
    include_trash: bool,
    output_path: str,
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    exporter = NoteExporter(storage, output_path)

    try:
        exporter.export_notebooks(single_notes, include_trash)
    except NothingToExportError:
        raise ProgramTerminatedError(
            "Database is empty, nothing to export."
            " Execute sync command to populate database first!"
        )

    logger.info("All notes have been exported!")
