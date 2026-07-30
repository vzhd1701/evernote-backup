import json
import sqlite3
import time
import uuid
from pathlib import Path
from ssl import SSLError
from unittest.mock import MagicMock

import jwt
import pytest
from click.testing import CliRunner
from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMNotFoundException,
    EDAMSystemException,
    EDAMUserException,
)
from evernote.edam.userstore.ttypes import AuthenticationParameters
from oauthlib.oauth2 import OAuth2Error
from requests_oauthlib.oauth1_session import TokenRequestDenied
from requests_sse import MessageEvent

import evernote_backup
from evernote_backup import cli_app, note_storage
from evernote_backup.cli import cli
from evernote_backup.evernote_client_api_http import RetryableMixin
from evernote_backup.token_util import EvernoteToken, OAuth2TokenBundle


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
def fake_init_db_jwt(fake_storage, fake_token_jwt, mock_evernote_client):
    mock_evernote_client.fake_user = "fake_user"

    cli_app.init_db(
        database=Path("fake_db"),
        auth_user=None,
        auth_password=None,
        auth_oauth_port=10500,
        auth_oauth_host="localhost",
        auth_token=fake_token_jwt,
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
def fake_token_jwt(mock_oauth_client):
    return mock_oauth_client.token_bundle.to_json()


@pytest.fixture
def fake_token_jwt_mock():
    return TokenBundleMock()


class TokenBundleMock(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fake_bad_fetch_token_response = False
        self.fake_bad_refresh_token_response = False
        self.fake_malformed_refresh_token_response = False

        self.fake_oauth_code = "aabbcc"
        self.fake_callback_response = (
            f"/auth/redirect?code={self.fake_oauth_code}&state=test"
        )

        self.client_id = "3FE74DA6-ABC8-4E20-9940-28D589D4E808"
        self.user_id = 111222333
        self.user_email = "test@example.com"
        self.user_shard = "s100"
        self.jwt_key = "12345"
        self.issued_at = int(time.time())
        self.expires_at = self.issued_at + 3600
        self.refresh_expires_at = self.issued_at + 31557600

    @property
    def token_bundle_raw(self):
        access_token = {
            "mono_authn_token": self.token_mono,
            "evernote_user_id": self.user_id,
            "client_id": self.client_id,
            "refresh_token_id": "111aaa",
            "aud": "api.evernote.com",
            "exp": self.expires_at,
            "iat": self.issued_at,
            "iss": "https://accounts.evernote.com",
        }

        id_token = {
            "monolith_token": self.token_mono,
            "notestore_url": "https://www.evernote.com/shard/s100/notestore",
            "user_id": str(self.user_id),
        }

        refresh_token = {
            "clientId": self.client_id,
            "consumerKey": "en-w32-xauth-new",
            "email": self.user_email,
            "evernoteId": self.user_id,
            "versionId": "222bbb",
            "exp": self.refresh_expires_at,
            "iat": self.issued_at,
            "iss": "https://accounts.evernote.com",
            "jti": "333ccc",
        }

        return {
            "access_token": jwt.encode(access_token, self.jwt_key),
            "expires_in": 3600,
            "id_token": jwt.encode(id_token, self.jwt_key),
            "refresh_token": jwt.encode(refresh_token, self.jwt_key),
            "token_type": "Bearer",
        }

    @property
    def token_bundle(self):
        return OAuth2TokenBundle.from_dict(self.token_bundle_raw)

    @property
    def token_mono(self):
        return f"S={self.user_shard}:U={self.user_id:#x}:E={self.expires_at * 1000:#x}:C={self.issued_at * 1000:#x}:P=100:A=appname:V=2:H=ffffff"


@pytest.fixture
def mock_oauth_client(mocker):
    def fake_fetch_token(self, url, **request_kwargs):
        if oauth_mock.fake_bad_fetch_token_response:
            raise ValueError("test")

        return oauth_mock.token_bundle_raw

    def fake_refresh_token(self, *args, **kwargs):
        if oauth_mock.fake_bad_refresh_token_response:
            raise OAuth2Error("test")

        if oauth_mock.fake_malformed_refresh_token_response:
            malformed_bundle = oauth_mock.token_bundle_raw.copy()
            malformed_bundle.pop("refresh_token")
            return malformed_bundle

        return oauth_mock.token_bundle_raw

    oauth_mock = TokenBundleMock()

    mocker.patch.object(
        evernote_backup.evernote_client_oauth.OAuth2Session,
        "fetch_token",
        fake_fetch_token,
    )

    mocker.patch.object(
        evernote_backup.evernote_client_oauth.OAuth2Session,
        "refresh_token",
        fake_refresh_token,
    )

    mocker.patch(
        "evernote_backup.evernote_client_oauth.register_mcp_client",
        return_value={"client_id": oauth_mock.client_id},
    )

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
