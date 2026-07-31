from typing import Optional

import click

from evernote_backup.cli_app_util import (
    ProgramTerminatedError,
    is_output_to_terminal,
)
from evernote_backup.errors import OAuthDeclinedError
from evernote_backup.evernote_client_oauth import (
    EvernoteOAuthCallbackHandler,
    EvernoteOAuthClient,
    EvernoteOAuthDesktopHandler,
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
    oauth_mcp: bool = False,
) -> str:
    if not is_output_to_terminal():
        raise ProgramTerminatedError("OAuth requires user input!")

    if oauth_mcp:
        return _evernote_login_oauth_mcp(backend, oauth_port, oauth_host)

    return _evernote_login_oauth_desktop(backend)


def _evernote_login_oauth_mcp(
    backend: str,
    oauth_port: int,
    oauth_host: str,
) -> str:
    oauth_client = EvernoteOAuthClient(backend=backend)
    oauth_handler = EvernoteOAuthCallbackHandler(oauth_client, oauth_port, oauth_host)

    oauth_url = oauth_handler.get_oauth_url()

    click.echo(
        "Opening authorization page (MCP OAuth)...\n"
        "If it didn't open automatically, please copy this URL into your browser:\n"
        f"{oauth_url}"
    )
    click.launch(oauth_url)

    try:
        return oauth_handler.wait_for_token()
    except OAuthDeclinedError as e:
        raise ProgramTerminatedError(f"OAuth error: {e}") from e


def _evernote_login_oauth_desktop(backend: str) -> str:
    oauth_client = EvernoteOAuthClient(backend=backend)
    oauth_handler = EvernoteOAuthDesktopHandler(oauth_client)

    oauth_url = oauth_handler.get_oauth_url()

    click.echo(
        "Opening authorization page (Desktop Client OAuth)...\n"
        "If it didn't open automatically, please copy this URL into your browser:\n"
        f"{oauth_url}\n"
        "\n"
        "After you authorize, the browser will redirect to an evernote:// URL.\n"
        "CANCEL THE REDIRECT AND DO NOT OPEN THE REDIRECT LINK VIA EVERNOTE!\n"
        'Copy the full redirect URL by right clicking on "Return to Evernote" link and paste it here.\n'
        "\n"
        "WARNING: free Evernote accounts allow only one active login session.\n"
        "This may sign you out of the Evernote Desktop app.\n"
    )
    click.launch(oauth_url)

    redirect_url = str(
        click.prompt(
            "Paste (Shift + Insert) the full evernote:// redirect URL",
            type=str,
        )
    )

    try:
        return oauth_handler.exchange_token(redirect_url)
    except OAuthDeclinedError as e:
        raise ProgramTerminatedError(f"OAuth error: {e}") from e
