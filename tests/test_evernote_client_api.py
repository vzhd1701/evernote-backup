import pytest

from evernote_backup.evernote_client_api_http import (
    NoteStoreClientRetryable,
    UserStoreClientRetryable,
)
from evernote_backup.evernote_client_util_ssl import get_cafile_path


def test_user_store_client_init():
    client = UserStoreClientRetryable(
        auth_token="test-token",
        store_url="https://test.com",
        user_agent="test-agent",
        headers={"test-header": "test-header-value"},
        retry_max=10,
        retry_delay=20,
        retry_backoff_factor=30,
        retry_exceptions=(RuntimeError,),
    )

    expected_headers = {
        "User-Agent": "test-agent",
        "accept": "application/x-thrift",
        "cache-control": "no-cache",
        "test-header": "test-header-value",
        "x-feature-version": "3",
    }

    assert client.authenticationToken == "test-token"
    assert client._retry_max == 10
    assert client._retry_delay == 20
    assert client._retry_backoff_factor == 30
    assert client._retry_exceptions == (RuntimeError,)

    assert client._base_client.url == "https://test.com"
    assert client._base_client.protocol.trans.host == "test.com"
    assert client._base_client.protocol.trans.scheme == "https"
    assert client._base_client._default_headers == expected_headers
    assert (
        client._base_client.protocol.trans._THttpClient__custom_headers
        == expected_headers
    )


def test_note_store_client_init():
    client = NoteStoreClientRetryable(
        auth_token="test-token",
        store_url="https://test.com",
        user_agent="test-agent",
        headers={"test-header": "test-header-value"},
        retry_max=10,
        retry_delay=20,
        retry_backoff_factor=30,
        retry_exceptions=(RuntimeError,),
    )

    expected_headers = {
        "User-Agent": "test-agent",
        "accept": "application/x-thrift",
        "cache-control": "no-cache",
        "test-header": "test-header-value",
        "x-feature-version": "3",
    }

    assert client.authenticationToken == "test-token"
    assert client._retry_max == 10
    assert client._retry_delay == 20
    assert client._retry_backoff_factor == 30
    assert client._retry_exceptions == (RuntimeError,)

    assert client._base_client.url == "https://test.com"
    assert client._base_client.protocol.trans.host == "test.com"
    assert client._base_client.protocol.trans.scheme == "https"
    assert client._base_client._default_headers == expected_headers
    assert (
        client._base_client.protocol.trans._THttpClient__custom_headers
        == expected_headers
    )


def test_note_store_client_bad_init(mocker):
    mock_tbin = mocker.patch(
        "evernote_backup.evernote_client_api_http.TBinaryProtocolHotfix"
    )
    mock_tbin.side_effect = RuntimeError("test")

    with pytest.raises(ConnectionError) as e:
        NoteStoreClientRetryable(auth_token="test-token", store_url="https://test.com")

    assert str(e.value) == "Failed to create Thrift binary http client: test"


def test_note_store_client_init_certifi_ca(mocker):
    cafile = get_cafile_path(use_system_ssl_ca=False)

    client = NoteStoreClientRetryable(
        auth_token="test-token",
        store_url="https://test.com",
        cafile=cafile,
    )

    assert client._base_client.protocol.trans.context is not None


def test_note_store_client_init_system_ca(mocker):
    client = NoteStoreClientRetryable(
        auth_token="test-token",
        store_url="https://test.com",
    )

    assert client._base_client.protocol.trans.context is None
