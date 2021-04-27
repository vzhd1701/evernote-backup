# -*- coding: utf-8 -*-

import logging
import os

from evernote_backup.cli_app_util import (
    ProgramTerminatedError,
    get_auth_token,
    get_storage,
    get_sync_client,
)
from evernote_backup.note_exporter import NoteExporter, NothingToExportError
from evernote_backup.note_storage import initialize_db
from evernote_backup.note_synchronizer import NoteSynchronizer, WrongAuthUserError

logger = logging.getLogger(__name__)


def init_db(
    database, auth_user, auth_password, auth_is_oauth, auth_token, force, backend
):
    if not auth_token:
        auth_token = get_auth_token(auth_user, auth_password, auth_is_oauth, backend)

    note_client = get_sync_client(auth_token, backend)

    logger.info("Initializing database {0}...".format(os.path.basename(database)))

    try:
        initialize_db(database, force)
    except FileExistsError:
        raise ProgramTerminatedError(
            "Database already exists."
            " Use --force option to overwrite existing database file."
        )

    storage = get_storage(database)

    new_user = note_client.user

    storage.config.set_config_value("USN", 0)
    storage.config.set_config_value("auth_token", auth_token)
    storage.config.set_config_value("user", new_user)
    storage.config.set_config_value("backend", backend)

    logger.info(f"Successfully initialized database for {new_user}!")


def reauth(database, auth_user, auth_password, auth_is_oauth, auth_token):
    storage = get_storage(database)

    backend = storage.config.get_config_value("backend")

    if not auth_token:
        auth_token = get_auth_token(auth_user, auth_password, auth_is_oauth, backend)

    note_client = get_sync_client(auth_token, backend)

    local_user = storage.config.get_config_value("user")

    if local_user != note_client.user:
        raise ProgramTerminatedError(
            f"Current user of this database is {local_user}, not {note_client.user}!"
            " Each user must use different database file."
        )

    storage.config.set_config_value("auth_token", auth_token)

    logger.info(f"Successfully refreshed auth token for {local_user}!")


def sync(database):
    storage = get_storage(database)

    backend = storage.config.get_config_value("backend")
    auth_token = storage.config.get_config_value("auth_token")

    note_client = get_sync_client(auth_token, backend)

    note_synchronizer = NoteSynchronizer(note_client, storage)

    try:
        note_synchronizer.sync()
    except WrongAuthUserError as e:
        raise ProgramTerminatedError(
            f"Current user of this database is {e.local_user}, not {e.remote_user}!"
            " Each user must use different database file."
        )

    logger.info("Synchronization completed!")


def export(database, single_notes, include_trash, output_path):
    storage = get_storage(database)

    exporter = NoteExporter(storage, output_path)

    try:
        exporter.export_notebooks(single_notes, include_trash)
    except NothingToExportError:
        raise ProgramTerminatedError(
            "Database is empty, nothing to export."
            " Execute sync command to populate database first!"
        )

    logger.info("All notes have been exported!")
