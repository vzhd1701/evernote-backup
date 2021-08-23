# -*- coding: utf-8 -*-

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from typing import Any, Dict, Iterable, List, Tuple

from click import progressbar
from evernote.edam.notestore.ttypes import SyncChunk
from evernote.edam.type.ttypes import LinkedNotebook, Note

from evernote_backup.cli_app_util import chunks, get_progress_output
from evernote_backup.evernote_client_sync import EvernoteClientSync
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


class NoteClientWorker(object):
    def __init__(
        self,
        token: str,
        backend: str,
        network_error_retry_count: int,
        max_chunk_results: int,
    ) -> None:
        self.stop = False
        self.token = token
        self.backend = backend
        self.network_error_retry_count = network_error_retry_count
        self.max_chunk_results = max_chunk_results

        self._thread_data = threading.local()

    def __call__(self, note_id: str, token: str = None) -> Note:
        if self.stop:
            raise WorkerStopException

        if token is None:
            token = self.token

        try:
            note_client = self.clients[token]
        except KeyError:
            note_client = EvernoteClientSync(
                token=token,
                backend=self.backend,
                network_error_retry_count=self.network_error_retry_count,
                max_chunk_results=self.max_chunk_results,
            )
            self.clients[token] = note_client

        return note_client.get_note(note_id)

    @property
    def clients(self) -> Any:
        try:
            return self._thread_data.note_clients
        except AttributeError:
            self._thread_data.note_clients = {}
            return self._thread_data.note_clients


class NoteSynchronizer(object):  # noqa: WPS214
    def __init__(
        self,
        note_client: EvernoteClientSync,
        note_storage: SqliteStorage,
        max_download_workers: int,
    ) -> None:
        self._count_updated_notebooks = 0
        self._count_updated_notes = 0

        self._count_expunged_notebooks = 0
        self._count_expunged_linked_notebooks = 0
        self._count_expunged_notes = 0

        self.note_client = note_client
        self.storage = note_storage
        self.max_download_workers = max_download_workers

        self.note_worker = NoteClientWorker(
            self.note_client.token,
            self.note_client.backend,
            self.note_client.network_error_retry_count,
            self.note_client.max_chunk_results,
        )
        self.linked_notebooks_auth: Dict[str, str] = {}

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
            logger.info("{0} notes to download...".format(len(notes_to_sync)))

            self._authorize_linked_notebooks_for_notes(notes_to_sync)
            self._download_scheduled_notes(notes_to_sync)

            self._count_updated_notes = len(notes_to_sync)

        report = [
            f"Updated or added notebooks: {self._count_updated_notebooks}",
            f"Updated or added notes: {self._count_updated_notes}",
            f"Expunged notebooks: {self._count_expunged_notebooks}",
            f"Expunged linked notebooks: {self._count_expunged_linked_notebooks}",
            f"Expunged notes: {self._count_expunged_notes}",
        ]

        for msg in report:
            logger.info(msg)

    def _authorize_linked_notebooks_for_notes(
        self, notes_to_sync: Tuple[NoteForSync, ...]
    ) -> None:
        linked_notebooks = {
            n.linked_notebook_guid for n in notes_to_sync if n.linked_notebook_guid
        }

        if linked_notebooks:
            logger.debug(
                "Requesting access to {0} linked notebooks...".format(
                    len(linked_notebooks)
                )
            )

            self.linked_notebooks_auth = {
                n_guid: self.note_client.auth_linked_notebook(n_guid)
                for n_guid in linked_notebooks
            }

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
        with progressbar(
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
            chunk.expungedNotebooks,
            chunk.expungedNotes,
            chunk.expungedLinkedNotebooks,
        )

        if chunk.notebooks:
            self.storage.notebooks.add_notebooks(chunk.notebooks)

            self._count_updated_notebooks += len(chunk.notebooks)

        if chunk.notes:
            self.storage.notes.add_notes_for_sync(chunk.notes)

    def _expunge(
        self,
        expunged_notebooks: List[str],
        expunged_notes: List[str],
        expunged_linked_notebooks: List[str],
    ) -> None:
        if expunged_notebooks:
            self.storage.notebooks.expunge_notebooks(expunged_notebooks)

            self._count_expunged_notebooks += len(expunged_notebooks)

        if expunged_notes:
            self.storage.notes.expunge_notes(expunged_notes)

            self._count_expunged_notes += len(expunged_notes)

        if expunged_linked_notebooks:
            for l_notebook_guid in expunged_linked_notebooks:
                notebook = self.storage.notebooks.get_notebook_by_linked_guid(
                    l_notebook_guid
                )

                if notebook:
                    self.storage.notebooks.expunge_notebooks((notebook.guid,))
                    self.storage.notes.expunge_notes_by_notebook(notebook.guid)

            self.storage.notebooks.expunge_linked_notebooks(expunged_linked_notebooks)

            self._count_expunged_linked_notebooks += len(expunged_linked_notebooks)

    def _download_scheduled_notes(self, notes_to_sync: Tuple[NoteForSync, ...]) -> None:
        with ThreadPoolExecutor(max_workers=self.max_download_workers) as executor:
            with progressbar(
                length=len(notes_to_sync),
                show_pos=True,
                file=get_progress_output(),
                item_show_func=lambda x: x.title if x else "",  # type: ignore
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
                note = note_f.result()
                self.storage.notes.add_note(note)
                notes_bar.update(1, note)
        except KeyboardInterrupt:
            self.note_worker.stop = True

            logger.warning("Aborting, please wait...")
            wait(note_futures)

            raise
