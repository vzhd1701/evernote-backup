from typing import Dict, Iterator, Optional

from evernote.edam.notestore import NoteStore
from evernote.edam.notestore.ttypes import SyncChunk
from evernote.edam.type.ttypes import Note

from evernote_backup.evernote_client import EvernoteClient


class EvernoteClientSync(EvernoteClient):
    def __init__(
        self,
        backend: str,
        token: str,
        network_error_retry_count: int,
        max_chunk_results: int,
    ) -> None:
        super().__init__(
            backend=backend,
            token=token,
            network_error_retry_count=network_error_retry_count,
        )

        self._tags: Optional[dict] = None
        self.max_chunk_results = max_chunk_results

    def get_note(self, note_guid: str) -> Note:
        note = self.note_store.getNote(
            note_guid, True, True, True, True  # noqa: WPS425
        )

        if note.tagGuids:
            note.tagNames = [self.tags[t] for t in note.tagGuids]

        return note

    def iter_sync_chunks(self, after_usn: int) -> Iterator[SyncChunk]:
        sync_filter = NoteStore.SyncChunkFilter(
            includeNotes=True,
            includeNoteResources=True,
            includeNoteAttributes=True,
            includeNotebooks=True,
            includeExpunged=True,
        )

        while True:
            chunk = self.note_store.getFilteredSyncChunk(
                after_usn, self.max_chunk_results, sync_filter
            )

            yield chunk

            after_usn = chunk.chunkHighUSN

            if chunk.chunkHighUSN == chunk.updateCount:
                return

    @property
    def tags(self) -> Dict[str, str]:
        if self._tags is None:
            self._tags = {t.guid: t.name for t in self.note_store.listTags()}
        return self._tags

    def get_remote_usn(self) -> int:
        return int(self.note_store.getSyncState().updateCount)
