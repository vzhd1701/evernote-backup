import functools
import inspect
import platform
from typing import Any, Optional, Union

from evernote.edam.error.ttypes import EDAMSystemException, EDAMUserException
from evernote.edam.notestore import NoteStore
from evernote.edam.userstore import UserStore
from thrift.protocol import TBinaryProtocol
from thrift.transport import THttpClient

from evernote_backup.evernote_client_classes import ClientV2
from evernote_backup.evernote_client_util import network_retry, raise_auth_error
from evernote_backup.token_util import get_token_shard


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
        self.shard = get_token_shard(token)

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
        return self.get_note_store()

    @property
    def user(self) -> str:
        if self._user is None:
            self._user = self.user_store.getUser().username
        return self._user

    def get_note_store(self, shard_id: str = None) -> "Store":
        if shard_id is None:
            shard_id = self.shard

        note_store_uri = self._get_endpoint(f"edam/note/{shard_id}")

        return Store(
            client_class=NoteStore.Client,
            store_url=note_store_uri,
            token=self.token,
            user_agent=self.user_agent,
            network_error_retry_count=self.network_error_retry_count,
        )


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
