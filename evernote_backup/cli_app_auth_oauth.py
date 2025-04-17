from typing import Optional

import click

from evernote_backup.cli_app_util import (
    ProgramTerminatedError,
    get_api_data,
    is_output_to_terminal,
)
from evernote_backup.evernote_client_oauth import (
    EvernoteOAuthCallbackHandler,
    EvernoteOAuthClient,
    OAuthDeclinedError,
)


def get_oauth_client(
    backend: str,
    custom_api_data: Optional[str],
) -> EvernoteOAuthClient:
    key, secret = get_api_data(backend, custom_api_data)

    return EvernoteOAuthClient(
        consumer_key=key,
        consumer_secret=secret,
        backend=backend,
    )


def prompt_ota(delivery_hint: str) -> str:
    if not is_output_to_terminal():
        raise ProgramTerminatedError("Two-factor authentication requires user input!")

    one_time_hint = ""
    if delivery_hint:
        one_time_hint = f" ({delivery_hint})"

    return str(click.prompt(f"Enter one-time code{one_time_hint}"))


def evernote_login_oauth(
    backend: str,
    oauth_port: int,
    oauth_host: str,
    custom_api_data: Optional[str],
) -> str:
    if not is_output_to_terminal():
        raise ProgramTerminatedError("OAuth requires user input!")

    oauth_client = get_oauth_client(backend, custom_api_data)

    oauth_handler = EvernoteOAuthCallbackHandler(oauth_client, oauth_port, oauth_host)

    oauth_url = oauth_handler.get_oauth_url()

    click.echo(
        f"Opening authorization page...\n"
        f"If it didn't open automatically, please copy this URL into your browser:\n"
        f"{oauth_url}"
    )
    click.launch(oauth_url)

    try:
        return oauth_handler.wait_for_token()
    except OAuthDeclinedError:
        raise ProgramTerminatedError("Authorization declined!")
