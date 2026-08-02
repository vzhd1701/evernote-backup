from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import requests
from oauthlib.oauth2 import OAuth2Error

from evernote_backup.config_defaults import EVERNOTE_API_USERS_ME_URL
from evernote_backup.errors import ProgramTerminatedError
from evernote_backup.token_util import (
    fetch_oauth_current_user,
    resolve_auth_token,
    verify_and_log_oauth_session,
)


def test_resolve_auth_token_legacy_monolith(fake_token):
    resolved = resolve_auth_token(fake_token)

    assert resolved.monolith_token == fake_token
    assert resolved.jwt_token is None
    assert resolved.auth_for_storage == fake_token
    assert resolved.updated is False


def test_resolve_auth_token_bundle_verifies_users_me(mock_oauth_client, caplog):
    bundle = mock_oauth_client.token_bundle

    with caplog.at_level("INFO"):
        resolved = resolve_auth_token(bundle.to_json())

    assert resolved.jwt_token == bundle.access_token
    assert resolved.monolith_token == bundle.monolith_token
    assert f"user ID {mock_oauth_client.user_id}" in caplog.text
    assert f"username {mock_oauth_client.user_name}" in caplog.text
    assert f"email {mock_oauth_client.user_email}" in caplog.text
    assert "Login session active since" in caplog.text
    assert "ago" in caplog.text


def test_resolve_auth_token_refresh_jwt_verifies_users_me(mock_oauth_client, caplog):
    refresh_token = mock_oauth_client.token_bundle.refresh_token

    with caplog.at_level("INFO"):
        resolved = resolve_auth_token(refresh_token)

    assert resolved.updated is True
    assert resolved.jwt_token == mock_oauth_client.token_bundle.access_token
    assert f"user ID {mock_oauth_client.user_id}" in caplog.text
    assert "Login session active since" in caplog.text


def test_resolve_auth_token_users_me_failure(mock_oauth_client):
    mock_oauth_client.fake_users_me_error = True
    bundle = mock_oauth_client.token_bundle

    with pytest.raises(ProgramTerminatedError, match="users/me"):
        resolve_auth_token(bundle.to_json())


def test_oauth2_token_bundle_auth_time(mock_oauth_client):
    bundle = mock_oauth_client.token_bundle
    expected = datetime.fromtimestamp(mock_oauth_client.auth_time, tz=timezone.utc)

    assert bundle.auth_time == expected
    assert bundle.auth_time_human.startswith(expected.strftime("%Y-%m-%d %H:%M:%S"))
    assert "ago" in bundle.auth_time_human


def test_fetch_oauth_current_user_uses_access_token(mock_oauth_client, mocker):
    bundle = mock_oauth_client.token_bundle
    session_cls = mocker.patch("evernote_backup.token_util.OAuth2Session")
    response = MagicMock()
    response.json.return_value = mock_oauth_client.users_me
    session_cls.return_value.get.return_value = response

    result = fetch_oauth_current_user(bundle)

    assert result == mock_oauth_client.users_me
    session_cls.assert_called_once_with(
        client_id=mock_oauth_client.client_id,
        token={
            "access_token": bundle.access_token,
            "token_type": "Bearer",
        },
    )
    session_cls.return_value.get.assert_called_once_with(
        EVERNOTE_API_USERS_ME_URL, timeout=30
    )


def test_fetch_oauth_current_user_http_error(mock_oauth_client, mocker):
    bundle = mock_oauth_client.token_bundle
    session_cls = mocker.patch("evernote_backup.token_util.OAuth2Session")
    session_cls.return_value.get.side_effect = requests.HTTPError("401")

    with pytest.raises(ProgramTerminatedError, match="Failed to verify"):
        fetch_oauth_current_user(bundle)


def test_fetch_oauth_current_user_oauth_error(mock_oauth_client, mocker):
    bundle = mock_oauth_client.token_bundle
    session_cls = mocker.patch("evernote_backup.token_util.OAuth2Session")
    session_cls.return_value.get.side_effect = OAuth2Error("bad token")

    with pytest.raises(ProgramTerminatedError, match="Failed to verify"):
        fetch_oauth_current_user(bundle)


def test_fetch_oauth_current_user_unexpected_format(mock_oauth_client, mocker):
    bundle = mock_oauth_client.token_bundle
    session_cls = mocker.patch("evernote_backup.token_util.OAuth2Session")
    response = MagicMock()
    response.json.return_value = ["not", "a", "dict"]
    session_cls.return_value.get.return_value = response

    with pytest.raises(ProgramTerminatedError, match="unexpected response format"):
        fetch_oauth_current_user(bundle)


def test_verify_and_log_oauth_session_logs_auth_time_human(
    mock_oauth_client, caplog, mocker
):
    mocker.patch(
        "evernote_backup.token_util.fetch_oauth_current_user",
        return_value=mock_oauth_client.users_me,
    )
    bundle = mock_oauth_client.token_bundle

    with caplog.at_level("INFO"):
        verify_and_log_oauth_session(bundle)

    assert f"Login session active since {bundle.auth_time_human}" in caplog.text


def test_verify_and_log_oauth_session_missing_user_fields(
    mock_oauth_client, caplog, mocker
):
    mocker.patch(
        "evernote_backup.token_util.fetch_oauth_current_user",
        return_value={},
    )

    with caplog.at_level("INFO"):
        verify_and_log_oauth_session(mock_oauth_client.token_bundle)

    assert "user ID unknown" in caplog.text
    assert "username unknown" in caplog.text
    assert "email unknown" in caplog.text
