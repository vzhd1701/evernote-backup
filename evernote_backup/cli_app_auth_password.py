import click
from evernote.edam.userstore.ttypes import AuthenticationResult

from evernote_backup.cli_app_util import (
    get_api_data,
    is_output_to_terminal,
)
from evernote_backup.errors import EvernoteAuthError, ProgramTerminatedError
from evernote_backup.evernote_client_auth import EvernoteClientAuth
from evernote_backup.evernote_client_util import require


def get_auth_client(
    backend: str,
    network_retry_count: int,
    cafile: str | None,
    custom_api_data: str | None,
) -> EvernoteClientAuth:
    key, secret = get_api_data(custom_api_data)

    return EvernoteClientAuth(
        consumer_key=key,
        consumer_secret=secret,
        backend=backend,
        network_error_retry_count=network_retry_count,
        cafile=cafile,
    )


def prompt_credentials(
    user: str | None,
    password: str | None,
) -> tuple[str, str]:
    if not is_output_to_terminal() and not all([user, password]):
        raise ProgramTerminatedError("--user and --password are required!")

    if not user:
        user = str(click.prompt("Username or Email"))
    if not password:
        password = str(click.prompt("Password", hide_input=True))

    return user, password


def evernote_login_password(
    auth_user: str | None,
    auth_password: str | None,
    backend: str,
    network_retry_count: int,
    cafile: str | None,
    custom_api_data: str | None,
) -> str:
    auth_user, auth_password = prompt_credentials(auth_user, auth_password)

    auth_client = get_auth_client(
        backend=backend,
        network_retry_count=network_retry_count,
        cafile=cafile,
        custom_api_data=custom_api_data,
    )

    try:
        auth_res = auth_client.login(auth_user, auth_password)
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)

    if auth_res.secondFactorRequired:
        auth_res = handle_two_factor_auth(
            auth_client,
            require(auth_res.authenticationToken),
            # Hint is display-only; server may omit it.
            auth_res.secondFactorDeliveryHint or "",
        )

    return require(auth_res.authenticationToken)


def handle_two_factor_auth(
    auth_client: EvernoteClientAuth, token: str, delivery_hint: str
) -> AuthenticationResult:
    ota_code = _prompt_ota(delivery_hint)

    try:
        return auth_client.two_factor_auth(token, ota_code)
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)


def _prompt_ota(delivery_hint: str) -> str:
    if not is_output_to_terminal():
        raise ProgramTerminatedError("Two-factor authentication requires user input!")

    one_time_hint = ""
    if delivery_hint:
        one_time_hint = f" ({delivery_hint})"

    return str(click.prompt(f"Enter one-time code{one_time_hint}"))
