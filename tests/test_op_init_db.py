from pathlib import Path

import pytest

from evernote_backup.errors import ProgramTerminatedError
from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.note_storage import SqliteStorage
from evernote_backup.desktop_session import DesktopSession
from evernote_backup.token_util import OAuth2TokenBundle


@pytest.mark.usefixtures("mock_evernote_client")
def test_init_db_existing_file(tmp_path, cli_invoker, fake_token):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    result = cli_invoker("init-db", "--database", test_db_path, "--token", fake_token)

    assert result.exit_code == 1
    assert "Database already exists" in result.output


@pytest.mark.usefixtures("mock_evernote_client")
def test_init_db_existing_file_force(tmp_path, cli_invoker, fake_token):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    result = cli_invoker(
        "init-db", "--database", test_db_path, "--token", fake_token, "--force"
    )

    assert result.exit_code == 0
    assert test_db_path.stat().st_size > 0


def test_init_db_new_file(tmp_path, cli_invoker, mock_evernote_client, fake_token):
    test_db_path = tmp_path / "test.db"

    mock_evernote_client.fake_user = "user1"

    result = cli_invoker("init-db", "--database", test_db_path, "--token", fake_token)

    storage = SqliteStorage(test_db_path)

    assert result.exit_code == 0
    assert storage.config.get_config_value("USN") == "0"
    assert storage.config.get_config_value("DB_VERSION") == str(CURRENT_DB_VERSION)
    assert storage.config.get_config_value("auth_token") == fake_token
    assert storage.config.get_config_value("user") == "user1"
    assert storage.config.get_config_value("backend") == "evernote"


@pytest.mark.parametrize(
    "backend",
    ["evernote", "china", "china:sandbox"],
)
def test_init_db_new_file_backend(
    backend, tmp_path, cli_invoker, mock_evernote_client, fake_token
):
    test_db_path = tmp_path / "test.db"

    mock_evernote_client.fake_user = "user1"

    result = cli_invoker(
        "init-db",
        "--database",
        test_db_path,
        "--token",
        fake_token,
        "--backend",
        backend,
    )

    storage = SqliteStorage(test_db_path)

    assert result.exit_code == 0
    assert storage.config.get_config_value("backend") == backend


def test_init_db_touch_token(cli_invoker, mocker):
    mocker.patch(
        "evernote_backup.cli_app.get_auth_token",
        side_effect=ProgramTerminatedError("test error"),
    )

    result = cli_invoker("init-db", "--database", "fake_db")

    assert result.exit_code == 1
    assert "test error" in result.output


@pytest.mark.usefixtures("mock_evernote_client")
def test_init_db_oauth_import(
    tmp_path, cli_invoker, mock_oauth_client, mocker, fake_token_jwt
):
    mocker.patch("evernote_backup.cli_app_auth_oauth.sys.platform", "win32")

    test_db_path = tmp_path / "test.db"
    refresh_token = OAuth2TokenBundle.from_json(fake_token_jwt).refresh_token

    mocker.patch(
        "evernote_backup.cli_app_auth_oauth.extract_token",
        return_value=DesktopSession(
            user_id="151636",
            username="testuser",
            email="test@example.com",
            s_token="S=s1:U=1:E=1:C=1:P=1:A=a:V=2:H=h",
            shard="s1",
            host="www.evernote.com",
            jwt_refresh=refresh_token,
        ),
    )

    result = cli_invoker(
        "init-db", "--database", test_db_path, "--oauth-method", "import"
    )

    storage = SqliteStorage(test_db_path)

    assert result.exit_code == 0
    assert "Imported OAuth refresh token" in result.output
    assert storage.config.get_config_value("auth_token") == fake_token_jwt
