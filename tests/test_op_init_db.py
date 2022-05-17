from pathlib import Path

import pytest

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.note_storage import SqliteStorage


@pytest.mark.usefixtures("mock_evernote_client")
def test_init_db_existing_file(tmp_path, cli_invoker, fake_token):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    with pytest.raises(ProgramTerminatedError):
        cli_invoker("init-db", "--database", test_db_path, "--token", fake_token)


@pytest.mark.usefixtures("mock_evernote_client")
def test_init_db_existing_file_force(tmp_path, cli_invoker, fake_token):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    cli_invoker("init-db", "--database", test_db_path, "--token", fake_token, "--force")

    assert test_db_path.stat().st_size > 0


def test_init_db_new_file(tmp_path, cli_invoker, mock_evernote_client, fake_token):
    test_db_path = tmp_path / "test.db"

    mock_evernote_client.fake_user = "user1"

    cli_invoker("init-db", "--database", test_db_path, "--token", fake_token)

    storage = SqliteStorage(test_db_path)

    assert storage.config.get_config_value("USN") == "0"
    assert storage.config.get_config_value("DB_VERSION") == str(CURRENT_DB_VERSION)
    assert storage.config.get_config_value("auth_token") == fake_token
    assert storage.config.get_config_value("user") == "user1"
    assert storage.config.get_config_value("backend") == "evernote"


@pytest.mark.parametrize(
    "backend",
    ["evernote", "evernote:sandbox", "china", "china:sandbox"],
)
def test_init_db_new_file_backend(
    backend, tmp_path, cli_invoker, mock_evernote_client, fake_token
):
    test_db_path = tmp_path / "test.db"

    mock_evernote_client.fake_user = "user1"

    cli_invoker(
        "init-db",
        "--database",
        test_db_path,
        "--token",
        fake_token,
        "--backend",
        backend,
    )

    storage = SqliteStorage(test_db_path)

    assert storage.config.get_config_value("backend") == backend


def test_init_db_touch_token(cli_invoker, mocker):
    mocker.patch(
        "evernote_backup.cli_app.get_auth_token", side_effect=ProgramTerminatedError
    )

    with pytest.raises(ProgramTerminatedError):
        cli_invoker("init-db", "--database", "fake_db")


@pytest.mark.usefixtures("mock_output_to_terminal")
def test_oauth_login_china_error(cli_invoker, fake_storage, mock_evernote_client):
    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("init-db", "-d", "fake_db", "--oauth", "--backend", "china")
    assert "Yinxiang" in str(excinfo.value)
