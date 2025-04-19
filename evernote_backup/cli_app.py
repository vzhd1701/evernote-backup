import logging
from pathlib import Path
from ssl import SSLError
from typing import Optional

from evernote_backup.cli_app_auth import (
    get_auth_token,
    get_ping_client,
    get_sync_client,
)
from evernote_backup.cli_app_storage import (
    get_storage,
    initialize_storage,
    raise_on_existing_database,
    raise_on_old_database_version,
)
from evernote_backup.cli_app_util import (
    DatabaseCorruptError,
    DatabaseEmptyError,
    ProgramTerminatedError,
)
from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.evernote_client_util_ssl import log_ssl_debug_info
from evernote_backup.note_checker import NoteChecker
from evernote_backup.note_exporter import NoteExporter
from evernote_backup.note_lister import NoteLister
from evernote_backup.note_synchronizer import NoteSynchronizer, WrongAuthUserError

logger = logging.getLogger(__name__)


def init_db(
    database: Path,
    auth_user: Optional[str],
    auth_password: Optional[str],
    auth_oauth_port: int,
    auth_oauth_host: str,
    auth_token: Optional[str],
    force: bool,
    backend: str,
    network_retry_count: int,
    use_system_ssl_ca: bool,
    custom_api_data: Optional[str],
) -> None:
    if not force:
        raise_on_existing_database(database)

    if not auth_token:
        auth_token = get_auth_token(
            auth_user=auth_user,
            auth_password=auth_password,
            auth_oauth_port=auth_oauth_port,
            auth_oauth_host=auth_oauth_host,
            backend=backend,
            network_retry_count=network_retry_count,
            use_system_ssl_ca=use_system_ssl_ca,
            custom_api_data=custom_api_data,
        )

    note_client = get_sync_client(
        auth_token=auth_token,
        backend=backend,
        network_error_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
        max_chunk_results=1,
        is_jwt_needed=False,
    )

    storage = initialize_storage(database, force)

    new_user = note_client.user

    storage.config.set_config_value("DB_VERSION", str(CURRENT_DB_VERSION))
    storage.config.set_config_value("USN", "0")
    storage.config.set_config_value("auth_token", auth_token)
    storage.config.set_config_value("user", new_user)
    storage.config.set_config_value("backend", backend)
    storage.config.set_config_value("last_connection_tasks", "0")

    logger.info(f"Successfully initialized database for {new_user}!")


def reauth(
    database: Path,
    auth_user: Optional[str],
    auth_password: Optional[str],
    auth_oauth_port: int,
    auth_oauth_host: str,
    auth_token: Optional[str],
    network_retry_count: int,
    use_system_ssl_ca: bool,
    custom_api_data: Optional[str],
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    backend = storage.config.get_config_value("backend")

    if not auth_token:
        auth_token = get_auth_token(
            auth_user=auth_user,
            auth_password=auth_password,
            auth_oauth_port=auth_oauth_port,
            auth_oauth_host=auth_oauth_host,
            backend=backend,
            network_retry_count=network_retry_count,
            use_system_ssl_ca=use_system_ssl_ca,
            custom_api_data=custom_api_data,
        )

    note_client = get_sync_client(
        auth_token=auth_token,
        backend=backend,
        network_error_retry_count=network_retry_count,
        max_chunk_results=1,
        is_jwt_needed=False,
        use_system_ssl_ca=use_system_ssl_ca,
    )

    local_user = storage.config.get_config_value("user")

    if local_user != note_client.user:
        raise ProgramTerminatedError(
            f"Current user of this database is {local_user}, not {note_client.user}!"
            " Each user must use a different database file."
        )

    storage.config.set_config_value("auth_token", auth_token)

    logger.info(f"Successfully refreshed auth token for {local_user}!")


def sync(
    database: Path,
    max_chunk_results: int,
    max_download_workers: int,
    download_cache_memory_limit: int,
    network_retry_count: int,
    use_system_ssl_ca: bool,
    include_tasks: bool,
    token: Optional[str],
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    backend = storage.config.get_config_value("backend")
    auth_token = token or storage.config.get_config_value("auth_token")

    is_jwt_needed = include_tasks

    note_client = get_sync_client(
        auth_token=auth_token,
        backend=backend,
        network_error_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
        max_chunk_results=max_chunk_results,
        is_jwt_needed=is_jwt_needed,
    )

    note_synchronizer = NoteSynchronizer(
        note_client,
        storage,
        max_download_workers,
        download_cache_memory_limit,
        include_tasks,
    )

    try:
        note_synchronizer.sync()
    except WrongAuthUserError as e:
        raise ProgramTerminatedError(
            f"Current user of this database is {e.local_user}, not {e.remote_user}!"
            " Each user must use a different database file."
        )

    logger.info("Synchronization completed!")


def export(
    database: Path,
    single_notes: bool,
    include_trash: bool,
    no_export_date: bool,
    add_guid: bool,
    overwrite: bool,
    output_path: Path,
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    exporter = NoteExporter(
        storage=storage,
        target_dir=output_path,
        single_notes=single_notes,
        export_trash=include_trash,
        no_export_date=no_export_date,
        add_guid=add_guid,
        overwrite=overwrite,
    )

    try:
        exporter.export_notebooks()
    except DatabaseEmptyError:
        raise ProgramTerminatedError(
            "Database is empty, nothing to export."
            " Execute sync command to populate database first!"
        )

    logger.info("All notes have been exported!")


def manage_ping(
    backend: str,
    network_retry_count: int,
    use_system_ssl_ca: bool,
) -> None:
    client = get_ping_client(
        backend=backend,
        network_error_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
    )

    backend_url = client.user_store._base_client.url
    backend_host = client.user_store._base_client.protocol.trans.host

    try:
        check_response = client.check_version()
    except SSLError as e:
        if logger.getEffectiveLevel() == logging.DEBUG:
            log_ssl_debug_info(backend_host, use_system_ssl_ca)

        raise ProgramTerminatedError(
            f"SSL certificate verification failed for host '{backend_host}': {e}"
        )

    logger.info("Connection OK!")

    logger.debug(f"Backend: {backend}")
    logger.debug(f"UserStore endpoint URL: {backend_url}")
    logger.debug(f"Version check status: {check_response}")


def manage_check(
    database: Path,
    mark_corrupted: bool,
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    checker = NoteChecker(storage, mark_corrupted)

    try:
        checker.check_notes()
    except DatabaseEmptyError:
        raise ProgramTerminatedError(
            "Database is empty, nothing to check."
            " Execute sync command to populate database first!"
        )
    except DatabaseCorruptError:
        raise ProgramTerminatedError(
            "Database integrity check failed."
            " You can try recovering your database or create a new one and do full resync."
        )

    logger.info("All notes have been checked!")


def manage_list(
    database: Path,
    notebook: Optional[str],
    is_list_all: bool,
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    checker = NoteLister(storage, notebook, is_list_all)

    checker.list_notebooks()
