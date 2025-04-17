import functools
import time
from http.client import HTTPException
from typing import Any, Callable, Optional

from requests.utils import DEFAULT_CA_BUNDLE_PATH, extract_zipped_paths
from six.moves import http_client
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


class TBinaryProtocolHotfix(TBinaryProtocol):
    """
    Hotfix to prevent crash on bad data string from server
    """

    def readString(self):  # pragma: no cover
        return self.readBinary().decode("utf-8", errors="replace")


class THttpClientHotfix(THttpClient):
    """
    Hotfix for deprecated `key_file` and `cert_file` args
    https://issues.apache.org/jira/browse/THRIFT-5847
    https://github.com/apache/thrift/pull/3108
    """

    def open(self):  # pragma: no cover
        if self.scheme == "http":
            self._THttpClient__http = http_client.HTTPConnection(
                self.host,
                self.port,
                timeout=self._THttpClient__timeout,
            )
        elif self.scheme == "https":
            self._THttpClient__http = http_client.HTTPSConnection(
                self.host,
                self.port,
                timeout=self._THttpClient__timeout,
                context=self.context,
            )
        if self.using_proxy():
            self._THttpClient__http.set_tunnel(
                self.realhost,
                self.realport,
                {"Proxy-Authorization": self.proxy_auth},
            )


class BinaryHttpThriftClient:
    def __init__(
        self,
        url: str,
        user_agent: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        use_system_ssl_ca: bool = False,
    ):
        self.url = url
        self.use_system_ssl_ca = use_system_ssl_ca

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
        if self.use_system_ssl_ca:
            cafile = None
        else:
            cafile = extract_zipped_paths(DEFAULT_CA_BUNDLE_PATH)

        try:
            thrift_http_client = THttpClientHotfix(self.url, cafile=cafile)
            thrift_http_client.setCustomHeaders(self._default_headers)
            return TBinaryProtocolHotfix(thrift_http_client)
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
        headers: Optional[dict[str, str]] = None,
        use_system_ssl_ca: bool = False,
    ):
        self._base_client = BinaryHttpThriftClient(
            url=store_url,
            user_agent=user_agent,
            headers=headers,
            use_system_ssl_ca=use_system_ssl_ca,
        )
        super().__init__(auth_token, self._base_client.protocol)


class NoteStoreClient(TokenizedNoteStoreClient):
    def __init__(
        self,
        auth_token: str,
        store_url: str,
        user_agent: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        use_system_ssl_ca: bool = False,
    ):
        self._base_client = BinaryHttpThriftClient(
            url=store_url,
            user_agent=user_agent,
            headers=headers,
            use_system_ssl_ca=use_system_ssl_ca,
        )
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
        retry_exceptions: tuple[type[Exception], ...] = DEFAULT_RETRY_EXCEPTIONS,
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
        headers: Optional[dict[str, str]] = None,
        use_system_ssl_ca: bool = False,
        # RetryableMixin params
        retry_max: int = DEFAULT_RETRY_MAX,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        retry_exceptions: tuple[type[Exception], ...] = DEFAULT_RETRY_EXCEPTIONS,
    ):
        super().__init__(
            auth_token=auth_token,
            store_url=store_url,
            user_agent=user_agent,
            headers=headers,
            use_system_ssl_ca=use_system_ssl_ca,
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
        headers: Optional[dict[str, str]] = None,
        use_system_ssl_ca: bool = False,
        # RetryableMixin params
        retry_max: int = DEFAULT_RETRY_MAX,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        retry_exceptions: tuple[type[Exception], ...] = DEFAULT_RETRY_EXCEPTIONS,
    ):
        super().__init__(
            auth_token=auth_token,
            store_url=store_url,
            user_agent=user_agent,
            headers=headers,
            use_system_ssl_ca=use_system_ssl_ca,
            retry_max=retry_max,
            retry_delay=retry_delay,
            retry_backoff_factor=retry_backoff_factor,
            retry_exceptions=retry_exceptions,
        )
