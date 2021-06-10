# -*- coding: utf-8 -*-

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from typing import Any, Iterable, List, Tuple

from click import progressbar
from evernote.edam.type.ttypes import Note

from evernote_backup.cli_app_util import chunks, get_progress_output
from evernote_backup.evernote_client_sync import EvernoteClientSync
from evernote_backup.note_storage import SqliteStorage

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

    def __call__(self, note_id: str) -> Note:
        if self.stop:
            raise WorkerStopException

        try:
            note_client = self._thread_data.note_client
        except AttributeError:
            note_client = EvernoteClientSync(
                token=self.token,
                backend=self.backend,
                network_error_retry_count=self.network_error_retry_count,
                max_chunk_results=self.max_chunk_results,
            )
            self._thread_data.note_client = note_client

        return note_client.get_note(note_id)


class NoteSynchronizer(object):
    def __init__(
        self,
        note_client: EvernoteClientSync,
        note_storage: SqliteStorage,
        max_download_workers: int,
    ) -> None:
        self._count_updated_notebooks = 0
        self._count_updated_notes = 0

        self._count_expunged_notebooks = 0
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

    def sync(self) -> None:
        self._raise_on_wrong_user()

        remote_usn = self.note_client.get_remote_usn()
        current_usn = int(self.storage.config.get_config_value("USN"))

        if remote_usn == current_usn:
            logger.info("Nothing to sync, current database is up to date!")
        else:
            logger.info("Syncing latest changes...")
            self._sync_chunks(current_usn, remote_usn)

        notes_to_sync = self.storage.notes.get_notes_for_sync()

        if notes_to_sync:
            logger.info("{0} notes to download...".format(len(notes_to_sync)))
            self._download_scheduled_notes(notes_to_sync)

            self._count_updated_notes = len(notes_to_sync)

        report = [
            f"Updated or added notebooks: {self._count_updated_notebooks}",
            f"Updated or added notes: {self._count_updated_notes}",
            f"Expunged notebooks: {self._count_expunged_notebooks}",
            f"Expunged notes: {self._count_expunged_notes}",
        ]

        for msg in report:
            logger.info(msg)

    def _raise_on_wrong_user(self) -> None:
        remote_user = self.note_client.user
        local_user = self.storage.config.get_config_value("user")

        if remote_user != local_user:
            raise WrongAuthUserError(local_user, remote_user)

    def _sync_chunks(self, current_usn: int, remote_usn: int) -> None:
        last_usn = current_usn
        with progressbar(
            length=remote_usn - current_usn,
            show_pos=True,
            file=get_progress_output(),
        ) as chunks_bar:
            for chunk in self.note_client.iter_sync_chunks(current_usn):
                if current_usn > 0:
                    self._expunge(chunk.expungedNotebooks, chunk.expungedNotes)

                if chunk.notebooks:
                    self.storage.notebooks.add_notebooks(chunk.notebooks)

                    self._count_updated_notebooks += len(chunk.notebooks)

                if chunk.notes:
                    self.storage.notes.add_notes_for_sync(chunk.notes)

                self.storage.config.set_config_value("USN", str(chunk.chunkHighUSN))

                chunks_bar.update(chunk.chunkHighUSN - last_usn)
                last_usn = chunk.chunkHighUSN

    def _expunge(
        self, expunged_notebooks: List[str], expunged_notes: List[str]
    ) -> None:
        if expunged_notebooks:
            self.storage.notebooks.expunge_notebooks(expunged_notebooks)

            self._count_expunged_notebooks += len(expunged_notebooks)

        if expunged_notes:
            self.storage.notes.expunge_notes(expunged_notes)

            self._count_expunged_notes += len(expunged_notes)

    def _download_scheduled_notes(
        self, notes_to_sync: Tuple[Tuple[str, str], ...]
    ) -> None:

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
        notes_chunk: Iterable[Tuple[str, str]],
    ) -> None:
        note_futures = {
            executor.submit(self.note_worker, note_guid): note_title
            for note_guid, note_title in notes_chunk
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
