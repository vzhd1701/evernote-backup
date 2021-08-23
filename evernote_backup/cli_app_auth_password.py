from typing import Optional, Tuple

import click
from evernote.edam.userstore.ttypes import AuthenticationResult

from evernote_backup.cli_app_auth_oauth import prompt_ota
from evernote_backup.cli_app_util import (
    ProgramTerminatedError,
    is_output_to_terminal,
    unscramble,
)
from evernote_backup.config import API_DATA
from evernote_backup.evernote_client_auth import EvernoteClientAuth
from evernote_backup.evernote_client_util import EvernoteAuthError


def get_auth_client(backend: str, network_retry_count: int) -> EvernoteClientAuth:
    key, secret = unscramble(API_DATA)

    return EvernoteClientAuth(
        consumer_key=key,
        consumer_secret=secret,
        backend=backend,
        network_error_retry_count=network_retry_count,
    )


def prompt_credentials(
    user: Optional[str],
    password: Optional[str],
) -> Tuple[str, str]:
    if not is_output_to_terminal() and not all([user, password]):
        raise ProgramTerminatedError("--user and --password are required!")

    if not user:
        user = str(click.prompt("Username or Email"))
    if not password:
        password = str(click.prompt("Password", hide_input=True))

    return user, password


def evernote_login_password(
    auth_user: Optional[str],
    auth_password: Optional[str],
    backend: str,
    network_retry_count: int,
) -> str:
    auth_user, auth_password = prompt_credentials(auth_user, auth_password)

    auth_client = get_auth_client(
        backend=backend, network_retry_count=network_retry_count
    )

    try:
        auth_res = auth_client.login(auth_user, auth_password)
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)

    if auth_res.secondFactorRequired:
        auth_res = handle_two_factor_auth(
            auth_client,
            auth_res.authenticationToken,
            auth_res.secondFactorDeliveryHint,
        )

    return str(auth_res.authenticationToken)


def handle_two_factor_auth(
    auth_client: EvernoteClientAuth, token: str, delivery_hint: str
) -> AuthenticationResult:
    ota_code = prompt_ota(delivery_hint)

    try:
        return auth_client.two_factor_auth(token, ota_code)
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)
