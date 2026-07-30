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
    register_mcp_client,
)

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
