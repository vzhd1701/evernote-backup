import logging
import sys
from pathlib import Path
from typing import Optional

import click

from evernote_backup.desktop_session import extract_token
from evernote_backup.errors import OAuthDeclinedError, ProgramTerminatedError
from evernote_backup.evernote_client_oauth import (
    EvernoteOAuthCallbackHandler,
    EvernoteOAuthClient,
    EvernoteOAuthDesktopHandler,
)

logger = logging.getLogger(__name__)


def evernote_login_oauth_import(
    user_id: Optional[str] = None,
    config_dir: Optional[Path] = None,
) -> str:
    if sys.platform != "darwin" and not sys.platform.startswith("win"):
        raise ProgramTerminatedError(
            "Importing an OAuth refresh token from the Evernote Desktop Client is only"
            " supported on Windows and macOS.\n"
            "You can extract refresh token manually on another system using evertoken app:"
            " https://github.com/vzhd1701/evertoken"
        )

    session = extract_token(user_id=user_id, config_dir=config_dir)

    if not session.jwt_refresh:
        raise ProgramTerminatedError(
            f"Desktop session for user {session.user_id!r} has no OAuth refresh"
            " token. Log in again in the Evernote Desktop Client and retry."
        )

    logger.info(
        f"Imported OAuth refresh token from Desktop Client session"
        f" (user {session.user_id}"
        f"{f', {session.username}' if session.username else ''}"
        f"{f', {session.email}' if session.email else ''})."
    )

    return session.jwt_refresh


def evernote_login_oauth_mcp(
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


def evernote_login_oauth_desktop(backend: str) -> str:
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
        "To avoid this, re-run with --oauth-method import to reuse the existing\n"
        "Desktop Client session instead of starting a new login.\n"
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
