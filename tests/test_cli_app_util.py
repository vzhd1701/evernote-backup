import pytest
from evernote.edam.error.ttypes import EDAMUserException

from evernote_backup import cli_app_util
from evernote_backup.cli_app_util import ProgramTerminatedError
from tests.utils import mock_evernote_client


def test_get_sync_client_token_expired_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_expired = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_util.get_sync_client("fake_token", "evernote")
    assert str(excinfo.value) == "Authentication token expired or revoked!"


def test_get_sync_client_token_invalid_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_invalid = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_util.get_sync_client("fake_token", "evernote")
    assert str(excinfo.value) == "Invalid authentication token!"


def test_get_sync_client_unexpected_error(mock_evernote_client):
    mock_evernote_client.fake_auth_verify_unexpected_error = True

    with pytest.raises(EDAMUserException):
        cli_app_util.get_sync_client("fake_token", "evernote")
