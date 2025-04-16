import logging
import struct
import threading
from collections.abc import Iterable
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, as_completed, wait
from typing import Any, Optional

from click import progressbar
from evernote.edam.error.ttypes import EDAMErrorCode, EDAMSystemException
from evernote.edam.notestore.ttypes import SyncChunk
from evernote.edam.type.ttypes import LinkedNotebook, Note

from evernote_backup.cli_app_util import chunks, get_progress_output
from evernote_backup.evernote_client_sync import EvernoteClientSync
from evernote_backup.evernote_client_util import NotebookAuth
from evernote_backup.evernote_types import SyncChunkV2
from evernote_backup.note_storage import NoteForSync, SqliteStorage

logger = logging.getLogger(__name__)


THREAD_CHUNK_SIZE = 1000


class WrongAuthUserError(Exception):
    """Raise when remote auth user is not the same as the one registered in database"""

    def __init__(self, local_user: str, remote_user: str) -> None:
        self.local_user = local_user
        self.remote_user = remote_user


class WorkerStopException(Exception):
    """Raise when workers are stopped"""


class NoteDownloadException(Exception):
    """Raise when downloading note fails"""


def get_note_size(note: Note) -> int:
    size = note.contentLength

    size += sum(r.data.size for r in note.resources or [])

    return int(size)


class NoteClientMemoryManager:
    def __init__(self, download_cache_memory_limit: int) -> None:
        self.memory_limit = download_cache_memory_limit * 1024 * 1024

        self.memory = 0
        self.memory_lock = threading.Lock()

        self.memory_cond = threading.Condition()

    def wait_till_enough_memory(self) -> None:
        with self.memory_cond:
            self.memory_cond.wait_for(self._is_enough_memory)

    def reset_memory(self) -> None:
        with self.memory_lock:
            self.memory = 0

        with self.memory_cond:
            self.memory_cond.notify_all()

    def add_note_size(self, note: Note) -> None:
        with self.memory_lock:
            self.memory += get_note_size(note)

    def sub_note_size(self, note: Note) -> None:
        with self.memory_lock:
            self.memory -= get_note_size(note)

        with self.memory_cond:
            if self._is_enough_memory():
                self.memory_cond.notify_all()

    def report_memory(self) -> None:
        with self.memory_lock:
            memory_percent = round(self.memory / self.memory_limit, 3)

        memory_total = self.memory_limit // (1024 * 1024)

        logger.debug(f"Memory consumed: {memory_percent}% [LIMIT {memory_total} MB]")

    def _is_enough_memory(self) -> bool:
        with self.memory_lock:
            return self.memory < self.memory_limit


class NoteClientWorker:
    def __init__(  # noqa: WPS211
        self,
        token: str,
        backend: str,
        network_error_retry_count: int,
        use_system_ssl_ca: bool,
        max_chunk_results: int,
        download_cache_memory_limit: int,
    ) -> None:
        self.stop = False
        self.token = token
        self.backend = backend
        self.network_error_retry_count = network_error_retry_count
        self.use_system_ssl_ca = use_system_ssl_ca
        self.max_chunk_results = max_chunk_results

        self.memory_manager = NoteClientMemoryManager(download_cache_memory_limit)

        self._thread_data = threading.local()
        self._note_client: EvernoteClientSync

    def __call__(self, note_id: str, auth_data: Optional[NotebookAuth] = None) -> Note:
        self.memory_manager.wait_till_enough_memory()

        if self.stop:
            raise WorkerStopException

        if auth_data is None:
            auth_data = NotebookAuth(token=self.token, shard="")

        client_id = auth_data.shard + auth_data.token

        try:
            self._note_client = self.clients[client_id]
        except KeyError:
            self._note_client = EvernoteClientSync(
                token=auth_data.token,
                backend=self.backend,
                network_error_retry_count=self.network_error_retry_count,
                use_system_ssl_ca=self.use_system_ssl_ca,
                max_chunk_results=self.max_chunk_results,
            )

            if auth_data.shard:
                self._note_client.shard = auth_data.shard
                self._note_client.shared_mode = True

            self.clients[client_id] = self._note_client

        note = self.download_note(note_id)

        self.memory_manager.add_note_size(note)
        self.memory_manager.report_memory()

        return note

    def download_note(self, note_id: str) -> Note:
        retry_count = 5

        for _ in range(retry_count):
            try:
                return self._note_client.get_note(note_id)
            except EDAMSystemException as e:
                if e.errorCode == EDAMErrorCode.RATE_LIMIT_REACHED:
                    raise

                raise NoteDownloadException(
                    f"Remote server returned system error ({e.errorCode.name} - {e.message})"
                    f" while downloading note [{note_id}]"
                )
            except struct.error:
                logger.debug(
                    f"Remote server returned bad data"
                    f" while downloading note [{note_id}], retrying..."
                )

        raise NoteDownloadException(
            f"Failed to download note [{note_id}] after {retry_count} attempts!"
        )

    @property
    def clients(self) -> Any:
        try:
            return self._thread_data.note_clients
        except AttributeError:
            self._thread_data.note_clients = {}
            return self._thread_data.note_clients


class NoteSynchronizer:  # noqa: WPS214
    def __init__(
        self,
        note_client: EvernoteClientSync,
        note_storage: SqliteStorage,
        max_download_workers: int,
        download_cache_memory_limit: int,
        include_tasks: bool,
    ) -> None:
        self._count_updated_notebooks = 0
        self._count_updated_notes = 0
        self._count_updated_tasks = 0
        self._count_updated_reminders = 0

        self._count_expunged_notebooks = 0
        self._count_expunged_linked_notebooks = 0
        self._count_expunged_notes = 0
        self._count_expunged_tasks = 0
        self._count_expunged_reminders = 0

        self.note_client = note_client
        self.storage = note_storage
        self.max_download_workers = max_download_workers
        self.include_tasks = include_tasks

        self.note_worker = NoteClientWorker(
            token=self.note_client.token,
            backend=self.note_client.backend,
            network_error_retry_count=self.note_client.network_error_retry_count,
            use_system_ssl_ca=self.note_client.use_system_ssl_ca,
            max_chunk_results=self.note_client.max_chunk_results,
            download_cache_memory_limit=download_cache_memory_limit,
        )
        self.linked_notebooks_auth: dict[str, NotebookAuth] = {}

    def sync(self) -> None:
        self._raise_on_wrong_user()

        logger.info("Syncing user notebooks...")

        self._sync_chunks()

        if self.note_client.linked_notebooks:
            logger.info("Syncing linked notebooks...")

            for l_notebook in self.note_client.linked_notebooks.values():
                self._sync_linked_notebook(l_notebook)

        notes_to_sync = self.storage.notes.get_notes_for_sync()

        if notes_to_sync:
            logger.info(f"{len(notes_to_sync)} note(s) to download...")

            self._authorize_linked_notebooks_for_notes(notes_to_sync)
            self._download_scheduled_notes(notes_to_sync)

            self._count_updated_notes = len(notes_to_sync)

        if self.include_tasks:
            logger.info("Syncing tasks...")
            self._sync_chunks_v2()

        report = [
            ("Updated or added notebooks", self._count_updated_notebooks),
            ("Updated or added notes", self._count_updated_notes),
            ("Updated or added tasks", self._count_updated_tasks),
            ("Updated or added reminders", self._count_updated_reminders),
            ("Expunged notebooks", self._count_expunged_notebooks),
            ("Expunged linked notebooks", self._count_expunged_linked_notebooks),
            ("Expunged notes", self._count_expunged_notes),
            ("Expunged tasks", self._count_expunged_tasks),
            ("Expunged reminders", self._count_expunged_reminders),
        ]

        for msg, count in report:
            if count > 0:
                logger.info(f"{msg}: {count}")

    def _authorize_linked_notebooks_for_notes(
        self, notes_to_sync: tuple[NoteForSync, ...]
    ) -> None:
        linked_notebooks = {
            n.linked_notebook_guid for n in notes_to_sync if n.linked_notebook_guid
        }

        if linked_notebooks:
            logger.info(
                f"Requesting access to {len(linked_notebooks)} linked notebook(s)..."
            )

            for ln_guid in linked_notebooks:
                nb = self.storage.notebooks.get_notebook_by_linked_guid(ln_guid)
                auth_token = self.note_client.auth_linked_notebook(ln_guid, nb.guid)

                self.linked_notebooks_auth[ln_guid] = auth_token

    def _raise_on_wrong_user(self) -> None:
        remote_user = self.note_client.user
        local_user = self.storage.config.get_config_value("user")

        if remote_user != local_user:
            raise WrongAuthUserError(local_user, remote_user)

    def _sync_chunks(self) -> None:
        remote_usn = self.note_client.get_remote_usn()
        current_usn = int(self.storage.config.get_config_value("USN"))

        if remote_usn == current_usn:
            logger.info("User notebooks are up to date, nothing to sync!")
            return

        last_usn = current_usn
        with progressbar(  # type: ignore
            length=remote_usn - current_usn,
            show_pos=True,
            file=get_progress_output(),
        ) as chunks_bar:
            for chunk in self.note_client.iter_sync_chunks(current_usn):
                self._process_chunk(chunk)

                self.storage.config.set_config_value("USN", str(chunk.chunkHighUSN))

                chunks_bar.update(chunk.chunkHighUSN - last_usn)
                last_usn = chunk.chunkHighUSN

    def _sync_linked_notebook(self, l_notebook: LinkedNotebook) -> None:
        current_usn = self.storage.notebooks.get_linked_notebook_usn(l_notebook.guid)

        l_notebook_chunks = self.note_client.iter_linked_notebook_sync_chunks(
            l_notebook, current_usn
        )

        for chunk in l_notebook_chunks:
            for notebook in chunk.notebooks or []:
                # Correct stack info is in LinkedNotebook
                notebook.stack = l_notebook.stack
                self.storage.notebooks.add_linked_notebook(l_notebook, notebook)

            self._process_chunk(chunk)

            self.storage.notebooks.set_linked_notebook_usn(
                l_notebook.guid, chunk.chunkHighUSN
            )

    def _process_chunk(self, chunk: SyncChunk) -> None:
        self._expunge(
            expunged_notebooks=chunk.expungedNotebooks,
            expunged_notes=chunk.expungedNotes,
            expunged_linked_notebooks=chunk.expungedLinkedNotebooks,
        )

        if chunk.notebooks:
            self.storage.notebooks.add_notebooks(chunk.notebooks)

            self._count_updated_notebooks += len(chunk.notebooks)

        if chunk.notes:
            self.storage.notes.add_notes_for_sync(chunk.notes)

    def _expunge(
        self,
        expunged_notebooks: Optional[list[str]] = None,
        expunged_notes: Optional[list[str]] = None,
        expunged_linked_notebooks: Optional[list[str]] = None,
        expunged_tasks: Optional[list[str]] = None,
        expunged_reminders: Optional[list[str]] = None,
    ) -> None:
        if expunged_notebooks:
            self.storage.notebooks.expunge_notebooks(expunged_notebooks)

            self._count_expunged_notebooks += len(expunged_notebooks)

        if expunged_notes:
            self.storage.notes.expunge_notes(expunged_notes)

            self._count_expunged_notes += len(expunged_notes)

        if expunged_tasks:
            self.storage.tasks.expunge_tasks(expunged_tasks)

            self._count_expunged_tasks += len(expunged_tasks)

        if expunged_reminders:
            self.storage.reminders.expunge_reminders(expunged_reminders)

            self._count_expunged_reminders += len(expunged_reminders)

        if expunged_linked_notebooks:
            for l_notebook_guid in expunged_linked_notebooks:
                self._expunge_linked_assoc(l_notebook_guid)

            self.storage.notebooks.expunge_linked_notebooks(expunged_linked_notebooks)

            self._count_expunged_linked_notebooks += len(expunged_linked_notebooks)

    def _expunge_linked_assoc(self, l_notebook_guid: str) -> None:
        try:
            notebook = self.storage.notebooks.get_notebook_by_linked_guid(
                l_notebook_guid
            )
        except ValueError:
            return

        self.storage.notebooks.expunge_notebooks((notebook.guid,))
        self.storage.notes.expunge_notes_by_notebook(notebook.guid)

    def _download_scheduled_notes(self, notes_to_sync: tuple[NoteForSync, ...]) -> None:
        logger.info(f"Downloading {len(notes_to_sync)} note(s)...")
        logger.debug(f"Sync worker threads: {self.max_download_workers}")

        with ThreadPoolExecutor(max_workers=self.max_download_workers) as executor:
            with progressbar(  # type: ignore
                length=len(notes_to_sync),
                show_pos=True,
                file=get_progress_output(),
            ) as notes_bar:
                for notes_to_sync_chunk in chunks(notes_to_sync, THREAD_CHUNK_SIZE):
                    self._process_download_chunk(
                        executor, notes_bar, notes_to_sync_chunk
                    )

    def _process_download_chunk(
        self,
        executor: Any,
        notes_bar: Any,
        notes_chunk: Iterable[NoteForSync],
    ) -> None:
        note_futures = {
            executor.submit(
                self.note_worker,
                n.guid,
                self.linked_notebooks_auth.get(n.linked_notebook_guid),  # type: ignore
            ): n.title
            for n in notes_chunk
        }

        try:
            for note_f in as_completed(note_futures):
                f_exc = note_f.exception()
                if f_exc is not None:
                    if isinstance(f_exc, NoteDownloadException):
                        logger.error(f_exc)
                        logger.warning(
                            f"Note '{note_futures[note_f]}' will be skipped for this run"
                            " and retried during the next sync."
                        )
                        notes_bar.update(1)
                        continue
                    elif isinstance(f_exc, EDAMSystemException):
                        # Only for rate limit error
                        raise f_exc
                    else:
                        logger.critical(
                            f"Unknown exception caught while downloading note"
                            f" '{note_futures[note_f]}'!"
                        )

                        raise f_exc

                note = note_f.result(timeout=120)  # noqa: WPS432
                self.storage.notes.add_note(note)

                self.note_worker.memory_manager.sub_note_size(note)

                notes_bar.update(1, note)

        except (KeyboardInterrupt, Exception):
            logger.warning("Aborting, please wait...")

            self.note_worker.stop = True
            self.note_worker.memory_manager.reset_memory()

            wait(note_futures, timeout=30, return_when=FIRST_EXCEPTION)  # noqa: WPS432

            raise

    def _sync_chunks_v2(self) -> None:
        last_connection_tasks = int(
            self.storage.config.get_config_value("last_connection_tasks")
        )

        chunk_iter = self.note_client.iter_sync_chunks_v2(last_connection_tasks)

        with progressbar(
            chunk_iter, show_pos=True, file=get_progress_output()
        ) as chunks_bar:
            for chunk in chunks_bar:
                self._process_chunk_v2(chunk)
                self.storage.config.set_config_value(
                    "last_connection_tasks", str(chunk.last_timestamp + 1)
                )

    def _process_chunk_v2(self, chunk: SyncChunkV2) -> None:
        self._expunge(
            expunged_tasks=chunk.expunged_tasks,
            expunged_reminders=chunk.expunged_reminders,
        )

        if chunk.tasks:
            self.storage.tasks.add_tasks(chunk.tasks)

            self._count_updated_tasks += len(chunk.tasks)

        if chunk.reminders:
            self.storage.reminders.add_reminders(chunk.reminders)

            self._count_updated_reminders += len(chunk.reminders)
