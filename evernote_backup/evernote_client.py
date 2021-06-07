import functools
import inspect
import platform
from typing import Any, Optional, Union

from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)
from evernote.edam.notestore import NoteStore
from evernote.edam.userstore import UserStore
from evernote.edam.userstore.ttypes import AuthenticationResult
from thrift.protocol import TBinaryProtocol
from thrift.transport import THttpClient

from evernote_backup.evernote_client_classes import ClientV2
from evernote_backup.evernote_client_util import EvernoteAuthError, network_retry


def raise_auth_error(exception: Union[EDAMSystemException, EDAMUserException]) -> None:
    messages = {
        EDAMErrorCode.BAD_DATA_FORMAT: {"authenticationToken": "Wrong token format!"},
        EDAMErrorCode.INVALID_AUTH: {
            "username": "Username not found!",
            "password": "Invalid password!",
            "oneTimeCode": "Invalid one-time code!",
            "authenticationToken": "Invalid authentication token!",
        },
        EDAMErrorCode.AUTH_EXPIRED: {
            "authenticationToken": "Authentication token expired or revoked!",
            "password": (
                "Password login disabled. Password reset required!\n"
                "Most probably, you log in to Evernote with Google or Apple account."
                " Use --oauth option to log in."
            ),
        },
    }

    if isinstance(exception, EDAMSystemException):
        error_param = exception.message
    else:
        error_param = exception.parameter

    try:
        error = messages[exception.errorCode][error_param]
    except KeyError:
        return

    raise EvernoteAuthError(error)


class EvernoteClientBase(object):
    def __init__(self, backend: str) -> None:
        self.backend = backend

        backends = {
            "evernote": "www.evernote.com",
            "evernote:sandbox": "sandbox.evernote.com",
            "china": "app.yinxiang.com",
            "china:sandbox": "sandbox.yinxiang.com",
        }

        self.service_host = backends[self.backend]

        if self.backend.startswith("china"):
            self.user_agent = "YXScript Windows/603139;"
        else:
            self.user_agent = "ENScript Windows/309091;"

        self.device_description = "evernote-backup"
        if platform.node():
            self.device_description += " [{0}]".format(platform.node())

    def _get_endpoint(self, path: str = "") -> str:
        return f"https://{self.service_host}/{path}"


class EvernoteClient(EvernoteClientBase):
    def __init__(
        self, backend: str, token: str, network_error_retry_count: int
    ) -> None:
        super().__init__(backend=backend)

        self.token = token
        self.network_error_retry_count = network_error_retry_count

        self._user: Optional[str] = None

    def verify_token(self) -> None:
        try:
            self.user_store.getUser()
        except (EDAMUserException, EDAMSystemException) as e:
            raise_auth_error(e)
            raise

    @property
    def user_store(self) -> "Store":
        user_store_uri = self._get_endpoint("edam/user")
        return Store(
            client_class=ClientV2,
            store_url=user_store_uri,
            token=self.token,
            user_agent=self.user_agent,
            network_error_retry_count=self.network_error_retry_count,
        )

    @property
    def note_store(self) -> "Store":
        note_store_uri = self.user_store.getNoteStoreUrl()
        return Store(
            client_class=NoteStore.Client,
            store_url=note_store_uri,
            token=self.token,
            user_agent=self.user_agent,
            network_error_retry_count=self.network_error_retry_count,
        )

    @property
    def user(self) -> str:
        if self._user is None:
            self._user = self.user_store.getUser().username
        return self._user


class EvernoteClientAuth(EvernoteClient):
    def __init__(
        self,
        backend: str,
        network_error_retry_count: int,
        consumer_key: str,
        consumer_secret: str,
    ):
        super().__init__(  # noqa: S106
            backend=backend,
            token="",
            network_error_retry_count=network_error_retry_count,
        )

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def login(self, username: str, password: str) -> AuthenticationResult:
        try:
            return self.user_store.authenticateLongSessionV2(
                username=username,
                password=password,
                ssoLoginToken=None,
                consumerKey=self.consumer_key,
                consumerSecret=self.consumer_secret,
                deviceIdentifier=None,
                deviceDescription=self.device_description,
                supportsTwoFactor=True,
                supportsBusinessOnlyAccounts=True,
            )
        except EDAMUserException as e:
            raise_auth_error(e)
            raise

    def two_factor_auth(self, auth_token: str, ota_code: str) -> AuthenticationResult:
        try:
            return self.user_store.completeTwoFactorAuthentication(
                authenticationToken=auth_token,
                oneTimeCode=ota_code,
                deviceIdentifier=None,
                deviceDescription=self.device_description,
            )
        except EDAMUserException as e:
            raise_auth_error(e)
            raise


class Store(object):
    def __init__(
        self,
        client_class: Union[UserStore.Client, NoteStore.Client],
        store_url: str,
        user_agent: str,
        network_error_retry_count: int,
        token: Optional[str] = None,
    ):
        self.token = token
        self.user_agent = user_agent
        self.network_error_retry_count = network_error_retry_count

        self._client = self._get_thrift_client(client_class, store_url)

    def __getattr__(self, name: str) -> Any:
        target_method = getattr(self._client, name)

        if not callable(target_method):
            return target_method

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            target_method_retry = network_retry(self.network_error_retry_count)(
                target_method
            )

            org_args = inspect.getfullargspec(target_method).args
            if len(org_args) == len(args) + 1:
                return target_method_retry(*args, **kwargs)
            elif self.token and "authenticationToken" in org_args:
                skip_args = ["self", "authenticationToken"]
                arg_names = [i for i in org_args if i not in skip_args]
                return functools.partial(
                    target_method_retry,
                    authenticationToken=self.token,
                )(
                    **dict(list(zip(arg_names, args))),
                )

            return target_method_retry(*args, **kwargs)

        return wrapper

    def _get_thrift_client(
        self,
        client_class: Union[UserStore.Client, NoteStore.Client],
        url: str,
    ) -> Union[UserStore.Client, NoteStore.Client]:
        http_client = THttpClient.THttpClient(url)
        http_client.setCustomHeaders(
            {
                "User-Agent": self.user_agent,
                "x-feature-version": 3,
                "accept": "application/x-thrift",
                "cache-control": "no-cache",
            }
        )

        thrift_protocol = TBinaryProtocol.TBinaryProtocol(http_client)
        return client_class(thrift_protocol)
