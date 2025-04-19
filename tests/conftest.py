import json
import sqlite3
import uuid
from pathlib import Path
from ssl import SSLError
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMNotFoundException,
    EDAMSystemException,
    EDAMUserException,
)
from evernote.edam.userstore.ttypes import AuthenticationParameters
from requests_oauthlib.oauth1_session import TokenRequestDenied
from requests_sse import MessageEvent

import evernote_backup
from evernote_backup import cli_app, note_storage
from evernote_backup.cli import cli
from evernote_backup.evernote_client_api_http import RetryableMixin
from evernote_backup.token_util import EvernoteToken


class FakeEvernoteValues:
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
        self.fake_is_token_bad_for_jwt = False

        self.fake_auth_invalid_pass = False
        self.fake_auth_invalid_name = False
        self.fake_auth_invalid_ota = False

        self.fake_auth_token = None
        self.fake_linked_notebook_auth_token = None
        self.fake_twofactor_req = False
        self.fake_twofactor_hint = None
        self.fake_jwt_token = None

        self.fake_auth_verify_unexpected_error = False
        self.fake_auth_get_jwt_unexpected_error = False
        self.fake_auth_unexpected_error = False
        self.fake_auth_twofactor_unexpected_error = False
        self.fake_auth_linked_notebook_error = False

        self.fake_auth_used_api_key = None
        self.fake_auth_used_api_secret = None

        self.fake_ping_ssl_error = False

        self.last_maxEntries = None
        self.fake_network_counter = 0

        self.fake_updates = []


class FakeEvernoteUserStore:
    fake_values = None

    def __init__(
        self,
        auth_token: str,
        store_url: str,
        user_agent: str,
        headers=None,
        cafile=None,
    ):
        self.auth_token = auth_token

        self._base_client = MagicMock()

    def getUser(self):
        if self.fake_values.fake_network_counter > 0:
            self.fake_values.fake_network_counter -= 1
            raise ConnectionError

        if self.fake_values.fake_auth_verify_unexpected_error:
            raise EDAMUserException
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

    def checkVersion(
        self,
        clientName: str,
        edamVersionMajor: int,
        edamVersionMinor: int,
    ):
        if self.fake_values.fake_ping_ssl_error:
            raise SSLError("test ssl error")

        return True

    def authenticateLongSessionV2(self, authParams: AuthenticationParameters):
        self.fake_values.fake_auth_used_api_key = authParams.consumerKey
        self.fake_values.fake_auth_used_api_secret = authParams.consumerSecret

        if self.fake_values.fake_auth_unexpected_error:
            raise EDAMUserException
        if self.fake_values.fake_auth_invalid_pass or (
            self.fake_values.fake_valid_password
            and self.fake_values.fake_valid_password != authParams.password
        ):
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="password"
            )
        if self.fake_values.fake_auth_invalid_name or (
            self.fake_values.fake_valid_username
            and self.fake_values.fake_valid_username != authParams.usernameOrEmail
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
        oneTimeCode,
        deviceIdentifier,
        deviceDescription,
    ):
        if self.fake_values.fake_auth_twofactor_unexpected_error:
            raise EDAMUserException
        if self.fake_values.fake_auth_invalid_ota:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="oneTimeCode"
            )
        return MagicMock(
            authenticationToken=self.fake_values.fake_auth_token,
        )

    def getNAPAccessToken(self):
        if self.fake_values.fake_is_token_bad_for_jwt:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.PERMISSION_DENIED,
                parameter="authenticationToken",
            )
        if self.fake_values.fake_auth_get_jwt_unexpected_error:
            raise EDAMUserException
        return self.fake_values.fake_jwt_token


class FakeEvernoteNoteStore:
    fake_values = None

    def __init__(
        self,
        auth_token: str,
        store_url: str,
        user_agent: str,
        headers=None,
        cafile=None,
    ):
        self.auth_token = auth_token
        self.shard = store_url[store_url.rfind("/") + 1 :]

        self._base_client = MagicMock()

    def getSyncState(self):
        return MagicMock(updateCount=self.fake_values.fake_usn)

    def listTags(self):
        return self.fake_values.fake_tags

    def getNote(
        self,
        guid,
        withContent,
        withResourcesData,
        withResourcesRecognition,
        withResourcesAlternateData,
    ):
        # If client shard is different, means we are trying to get note from linked nb
        token_shard = EvernoteToken.from_string(self.auth_token).shard
        if token_shard != self.shard:
            return next(n for n in self.fake_values.fake_l_notes if n.guid == guid)

        return next(n for n in self.fake_values.fake_notes if n.guid == guid)

    def getFilteredSyncChunk(self, afterUSN, maxEntries, filter):
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
        self, linkedNotebook, afterUSN, maxEntries, fullSyncOnly
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

    def listLinkedNotebooks(self):
        return self.fake_values.fake_linked_notebooks

    def authenticateToSharedNotebook(self, shareKeyOrGlobalId):
        return MagicMock(
            authenticationToken=self.fake_values.fake_linked_notebook_auth_token,
        )

    def listTagsByNotebook(self, notebookGuid):
        return self.fake_values.fake_l_tags


class FakeSyncEventSource(MagicMock):
    fake_values = None

    def __enter__(self):
        connection_id = str(uuid.uuid4())
        event_id = f"{connection_id}::0"
        origin = "https://api.evernote.com"

        return [
            MessageEvent(
                last_event_id=event_id,
                origin=origin,
                type="connection",
                data=f'{{"connectionId": "{connection_id}","identityIds": [12345]}}',
            ),
            # unknown message type
            MessageEvent(
                last_event_id=event_id,
                origin=origin,
                type="boop",
                data="[]",
            ),
            # empty update message
            MessageEvent(
                last_event_id=event_id,
                origin=origin,
                type="sync",
                data="[]",
            ),
            # glitchy update message
            MessageEvent(
                last_event_id=event_id,
                origin=origin,
                type="sync",
                data='{"items": [1, 2, 3',
            ),
            MessageEvent(
                last_event_id=event_id,
                origin=origin,
                type="sync",
                data=json.dumps(self.fake_values.fake_updates),
            ),
            MessageEvent(
                last_event_id=event_id,
                origin=origin,
                type="complete",
                data=f'{{"documentCount":{len(self.fake_values.fake_updates)}}}',
            ),
            MessageEvent(
                last_event_id=event_id,
                origin=origin,
                type="close",
                data='{"completed":true}',
            ),
        ]

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False  # Don't suppress exceptions


@pytest.fixture
def mock_evernote_client(mocker):
    fake_values = FakeEvernoteValues()

    FakeEvernoteUserStore.fake_values = fake_values
    FakeEvernoteNoteStore.fake_values = fake_values
    FakeSyncEventSource.fake_values = fake_values

    class FakeUserStoreClientRetryable(RetryableMixin, FakeEvernoteUserStore):
        pass

    class FakeNoteStoreClientRetryable(RetryableMixin, FakeEvernoteNoteStore):
        pass

    mocker.patch(
        "evernote_backup.evernote_client.UserStoreClientRetryable",
        new=FakeUserStoreClientRetryable,
    )

    mocker.patch(
        "evernote_backup.evernote_client.NoteStoreClientRetryable",
        new=FakeNoteStoreClientRetryable,
    )

    mocker.patch("evernote_backup.evernote_client.EventSource", new=FakeSyncEventSource)

    return fake_values


@pytest.fixture
def cli_invoker():
    cli_runner = CliRunner()
    return lambda *x: cli_runner.invoke(cli, x, catch_exceptions=False)


@pytest.fixture
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


@pytest.fixture
def fake_init_db(fake_storage, fake_token, mock_evernote_client):
    mock_evernote_client.fake_user = "fake_user"

    cli_app.init_db(
        database=Path("fake_db"),
        auth_user=None,
        auth_password=None,
        auth_oauth_port=10500,
        auth_oauth_host="localhost",
        auth_token=fake_token,
        force=False,
        backend="evernote",
        network_retry_count=50,
        use_system_ssl_ca=False,
        custom_api_data=None,
    )


@pytest.fixture
def fake_init_db_china(fake_storage, fake_token, mock_evernote_client):
    mock_evernote_client.fake_user = "fake_user"

    cli_app.init_db(
        database=Path("fake_db"),
        auth_user=None,
        auth_password=None,
        auth_oauth_port=10500,
        auth_oauth_host="localhost",
        auth_token=fake_token,
        force=False,
        backend="china",
        network_retry_count=50,
        use_system_ssl_ca=False,
        custom_api_data=None,
    )


@pytest.fixture
def fake_token():
    return "S=s1:U=ff:E=fff:C=ff:P=1:A=test:V=2:H=ff"


@pytest.fixture
def mock_oauth_client(mocker):
    def fake_request(self, url, **request_kwargs):
        if self._client.client.resource_owner_key is None:
            token = {
                "oauth_token": oauth_mock.fake_oauth_token_id,
                "oauth_token_secret": oauth_mock.fake_oauth_secret,
                "oauth_callback_confirmed": "true",
            }
        else:
            if oauth_mock.fake_bad_response:
                raise TokenRequestDenied(None, None)

            token = {
                "oauth_token": oauth_mock.fake_token,
                "oauth_verifier": "FFF2",
                "sandbox_lnb": "false",
            }

        self._populate_attributes(token)
        self.token = token
        return token

    oauth_mock = mocker.patch.object(
        evernote_backup.evernote_client_oauth.OAuth1Session,
        "_fetch_token",
        fake_request,
    )

    oauth_mock.fake_oauth_token_id = "fake_app.FFF"
    oauth_mock.fake_oauth_secret = "FFF1"

    oauth_mock.fake_callback_response = f"/?oauth_token={oauth_mock.fake_oauth_token_id}&oauth_verifier=FFF2&sandbox_lnb=false"

    oauth_mock.fake_token = "S=s100:U=fff:E=ffff:C=ffff:P=100:A=appname:V=2:H=ffffff"

    oauth_mock.fake_bad_response = False

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


@pytest.fixture
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
