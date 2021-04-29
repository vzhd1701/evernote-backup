import base64

import click
import pytest
from evernote.edam.error.ttypes import EDAMUserException

from evernote_backup import cli_app_auth, cli_app_util
from evernote_backup.cli_app_util import NaturalOrderGroup, ProgramTerminatedError


def test_get_sync_client_token_expired_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_expired = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_auth.get_sync_client("fake_token", "evernote")
    assert str(excinfo.value) == "Authentication token expired or revoked!"


def test_get_sync_client_token_invalid_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_invalid = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_auth.get_sync_client("fake_token", "evernote")
    assert str(excinfo.value) == "Invalid authentication token!"


def test_get_sync_client_unexpected_error(mock_evernote_client):
    mock_evernote_client.fake_auth_verify_unexpected_error = True

    with pytest.raises(EDAMUserException):
        cli_app_auth.get_sync_client("fake_token", "evernote")


def test_unscrambler():
    test_data = base64.b64encode(b":8:<2&00000")
    expected = ["12345", "54321"]

    result_data = cli_app_util.unscramble(test_data)

    assert result_data == expected


def test_natural_order_group():
    @click.group(cls=NaturalOrderGroup)
    def test_cli():
        """pass"""

    @test_cli.command()
    def test_command1():
        """pass"""

    @test_cli.command()
    def test_command3():
        """pass"""

    @test_cli.command()
    def test_command2():
        """pass"""

    assert list(test_cli.list_commands(None)) == [
        "test-command1",
        "test-command3",
        "test-command2",
    ]

    pass
