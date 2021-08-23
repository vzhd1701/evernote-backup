import logging
from typing import Dict, Iterator, Optional

from evernote.edam.error.ttypes import EDAMNotFoundException
from evernote.edam.notestore import NoteStore
from evernote.edam.notestore.ttypes import SyncChunk
from evernote.edam.type.ttypes import LinkedNotebook, Note

from evernote_backup.evernote_client import EvernoteClient

logger = logging.getLogger(__name__)


class EvernoteClientSync(EvernoteClient):  # noqa: WPS214
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
        self._linked_notebooks: Optional[dict] = None
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
            includeLinkedNotebooks=True,
        )

        while True:
            chunk = self.note_store.getFilteredSyncChunk(
                after_usn, self.max_chunk_results, sync_filter
            )

            yield chunk

            after_usn = chunk.chunkHighUSN
            if chunk.chunkHighUSN == chunk.updateCount:
                return

    def iter_linked_notebook_sync_chunks(
        self, l_notebook: LinkedNotebook, after_usn: int
    ) -> Iterator[SyncChunk]:
        ln_note_store = self.get_note_store(l_notebook.shardId)
        is_full_sync = False

        while True:
            try:
                chunk = ln_note_store.getLinkedNotebookSyncChunk(
                    l_notebook, after_usn, self.max_chunk_results, is_full_sync
                )
            except EDAMNotFoundException:
                # Happens when linked notebook was unshared
                # just skip it, since expunging removed notebook will alter account data
                logger.warning(
                    f"Linked notebook '{l_notebook.shareName}' [{l_notebook.guid}]"
                    f" is not accessible, skipping..."
                )
                return

            if after_usn == chunk.updateCount:
                return

            yield chunk

            after_usn = chunk.chunkHighUSN
            if chunk.chunkHighUSN == chunk.updateCount:
                return

    def auth_linked_notebook(self, l_notebook_guid: str) -> str:
        l_notebook = self.linked_notebooks[l_notebook_guid]

        ln_note_store = self.get_note_store(l_notebook.shardId)

        auth_res = ln_note_store.authenticateToSharedNotebook(l_notebook.shareKey)

        return str(auth_res.authenticationToken)

    @property
    def linked_notebooks(self) -> Dict[str, LinkedNotebook]:
        if self._linked_notebooks is None:
            self._linked_notebooks = {
                ln.guid: ln for ln in self.note_store.listLinkedNotebooks()
            }
        return self._linked_notebooks

    @property
    def tags(self) -> Dict[str, str]:
        if self._tags is None:
            self._tags = {t.guid: t.name for t in self.note_store.listTags()}
        return self._tags

    def get_remote_usn(self) -> int:
        return int(self.note_store.getSyncState().updateCount)
