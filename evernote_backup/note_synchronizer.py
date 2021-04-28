# -*- coding: utf-8 -*-

import logging
import threading
from concurrent import futures

from click import progressbar

from evernote_backup.cli_app_util import get_progress_output
from evernote_backup.config import SYNC_MAX_DOWNLOAD_WORKERS
from evernote_backup.evernote_client_sync import EvernoteClientSync

logger = logging.getLogger(__name__)


class WrongAuthUserError(Exception):
    """Raise when remote auth user is not the same as the one registered in database"""

    def __init__(self, local_user, remote_user):
        self.local_user = local_user
        self.remote_user = remote_user


class NoteClientWorker(object):
    def __init__(self, token, backend):
        self.stop = False
        self.token = token
        self.backend = backend

        self._thread_data = threading.local()

    def __call__(self, note_id):
        if self.stop:
            return  # noqa: WPS324

        try:
            note_client = self._thread_data.note_client
        except AttributeError:
            note_client = EvernoteClientSync(token=self.token, backend=self.backend)
            self._thread_data.note_client = note_client

        return note_client.get_note(note_id)


class NoteSynchronizer(object):
    def __init__(self, note_client, note_storage):
        self._count_updated_notebooks = 0
        self._count_updated_notes = 0

        self._count_expunged_notebooks = 0
        self._count_expunged_notes = 0

        self.note_client = note_client
        self.storage = note_storage

    def sync(self):
        self._raise_on_wrong_user()

        remote_usn = self.note_client.get_remote_usn()
        current_usn = int(self.storage.config.get_config_value("USN"))

        if remote_usn == current_usn:
            logger.info("Noting to sync, current database is up to date!")
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

    def _raise_on_wrong_user(self):
        remote_user = self.note_client.user
        local_user = self.storage.config.get_config_value("user")

        if remote_user != local_user:
            raise WrongAuthUserError(local_user, remote_user)

    def _sync_chunks(self, current_usn, remote_usn):
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

    def _expunge(self, expunged_notebooks, expunged_notes):
        if expunged_notebooks:
            self.storage.notebooks.expunge_notebooks(expunged_notebooks)

            self._count_expunged_notebooks += len(expunged_notebooks)

        if expunged_notes:
            self.storage.notes.expunge_notes(expunged_notes)

            self._count_expunged_notes += len(expunged_notes)

    def _download_scheduled_notes(self, notes_to_sync):
        with futures.ThreadPoolExecutor(
            max_workers=SYNC_MAX_DOWNLOAD_WORKERS
        ) as executor:
            note_worker = NoteClientWorker(
                self.note_client.token,
                self.note_client.backend,
            )

            note_futures = {
                executor.submit(note_worker, note_guid): note_title
                for note_guid, note_title in notes_to_sync
            }

            try:
                self._progress_sync_notes(note_futures)
            except KeyboardInterrupt:
                note_worker.stop = True

                logger.warning("Aborting, please wait...")
                futures.wait(note_futures)

                raise

    def _progress_sync_notes(self, note_futures):
        notes = futures.as_completed(note_futures)

        with progressbar(
            notes,
            length=len(note_futures),
            item_show_func=lambda x: note_futures[x] if x else None,
            show_pos=True,
            file=get_progress_output(),
        ) as notes_bar:
            for note_f in notes_bar:
                note = note_f.result()
                self.storage.notes.add_note(note)
