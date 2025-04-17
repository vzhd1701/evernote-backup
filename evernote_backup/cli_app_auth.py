import logging
from typing import Optional

from evernote_backup.cli_app_auth_oauth import evernote_login_oauth
from evernote_backup.cli_app_auth_password import evernote_login_password
from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.evernote_client import EvernoteClient
from evernote_backup.evernote_client_sync import EvernoteClientSync
from evernote_backup.evernote_client_util import EvernoteAuthError
from evernote_backup.evernote_client_util_ssl import get_cafile_path
from evernote_backup.token_util import get_token_expiration_date

logger = logging.getLogger(__name__)


def get_sync_client(
    auth_token: str,
    backend: str,
    network_error_retry_count: int,
    use_system_ssl_ca: bool,
    max_chunk_results: int,
    is_jwt_needed: bool,
) -> EvernoteClientSync:
    logger.info(f"Authorizing auth token, {backend} backend...")

    cafile = get_cafile_path(use_system_ssl_ca)

    client = EvernoteClientSync(
        token=auth_token,
        backend=backend,
        network_error_retry_count=network_error_retry_count,
        cafile=cafile,
        max_chunk_results=max_chunk_results,
    )

    try:
        client.verify_token()
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)

    if is_jwt_needed:
        logger.info("Retrieving JWT token...")

        try:
            client.refresh_jwt_token()
        except EvernoteAuthError as e:
            raise ProgramTerminatedError(e)

    token_expiration = get_token_expiration_date(auth_token)

    logger.info(f"Successfully authenticated as {client.user}!")
    logger.info(f"Current login will expire at {token_expiration}.")

    return client


def get_auth_token(
    auth_user: Optional[str],
    auth_password: Optional[str],
    auth_oauth_port: int,
    auth_oauth_host: str,
    backend: str,
    network_retry_count: int,
    use_system_ssl_ca: bool,
    custom_api_data: Optional[str],
) -> str:
    logger.info("Logging in to Evernote...")

    cafile = get_cafile_path(use_system_ssl_ca)

    if backend.startswith("china"):
        logger.info("Using password authentication...")

        return evernote_login_password(
            auth_user=auth_user,
            auth_password=auth_password,
            backend=backend,
            network_retry_count=network_retry_count,
            cafile=cafile,
            custom_api_data=custom_api_data,
        )

    logger.info("Using OAuth authentication...")
    return evernote_login_oauth(
        backend=backend,
        oauth_port=auth_oauth_port,
        oauth_host=auth_oauth_host,
        custom_api_data=custom_api_data,
    )


def get_ping_client(
    backend: str,
    network_error_retry_count: int,
    use_system_ssl_ca: bool,
) -> EvernoteClient:
    cafile = get_cafile_path(use_system_ssl_ca)

    return EvernoteClient(
        backend=backend,
        network_error_retry_count=network_error_retry_count,
        cafile=cafile,
    )
