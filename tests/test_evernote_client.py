import pytest

from evernote_backup.evernote_client import Store
from evernote_backup.evernote_client_util import network_retry


def test_network_retry(mocker):
    mocker.patch("evernote_backup.evernote_client_util.time.sleep")

    call_count = 0

    test_network_error_retry_count = 69

    @network_retry(test_network_error_retry_count)
    def test_error_function():
        nonlocal call_count
        call_count += 1
        raise ConnectionError

    with pytest.raises(ConnectionError):
        test_error_function()
    assert call_count == test_network_error_retry_count


def test_store_no_method():
    class fake_client(object):
        def __init__(self, *args, **kwargs):
            pass

    store = Store(
        client_class=fake_client,
        store_url="https://fake.com",
        user_agent="fake_uagent",
        network_error_retry_count=50,
    )

    with pytest.raises(AttributeError):
        store.fake_method()


def test_store_no_auth():
    class fake_client(object):
        def __init__(self, *args, **kwargs):
            pass

        def no_auth_method(self):
            return "test response"

    store = Store(
        client_class=fake_client,
        store_url="https://fake.com",
        user_agent="fake_uagent",
        network_error_retry_count=50,
    )

    assert store.no_auth_method() == "test response"


def test_store_non_callable():
    class fake_client(object):
        def __init__(self, *args, **kwargs):
            self.non_callable = "test"

    store = Store(
        client_class=fake_client,
        store_url="https://fake.com",
        user_agent="fake_uagent",
        network_error_retry_count=50,
    )

    assert store.non_callable == "test"


def test_store_auth_no_token_error():
    class fake_client(object):
        def __init__(self, *args, **kwargs):
            pass

        def auth_method(self, authenticationToken):
            """pass"""

    store = Store(
        client_class=fake_client,
        store_url="https://fake.com",
        user_agent="fake_uagent",
        network_error_retry_count=50,
    )

    with pytest.raises(TypeError):
        store.auth_method()


def test_store_auth_token():
    class fake_client(object):
        def __init__(self, *args, **kwargs):
            pass

        def auth_method(self, authenticationToken):
            return authenticationToken

    store = Store(
        client_class=fake_client,
        store_url="https://fake.com",
        user_agent="fake_uagent",
        token="fake_token",
        network_error_retry_count=50,
    )

    assert store.auth_method() == "fake_token"
