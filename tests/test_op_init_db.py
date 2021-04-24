from pathlib import Path

import pytest

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.note_storage import SqliteStorage
from tests.utils import FAKE_TOKEN, cli_invoker, mock_evernote_client


@pytest.mark.usefixtures("mock_evernote_client")
def test_init_db_existing_file(tmp_path, cli_invoker):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    with pytest.raises(ProgramTerminatedError):
        cli_invoker("init-db", "--database", test_db_path, "--token", FAKE_TOKEN)


@pytest.mark.usefixtures("mock_evernote_client")
def test_init_db_existing_file_force(tmp_path, cli_invoker):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    cli_invoker("init-db", "--database", test_db_path, "--token", FAKE_TOKEN, "--force")

    assert test_db_path.stat().st_size > 0


def test_init_db_new_file(tmp_path, cli_invoker, mock_evernote_client):
    test_db_path = str(tmp_path / "test.db")

    mock_evernote_client.fake_user = "user1"

    cli_invoker("init-db", "--database", test_db_path, "--token", FAKE_TOKEN)

    storage = SqliteStorage(test_db_path)

    assert storage.config.get_config_value("auth_token") == FAKE_TOKEN
    assert storage.config.get_config_value("user") == "user1"
    assert storage.config.get_config_value("backend") == "evernote"


@pytest.mark.parametrize(
    "backend",
    ["evernote", "evernote:sandbox", "china", "china:sandbox"],
)
def test_init_db_new_file_backend(backend, tmp_path, cli_invoker, mock_evernote_client):
    test_db_path = str(tmp_path / "test.db")

    mock_evernote_client.fake_user = "user1"

    cli_invoker(
        "init-db",
        "--database",
        test_db_path,
        "--token",
        FAKE_TOKEN,
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
