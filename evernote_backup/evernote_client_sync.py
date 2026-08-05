import json
import logging
from collections.abc import Iterator, Sequence
from typing import Any, Optional

from evernote.edam.error.ttypes import EDAMNotFoundException
from evernote.edam.notestore import NoteStore
from evernote.edam.notestore.ttypes import SyncChunk
from evernote.edam.type.ttypes import LinkedNotebook, Note

from evernote_backup.evernote_client import EvernoteClient
from evernote_backup.evernote_client_util import NotebookAuth, NoteStoreAccess
from evernote_backup.evernote_types import (
    EvernoteEntityType,
    EvernoteMembershipType,
    EvernoteSyncInstanceType,
    EvernoteSyncOperationType,
    Reminder,
    SharedNoteMembership,
    SyncChunkV2,
    Task,
    EVERNOTE_DEL_OPERATIONS,
)

logger = logging.getLogger(__name__)


class EvernoteClientSync(EvernoteClient):  # noqa: WPS214
    def __init__(
        self,
        backend: str,
        token: str,
        network_error_retry_count: int,
        max_chunk_results: int,
        cafile: Optional[str],
        jwt_token: Optional[str] = None,
    ) -> None:
        super().__init__(
            backend=backend,
            token=token,
            network_error_retry_count=network_error_retry_count,
            cafile=cafile,
            jwt_token=jwt_token,
        )

        self._tags: Optional[dict] = None
        self._notebook_tags: dict[str, dict[str, str]] = {}
        self._linked_notebooks: Optional[dict] = None
        self.max_chunk_results = max_chunk_results

        self.access = NoteStoreAccess.OWN

    def get_note(self, note_guid: str) -> Note:
        logger.debug(f"Downloading note [{note_guid}]")

        note = self.note_store.getNote(
            note_guid,
            True,
            True,
            True,
            True,  # noqa: WPS425
        )

        # getNote returns tagGuids but not names. Map guids → names for export/filter.
        # SINGLE_NOTE_SHARE: no usable tag API on the foreign shard (permission denied).
        if note.tagGuids and self.access is not NoteStoreAccess.SINGLE_NOTE_SHARE:
            if self.access is NoteStoreAccess.LINKED_NOTEBOOK:
                nb_tags = self.list_notebook_tags(note.notebookGuid)
                note.tagNames = [nb_tags[t] for t in note.tagGuids]
            else:
                note.tagNames = [self.tags[t] for t in note.tagGuids]

        logger.debug(f"Finished downloading note [{note.guid}]")

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

    def auth_linked_notebook(
        self, l_notebook_guid: str, notebook_guid: str
    ) -> NotebookAuth:
        l_notebook = self.linked_notebooks[l_notebook_guid]
        is_notebook_public = (
            l_notebook.sharedNotebookGlobalId is None and l_notebook.uri is not None
        )

        if logger.getEffectiveLevel() == logging.DEBUG:  # pragma: no cover
            ln_info = f"{l_notebook.shareName} [{l_notebook.guid}]"
            if is_notebook_public:
                ln_info += " [PUBLIC]"  # noqa: WPS336

            logger.debug(f"Requesting access to linked notebook {ln_info}")

        ln_note_store = self.get_note_store(l_notebook.shardId)

        if is_notebook_public:
            auth_token = str(self.token)
        else:
            auth_token = ln_note_store.authenticateToSharedNotebook(
                notebook_guid
            ).authenticationToken

        return NotebookAuth(
            token=auth_token,
            shard=l_notebook.shardId,
            access=NoteStoreAccess.LINKED_NOTEBOOK,
        )

    @property
    def linked_notebooks(self) -> dict[str, LinkedNotebook]:
        if self._linked_notebooks is None:
            self._linked_notebooks = {
                ln.guid: ln for ln in self.note_store.listLinkedNotebooks()
            }
        return self._linked_notebooks

    @property
    def tags(self) -> dict[str, str]:
        if self._tags is None:
            self._tags = {t.guid: t.name for t in self.note_store.listTags()}
        return self._tags

    def list_notebook_tags(self, notebook_guid: str) -> dict[str, str]:
        if notebook_guid not in self._notebook_tags:
            self._notebook_tags[notebook_guid] = {
                t.guid: t.name
                for t in self.note_store.listTagsByNotebook(notebook_guid)
            }
        return self._notebook_tags[notebook_guid]

    def get_remote_usn(self) -> int:
        return int(self.note_store.getSyncState().updateCount)

    def iter_sync_chunks_v2(
        self,
        last_connection: int,
        entity_filter: Sequence[EvernoteEntityType],
    ) -> Iterator[SyncChunkV2]:
        for event in self.iter_sync_events(
            last_connection, entity_filter=entity_filter
        ):
            try:
                data = json.loads(event.data)
            except ValueError:
                logger.warning("Failed to decode sync chunk data")
                continue

            if event.type == "sync":
                logger.debug(f"Sync event. Updates count: {len(data)}")

                if not data:
                    continue

                yield _parse_sync_event_data(data, current_user_id=self.user_id)

            elif event.type == "connection":
                logger.debug(f"Sync started. Connection ID: {data.get('connectionId')}")
            elif event.type == "complete":
                logger.debug(
                    f"Sync completed. Documents processed: {data.get('documentCount')}"
                )
            elif event.type == "close":
                logger.debug("Sync connection closed")
                break
            else:
                logger.warning(f"Unknown sync event type: {event.type}")


# conduit-core/dist/repositories/sync/ConduitNSyncProcessor.js
def _parse_sync_event_data(
    sync_data: list[dict],
    current_user_id: int,
) -> SyncChunkV2:
    result: dict[str, Any] = {
        "tasks": {},
        "reminders": {},
        "expunged_tasks": set(),
        "expunged_reminders": set(),
        "shared_note_memberships": {},
        "expunged_shared_note_memberships": set(),
        "notes_to_sync": set(),
        "expunged_notes": set(),
    }

    for item in sync_data:
        try:
            operation = EvernoteSyncOperationType(item["operation"])
        except ValueError:
            logger.debug("Sync data inconsistency - unknown operation type")
            logger.debug(item)
            continue

        if operation == EvernoteSyncOperationType.NOTIFY:
            continue

        try:
            instance = item["instance"]
            instance_type = EvernoteSyncInstanceType(instance["type"])
        except (ValueError, KeyError, TypeError):
            logger.debug("Sync data inconsistency - unknown instance type")
            logger.debug(item)
            continue

        if instance_type == EvernoteSyncInstanceType.MEMBERSHIP:
            _parse_membership_instance(
                instance,
                operation,
                result,
                current_user_id,
            )
            continue

        if instance_type != EvernoteSyncInstanceType.ENTITY:
            continue

        try:
            guid = instance["ref"]["id"]
            entity_type = EvernoteEntityType(instance["ref"]["type"])
        except (ValueError, KeyError, TypeError):
            logger.debug("Sync data inconsistency - unknown entity type")
            logger.debug(item)
            continue

        if entity_type == EvernoteEntityType.NOTE:
            _parse_note_entity_instance(
                guid,
                instance,
                operation,
                result,
                current_user_id,
            )
            continue

        try:
            parent_id = instance["parentEntity"]["id"]
            parent_type = EvernoteEntityType(instance["parentEntity"]["type"])
        except (ValueError, KeyError, TypeError):
            logger.debug("Sync data inconsistency - entity without parent")
            logger.debug(item)
            continue

        if operation in EVERNOTE_DEL_OPERATIONS:
            if entity_type == EvernoteEntityType.TASK:
                result["tasks"].pop(guid, None)
                result["expunged_tasks"].add(guid)
            if entity_type == EvernoteEntityType.REMINDER:
                result["reminders"].pop(guid, None)
                result["expunged_reminders"].add(guid)
            continue

        if entity_type == EvernoteEntityType.TASK:
            if parent_type != EvernoteEntityType.NOTE:
                logger.debug("Sync data inconsistency - task outside of note")
                logger.debug(item)
                continue

            task = Task(
                taskId=guid,
                parentId=parent_id,
                parentType=parent_type,
                noteLevelID=instance.get("noteLevelID"),
                taskGroupNoteLevelID=instance.get("taskGroupNoteLevelID"),
                label=instance.get("label"),
                description=instance.get("description"),
                dueDate=instance.get("dueDate"),
                dueDateUIOption=instance.get("dueDateUIOption"),
                timeZone=instance.get("timeZone"),
                status=instance.get("status"),
                statusUpdated=instance.get("statusUpdated"),
                inNote=instance.get("inNote"),
                flag=instance.get("flag"),
                taskFlag=instance.get("taskFlag"),
                priority=instance.get("priority"),
                idClock=instance.get("idClock"),
                sortWeight=instance.get("sortWeight"),
                creator=instance.get("creator"),
                lastEditor=instance.get("lastEditor"),
                ownerId=instance.get("ownerId"),
                created=instance.get("created"),
                updated=instance.get("updated"),
                assigneeUserId=instance.get("assigneeUserID"),
                assigneeEmail=instance.get("assigneeEmail"),
                assignedByUserId=instance.get("assignedByUserID"),
                recurrence=instance.get("recurrence"),
                repeatAfterCompletion=instance.get("repeatAfterCompletion"),
            )

            result["tasks"][guid] = task

        elif entity_type == EvernoteEntityType.REMINDER:
            if parent_type != EvernoteEntityType.TASK:
                logger.debug("Sync data inconsistency - reminder outside of task")
                logger.debug(item)
                continue

            reminder = Reminder(
                reminderId=guid,
                sourceId=parent_id,
                sourceType=parent_type,
                noteLevelID=instance.get("noteLevelID"),
                reminderDate=instance.get("reminderDate"),
                reminderDateUIOption=instance.get("reminderDateUIOption"),
                timeZone=instance.get("timeZone"),
                dueDateOffset=instance.get("dueDateOffset"),
                status=instance.get("status"),
                ownerId=instance.get("ownerId"),
                created=instance.get("created"),
                updated=instance.get("updated"),
            )

            result["reminders"][guid] = reminder

    last_timestamp = max([sd.get("updated", 0) for sd in sync_data])

    return SyncChunkV2(
        last_timestamp=last_timestamp,
        tasks=list(result["tasks"].values()),
        reminders=list(result["reminders"].values()),
        expunged_tasks=list(result["expunged_tasks"]),
        expunged_reminders=list(result["expunged_reminders"]),
        shared_note_memberships=list(result["shared_note_memberships"].values()),
        expunged_shared_note_memberships=list(
            result["expunged_shared_note_memberships"]
        ),
        notes_to_sync=list(result["notes_to_sync"]),
        expunged_notes=list(result["expunged_notes"]),
    )


def _parse_membership_instance(
    instance: dict,
    operation: EvernoteSyncOperationType,
    result: dict[str, Any],
    current_user_id: int,
) -> None:
    """Handle MEMBERSHIP instances for single-note EXPLICIT shares only."""
    try:
        dst_type = EvernoteEntityType(instance["ref"]["dst"]["type"])
        note_guid: str = instance["ref"]["dst"]["id"]
        ref_type: int = instance["ref"]["type"]
        owner_id: int = instance["ownerId"]
        sharer_id: int = instance["sharerId"]
        shard_id: str = instance["shardId"]
        share_type: str = instance.get("shareType", "")
    except (ValueError, KeyError, TypeError):
        logger.debug("Sync data inconsistency - malformed membership instance")
        logger.debug(instance)
        return

    # Notebook shares stay on Linked Notebooks (EDAM).
    if dst_type != EvernoteEntityType.NOTE:
        return

    # Invitation (0) is only a precursor; EXPLICIT share is ref.type == SHARE (1).
    if ref_type != EvernoteMembershipType.SHARE:
        return

    if share_type != "EXPLICIT":
        return

    # Ignore shares the local user created (outgoing shares of own notes).
    if owner_id == current_user_id or sharer_id == current_user_id:
        return

    is_delete = operation in EVERNOTE_DEL_OPERATIONS

    if is_delete:
        result["shared_note_memberships"].pop(note_guid, None)
        result["expunged_shared_note_memberships"].add(note_guid)
        result["notes_to_sync"].discard(note_guid)
        return

    result["expunged_shared_note_memberships"].discard(note_guid)
    result["shared_note_memberships"][note_guid] = SharedNoteMembership(
        note_guid=note_guid,
        shard_id=shard_id,
        owner_id=owner_id,
    )
    result["notes_to_sync"].add(note_guid)


def _parse_note_entity_instance(
    guid: str,
    instance: dict,
    operation: EvernoteSyncOperationType,
    result: dict[str, Any],
    current_user_id: int,
) -> None:
    """Handle NOTE entity updates for notes shared with the user.

    Own notes are synced via USN/EDAM and ignored here. Foreign note entity
    events are recorded so the synchronizer can redownload/expunge only notes
    already tracked as single-note shares (membership alone schedules the
    initial download; entity events only matter for later updates).
    """
    try:
        owner_id: int = instance["ownerId"]
    except (ValueError, KeyError, TypeError):
        logger.debug("Sync data inconsistency - malformed note instance")
        logger.debug(instance)
        return

    if owner_id == current_user_id:
        return

    is_delete = operation in EVERNOTE_DEL_OPERATIONS

    if is_delete:
        result["notes_to_sync"].discard(guid)
        result["expunged_notes"].add(guid)
        return

    # Candidate for redownload; synchronizer filters to known shared notes.
    result["notes_to_sync"].add(guid)
