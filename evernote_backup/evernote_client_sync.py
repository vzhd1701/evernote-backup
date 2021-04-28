from evernote.edam.notestore import NoteStore

from evernote_backup.config import SYNC_CHUNK_MAX_RESULTS
from evernote_backup.evernote_client import EvernoteClient


class EvernoteClientSync(EvernoteClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._tags = None

    def get_note(self, note_guid):
        note = self.note_store.getNote(
            note_guid, True, True, True, True  # noqa: WPS425
        )

        if note.tagGuids:
            note.tagNames = [self.tags[t] for t in note.tagGuids]

        return note

    def iter_sync_chunks(self, after_usn):
        sync_filter = NoteStore.SyncChunkFilter(
            includeNotes=True,
            includeNoteResources=True,
            includeNoteAttributes=True,
            includeNotebooks=True,
            includeExpunged=True,
        )

        max_results = SYNC_CHUNK_MAX_RESULTS

        while True:
            chunk = self.note_store.getFilteredSyncChunk(
                after_usn, max_results, sync_filter
            )

            yield chunk

            after_usn = chunk.chunkHighUSN

            if chunk.chunkHighUSN == chunk.updateCount:
                return

    @property
    def tags(self):
        if self._tags is None:
            self._tags = {t.guid: t.name for t in self.note_store.listTags()}
        return self._tags

    def get_remote_usn(self):
        return int(self.note_store.getSyncState().updateCount)
