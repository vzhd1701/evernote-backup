import sys
import threading
import time
from collections.abc import Collection
from enum import IntEnum
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from oauthlib.oauth2 import OAuth2Error
from requests_oauthlib import OAuth2Session

from evernote_backup.cli_app_util import is_inside_docker
from evernote_backup.config import MCP_NAME
from evernote_backup.config_defaults import (
    DESKTOP_CLIENT_ID,
    DESKTOP_REDIRECT_URI,
    EVERNOTE_AUTHORIZE_URL,
    EVERNOTE_DISCOVERY_URL,
    EVERNOTE_TOKEN_URL,
    OAUTH_SCOPES,
)
from evernote_backup.errors import OAuthCallbackURLError, OAuthDeclinedError
from evernote_backup.evernote_client import EvernoteClientBase
from evernote_backup.token_util import OAuth2TokenBundle


class HTTPCode(IntEnum):
    OK = 200
    NOT_FOUND = 404


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not self.path.startswith("/oauth_callback?"):
            self.send_response(HTTPCode.NOT_FOUND)
            self.end_headers()
            return

        self.server.callback_response = self.path  # type: ignore

        self.send_response(HTTPCode.OK)
        self.end_headers()
        self.wfile.write(
            b"<html><head><title>OAuth Callback</title></head>"
            b"<body>You can close this tab now...</body></html>"
        )

    def log_message(self, *args, **kwargs) -> None:
        """Silencing server log"""


class StoppableHTTPServer(HTTPServer):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.callback_response: str = ""

    def run(self) -> None:
        try:
            self.serve_forever()
        finally:
            self.server_close()


class EvernoteOAuthCallbackHandler:
    def __init__(
        self, oauth_client: "EvernoteOAuthClient", oauth_port: int, server_host: str
    ) -> None:
        self.client = oauth_client

        self.server_host = server_host
        self.server_port = oauth_port

    def get_oauth_url(self) -> str:
        return self.client.get_authorize_url_mcp(
            f"http://{self.server_host}:{self.server_port}/oauth_callback"
        )

    def wait_for_token(self) -> str:
        """Complete OAuth code exchange and return token bundle JSON for storage.

        Accepts either the local HTTP redirect callback or a callback URL pasted
        on stdin (for headless / remote OAuth where the browser cannot reach
        the local listener).
        """
        bundle = self.client.get_access_token(self._wait_for_callback())
        return bundle.to_json()

    def exchange_token(self, callback_url: str) -> str:
        """Exchange a pasted MCP callback URL for token bundle JSON."""
        bundle = self.client.get_access_token(
            normalize_oauth_callback_url(
                callback_url, allowed_schemes=("http", "https")
            )
        )
        return bundle.to_json()

    def _wait_for_callback(self) -> str:
        if is_inside_docker():
            server_param = ("0.0.0.0", self.server_port)  # noqa: S104
        else:
            server_param = (self.server_host, self.server_port)

        callback_server = StoppableHTTPServer(server_param, CallbackHandler)

        thread = threading.Thread(target=callback_server.run)
        thread.start()

        pasted: list[str] = []
        stop_paste = threading.Event()

        def read_pasted_url() -> None:
            try:
                line = sys.stdin.readline()
            except Exception:
                return

            if line and not stop_paste.is_set():
                pasted.append(line)

        paste_thread = threading.Thread(target=read_pasted_url, daemon=True)
        paste_thread.start()

        try:
            while not callback_server.callback_response and not pasted:
                time.sleep(0.1)
        finally:
            stop_paste.set()
            callback_server.shutdown()
            thread.join()

        if callback_server.callback_response:
            return callback_server.callback_response

        return normalize_oauth_callback_url(
            pasted[0], allowed_schemes=("http", "https")
        )


class EvernoteOAuthDesktopHandler:
    """
    Desktop-client OAuth: browser redirects to evernote://... which we cannot catch.
    User pastes the full redirect URL into the terminal.
    """

    def __init__(self, oauth_client: "EvernoteOAuthClient") -> None:
        self.client = oauth_client

    def get_oauth_url(self) -> str:
        return self.client.get_authorize_url_desktop()

    def parse_redirect_url(self, redirect_url: str) -> str:
        """Validate a pasted evernote:// redirect URL and return its /path?query.

        Raises OAuthCallbackURLError for a paste that is wrong but can be retried
        (bad format, or a URL left over from another authorization attempt), and
        OAuthDeclinedError if the redirect reports that authorization was declined.
        """
        callback = normalize_oauth_callback_url(
            redirect_url, allowed_schemes=("evernote",)
        )
        self.client.check_callback_state(callback)
        return callback

    def exchange_token(self, callback: str) -> str:
        """Exchange a callback from parse_redirect_url for token bundle JSON."""
        return self.client.get_access_token(callback).to_json()


class EvernoteOAuthClient(EvernoteClientBase):
    def __init__(self, backend: str) -> None:
        super().__init__(backend=backend)

        self._session: OAuth2Session | None = None
        self._state: str | None = None

    def get_authorize_url_mcp(self, callback_url: str) -> str:
        mcp_client = register_mcp_client(callback_url)

        return self.get_authorize_url(mcp_client["client_id"], callback_url)

    def get_authorize_url_desktop(self) -> str:
        return self.get_authorize_url(DESKTOP_CLIENT_ID, DESKTOP_REDIRECT_URI)

    def get_authorize_url(self, client_id: str, callback_url: str) -> str:
        self._session = OAuth2Session(
            client_id=client_id,
            scope=OAUTH_SCOPES,
            redirect_uri=callback_url,
            pkce="S256",
        )

        authorization_url, state = self._session.authorization_url(
            EVERNOTE_AUTHORIZE_URL
        )
        self._state = str(state)

        return str(authorization_url)

    def check_callback_state(self, callback: str) -> None:
        """Reject a callback issued for a different authorization attempt.

        oauthlib would reject it too, but only during the token exchange, which
        callers treat as fatal; checking first lets the user paste again.
        """
        if not self._state:
            raise RuntimeError("Session used before initialization")

        state = parse_qs(urlparse(callback).query).get("state", [""])[0]
        if state != self._state:
            raise OAuthCallbackURLError(
                "Redirect URL does not belong to this login attempt"
                " (is it left over from an earlier run?)"
            )

    def get_access_token(self, callback_response_raw: str) -> OAuth2TokenBundle:
        if not self._session:
            raise RuntimeError("Session used before initialization")

        # need to add https because oauth checks it in is_secure_transport
        callback_response_raw = "https://localhost" + callback_response_raw

        try:
            token = self._session.fetch_token(
                EVERNOTE_TOKEN_URL,
                authorization_response=callback_response_raw,
                include_client_id=True,
            )
        except (OAuth2Error, ValueError) as e:
            raise OAuthDeclinedError(str(e)) from e

        return OAuth2TokenBundle.from_dict(token)


def clean_pasted_url(raw: str) -> str:
    """Strip surrounding whitespace and quotes from a pasted URL."""
    return raw.strip().strip('"').strip("'")


def normalize_oauth_callback_url(
    raw: str,
    allowed_schemes: Collection[str],
) -> str:
    """Normalize a pasted OAuth callback URL to /path?query form (no scheme/host).

    ``allowed_schemes`` restricts accepted URL schemes, e.g. ``("evernote",)`` for
    desktop OAuth or ``("http", "https")`` for MCP callback paste.
    """
    url = clean_pasted_url(raw)

    if not url:
        raise OAuthCallbackURLError("Empty callback URL")

    allowed = {scheme.lower() for scheme in allowed_schemes}
    preview = f"{raw[:120]}{'...' if len(raw) > 120 else ''}"
    schemes_txt = " or ".join(f"{scheme}://" for scheme in sorted(allowed))
    allows_http = "http" in allowed or "https" in allowed

    def bad_scheme_error() -> OAuthCallbackURLError:
        return OAuthCallbackURLError(
            f"Expected an {schemes_txt} redirect URL (got: {preview})"
        )

    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise OAuthCallbackURLError(f"Malformed redirect URL: {e}") from e

    scheme = (parsed.scheme or "").lower()

    # urlparse treats "localhost:10500/path" as scheme="localhost".
    if (
        scheme
        and scheme not in allowed
        and allows_http
        and "://" not in url.split("?", 1)[0]
    ):
        try:
            parsed = urlparse(f"http://{url}")
        except ValueError as e:
            raise OAuthCallbackURLError(f"Malformed redirect URL: {e}") from e
        scheme = (parsed.scheme or "").lower()

    params = parse_qs(parsed.query, keep_blank_values=True)

    # An OAuth error response means the user declined; retrying cannot help,
    # whatever URL form it was pasted in.
    if "error" in params:
        raise OAuthDeclinedError(_format_oauth_error(params))

    if not scheme:
        # Path-only form is only accepted for HTTP-style callbacks (MCP paste).
        if not (allows_http and url.startswith("/")):
            raise bad_scheme_error()
        path = parsed.path or ""
        query = parsed.query or ""
    elif scheme not in allowed:
        raise bad_scheme_error()
    else:
        path = parsed.path or ""
        query = parsed.query or ""

    if not params.get("code", [""])[0]:
        raise OAuthCallbackURLError(
            "Redirect URL is missing the authorization code parameter"
        )

    if not path.startswith("/"):
        path = f"/{path}" if path else "/"

    return f"{path}?{query}" if query else path


def _format_oauth_error(params: dict[str, list[str]]) -> str:
    error = params["error"][0] or "unknown error"
    description = params.get("error_description", [""])[0]
    return f"{error} ({description})" if description else error


def register_mcp_client(redirect_uri: str) -> dict[str, Any]:
    disc_response = requests.get(EVERNOTE_DISCOVERY_URL, timeout=30)
    disc_response.raise_for_status()
    metadata = disc_response.json()

    registration_endpoint = metadata.get("registration_endpoint")
    if not registration_endpoint:
        raise RuntimeError(
            "The authorization server does not support"
            " Dynamic Client Registration (DCR)."
        )

    registration_payload = {
        "client_name": MCP_NAME,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    reg_response = requests.post(
        registration_endpoint,
        json=registration_payload,
        headers=headers,
        timeout=30,
    )
    if reg_response.status_code not in (200, 201):
        raise RuntimeError(
            f"Registration failed [{reg_response.status_code}]: {reg_response.text}"
        )

    return reg_response.json()
