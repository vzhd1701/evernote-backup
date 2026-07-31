import logging
from typing import Optional

from evernote_backup.cli_app_auth_oauth import evernote_login_oauth
from evernote_backup.cli_app_auth_password import evernote_login_password
from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.evernote_client import EvernoteClient
from evernote_backup.evernote_client_sync import EvernoteClientSync
from evernote_backup.evernote_client_util import EvernoteAuthError
from evernote_backup.evernote_client_util_ssl import get_cafile_path

logger = logging.getLogger(__name__)


def get_sync_client(
    auth_token: str,
    backend: str,
    network_error_retry_count: int,
    use_system_ssl_ca: bool,
    max_chunk_results: int,
    jwt_token: Optional[str] = None,
) -> EvernoteClientSync:
    logger.info(f"Authorizing auth token, {backend} backend...")

    cafile = get_cafile_path(use_system_ssl_ca)

    client = EvernoteClientSync(
        token=auth_token,
        backend=backend,
        network_error_retry_count=network_error_retry_count,
        cafile=cafile,
        max_chunk_results=max_chunk_results,
        jwt_token=jwt_token,
    )

    try:
        client.verify_token()
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)

    logger.info(f"Successfully authenticated as {client.user}!")
    logger.info(f"Current login expires at {client.token.expiration_human}.")  # type: ignore

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
    oauth_mcp: bool = False,
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

    if oauth_mcp:
        logger.info("Using MCP OAuth authentication...")
    else:
        logger.info("Using Desktop OAuth authentication (paste redirect URL)...")

    return evernote_login_oauth(
        backend=backend,
        oauth_port=auth_oauth_port,
        oauth_host=auth_oauth_host,
        oauth_mcp=oauth_mcp,
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
