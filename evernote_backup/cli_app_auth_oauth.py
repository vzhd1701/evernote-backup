import logging
import sys
from functools import partial
from pathlib import Path

import click

from evernote_backup.config_defaults import EVERNOTE_AUTHORIZE_URL
from evernote_backup.desktop_session import extract_token
from evernote_backup.errors import (
    OAuthCallbackURLError,
    OAuthDeclinedError,
    ProgramTerminatedError,
)
from evernote_backup.evernote_client_oauth import (
    EvernoteOAuthCallbackHandler,
    EvernoteOAuthClient,
    EvernoteOAuthDesktopHandler,
    clean_pasted_url,
)

logger = logging.getLogger(__name__)


def evernote_login_oauth_import(
    user_id: str | None = None,
    config_dir: Path | None = None,
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
    callback_base = f"http://{oauth_host}:{oauth_port}/oauth_callback"

    click.echo(
        "Opening authorization page (MCP OAuth)...\n"
        "If it didn't open automatically, please copy this URL into your browser:\n"
        f"{oauth_url}\n"
        "\n"
        f"Waiting for OAuth callback on {callback_base} ...\n"
        "For headless or remote sessions (when the browser cannot reach this host),\n"
        "copy the full callback URL from the browser address bar after authorizing\n"
        f"(it should start with {callback_base}?code=...) and paste it here, then press Enter.\n"
    )
    click.launch(oauth_url)

    try:
        return oauth_handler.wait_for_token()
    except (OAuthDeclinedError, OAuthCallbackURLError) as e:
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

    # Invalid pastes are re-prompted (click handles BadParameter from value_proc),
    # so a mistake doesn't force restarting the whole authorization flow.
    # OAuthDeclinedError (declined in the browser) is not retryable and ends it.
    try:
        callback: str = click.prompt(
            "Paste (Shift + Insert) the full evernote:// redirect URL",
            value_proc=partial(_parse_desktop_redirect_url, oauth_handler),
        )
        return oauth_handler.exchange_token(callback)
    except OAuthDeclinedError as e:
        raise ProgramTerminatedError(f"OAuth error: {e}") from e


def _parse_desktop_redirect_url(
    oauth_handler: EvernoteOAuthDesktopHandler, raw: str
) -> str:
    try:
        return oauth_handler.parse_redirect_url(raw)
    except OAuthCallbackURLError as e:
        raise click.BadParameter(_with_paste_hint(raw, str(e))) from e


def _with_paste_hint(raw: str, message: str) -> str:
    url = clean_pasted_url(raw).lower()

    if url.startswith(EVERNOTE_AUTHORIZE_URL.lower()):
        hint = (
            "This is the authorization URL. Open it in your browser, authorize,"
            ' then paste the address of the "Return to Evernote" link.'
        )
    elif url.startswith(("http://", "https://")):
        hint = (
            'Copy the address of the "Return to Evernote" link (right click on it),'
            " not the URL from the browser address bar."
        )
    else:
        return message

    return f"{message}\n{hint}"
