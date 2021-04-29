from datetime import datetime
from typing import Optional

from evernote_backup.cli_app_auth_oauth import evernote_login_oauth
from evernote_backup.cli_app_auth_password import evernote_login_password
from evernote_backup.cli_app_util import ProgramTerminatedError, logger
from evernote_backup.evernote_client_sync import EvernoteClientSync
from evernote_backup.evernote_client_util import EvernoteAuthError


def get_sync_client(auth_token: str, backend: str) -> EvernoteClientSync:
    logger.info(f"Authorizing auth token, {backend} backend...")

    client = EvernoteClientSync(token=auth_token, backend=backend)

    try:
        client.verify_token()
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)

    token_expiration = get_token_expiration_date(auth_token)

    logger.info(f"Successfully authenticated as {client.user}!")
    logger.info(f"Current login will expire at {token_expiration}.")

    return client


def get_auth_token(
    auth_user: Optional[str],
    auth_password: Optional[str],
    auth_is_oauth: bool,
    backend: str,
) -> str:
    logger.info("Logging in to Evernote...")

    if auth_is_oauth:
        return evernote_login_oauth(backend)

    return evernote_login_password(auth_user, auth_password, backend)


def get_token_expiration_date(token: str) -> datetime:
    hex_base = 16
    token_parts = token.split(":")
    token_expire_ts = int(token_parts[2][2:], base=hex_base) // 1000

    return datetime.utcfromtimestamp(token_expire_ts)
