import json
import platform
import uuid
from collections.abc import Iterator
from typing import Optional

from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)
from evernote.edam.userstore.constants import EDAM_VERSION_MAJOR, EDAM_VERSION_MINOR
from requests_sse import EventSource, MessageEvent

from evernote_backup.evernote_client_api_http import (
    NoteStoreClientRetryable,
    UserStoreClientRetryable,
)
from evernote_backup.evernote_client_util import EvernoteAuthError, raise_auth_error
from evernote_backup.evernote_types import EvernoteEntityType
from evernote_backup.token_util import EvernoteToken


class EvernoteClientBase:
    def __init__(self, backend: str) -> None:
        self.backend = backend

        backends = {
            "evernote": "www.evernote.com",
            "china": "app.yinxiang.com",
            "china:sandbox": "sandbox.yinxiang.com",
        }

        self.service_host = backends[self.backend]

        if self.backend.startswith("china"):
            self.user_agent = "YXScript Windows/603139;"
        else:
            self.user_agent = "ENScript Windows/309091;"

        platform_node = platform.node()
        platform_node_postfix = f" [{platform_node}]" if platform_node else ""

        self.device_description = f"evernote-backup{platform_node_postfix}"

    def _get_endpoint(self, path: str = "") -> str:
        return f"https://{self.service_host}/{path}"


class EvernoteClient(EvernoteClientBase):
    def __init__(
        self,
        backend: str,
        token: Optional[str] = None,
        network_error_retry_count: int = 5,
        cafile: Optional[str] = None,
    ) -> None:
        super().__init__(backend=backend)

        self.token: Optional[EvernoteToken] = None
        self.shard: Optional[str] = None

        if token:
            self.token = EvernoteToken.from_string(token)
            self.shard = self.token.shard

        self.network_error_retry_count = network_error_retry_count
        self.cafile = cafile

        self._user: Optional[str] = None
        self._token_jwt: Optional[str] = None

    def check_version(self) -> bool:
        return self.user_store.checkVersion(
            self.user_agent, EDAM_VERSION_MAJOR, EDAM_VERSION_MINOR
        )

    def verify_token(self) -> None:
        try:
            self.user_store.getUser()
        except (EDAMUserException, EDAMSystemException) as e:
            raise_auth_error(e)
            raise

    @property
    def user_store(self) -> "UserStoreClientRetryable":
        token = str(self.token) if self.token else ""
        user_store_uri = self._get_endpoint("edam/user")

        return UserStoreClientRetryable(
            auth_token=token,
            store_url=user_store_uri,
            user_agent=self.user_agent,
            retry_max=self.network_error_retry_count,
            cafile=self.cafile,
        )

    @property
    def note_store(self) -> "NoteStoreClientRetryable":
        return self.get_note_store()

    @property
    def user(self) -> str:
        if self._user is None:
            self._user = self.user_store.getUser().username
        return self._user

    def get_note_store(
        self,
        shard: Optional[str] = None,
    ) -> "NoteStoreClientRetryable":
        token = str(self.token) if self.token else ""
        shard = shard if shard else self.shard
        note_store_uri = self._get_endpoint(f"edam/note/{shard}")

        return NoteStoreClientRetryable(
            auth_token=token,
            store_url=note_store_uri,
            user_agent=self.user_agent,
            retry_max=self.network_error_retry_count,
            cafile=self.cafile,
        )

    def refresh_jwt_token(self) -> None:
        try:
            self._token_jwt = self.user_store.getNAPAccessToken()
        except (EDAMUserException, EDAMSystemException) as e:
            if e.errorCode == EDAMErrorCode.PERMISSION_DENIED:
                raise EvernoteAuthError(
                    "This auth token does not have permission to use the new Evernote API."
                    " Please refer to readme file (Tasks section) for more information:"
                    " https://github.com/vzhd1701/evernote-backup#tasks"
                )
            raise_auth_error(e)
            raise

    def iter_sync_events(self, last_connection: int) -> Iterator[MessageEvent]:
        if not self._token_jwt:
            self.refresh_jwt_token()

        headers = {
            "User-Agent": self.user_agent,
            "x-feature-version": "4",
            "x-conduit-version": "2.40.2",
            "Authorization": f"Bearer {self._token_jwt}",
        }

        connection_id = uuid.uuid4()

        entity_filter = [EvernoteEntityType.TASK, EvernoteEntityType.REMINDER]
        entity_filter_arg = json.dumps(entity_filter, separators=(",", ":"))

        url = f"https://api.evernote.com/sync/v1/download?lastConnection={last_connection}&connectionId={connection_id}&entityFilter={entity_filter_arg}"

        with EventSource(url, timeout=30, headers=headers) as event_source:
            yield from event_source
