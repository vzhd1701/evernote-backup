import base64

import click
import pytest
from evernote.edam.error.ttypes import EDAMUserException

from evernote_backup import cli_app_auth, cli_app_util
from evernote_backup.cli_app_click_util import NaturalOrderGroup
from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.log_util import get_time_txt


def test_get_sync_client_token_expired_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_expired = True
    network_error_retry_count = 50
    max_chunk_results = 200
    fake_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_auth.get_sync_client(
            fake_token, "evernote", network_error_retry_count, max_chunk_results
        )
    assert str(excinfo.value) == "Authentication token expired or revoked!"


def test_get_sync_client_token_invalid_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_invalid = True
    network_error_retry_count = 50
    max_chunk_results = 200
    fake_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_auth.get_sync_client(
            fake_token, "evernote", network_error_retry_count, max_chunk_results
        )
    assert str(excinfo.value) == "Invalid authentication token!"


def test_get_sync_client_unexpected_error(mock_evernote_client):
    mock_evernote_client.fake_auth_verify_unexpected_error = True
    network_error_retry_count = 50
    max_chunk_results = 200
    fake_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    with pytest.raises(EDAMUserException):
        cli_app_auth.get_sync_client(
            fake_token, "evernote", network_error_retry_count, max_chunk_results
        )


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


@pytest.mark.parametrize(
    "time_seconds,time_txt",
    [
        (10, "0:10"),
        (65, "01:05"),
        (3605, "01:00:05"),
    ],
)
def test_cli_test_tty(time_seconds, time_txt):
    assert get_time_txt(time_seconds) == time_txt
