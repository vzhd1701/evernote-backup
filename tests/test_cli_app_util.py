import base64
from datetime import datetime, timezone

import click
import pytest
from evernote.edam.error.ttypes import EDAMUserException

from evernote_backup import cli_app_auth, cli_app_util
from evernote_backup.cli_app_click_util import NaturalOrderGroup
from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.log_util import get_time_txt
from evernote_backup.token_util import EvernoteToken


def test_get_sync_client_token_expired_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_expired = True
    network_error_retry_count = 50
    max_chunk_results = 200
    fake_token = "S=s1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_auth.get_sync_client(
            auth_token=fake_token,
            backend="evernote",
            network_error_retry_count=network_error_retry_count,
            max_chunk_results=max_chunk_results,
            is_jwt_needed=False,
            use_system_ssl_ca=False,
        )
    assert str(excinfo.value) == "Authentication token expired or revoked!"


def test_get_sync_client_token_invalid_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_invalid = True
    network_error_retry_count = 50
    max_chunk_results = 200
    fake_token = "S=s1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_app_auth.get_sync_client(
            auth_token=fake_token,
            backend="evernote",
            network_error_retry_count=network_error_retry_count,
            max_chunk_results=max_chunk_results,
            is_jwt_needed=False,
            use_system_ssl_ca=False,
        )
    assert str(excinfo.value) == "Invalid authentication token!"


def test_get_sync_client_unexpected_error(mock_evernote_client):
    mock_evernote_client.fake_auth_verify_unexpected_error = True
    network_error_retry_count = 50
    max_chunk_results = 200
    fake_token = "S=s1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    with pytest.raises(EDAMUserException):
        cli_app_auth.get_sync_client(
            auth_token=fake_token,
            backend="evernote",
            network_error_retry_count=network_error_retry_count,
            max_chunk_results=max_chunk_results,
            is_jwt_needed=False,
            use_system_ssl_ca=False,
        )


def test_unscrambler():
    test_data = base64.b64encode(b":8:<2&00000")
    expected = ("12345", "54321")

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


def test_evernote_token_parser():
    test_token_str = "S=s200:U=ff:E=ffffaa:C=ffffbb:P=1:A=test222:V=2:H=ff"

    expected_token = EvernoteToken(
        shard="s200",
        user_id=255,
        creation=datetime(1970, 1, 1, 4, 39, 37, 147000, tzinfo=timezone.utc),
        expiration=datetime(1970, 1, 1, 4, 39, 37, 130000, tzinfo=timezone.utc),
        agent="test222",
        shard_id=200,
        raw=test_token_str,
    )

    result_token = EvernoteToken.from_string(test_token_str)

    assert result_token == expected_token


def test_evernote_token_parser_bad_format():
    test_token_str = "S=s200:U=ff:E=ffffaa:P=1:A=test222:V=2"

    with pytest.raises(ValueError) as e:
        EvernoteToken.from_string(test_token_str)

    assert "Invalid token format" in str(e.value)


def test_evernote_token_parser_extra_fields():
    test_token_str = "S=s31:U=aabbcc:E=196586d29d4:C=19658363b54:P=100:N=bbbbb:R=aaaaaa:A=yx-w32-xauth-new:V=2:H=aaaaaa"

    expected_token = EvernoteToken(
        shard="s31",
        user_id=11189196,
        creation=datetime(2025, 4, 21, 11, 57, 51, 316000, tzinfo=timezone.utc),
        expiration=datetime(2025, 4, 21, 12, 57, 51, 316000, tzinfo=timezone.utc),
        agent="yx-w32-xauth-new",
        shard_id=31,
        raw=test_token_str,
    )

    result_token = EvernoteToken.from_string(test_token_str)

    assert result_token == expected_token


@pytest.mark.parametrize(
    "time_set,time_expected",
    [
        ("111111000", "1970-02-23 00:34:58 (3 days left)"),
        ("101111000", "1970-02-19 22:01:02 (5 hours left)"),
        ("100011000", "1970-02-19 17:03:56 (1 minute left)"),
        ("100001000", "1970-02-19 17:02:51 (4 seconds left)"),
        ("ffffffff", "1970-02-19 17:02:47 (0 seconds left)"),
        ("ffffaaaa", "1970-02-19 17:02:25 (22 seconds ago)"),
        ("fffaaaaa", "1970-02-19 16:56:57 (6 minutes ago)"),
        ("ffaaaaaa", "1970-02-19 15:29:34 (2 hours ago)"),
        ("aaaaaaaa", "1970-02-03 03:21:51 (16 days ago)"),
    ],
)
def test_evernote_token_parser_expiration_human(time_set, time_expected, mocker):
    FAKE_TIME = datetime.fromtimestamp(int("ffffffff", 16) / 1000, tz=timezone.utc)

    class fakedatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return FAKE_TIME

    mocker.patch("evernote_backup.token_util.datetime", new=fakedatetime)

    test_token_str = f"S=s200:U=ff:E={time_set}:C=ffffbb:P=1:A=test222:V=2:H=ff"

    result_token = EvernoteToken.from_string(test_token_str)

    assert result_token.expiration_human == time_expected
