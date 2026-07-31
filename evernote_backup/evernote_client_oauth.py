import re
import threading
import time
from enum import IntEnum
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import urlparse

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
from evernote_backup.errors import OAuthDeclinedError
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

    def log_message(self, *args, **kwargs) -> None:  # type: ignore
        """Silencing server log"""


class StoppableHTTPServer(HTTPServer):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)

        self.callback_response: str = ""

    def run(self) -> None:
        try:  # noqa: WPS501
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
        """Complete OAuth code exchange and return token bundle JSON for storage."""
        bundle = self.client.get_access_token(self._wait_for_callback())
        return bundle.to_json()

    def _wait_for_callback(self) -> str:
        if is_inside_docker():
            server_param = ("0.0.0.0", self.server_port)  # noqa: S104
        else:
            server_param = (self.server_host, self.server_port)

        callback_server = StoppableHTTPServer(server_param, CallbackHandler)

        thread = threading.Thread(target=callback_server.run)
        thread.start()

        try:  # noqa: WPS501
            while not callback_server.callback_response:
                time.sleep(0.1)
        finally:
            callback_server.shutdown()
            thread.join()

        return callback_server.callback_response


class EvernoteOAuthDesktopHandler:
    """
    Desktop-client OAuth: browser redirects to evernote://... which we cannot catch.
    User pastes the full redirect URL into the terminal.
    """

    def __init__(self, oauth_client: "EvernoteOAuthClient") -> None:
        self.client = oauth_client

    def get_oauth_url(self) -> str:
        return self.client.get_authorize_url_desktop()

    def exchange_token(self, redirect_url: str) -> str:
        """Exchange pasted evernote:// redirect URL for token bundle JSON."""
        bundle = self.client.get_access_token(
            normalize_desktop_redirect_url(redirect_url)
        )
        return bundle.to_json()


class EvernoteOAuthClient(EvernoteClientBase):
    def __init__(self, backend: str) -> None:
        super().__init__(backend=backend)

        self._session: Optional[OAuth2Session] = None

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

        authorization_url, _state = self._session.authorization_url(
            EVERNOTE_AUTHORIZE_URL
        )

        return str(authorization_url)

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


def normalize_desktop_redirect_url(raw: str) -> str:
    url = raw.strip().strip('"').strip("'")

    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise OAuthDeclinedError(f"Malformed redirect URL: {e}")

    if parsed.scheme != "evernote":
        raise OAuthDeclinedError(
            "Expected an evernote:// redirect URL"
            f" (got: {raw[:120]}{'...' if len(raw) > 120 else ''})"
        )

    if "code=" not in parsed.query:
        raise OAuthDeclinedError(
            "Redirect URL is missing the authorization code parameter"
        )

    result = parsed._replace(scheme="", netloc="").geturl()
    return result


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
