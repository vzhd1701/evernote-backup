import os

import pytest
import requests

from evernote_backup.config import MCP_NAME
from evernote_backup.config_defaults import EVERNOTE_DISCOVERY_URL
from evernote_backup.errors import OAuthDeclinedError
from evernote_backup.evernote_client_oauth import (
    CallbackHandler,
    EvernoteOAuthCallbackHandler,
    EvernoteOAuthClient,
    HTTPCode,
    normalize_oauth_callback_url,
    register_mcp_client,
)

MCP_SCHEMES = ("http", "https")
DESKTOP_SCHEMES = ("evernote",)

FAKE_OAUTH_PORT = 10500
FAKE_OAUTH_HOST = "localhost"
FAKE_REDIRECT_URI = f"http://{FAKE_OAUTH_HOST}:{FAKE_OAUTH_PORT}/oauth_callback"
FAKE_REGISTRATION_ENDPOINT = "https://accounts.evernote.com/auth/register"


@pytest.fixture
def mock_evernote_oauth_client(mock_oauth_client):
    return EvernoteOAuthClient(backend="evernote")


def test_get_auth_token_before_init(mock_oauth_client, mock_evernote_oauth_client):
    with pytest.raises(RuntimeError) as e:
        mock_evernote_oauth_client.get_access_token("test_response")

    assert e.value.args[0] == "Session used before initialization"


@pytest.mark.usefixtures("mock_oauth_http_server")
def test_get_auth_token(mock_oauth_client, mock_evernote_oauth_client):
    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )
    oauth_handler.get_oauth_url()

    test_token = oauth_handler.wait_for_token()

    assert test_token == mock_oauth_client.token_bundle.to_json()


def test_server_no_docker(
    mock_oauth_client, mock_evernote_oauth_client, mock_oauth_http_server, mocker
):
    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )
    oauth_handler.get_oauth_url()

    oauth_handler.wait_for_token()

    mock_oauth_http_server.assert_any_call(
        (FAKE_OAUTH_HOST, FAKE_OAUTH_PORT), mocker.ANY
    )


def test_server_yes_docker(
    mock_oauth_client, mock_evernote_oauth_client, mock_oauth_http_server, mocker
):
    os.environ["INSIDE_DOCKER_CONTAINER"] = "1"

    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )
    oauth_handler.get_oauth_url()

    oauth_handler.wait_for_token()

    mock_oauth_http_server.assert_any_call(("0.0.0.0", FAKE_OAUTH_PORT), mocker.ANY)

    del os.environ["INSIDE_DOCKER_CONTAINER"]


@pytest.mark.usefixtures("mock_oauth_http_server")
def test_get_auth_token_url(mock_oauth_client, mock_evernote_oauth_client):
    expected_url = "https://accounts.evernote.com/auth/authorize?response_type=code&client_id=3FE74DA6-ABC8-4E20-9940-28D589D4E808&redirect_uri=http%3A%2F%2Flocalhost%3A10500%2Foauth_callback&scope=openid+profile+mono_authn_token+email+offline_access&state="
    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )

    url = oauth_handler.get_oauth_url()

    assert url.startswith(expected_url)


@pytest.mark.usefixtures("mock_oauth_http_server")
def test_get_auth_token_declined_bad_response(
    mock_oauth_client, mock_evernote_oauth_client
):
    mock_oauth_client.fake_bad_fetch_token_response = True

    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )
    oauth_handler.get_oauth_url()

    with pytest.raises(OAuthDeclinedError):
        oauth_handler.wait_for_token()


def test_get_auth_token_via_paste(
    mock_oauth_client, mock_evernote_oauth_client, mocker
):
    mock_server = mocker.patch(
        "evernote_backup.evernote_client_oauth.StoppableHTTPServer"
    )
    mock_server.return_value.callback_response = ""
    mock_server.return_value.run.side_effect = lambda: None

    pasted_url = (
        f"http://{FAKE_OAUTH_HOST}:{FAKE_OAUTH_PORT}"
        f"{mock_oauth_client.fake_callback_response}\n"
    )
    mocker.patch("sys.stdin.readline", return_value=pasted_url)

    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )
    oauth_handler.get_oauth_url()

    test_token = oauth_handler.wait_for_token()

    assert test_token == mock_oauth_client.token_bundle.to_json()


def test_exchange_token_via_paste(mock_oauth_client, mock_evernote_oauth_client):
    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )
    oauth_handler.get_oauth_url()

    pasted_url = (
        f"http://{FAKE_OAUTH_HOST}:{FAKE_OAUTH_PORT}"
        f"{mock_oauth_client.fake_callback_response}"
    )
    test_token = oauth_handler.exchange_token(pasted_url)

    assert test_token == mock_oauth_client.token_bundle.to_json()


def test_get_auth_token_interrupted(
    mock_oauth_client,
    mock_evernote_oauth_client,
    mocker,
):
    mocker.patch(
        "evernote_backup.evernote_client_oauth.StoppableHTTPServer.serve_forever"
    )
    mocker.patch("evernote_backup.evernote_client_oauth.StoppableHTTPServer.shutdown")
    mocker.patch(
        "evernote_backup.evernote_client_oauth.time.sleep",
        side_effect=KeyboardInterrupt,
    )

    oauth_handler = EvernoteOAuthCallbackHandler(
        mock_evernote_oauth_client, FAKE_OAUTH_PORT, FAKE_OAUTH_HOST
    )
    oauth_handler.get_oauth_url()

    with pytest.raises(KeyboardInterrupt):
        oauth_handler.wait_for_token()


def test_callback_handler_bad_url(mocker):
    mock_instance = mocker.MagicMock()
    mock_instance.path = "/fake_page"

    CallbackHandler.do_GET(mock_instance)

    mock_instance.send_response.assert_called_once_with(HTTPCode.NOT_FOUND)


def test_callback_handler(mocker):
    mock_instance = mocker.MagicMock()
    mock_instance.path = "/oauth_callback?test_param=test"

    CallbackHandler.do_GET(mock_instance)

    assert mock_instance.server.callback_response == mock_instance.path
    mock_instance.send_response.assert_called_once_with(HTTPCode.OK)


@pytest.mark.parametrize(
    ("raw", "allowed", "expected"),
    [
        (
            "http://localhost:10500/oauth_callback?code=abc&state=xyz",
            MCP_SCHEMES,
            "/oauth_callback?code=abc&state=xyz",
        ),
        (
            "https://localhost:10500/oauth_callback?code=abc&state=xyz",
            MCP_SCHEMES,
            "/oauth_callback?code=abc&state=xyz",
        ),
        (
            "HTTP://localhost:10500/oauth_callback?code=abc",
            MCP_SCHEMES,
            "/oauth_callback?code=abc",
        ),
        (
            "/oauth_callback?code=abc&state=xyz",
            MCP_SCHEMES,
            "/oauth_callback?code=abc&state=xyz",
        ),
        (
            "localhost:10500/oauth_callback?code=abc&state=xyz",
            MCP_SCHEMES,
            "/oauth_callback?code=abc&state=xyz",
        ),
        (
            '  "http://localhost:10500/oauth_callback?code=abc&state=xyz"  ',
            MCP_SCHEMES,
            "/oauth_callback?code=abc&state=xyz",
        ),
        (
            "  'https://localhost/oauth_callback?code=abc'  ",
            MCP_SCHEMES,
            "/oauth_callback?code=abc",
        ),
        (
            "http://localhost?code=abc",
            MCP_SCHEMES,
            "/?code=abc",
        ),
        (
            "evernote://www.evernote.com/auth/redirect?code=test&state=test",
            DESKTOP_SCHEMES,
            "/auth/redirect?code=test&state=test",
        ),
        (
            "EVERNOTE://www.evernote.com/auth/redirect?code=test",
            DESKTOP_SCHEMES,
            "/auth/redirect?code=test",
        ),
        (
            "evernote://www.evernote.com/auth/redirect?code=test",
            ("Evernote",),
            "/auth/redirect?code=test",
        ),
    ],
)
def test_normalize_oauth_callback_url_valid(raw, allowed, expected):
    assert normalize_oauth_callback_url(raw, allowed) == expected


def test_normalize_oauth_callback_url_empty():
    with pytest.raises(OAuthDeclinedError, match="Empty callback URL"):
        normalize_oauth_callback_url("   ", MCP_SCHEMES)


@pytest.mark.parametrize(
    ("raw", "allowed", "match"),
    [
        (
            "http://localhost:10500/oauth_callback?state=xyz",
            MCP_SCHEMES,
            "authorization code",
        ),
        (
            "/oauth_callback?state=xyz",
            MCP_SCHEMES,
            "authorization code",
        ),
        (
            "localhost:10500/oauth_callback?state=xyz",
            MCP_SCHEMES,
            "authorization code",
        ),
        (
            "evernote://www.evernote.com/auth/redirect?state=test",
            DESKTOP_SCHEMES,
            "authorization code",
        ),
        (
            "not-a-url",
            MCP_SCHEMES,
            "Expected an http",
        ),
        (
            "ftp://example.com/oauth_callback?code=abc",
            MCP_SCHEMES,
            "Expected an http",
        ),
        (
            "http://localhost:10500/oauth_callback?code=abc",
            DESKTOP_SCHEMES,
            "Expected an evernote://",
        ),
        (
            "/auth/redirect?code=test&state=test",
            DESKTOP_SCHEMES,
            "Expected an evernote://",
        ),
        (
            "localhost:10500/oauth_callback?code=abc",
            DESKTOP_SCHEMES,
            "Expected an evernote://",
        ),
        (
            "evernote://www.evernote.com/auth/redirect?code=test",
            MCP_SCHEMES,
            "Expected an http",
        ),
    ],
)
def test_normalize_oauth_callback_url_invalid(raw, allowed, match):
    with pytest.raises(OAuthDeclinedError, match=match):
        normalize_oauth_callback_url(raw, allowed)


def test_normalize_oauth_callback_url_long_preview_truncated():
    long_tail = "x" * 200
    raw = f"ftp://example.com/oauth_callback?code=abc&junk={long_tail}"

    with pytest.raises(OAuthDeclinedError, match=r"got: .+\.\.\.") as exc_info:
        normalize_oauth_callback_url(raw, MCP_SCHEMES)

    message = str(exc_info.value)
    assert "..." in message
    assert long_tail not in message


def test_normalize_oauth_callback_url_malformed_urlparse(mocker):
    mocker.patch(
        "evernote_backup.evernote_client_oauth.urlparse",
        side_effect=ValueError("bad url"),
    )

    with pytest.raises(OAuthDeclinedError, match="Malformed redirect URL: bad url"):
        normalize_oauth_callback_url(
            "http://localhost/oauth_callback?code=abc", MCP_SCHEMES
        )


def test_normalize_oauth_callback_url_malformed_host_without_scheme(mocker):
    real_urlparse = __import__("urllib.parse", fromlist=["urlparse"]).urlparse

    def fake_urlparse(value):
        if value.startswith("http://"):
            raise ValueError("bad host form")
        return real_urlparse(value)

    mocker.patch(
        "evernote_backup.evernote_client_oauth.urlparse",
        side_effect=fake_urlparse,
    )

    with pytest.raises(
        OAuthDeclinedError, match="Malformed redirect URL: bad host form"
    ):
        normalize_oauth_callback_url(
            "localhost:10500/oauth_callback?code=abc", MCP_SCHEMES
        )


def test_normalize_oauth_callback_url_adds_leading_slash(mocker):
    from urllib.parse import ParseResult

    mocker.patch(
        "evernote_backup.evernote_client_oauth.urlparse",
        return_value=ParseResult(
            scheme="http",
            netloc="localhost",
            path="oauth_callback",
            params="",
            query="code=abc&state=xyz",
            fragment="",
        ),
    )

    assert (
        normalize_oauth_callback_url("http://ignored", MCP_SCHEMES)
        == "/oauth_callback?code=abc&state=xyz"
    )


def test_register_mcp_client_success(requests_mock):
    expected_client = {"client_id": "test-client-id", "client_name": MCP_NAME}

    requests_mock.get(
        EVERNOTE_DISCOVERY_URL,
        json={"registration_endpoint": FAKE_REGISTRATION_ENDPOINT},
    )
    requests_mock.post(
        FAKE_REGISTRATION_ENDPOINT, json=expected_client, status_code=200
    )

    result = register_mcp_client(FAKE_REDIRECT_URI)

    assert result == expected_client
    assert requests_mock.last_request.json() == {
        "client_name": MCP_NAME,
        "redirect_uris": [FAKE_REDIRECT_URI],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    assert requests_mock.last_request.headers["Content-Type"] == "application/json"


def test_register_mcp_client_discovery_http_error(requests_mock):
    requests_mock.get(EVERNOTE_DISCOVERY_URL, status_code=503, reason="Server Error")

    with pytest.raises(requests.HTTPError):
        register_mcp_client(FAKE_REDIRECT_URI)

    assert not requests_mock.request_history[1:]  # only the GET happened, no POST


def test_register_mcp_client_missing_registration_endpoint(requests_mock):
    requests_mock.get(EVERNOTE_DISCOVERY_URL, json={"issuer": "https://example.com"})

    with pytest.raises(RuntimeError, match="Dynamic Client Registration"):
        register_mcp_client(FAKE_REDIRECT_URI)


@pytest.mark.parametrize("status_code", [400, 401, 403, 500])
def test_register_mcp_client_registration_failed(requests_mock, status_code):
    error_body = '{"error":"invalid_redirect_uri"}'
    requests_mock.get(
        EVERNOTE_DISCOVERY_URL,
        json={"registration_endpoint": FAKE_REGISTRATION_ENDPOINT},
    )
    requests_mock.post(
        FAKE_REGISTRATION_ENDPOINT, text=error_body, status_code=status_code
    )

    with pytest.raises(RuntimeError, match=f"Registration failed \\[{status_code}\\]"):
        register_mcp_client(FAKE_REDIRECT_URI)
