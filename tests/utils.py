import sqlite3
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)

from evernote_backup import cli_app, note_storage
from evernote_backup.cli import cli


class FakeEvernoteValues(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fake_user = None
        self.fake_tags = []
        self.fake_notebooks = []
        self.fake_notes = []
        self.fake_expunged_notebooks = []
        self.fake_expunged_notes = []
        self.fake_usn = 100

        self.fake_valid_username = None
        self.fake_valid_password = None

        self.fake_is_token_expired = False
        self.fake_is_token_invalid = False
        self.fake_is_token_bad = False

        self.fake_auth_invalid_pass = False
        self.fake_auth_invalid_name = False
        self.fake_auth_invalid_ota = False

        self.fake_auth_token = None
        self.fake_twofactor_req = False
        self.fake_twofactor_hint = None

        self.fake_auth_verify_unexpected_error = False
        self.fake_auth_unexpected_error = False
        self.fake_auth_twofactor_unexpected_error = False


class FakeEvernoteUserStore(MagicMock):
    def __init__(self, fake_values, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.values = fake_values

    def getUser(self):
        if self.values.fake_auth_verify_unexpected_error:
            raise EDAMUserException()
        if self.values.fake_is_token_expired:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.AUTH_EXPIRED, parameter="authenticationToken"
            )
        if self.values.fake_is_token_invalid:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="authenticationToken"
            )
        if self.values.fake_is_token_bad:
            raise EDAMSystemException(
                errorCode=EDAMErrorCode.BAD_DATA_FORMAT, message="authenticationToken"
            )
        return MagicMock(username=self.values.fake_user)

    def getNoteStoreUrl(self):
        return "https://www.evernote.com/shard/s520/notestore"

    def authenticateLongSessionV2(self, *args, **kwargs):
        if self.values.fake_auth_unexpected_error:
            raise EDAMUserException()
        if self.values.fake_auth_invalid_pass or (
            self.values.fake_valid_password
            and self.values.fake_valid_password != kwargs["password"]
        ):
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="password"
            )
        if self.values.fake_auth_invalid_name or (
            self.values.fake_valid_username
            and self.values.fake_valid_username != kwargs["username"]
        ):
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="username"
            )
        return MagicMock(
            secondFactorRequired=self.values.fake_twofactor_req,
            secondFactorDeliveryHint=self.values.fake_twofactor_hint,
            authenticationToken=self.values.fake_auth_token,
        )

    def completeTwoFactorAuthentication(self, *args, **kwargs):
        if self.values.fake_auth_twofactor_unexpected_error:
            raise EDAMUserException()
        if self.values.fake_auth_invalid_ota:
            raise EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH, parameter="oneTimeCode"
            )
        return MagicMock(
            authenticationToken=self.values.fake_auth_token,
        )


class FakeEvernoteNoteStore(MagicMock):
    def __init__(self, fake_values, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.values = fake_values

    def getSyncState(self):
        return MagicMock(updateCount=self.values.fake_usn)

    def listTags(self):
        return self.values.fake_tags

    def getNote(self, guid, *args, **kwargs):
        return next(n for n in self.values.fake_notes if n.guid == guid)

    def getFilteredSyncChunk(self, *args, **kwargs):
        fake_chunk = MagicMock()

        fake_chunk.notebooks = self.values.fake_notebooks
        fake_chunk.notes = self.values.fake_notes
        fake_chunk.expungedNotebooks = self.values.fake_expunged_notebooks
        fake_chunk.expungedNotes = self.values.fake_expunged_notes

        # This will result in only 1 iteration of chunks
        fake_chunk.chunkHighUSN = self.values.fake_usn
        fake_chunk.updateCount = self.values.fake_usn

        return fake_chunk


@pytest.fixture()
def mock_evernote_client(mocker):
    fake_values = FakeEvernoteValues()

    def store_dispencer(store_url, *args, **kwargs):
        if "notestore" in store_url:
            return FakeEvernoteNoteStore(fake_values)
        return FakeEvernoteUserStore(fake_values)

    mock_client_cls = mocker.patch("evernote_backup.evernote_client.Store")
    mock_client_cls.side_effect = store_dispencer

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
    monkeypatch.setattr(cli_app, "initialize_db", lambda *a, **kw: None)

    yield fake_storage

    db.close()


@pytest.fixture()
def fake_init_db(fake_storage, mock_evernote_client):
    cli_app.init_db(
        database="fake_db",
        auth_user=None,
        auth_password=None,
        auth_token=FAKE_TOKEN,
        force=False,
        backend="evernote",
    )


@pytest.fixture()
def mock_formatter(mocker):
    fake_values = MagicMock(fake_body="test")

    mock_formatter = mocker.patch("evernote_backup.note_storage.NoteFormatter")
    mock_formatter().format_note.side_effect = lambda *a, **kw: fake_values.fake_body

    return fake_values


FAKE_TOKEN = "S=1:U=ff:E=fff:C=ff:P=1:A=test:V=2:H=ff"
