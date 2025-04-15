import functools
import time
from http.client import HTTPException
from typing import Any, Callable, Dict, Optional, Tuple, Type

from thrift.protocol.TBinaryProtocol import TBinaryProtocol
from thrift.transport.THttpClient import THttpClient

from evernote_backup.evernote_client_api_tokenized import (
    TokenizedNoteStoreClient,
    TokenizedUserStoreClient,
)

DEFAULT_RETRY_MAX = 3
DEFAULT_RETRY_DELAY = 0.5
DEFAULT_RETRY_BACKOFF_FACTOR = 2.0
DEFAULT_RETRY_EXCEPTIONS = (HTTPException, ConnectionError)


class BinaryHttpThriftClient:
    def __init__(
        self,
        url: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.url = url

        self._default_headers = {
            "x-feature-version": "3",
            "accept": "application/x-thrift",
            "cache-control": "no-cache",
        }

        if user_agent:
            self._default_headers["User-Agent"] = user_agent

        if headers:
            self._default_headers.update(headers)

        self._protocol = self._create_protocol()

    def _create_protocol(self):
        try:
            thrift_http_client = THttpClient(self.url)
            thrift_http_client.setCustomHeaders(self._default_headers)
            return TBinaryProtocol(thrift_http_client)
        except Exception as e:
            raise ConnectionError(f"Failed to create Thrift binary http client: {e}")

    @property
    def protocol(self):
        return self._protocol


class UserStoreClient(TokenizedUserStoreClient):
    def __init__(
        self,
        auth_token: str,
        store_url: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self._base_client = BinaryHttpThriftClient(store_url, user_agent, headers)
        super().__init__(auth_token, self._base_client.protocol)


class NoteStoreClient(TokenizedNoteStoreClient):
    def __init__(
        self,
        auth_token: str,
        store_url: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self._base_client = BinaryHttpThriftClient(store_url, user_agent, headers)
        super().__init__(auth_token, self._base_client.protocol)


class RetryableMixin:
    """
    Mixin class that adds retry capability for network (or other) exceptions to each non-private method.
    """

    def __init__(
        self,
        *args,
        retry_max: int = DEFAULT_RETRY_MAX,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        retry_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRY_EXCEPTIONS,
        **kwargs,
    ):
        self._retry_max = retry_max
        self._retry_delay = retry_delay
        self._retry_backoff_factor = retry_backoff_factor
        self._retry_exceptions = retry_exceptions

        super().__init__(*args, **kwargs)

    def __getattribute__(self, name: str) -> Any:
        attr = object.__getattribute__(self, name)

        if name.startswith("_") or not callable(attr):
            return attr

        return self._retry()(attr)

    def _retry(self) -> Callable:
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                delay = self._retry_delay

                for attempt in range(self._retry_max + 1):
                    try:
                        return func(*args, **kwargs)
                    except self._retry_exceptions as e:
                        last_exception = e
                        if attempt < self._retry_max:
                            time.sleep(delay)
                            delay *= self._retry_backoff_factor
                        else:
                            raise last_exception

            return wrapper

        return decorator


class UserStoreClientRetryable(RetryableMixin, UserStoreClient):
    # Stating all params explicitly for IDE hints
    def __init__(
        self,
        # UserStoreClient params
        auth_token: str,
        store_url: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        # RetryableMixin params
        retry_max: int = DEFAULT_RETRY_MAX,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        retry_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRY_EXCEPTIONS,
    ):
        super().__init__(
            auth_token=auth_token,
            store_url=store_url,
            user_agent=user_agent,
            headers=headers,
            retry_max=retry_max,
            retry_delay=retry_delay,
            retry_backoff_factor=retry_backoff_factor,
            retry_exceptions=retry_exceptions,
        )


class NoteStoreClientRetryable(RetryableMixin, NoteStoreClient):
    # Stating all params explicitly for IDE hints
    def __init__(
        self,
        # NoteStoreClient params
        auth_token: str,
        store_url: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        # RetryableMixin params
        retry_max: int = DEFAULT_RETRY_MAX,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        retry_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRY_EXCEPTIONS,
    ):
        super().__init__(
            auth_token=auth_token,
            store_url=store_url,
            user_agent=user_agent,
            headers=headers,
            retry_max=retry_max,
            retry_delay=retry_delay,
            retry_backoff_factor=retry_backoff_factor,
            retry_exceptions=retry_exceptions,
        )
