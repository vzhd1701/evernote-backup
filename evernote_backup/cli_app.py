import logging
from pathlib import Path
from ssl import SSLError
from typing import Optional

from evernote_backup.cli_app_auth import (
    get_auth_token,
    get_ping_client,
    get_sync_client,
)
from evernote_backup.token_util import resolve_auth_token
from evernote_backup.cli_app_storage import (
    get_storage,
    initialize_storage,
    raise_on_existing_database,
    raise_on_old_database_version,
)
from evernote_backup.cli_app_util import (
    parse_guid,
)
from evernote_backup.errors import (
    ProgramTerminatedError,
    DatabaseEmptyError,
    DatabaseCorruptError,
    WrongAuthUserError,
)
from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.evernote_client_util_ssl import log_ssl_debug_info
from evernote_backup.note_checker import NoteChecker
from evernote_backup.note_exporter import NoteExporter
from evernote_backup.note_lister import NoteLister
from evernote_backup.note_synchronizer import NoteSynchronizer

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
    oauth_method: str = "desktop",
    oauth_en_user: Optional[str] = None,
    oauth_en_config_dir: Optional[Path] = None,
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
            oauth_method=oauth_method,
            oauth_en_user=oauth_en_user,
            oauth_en_config_dir=oauth_en_config_dir,
        )

    auth_resolved = resolve_auth_token(auth_token)

    note_client = get_sync_client(
        auth_token=auth_resolved.monolith_token,
        jwt_token=auth_resolved.jwt_token,
        backend=backend,
        network_error_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
        max_chunk_results=1,
    )

    storage = initialize_storage(database, force)

    new_user = note_client.user

    storage.config.set_config_value("DB_VERSION", str(CURRENT_DB_VERSION))
    storage.config.set_config_value("USN", "0")
    storage.config.set_config_value("auth_token", auth_resolved.auth_for_storage)
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
    oauth_method: str = "desktop",
    oauth_en_user: Optional[str] = None,
    oauth_en_config_dir: Optional[Path] = None,
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
            oauth_method=oauth_method,
            oauth_en_user=oauth_en_user,
            oauth_en_config_dir=oauth_en_config_dir,
        )

    auth_resolved = resolve_auth_token(auth_token)

    note_client = get_sync_client(
        auth_token=auth_resolved.monolith_token,
        jwt_token=auth_resolved.jwt_token,
        backend=backend,
        network_error_retry_count=network_retry_count,
        max_chunk_results=1,
        use_system_ssl_ca=use_system_ssl_ca,
    )

    local_user = storage.config.get_config_value("user")

    if local_user != note_client.user:
        raise ProgramTerminatedError(
            f"Current user of this database is {local_user}, not {note_client.user}!"
            " Each user must use a different database file."
        )

    storage.config.set_config_value("auth_token", auth_resolved.auth_for_storage)

    logger.info(f"Successfully refreshed auth token for {local_user}!")


def sync(
    database: Path,
    max_chunk_results: int,
    max_download_workers: int,
    download_cache_memory_limit: int,
    network_retry_count: int,
    use_system_ssl_ca: bool,
    token: Optional[str],
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    backend = storage.config.get_config_value("backend")
    auth_token = token or storage.config.get_config_value("auth_token")

    auth_resolved = resolve_auth_token(auth_token)

    # Persist refreshed OAuth bundle when using stored credentials (not one-off --token).
    if auth_resolved.updated and not token:
        storage.config.set_config_value("auth_token", auth_resolved.auth_for_storage)
        logger.info("Stored refreshed OAuth2 token bundle in the database.")

    # Tasks/reminders use the new sync API and require an OAuth2 JWT access token.
    include_tasks = auth_resolved.jwt_token is not None
    if backend == "evernote" and not include_tasks:
        logger.warning(
            "Tasks and reminders will not be synced because this database has no"
            " OAuth2 credentials. Run 'evernote-backup reauth' to enable tasks and reminders sync."
        )

    note_client = get_sync_client(
        auth_token=auth_resolved.monolith_token,
        jwt_token=auth_resolved.jwt_token,
        backend=backend,
        network_error_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
        max_chunk_results=max_chunk_results,
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
    add_metadata: bool,
    overwrite: bool,
    notebooks: tuple[str],
    tags: tuple[str],
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
        add_metadata=add_metadata,
        filter_notebooks=notebooks,
        filter_tags=tags,
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


def manage_blacklist(
    database: Path,
    add_note_id: tuple[str, ...],
    del_note_id: tuple[str, ...],
    add_notebook_id: tuple[str, ...],
    del_notebook_id: tuple[str, ...],
    reset_notes: bool,
    reset_notebooks: bool,
) -> None:
    storage = get_storage(database)

    raise_on_old_database_version(storage)

    has_changes = any(
        (
            add_note_id,
            del_note_id,
            add_notebook_id,
            del_notebook_id,
            reset_notes,
            reset_notebooks,
        )
    )

    if not has_changes:
        _list_blacklist(storage)
        return

    # Validate all GUIDs before applying any changes.
    del_notes = _parse_guids(del_note_id)
    del_notebooks = _parse_guids(del_notebook_id)
    add_notes = _parse_guids(add_note_id)
    add_notebooks = _parse_guids(add_notebook_id)

    if reset_notes:
        storage.config.set_blacklist_notes([])
        logger.info("Cleared blacklisted notes.")

    if reset_notebooks:
        storage.config.set_blacklist_notebooks([])
        logger.info("Cleared blacklisted notebooks.")

    notes = storage.config.get_blacklist_notes()
    notebooks = storage.config.get_blacklist_notebooks()

    for note_id in del_notes:
        if note_id in notes:
            notes = [n for n in notes if n != note_id]
            logger.info(f"Removed note [{note_id}] from blacklist.")
        else:
            logger.warning(f"Note [{note_id}] is not blacklisted.")

    for notebook_id in del_notebooks:
        if notebook_id in notebooks:
            notebooks = [n for n in notebooks if n != notebook_id]
            logger.info(f"Removed notebook [{notebook_id}] from blacklist.")
        else:
            logger.warning(f"Notebook [{notebook_id}] is not blacklisted.")

    for note_id in add_notes:
        if note_id in notes:
            logger.warning(f"Note [{note_id}] is already blacklisted.")
        else:
            notes.append(note_id)
            logger.info(f"Added note [{note_id}] to blacklist.")

    for notebook_id in add_notebooks:
        if notebook_id in notebooks:
            logger.warning(f"Notebook [{notebook_id}] is already blacklisted.")
        else:
            notebooks.append(notebook_id)
            logger.info(f"Added notebook [{notebook_id}] to blacklist.")

    storage.config.set_blacklist_notes(notes)
    storage.config.set_blacklist_notebooks(notebooks)


def _parse_guids(values: tuple[str, ...]) -> list[str]:
    parsed: list[str] = []

    for value in values:
        try:
            parsed.append(parse_guid(value))
        except ValueError as e:
            raise ProgramTerminatedError(str(e)) from e

    return parsed


def _list_blacklist(storage) -> None:
    notes = storage.config.get_blacklist_notes()
    notebooks = storage.config.get_blacklist_notebooks()

    if not notes and not notebooks:
        logger.info("Blacklist is empty.")
        return

    logger.info("Blacklisted notes:")
    if notes:
        for note_id in notes:
            logger.info(f"- {note_id}")
    else:
        logger.info("- (none)")

    logger.info("Blacklisted notebooks:")
    if notebooks:
        for notebook_id in notebooks:
            logger.info(f"- {notebook_id}")
    else:
        logger.info("- (none)")
