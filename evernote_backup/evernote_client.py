import json
import platform
import uuid
from typing import Iterator, Optional

from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)
from requests_sse import EventSource, MessageEvent

from evernote_backup.evernote_client_api_http import (
    NoteStoreClientRetryable,
    UserStoreClientRetryable,
)
from evernote_backup.evernote_client_util import EvernoteAuthError, raise_auth_error
from evernote_backup.evernote_types import EvernoteEntityType
from evernote_backup.token_util import get_token_shard


class EvernoteClientBase(object):
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
        self._token_jwt: Optional[str] = None

    def verify_token(self) -> None:
        try:
            self.user_store.getUser()
        except (EDAMUserException, EDAMSystemException) as e:
            raise_auth_error(e)
            raise

    @property
    def user_store(self) -> "UserStoreClientRetryable":
        user_store_uri = self._get_endpoint("edam/user")

        us = UserStoreClientRetryable(
            auth_token=self.token,
            store_url=user_store_uri,
            user_agent=self.user_agent,
            retry_max=self.network_error_retry_count,
        )

        return UserStoreClientRetryable(
            auth_token=self.token,
            store_url=user_store_uri,
            user_agent=self.user_agent,
            retry_max=self.network_error_retry_count,
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
        shard_id: Optional[str] = None,
    ) -> "NoteStoreClientRetryable":
        if shard_id is None:
            shard_id = self.shard

        note_store_uri = self._get_endpoint(f"edam/note/{shard_id}")

        return NoteStoreClientRetryable(
            auth_token=self.token,
            store_url=note_store_uri,
            user_agent=self.user_agent,
            retry_max=self.network_error_retry_count,
        )

    def refresh_jwt_token(self):
        try:
            self._token_jwt = self.user_store.getNAPAccessToken()
        except (EDAMUserException, EDAMSystemException) as e:
            if e.errorCode == EDAMErrorCode.PERMISSION_DENIED:
                raise EvernoteAuthError(
                    "This auth token does not have permission to use the new Evernote API."
                    " Please refer to readme file (Tasks section) for more information:"
                    " https://github.com/vzhd1701/evernote-backup#Tasks"
                )
            raise_auth_error(e)
            raise

    def iter_sync_events(self, last_connection: int) -> Iterator[MessageEvent]:
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
