import pytest
from evernote.edam.error.ttypes import EDAMUserException

from evernote_backup.cli_app_util import ProgramTerminatedError


@pytest.fixture()
def mock_click_prompt(mocker):
    click_mock = mocker.patch("evernote_backup.cli_app_util.click.prompt")
    click_mock.fake_input = None
    click_mock.side_effect = lambda *a, **kw: click_mock.fake_input

    return click_mock


@pytest.mark.usefixtures("mock_evernote_client")
@pytest.mark.usefixtures("fake_init_db")
def test_token_refresh(fake_storage, cli_invoker):
    fake_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    cli_invoker("reauth", "--database", "fake_db", "--token", fake_token)

    assert fake_storage.config.get_config_value("auth_token") == fake_token


@pytest.mark.usefixtures("fake_init_db")
def test_user_mismatch_error(fake_storage, cli_invoker, mock_evernote_client):
    fake_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    mock_evernote_client.fake_user = "user1"
    fake_storage.config.set_config_value("user", "user2")

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "--database", "fake_db", "--token", fake_token)
    assert "Each user must use different database file" in str(excinfo.value)


@pytest.mark.usefixtures("mock_evernote_client")
@pytest.mark.usefixtures("fake_init_db")
def test_no_username_error(fake_storage, cli_invoker):
    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "--database", "fake_db")
    assert "--user and --password are required!" in str(excinfo.value)


@pytest.mark.usefixtures("mock_evernote_client")
def test_no_database_error(cli_invoker, fake_token):
    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "--database", "fake_db", "--token", fake_token)
    assert "Initialize database first!" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_password_login(cli_invoker, fake_storage, mock_evernote_client):
    mock_evernote_client.fake_auth_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")

    assert (
        fake_storage.config.get_config_value("auth_token")
        == mock_evernote_client.fake_auth_token
    )


@pytest.mark.usefixtures("fake_init_db")
def test_password_login_unexpected_error(
    cli_invoker, fake_storage, mock_evernote_client
):
    mock_evernote_client.fake_auth_unexpected_error = True

    with pytest.raises(EDAMUserException):
        cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")


@pytest.mark.usefixtures("fake_init_db")
def test_password_login_bad_token_error(
    cli_invoker, fake_storage, mock_evernote_client, fake_token
):
    mock_evernote_client.fake_is_token_bad = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "-d", "fake_db", "-t", fake_token)
    assert "Wrong token format!" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_password_login_wrong_username_error(
    cli_invoker, fake_storage, mock_evernote_client
):
    mock_evernote_client.fake_auth_invalid_name = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")
    assert "Username not found!" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_password_login_wrong_password_error(
    cli_invoker, fake_storage, mock_evernote_client
):
    mock_evernote_client.fake_auth_invalid_pass = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")
    assert "Invalid password!" in str(excinfo.value)


@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_password_login_no_pass(
    cli_invoker, fake_storage, mock_evernote_client, mock_click_prompt
):
    mock_click_prompt.fake_input = "asd123"
    mock_evernote_client.fake_auth_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    mock_evernote_client.fake_valid_username = "fake_user"
    mock_evernote_client.fake_valid_password = "asd123"

    cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user")

    mock_click_prompt.assert_called_once_with("Password", hide_input=True)
    assert (
        fake_storage.config.get_config_value("auth_token")
        == mock_evernote_client.fake_auth_token
    )


@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_password_login_no_login(
    cli_invoker, fake_storage, mock_evernote_client, mock_click_prompt
):
    mock_click_prompt.fake_input = "fake_user"
    mock_evernote_client.fake_auth_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    mock_evernote_client.fake_valid_username = "fake_user"
    mock_evernote_client.fake_valid_password = "asd123"

    cli_invoker("reauth", "-d", "fake_db", "-p", "asd123")

    mock_click_prompt.assert_called_once_with("Username or Email")
    assert (
        fake_storage.config.get_config_value("auth_token")
        == mock_evernote_client.fake_auth_token
    )


@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_password_login_two_factor(
    cli_invoker, fake_storage, mock_evernote_client, mock_click_prompt
):
    mock_click_prompt.fake_input = "123"
    mock_evernote_client.fake_twofactor_req = True
    mock_evernote_client.fake_auth_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")

    assert (
        fake_storage.config.get_config_value("auth_token")
        == mock_evernote_client.fake_auth_token
    )


@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_password_login_two_factor_hint(
    cli_invoker, fake_storage, mock_evernote_client, mock_click_prompt
):
    mock_click_prompt.fake_input = "123"
    mock_evernote_client.fake_twofactor_req = True
    mock_evernote_client.fake_twofactor_hint = "test_hint"
    mock_evernote_client.fake_auth_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")

    assert mock_evernote_client.fake_twofactor_hint in mock_click_prompt.call_args[0][0]
    assert (
        fake_storage.config.get_config_value("auth_token")
        == mock_evernote_client.fake_auth_token
    )


@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_password_login_two_factor_bad_ota_error(
    cli_invoker, fake_storage, mock_evernote_client, mock_click_prompt, fake_token
):
    mock_click_prompt.fake_input = "123"
    mock_evernote_client.fake_twofactor_req = True
    mock_evernote_client.fake_auth_token = fake_token
    mock_evernote_client.fake_auth_invalid_ota = True

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")
    assert "Invalid one-time code!" in str(excinfo.value)


@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_password_login_two_factor_unexpected_error(
    cli_invoker, fake_storage, mock_evernote_client, mock_click_prompt
):
    mock_click_prompt.fake_input = "123"
    mock_evernote_client.fake_twofactor_req = True
    mock_evernote_client.fake_auth_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    mock_evernote_client.fake_auth_twofactor_unexpected_error = True

    with pytest.raises(EDAMUserException):
        cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")


@pytest.mark.usefixtures("fake_init_db")
def test_password_login_two_factor_silent_error(
    cli_invoker, fake_storage, mock_evernote_client, mock_output_to_terminal
):
    mock_output_to_terminal.is_tty = False
    mock_evernote_client.fake_twofactor_req = True
    mock_evernote_client.fake_auth_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "-d", "fake_db", "-u", "fake_user", "-p", "fake_pass")
    assert "requires user input" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_oauth_login_silent_error(
    cli_invoker, fake_storage, mock_evernote_client, mock_output_to_terminal
):
    mock_output_to_terminal.is_tty = False

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "-d", "fake_db", "--oauth")
    assert "requires user input" in str(excinfo.value)


@pytest.mark.usefixtures("mock_oauth_http_server")
@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_oauth_login(
    cli_invoker, fake_storage, mock_evernote_client, mock_oauth_client, mocker
):
    mocker.patch("evernote_backup.cli_app_util.click.echo")
    mock_launch = mocker.patch("evernote_backup.cli_app_util.click.launch")

    cli_invoker("reauth", "-d", "fake_db", "--oauth")

    mock_launch.assert_called_once_with(
        "https://www.evernote.com/OAuth.action?oauth_token=fake_app.FFF"
    )
    assert (
        fake_storage.config.get_config_value("auth_token")
        == mock_oauth_client.fake_token
    )


@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_oauth_login_custom_port(
    cli_invoker,
    fake_storage,
    mock_evernote_client,
    mock_oauth_client,
    mocker,
    mock_oauth_http_server,
):
    mocker.patch("evernote_backup.cli_app_util.click.echo")
    mock_launch = mocker.patch("evernote_backup.cli_app_util.click.launch")

    test_port = 10666

    cli_invoker("reauth", "-d", "fake_db", "--oauth", "--oauth-port", test_port)

    mock_oauth_http_server.assert_any_call(("localhost", test_port), mocker.ANY)
    mock_launch.assert_called_once_with(
        "https://www.evernote.com/OAuth.action?oauth_token=fake_app.FFF"
    )
    assert (
        fake_storage.config.get_config_value("auth_token")
        == mock_oauth_client.fake_token
    )


@pytest.mark.usefixtures("mock_oauth_http_server")
@pytest.mark.usefixtures("mock_output_to_terminal")
@pytest.mark.usefixtures("fake_init_db")
def test_oauth_login_declined_error(
    cli_invoker, fake_storage, mock_evernote_client, mock_oauth_client, mocker
):
    del mock_oauth_client.fake_callback_response["oauth_verifier"]

    mocker.patch("evernote_backup.cli_app_util.click.echo")
    mock_launch = mocker.patch("evernote_backup.cli_app_util.click.launch")

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "-d", "fake_db", "--oauth")
    assert "declined" in str(excinfo.value)

    mock_launch.assert_called_once_with(
        "https://www.evernote.com/OAuth.action?oauth_token=fake_app.FFF"
    )


@pytest.mark.usefixtures("mock_evernote_client")
@pytest.mark.usefixtures("fake_init_db")
def test_old_db_error(cli_invoker, fake_storage, fake_token):
    fake_storage.config.set_config_value("DB_VERSION", "0")

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("reauth", "--database", "fake_db", "--token", fake_token)
    assert "Full resync is required" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_custom_network_retry_count_fail(
    fake_storage, cli_invoker, mock_evernote_client, mocker
):
    fake_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    mocker.patch("evernote_backup.evernote_client_util.time.sleep")

    test_network_retry_count = 10
    mock_evernote_client.fake_network_counter = test_network_retry_count

    with pytest.raises(ConnectionError):
        cli_invoker(
            "reauth",
            "--database",
            "fake_db",
            "--token",
            fake_token,
            "--network-retry-count",
            test_network_retry_count,
        )


@pytest.mark.usefixtures("fake_init_db")
def test_custom_network_retry_count(
    fake_storage, cli_invoker, mock_evernote_client, mocker
):
    fake_token = "S=1:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"

    mocker.patch("evernote_backup.evernote_client_util.time.sleep")

    test_network_retry_count = 90
    mock_evernote_client.fake_network_counter = test_network_retry_count - 1

    cli_invoker(
        "reauth",
        "--database",
        "fake_db",
        "--token",
        fake_token,
        "--network-retry-count",
        test_network_retry_count,
    )

    assert fake_storage.config.get_config_value("auth_token") == fake_token
