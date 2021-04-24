import functools
import inspect
import platform

from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)
from evernote.edam.notestore import NoteStore
from thrift.protocol import TBinaryProtocol
from thrift.transport import THttpClient

from evernote_backup.evernote_client_classes import ClientV2
from evernote_backup.evernote_client_util import EvernoteAuthError, network_retry


def raise_auth_error(exception):
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
            "password": "Password login disabled. Password reset required!",
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


class EvernoteClient(object):
    def __init__(self, token=None, backend=None):
        self.token = token
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

        self._user = None

    @network_retry
    def verify_token(self):
        try:
            self.user_store.getUser()
        except (EDAMUserException, EDAMSystemException) as e:
            raise_auth_error(e)
            raise

    @property
    def user_store(self):
        user_store_uri = self._get_endpoint("/edam/user")
        return Store(
            client_class=ClientV2,
            store_url=user_store_uri,
            token=self.token,
            user_agent=self.user_agent,
        )

    @property
    @network_retry
    def note_store(self):
        note_store_uri = self.user_store.getNoteStoreUrl()
        return Store(
            client_class=NoteStore.Client,
            store_url=note_store_uri,
            token=self.token,
            user_agent=self.user_agent,
        )

    @property
    @network_retry
    def user(self):
        if self._user is None:
            self._user = self.user_store.getUser().username
        return self._user

    def _get_endpoint(self, path=""):
        return f"https://{self.service_host}{path}"


class EvernoteClientAuth(EvernoteClient):
    def __init__(
        self,
        token=None,
        backend=None,
        consumer_key=None,
        consumer_secret=None,
    ):
        super().__init__(token=token, backend=backend)

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    @network_retry
    def login(self, username, password):
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

    @network_retry
    def two_factor_auth(self, auth_token, ota_code):
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


class Store(object):  # pragma: no cover
    def __init__(self, client_class, store_url, user_agent, token=None):
        self.token = token
        self.user_agent = user_agent

        self._client = self._get_thrift_client(client_class, store_url)

    def __getattr__(self, name):
        def delegate_method(*args, **kwargs):  # noqa: WPS430
            targetMethod = getattr(self._client, name, None)
            if targetMethod is None:
                return object.__getattribute__(self, name)(  # noqa: WPS609
                    *args,
                    **kwargs,
                )

            org_args = inspect.getfullargspec(targetMethod).args
            if len(org_args) == len(args) + 1:
                return targetMethod(*args, **kwargs)
            elif self.token and "authenticationToken" in org_args:
                skip_args = ["self", "authenticationToken"]
                arg_names = [i for i in org_args if i not in skip_args]
                return functools.partial(targetMethod, authenticationToken=self.token)(
                    **dict(list(zip(arg_names, args))),
                )

            return targetMethod(*args, **kwargs)

        return delegate_method

    def _get_thrift_client(self, client_class, url):
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
