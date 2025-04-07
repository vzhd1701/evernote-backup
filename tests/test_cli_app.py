import io
import logging

import pytest
from evernote.edam.error.ttypes import EDAMSystemException
from thrift.Thrift import TApplicationException

from evernote_backup import cli as cli_module
from evernote_backup.cli_app_util import ProgramTerminatedError, get_progress_output


@pytest.mark.parametrize(
    "is_quiet,log_level_expected",
    [
        (True, logging.CRITICAL),
        (False, logging.INFO),
    ],
)
def test_cli_quiet(is_quiet, log_level_expected, cli_invoker, mocker):
    mocker.patch("evernote_backup.cli.cli_app")

    if is_quiet:
        cli_invoker("--quiet", "init-db")
    else:
        cli_invoker("init-db")

    logger = logging.getLogger("evernote_backup")

    assert logger.getEffectiveLevel() == log_level_expected


@pytest.mark.parametrize(
    "is_verbose,log_level_expected",
    [
        (True, logging.DEBUG),
        (False, logging.INFO),
    ],
)
def test_cli_verbose(is_verbose, log_level_expected, cli_invoker, mocker):
    mocker.patch("evernote_backup.cli.cli_app")

    if is_verbose:
        cli_invoker("--verbose", "init-db")
    else:
        cli_invoker("init-db")

    logger = logging.getLogger("evernote_backup")

    assert logger.getEffectiveLevel() == log_level_expected


def test_cli_log_file(cli_invoker, tmp_path):
    log_file = tmp_path / "test.log"

    result = cli_invoker("--log", log_file, "init-db")

    log_content = log_file.read_text(encoding="utf-8")

    assert result.exit_code == 1
    assert log_file.exists()
    assert "Logging in to Evernote" in log_content


@pytest.mark.parametrize(
    "is_tty,log_format",
    [
        (False, "%(asctime)s | %(levelname)s | %(message)s"),
        (True, "%(message)s"),
    ],
)
def test_cli_test_tty(is_tty, log_format, cli_invoker, mocker, mock_output_to_terminal):
    mocker.patch("evernote_backup.cli.cli_app")

    mock_output_to_terminal.is_tty = is_tty

    cli_invoker("init-db")

    logger = logging.getLogger("evernote_backup")

    assert logger.handlers[0].formatter._fmt == log_format


def test_cli_program_error(cli_invoker, mocker):
    cli_app_mock = mocker.patch("evernote_backup.cli.cli_app")
    cli_app_mock.init_db.side_effect = ProgramTerminatedError("test error")

    result = cli_invoker("init-db")

    assert result.exit_code == 1
    assert "test error" in result.output


def test_cli_program_error_unexpected(cli_invoker, mocker):
    cli_app_mock = mocker.patch("evernote_backup.cli.cli_app")
    cli_app_mock.init_db.side_effect = RuntimeError("test2")

    result = cli_invoker("init-db")

    assert result.exit_code == 1
    assert "Unknown exception" in result.output
    assert "Traceback" in result.output
    assert "test2" in result.output


def test_cli_program_error_thrift(cli_invoker, mocker):
    cli_app_mock = mocker.patch("evernote_backup.cli.cli_app")
    cli_app_mock.init_db.side_effect = TApplicationException(message="test2")

    result = cli_invoker("init-db")

    assert result.exit_code == 1
    assert "Thrift exception: test2" in result.output
    assert "Traceback" in result.output


def test_cli_program_error_thrift_bytes(cli_invoker, mocker):
    cli_app_mock = mocker.patch("evernote_backup.cli.cli_app")
    cli_app_mock.init_db.side_effect = TApplicationException(message=b"test2")

    result = cli_invoker("init-db")

    assert result.exit_code == 1
    assert "Thrift exception: test2" in result.output
    assert "Traceback" in result.output


def test_cli_program_error_unexpected_edam(cli_invoker, mocker):
    cli_app_mock = mocker.patch("evernote_backup.cli.cli_app")
    cli_app_mock.init_db.side_effect = EDAMSystemException(errorCode=100)

    result = cli_invoker("init-db")

    assert result.exit_code == 1
    assert "EDAMSystemException" in result.output
    assert "Traceback" in result.output


def test_cli_program_error_rate_limit(cli_invoker, mocker):
    cli_app_mock = mocker.patch("evernote_backup.cli.cli_app")
    cli_app_mock.init_db.side_effect = EDAMSystemException(
        errorCode=19, rateLimitDuration=10
    )

    result = cli_invoker("init-db")

    assert result.exit_code == 1
    assert "Rate limit reached" in result.output


@pytest.mark.parametrize(
    "is_quiet,progress_output,is_tty",
    [
        (True, "StringIO", True),
        (False, None, True),
        (True, "StringIO", False),
        (False, "StringIO", False),
    ],
)
def test_silent_progress(is_quiet, progress_output, is_tty, cli_invoker, mocker):
    sys_mock = mocker.patch("evernote_backup.cli_app_util.sys")
    sys_mock.stdout.isatty.return_value = is_tty

    test_out = None

    def test_output(*a, **kw):
        nonlocal test_out
        test_out = get_progress_output()

    init_mock = mocker.patch("evernote_backup.cli.cli_app.init_db")
    init_mock.side_effect = test_output

    if is_quiet:
        cli_invoker("--quiet", "init-db")
    else:
        cli_invoker("init-db")

    if progress_output == "StringIO":
        assert isinstance(test_out, io.StringIO)
    else:
        assert test_out == progress_output


def test_cli_main_call(mocker):
    mocker.patch("evernote_backup.cli.cli")
    cli_module.main()


def test_cli_main_import():
    from evernote_backup import __main__
