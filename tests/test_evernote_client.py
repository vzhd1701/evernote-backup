"""Unit tests for EvernoteClient / EvernoteClientBase."""

from unittest.mock import MagicMock

import pytest
from evernote.edam.error.ttypes import EDAMErrorCode, EDAMUserException
from requests_sse import MessageEvent

from evernote_backup.errors import EvernoteAuthError
from evernote_backup.evernote_client import EvernoteClient, EvernoteClientBase
from evernote_backup.evernote_types import EvernoteEntityType


FAKE_TOKEN = "S=s100:U=ff:E=fff:C=ff:P=1:A=test:V=2:H=ff"


def test_client_base_backend_hosts():
    en = EvernoteClientBase(backend="evernote")
    assert en.service_host == "www.evernote.com"
    assert en.user_agent.startswith("ENScript")
    assert en._get_endpoint("edam/user") == "https://www.evernote.com/edam/user"

    cn = EvernoteClientBase(backend="china")
    assert cn.service_host == "app.yinxiang.com"
    assert cn.user_agent.startswith("YXScript")

    sandbox = EvernoteClientBase(backend="china:sandbox")
    assert sandbox.service_host == "sandbox.yinxiang.com"


def test_client_parses_token_shard_and_user_id():
    client = EvernoteClient(backend="evernote", token=FAKE_TOKEN)

    assert client.shard == "s100"
    assert client.user_id == 0xFF
    assert client.token is not None


def test_client_user_id_without_token_raises():
    client = EvernoteClient(backend="evernote", token=None)

    with pytest.raises(EvernoteAuthError, match="user_id before providing token"):
        _ = client.user_id


def test_client_user_cached(mock_evernote_client):
    mock_evernote_client.fake_user = "alice"
    client = EvernoteClient(backend="evernote", token=FAKE_TOKEN)

    assert client.user == "alice"
    assert client.user == "alice"  # cached
    assert client._user == "alice"


def test_client_check_version(mock_evernote_client):
    client = EvernoteClient(backend="evernote", token=FAKE_TOKEN)
    assert client.check_version() is True


def test_client_verify_token_ok(mock_evernote_client):
    mock_evernote_client.fake_user = "bob"
    client = EvernoteClient(backend="evernote", token=FAKE_TOKEN)
    client.verify_token()  # does not raise


def test_client_verify_token_auth_error(mock_evernote_client):
    mock_evernote_client.fake_is_token_invalid = True
    client = EvernoteClient(backend="evernote", token=FAKE_TOKEN)

    with pytest.raises(EvernoteAuthError):
        client.verify_token()


def test_client_get_note_store_default_and_custom_shard(mock_evernote_client):
    client = EvernoteClient(backend="evernote", token=FAKE_TOKEN)

    default_store = client.note_store
    assert default_store.shard == "s100"

    other = client.get_note_store("s532")
    assert other.shard == "s532"


def test_client_iter_sync_events_builds_url_and_headers(mocker, mock_evernote_client):
    captured = {}

    class FakeES:
        def __init__(self, url, timeout=None, headers=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["timeout"] = timeout

        def __enter__(self):
            return [
                MessageEvent(
                    last_event_id="1",
                    origin="https://api.evernote.com",
                    type="close",
                    data="{}",
                )
            ]

        def __exit__(self, *args):
            return False

    mocker.patch("evernote_backup.evernote_client.EventSource", FakeES)

    client = EvernoteClient(
        backend="evernote",
        token=FAKE_TOKEN,
        jwt_token="jwt-abc",
    )

    events = list(
        client.iter_sync_events(
            last_connection=42,
            entity_filter=[EvernoteEntityType.NOTE, EvernoteEntityType.TASK],
        )
    )

    assert len(events) == 1
    assert "lastConnection=42" in captured["url"]
    assert "entityFilter=" in captured["url"]
    assert (
        "[0,15]" in captured["url"]
        or "%5B0%2C15%5D" in captured["url"]
        or ("0" in captured["url"] and "15" in captured["url"])
    )
    assert captured["headers"]["Authorization"] == "Bearer jwt-abc"
    assert captured["headers"]["x-feature-version"] == "4"
    assert captured["timeout"] == 30


def test_client_note_store_without_token(mock_evernote_client):
    client = EvernoteClient(backend="evernote", token=None)
    # Should still construct a store with empty auth token
    store = client.get_note_store("s1")
    assert store.auth_token == ""
