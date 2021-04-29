import logging
import os

import pytest

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
    logger_mock = mocker.patch("evernote_backup.cli.logger")
    mocker.patch("evernote_backup.cli.cli_app")

    if is_quiet:
        cli_invoker("--quiet", "init-db")
    else:
        cli_invoker("init-db")

    logger_mock.setLevel.assert_called_once_with(log_level_expected)


@pytest.mark.parametrize(
    "is_tty,log_format",
    [
        (False, "%(asctime)s | [%(levelname)s] | %(message)s"),
        (True, "%(message)s"),
    ],
)
def test_cli_test_tty(is_tty, log_format, cli_invoker, mocker, mock_output_to_terminal):
    mocker.patch("evernote_backup.cli.cli_app")

    logging_mock = mocker.patch("evernote_backup.cli.logging.basicConfig")
    mock_output_to_terminal.is_tty = is_tty

    cli_invoker("init-db")

    # only works in python >=38
    # assert logging_mock.call_args.kwargs["format"] == log_format
    assert logging_mock.call_args[-1]["format"] == log_format


def test_cli_program_error(mocker, caplog):
    cli_mock = mocker.patch("evernote_backup.cli.cli")
    cli_mock.side_effect = ProgramTerminatedError("test")

    with pytest.raises(SystemExit):
        cli_module.main()

    assert caplog.messages[0] == "test"


def test_cli_program_error_unexpected(mocker, caplog):
    cli_mock = mocker.patch("evernote_backup.cli.cli")
    cli_mock.side_effect = RuntimeError("test2")

    with pytest.raises(SystemExit):
        cli_module.main()

    assert "test2" in caplog.messages[0]
    assert "Traceback" in caplog.messages[0]


@pytest.mark.parametrize(
    "is_quiet,progress_output,is_tty",
    [
        (True, os.devnull, True),
        (False, None, True),
        (True, os.devnull, False),
        (False, os.devnull, False),
    ],
)
def test_silent_progress(is_quiet, progress_output, is_tty, cli_invoker, mocker):
    sys_mock = mocker.patch("evernote_backup.cli_app_util.sys")
    sys_mock.stdout.isatty.return_value = is_tty

    mocker.patch("evernote_backup.cli.logger")

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

    assert test_out == progress_output


def test_cli_main_import():
    from evernote_backup import __main__
