import sqlite3
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMNotFoundException,
    EDAMSystemException,
    EDAMUserException,
)

from evernote_backup import cli_app, note_storage
from evernote_backup.cli import cli
from evernote_backup.token_util import get_token_shard


class FakeEvernoteValues(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fake_user = None

        self.fake_tags = []
        self.fake_notebooks = []
        self.fake_linked_notebooks = []
        self.fake_notes = []
        self.fake_expunged_notebooks = []
        self.fake_expunged_linked_notebooks = []
        self.fake_expunged_notes = []
        self.fake_usn = 100

        self.fake_l_notebooks = []
        self.fake_l_tags = []
        self.fake_l_notes = []
        self.fake_l_expunged_notebooks = []
        self.fake_l_expunged_notes = []
        self.fake_l_usn = 100

        self.fake_valid_username = None
        self.fake_valid_password = None

        self.fake_is_token_expired = False
        self.fake_is_token_invalid = False
        self.fake_is_token_bad = False

        self.fake_auth_invalid_pass = False
        self.fake_auth_invalid_name = False
        self.fake_auth_invalid_ota = False

        self.fake_auth_token = None
        self.fake_linked_notebook_auth_token = None
        self.fake_twofactor_req = False
        self.fake_twofactor_hint = None

        self.fake_auth_verify_unexpected_error = False
        self.fake_auth_unexpected_error = False
        self.fake_auth_twofactor_unexpected_error = False
        self.fake_auth_linked_notebook_error = False

        self.last_maxEntries = None
        self.fake_network_counter = 0


class FakeEvernoteUserStore(MagicMock):
    fake_values = None

    def getUser(self, authenticationToken):
        if self.fake_values.fake_network_counter > 0:
            self.fake_values.fake_network_counter -= 1
            raise ConnectionError

        if self.fake_values.fake_auth_verify_unexpected_error:
            raise EDAMUserException()
        if self.fake_values.fake_is_token_expired:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.AUTH_EXPIRED, parameter="authenticationToken"
            )
        if self.fake_values.fake_is_token_invalid:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="authenticationToken"
            )
        if self.fake_values.fake_is_token_bad:
            raise EDAMSystemException(
                errorCode=EDAMErrorCode.BAD_DATA_FORMAT, message="authenticationToken"
            )
        return MagicMock(username=self.fake_values.fake_user)

    def getNoteStoreUrl(self, authenticationToken):
        return "https://www.evernote.com/shard/s520/notestore"

    def authenticateLongSessionV2(
        self,
        username,
        password,
        ssoLoginToken,
        consumerKey,
        consumerSecret,
        deviceIdentifier,
        deviceDescription,
        supportsTwoFactor,
        supportsBusinessOnlyAccounts,
    ):
        if self.fake_values.fake_auth_unexpected_error:
            raise EDAMUserException()
        if self.fake_values.fake_auth_invalid_pass or (
            self.fake_values.fake_valid_password
            and self.fake_values.fake_valid_password != password
        ):
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="password"
            )
        if self.fake_values.fake_auth_invalid_name or (
            self.fake_values.fake_valid_username
            and self.fake_values.fake_valid_username != username
        ):
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="username"
            )
        return MagicMock(
            secondFactorRequired=self.fake_values.fake_twofactor_req,
            secondFactorDeliveryHint=self.fake_values.fake_twofactor_hint,
            authenticationToken=self.fake_values.fake_auth_token,
        )

    def completeTwoFactorAuthentication(
        self,
        authenticationToken,
        oneTimeCode,
        deviceIdentifier,
        deviceDescription,
    ):
        if self.fake_values.fake_auth_twofactor_unexpected_error:
            raise EDAMUserException()
        if self.fake_values.fake_auth_invalid_ota:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="oneTimeCode"
            )
        return MagicMock(
            authenticationToken=self.fake_values.fake_auth_token,
        )


class FakeEvernoteNoteStore(MagicMock):
    fake_values = None

    def __init__(self, iprot, oprot=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.shard = iprot.trans.path[len("/edam/note/") :]

    def getSyncState(self, authenticationToken):
        return MagicMock(updateCount=self.fake_values.fake_usn)

    def listTags(self, authenticationToken):
        return self.fake_values.fake_tags

    def getNote(
        self,
        authenticationToken,
        guid,
        withContent,
        withResourcesData,
        withResourcesRecognition,
        withResourcesAlternateData,
    ):
        # if authenticationToken == self.fake_values.fake_linked_notebook_auth_token:

        # If client shard is different, means we are trying to get note from linked nb
        token_shard = get_token_shard(authenticationToken)
        if token_shard != self.shard:
            return next(n for n in self.fake_values.fake_l_notes if n.guid == guid)

        return next(n for n in self.fake_values.fake_notes if n.guid == guid)

    def getFilteredSyncChunk(self, authenticationToken, afterUSN, maxEntries, filter):
        self.fake_values.last_maxEntries = maxEntries

        fake_chunk = MagicMock()

        fake_chunk.notebooks = self.fake_values.fake_notebooks
        fake_chunk.notes = self.fake_values.fake_notes
        fake_chunk.expungedNotebooks = self.fake_values.fake_expunged_notebooks
        fake_chunk.expungedLinkedNotebooks = (
            self.fake_values.fake_expunged_linked_notebooks
        )
        fake_chunk.expungedNotes = self.fake_values.fake_expunged_notes

        # This will result in only 1 iteration of chunks
        fake_chunk.chunkHighUSN = self.fake_values.fake_usn
        fake_chunk.updateCount = self.fake_values.fake_usn

        return fake_chunk

    def getLinkedNotebookSyncChunk(
        self, authenticationToken, linkedNotebook, afterUSN, maxEntries, fullSyncOnly
    ):
        if self.fake_values.fake_auth_linked_notebook_error:
            raise EDAMNotFoundException

        self.fake_values.last_maxEntries = maxEntries

        fake_chunk = MagicMock()

        fake_chunk.notebooks = self.fake_values.fake_l_notebooks
        fake_chunk.notes = self.fake_values.fake_l_notes
        fake_chunk.expungedNotebooks = self.fake_values.fake_l_expunged_notebooks
        fake_chunk.expungedLinkedNotebooks = []
        fake_chunk.expungedNotes = self.fake_values.fake_l_expunged_notes

        # This will result in only 1 iteration of chunks
        fake_chunk.chunkHighUSN = self.fake_values.fake_l_usn
        fake_chunk.updateCount = self.fake_values.fake_l_usn

        return fake_chunk

    def listLinkedNotebooks(self, authenticationToken):
        return self.fake_values.fake_linked_notebooks

    def authenticateToSharedNotebook(self, shareKeyOrGlobalId, authenticationToken):
        return MagicMock(
            authenticationToken=self.fake_values.fake_linked_notebook_auth_token,
        )

    def listTagsByNotebook(self, authenticationToken, notebookGuid):
        return self.fake_values.fake_l_tags


@pytest.fixture()
def mock_evernote_client(mocker):
    fake_values = FakeEvernoteValues()

    FakeEvernoteUserStore.fake_values = fake_values
    FakeEvernoteNoteStore.fake_values = fake_values

    mocker.patch("evernote_backup.evernote_client.ClientV2", new=FakeEvernoteUserStore)

    mocker.patch(
        "evernote_backup.evernote_client.NoteStore.Client", new=FakeEvernoteNoteStore
    )

    return fake_values


@pytest.fixture()
def cli_invoker():
    cli_runner = CliRunner()
    return lambda *x: cli_runner.invoke(cli, x, catch_exceptions=False)


@pytest.fixture()
def fake_storage(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row

    with db as con:
        con.executescript(note_storage.DB_SCHEMA)

    fake_storage = note_storage.SqliteStorage(db)

    monkeypatch.setattr(cli_app, "get_storage", lambda *a, **kw: fake_storage)
    monkeypatch.setattr(cli_app, "initialize_storage", lambda *a, **kw: fake_storage)

    yield fake_storage

    db.close()


@pytest.fixture()
def fake_init_db(fake_storage, fake_token, mock_evernote_client):
    mock_evernote_client.fake_user = "fake_user"

    cli_app.init_db(
        database=Path("fake_db"),
        auth_user=None,
        auth_password=None,
        auth_is_oauth=False,
        auth_oauth_port=10500,
        auth_oauth_host="localhost",
        auth_token=fake_token,
        force=False,
        backend="evernote",
        network_retry_count=50,
    )


@pytest.fixture()
def fake_token():
    return "S=1:U=ff:E=fff:C=ff:P=1:A=test:V=2:H=ff"


@pytest.fixture
def mock_oauth_client(mocker):
    oauth_mock = mocker.patch("evernote_backup.evernote_client_oauth.oauth2")

    oauth_mock.fake_oauth_token_id = "fake_app.FFF"
    oauth_mock.fake_oauth_secret = "FFF1"
    oauth_mock.fake_request_url = (
        f"oauth_token={oauth_mock.fake_oauth_token_id}&"
        f"oauth_token_secret={oauth_mock.fake_oauth_secret}&"
        f"oauth_callback_confirmed=true"
    ).encode()

    oauth_mock.fake_callback_response = {
        "oauth_token": oauth_mock.fake_oauth_token_id,
        "oauth_verifier": "FFF2",
        "sandbox_lnb": "false",
    }

    oauth_mock.fake_token = "S=s100:U=fff:E=ffff:C=ffff:P=100:A=appname:V=2:H=ffffff"

    def fake_request(url, method):
        if method == "POST":
            response = urllib.parse.urlencode(
                {"oauth_token": oauth_mock.fake_token}
            ).encode()
        else:
            response = oauth_mock.fake_request_url

        return None, response

    oauth_mock.Client().request.side_effect = fake_request

    return oauth_mock


@pytest.fixture
def mock_oauth_http_server(mock_oauth_client, mocker):
    mock_server = mocker.patch(
        "evernote_backup.evernote_client_oauth.StoppableHTTPServer"
    )

    def callback_setter():
        mock_server().callback_response = mock_oauth_client.fake_callback_response

    mock_server().run.side_effect = callback_setter

    return mock_server


@pytest.fixture()
def mock_output_to_terminal(mocker, monkeypatch):
    tty_mock = MagicMock()

    tty_mock.is_tty = True
    tty_mock.side_effect = lambda *a, **kw: tty_mock.is_tty

    mocker.patch(
        "evernote_backup.cli_app_auth_oauth.is_output_to_terminal", new=tty_mock
    )
    mocker.patch(
        "evernote_backup.cli_app_auth_password.is_output_to_terminal", new=tty_mock
    )
    # mocker.patch("evernote_backup.cli.is_output_to_terminal", new=tty_mock)
    mocker.patch("evernote_backup.cli_app_util.is_output_to_terminal", new=tty_mock)
    mocker.patch("evernote_backup.log_util.is_output_to_terminal", new=tty_mock)

    return tty_mock
