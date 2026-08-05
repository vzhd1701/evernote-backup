"""Unit tests for v2 parser membership / NOTE entity handling."""

from evernote_backup.evernote_client_sync import _parse_sync_event_data
from evernote_backup.evernote_types import (
    EvernoteEntityType,
    EvernoteMembershipType,
    EvernoteSyncInstanceType,
    EvernoteSyncOperationType,
)

LOCAL_USER_ID = 111222333
OTHER_USER_ID = 312066334
NOTE_GUID = "note-shared-1"
SHARD = "s532"


def _membership(
    *,
    note_guid=NOTE_GUID,
    operation=EvernoteSyncOperationType.CREATE,
    owner_id=OTHER_USER_ID,
    sharer_id=OTHER_USER_ID,
    shard_id=SHARD,
    share_type="EXPLICIT",
    ref_type=EvernoteMembershipType.SHARE,
    dst_type=EvernoteEntityType.NOTE,
    updated=1000,
):
    return {
        "instance": {
            "ownerId": owner_id,
            "sharerId": sharer_id,
            "shardId": shard_id,
            "shareType": share_type,
            "ref": {
                "dst": {"id": note_guid, "type": dst_type},
                "src": {"id": str(LOCAL_USER_ID), "type": 2},
                "type": ref_type,
            },
            "type": EvernoteSyncInstanceType.MEMBERSHIP,
            "updated": updated,
        },
        "operation": operation,
        "updated": updated,
    }


def _note_entity(
    *,
    note_guid=NOTE_GUID,
    operation=EvernoteSyncOperationType.UPDATE,
    owner_id=OTHER_USER_ID,
    updated=2000,
):
    return {
        "instance": {
            "ownerId": owner_id,
            "label": "title",
            "ref": {"id": note_guid, "type": EvernoteEntityType.NOTE},
            "type": EvernoteSyncInstanceType.ENTITY,
            "updated": updated,
        },
        "operation": operation,
        "updated": updated,
    }


def test_parse_membership_create():
    chunk = _parse_sync_event_data([_membership()], current_user_id=LOCAL_USER_ID)

    assert len(chunk.shared_note_memberships) == 1
    m = chunk.shared_note_memberships[0]
    assert m.note_guid == NOTE_GUID
    assert m.shard_id == SHARD
    assert m.owner_id == OTHER_USER_ID
    assert NOTE_GUID in chunk.notes_to_sync
    assert chunk.expunged_shared_note_memberships == []
    assert chunk.last_timestamp == 1000


def test_parse_membership_delete():
    chunk = _parse_sync_event_data(
        [_membership(operation=EvernoteSyncOperationType.DELETE, updated=3000)],
        current_user_id=LOCAL_USER_ID,
    )

    assert chunk.shared_note_memberships == []
    assert chunk.expunged_shared_note_memberships == [NOTE_GUID]
    assert NOTE_GUID not in chunk.notes_to_sync


def test_parse_membership_expunge():
    chunk = _parse_sync_event_data(
        [_membership(operation=EvernoteSyncOperationType.EXPUNGE)],
        current_user_id=LOCAL_USER_ID,
    )

    assert chunk.expunged_shared_note_memberships == [NOTE_GUID]


def test_parse_membership_create_then_delete_same_chunk():
    chunk = _parse_sync_event_data(
        [
            _membership(operation=EvernoteSyncOperationType.CREATE, updated=1000),
            _membership(operation=EvernoteSyncOperationType.DELETE, updated=2000),
        ],
        current_user_id=LOCAL_USER_ID,
    )

    assert chunk.shared_note_memberships == []
    assert chunk.expunged_shared_note_memberships == [NOTE_GUID]
    assert NOTE_GUID not in chunk.notes_to_sync


def test_parse_membership_delete_then_create_same_chunk():
    chunk = _parse_sync_event_data(
        [
            _membership(operation=EvernoteSyncOperationType.DELETE, updated=1000),
            _membership(operation=EvernoteSyncOperationType.CREATE, updated=2000),
        ],
        current_user_id=LOCAL_USER_ID,
    )

    assert len(chunk.shared_note_memberships) == 1
    assert chunk.expunged_shared_note_memberships == []
    assert NOTE_GUID in chunk.notes_to_sync


def test_parse_ignore_invitation():
    chunk = _parse_sync_event_data(
        [_membership(ref_type=EvernoteMembershipType.INVITATION)],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.shared_note_memberships == []


def test_parse_ignore_non_explicit_share_type():
    chunk = _parse_sync_event_data(
        [_membership(share_type="LINK")],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.shared_note_memberships == []


def test_parse_ignore_notebook_membership():
    chunk = _parse_sync_event_data(
        [_membership(dst_type=EvernoteEntityType.NOTEBOOK)],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.shared_note_memberships == []


def test_parse_ignore_outgoing_by_owner():
    chunk = _parse_sync_event_data(
        [_membership(owner_id=LOCAL_USER_ID, sharer_id=OTHER_USER_ID)],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.shared_note_memberships == []


def test_parse_ignore_outgoing_by_sharer():
    chunk = _parse_sync_event_data(
        [_membership(owner_id=OTHER_USER_ID, sharer_id=LOCAL_USER_ID)],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.shared_note_memberships == []


def test_parse_malformed_membership_skipped():
    chunk = _parse_sync_event_data(
        [
            {
                "instance": {
                    "type": EvernoteSyncInstanceType.MEMBERSHIP,
                    # missing required fields
                },
                "operation": EvernoteSyncOperationType.CREATE,
                "updated": 1,
            }
        ],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.shared_note_memberships == []
    assert chunk.last_timestamp == 1


def test_parse_note_entity_update_foreign():
    chunk = _parse_sync_event_data(
        [_note_entity()],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.notes_to_sync == [NOTE_GUID]
    assert chunk.expunged_notes == []


def test_parse_note_entity_delete_foreign():
    chunk = _parse_sync_event_data(
        [_note_entity(operation=EvernoteSyncOperationType.DELETE)],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.notes_to_sync == []
    assert chunk.expunged_notes == [NOTE_GUID]


def test_parse_note_entity_ignore_own():
    chunk = _parse_sync_event_data(
        [_note_entity(owner_id=LOCAL_USER_ID)],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.notes_to_sync == []
    assert chunk.expunged_notes == []


def test_parse_note_entity_malformed_skipped():
    chunk = _parse_sync_event_data(
        [
            {
                "instance": {
                    "ref": {"id": NOTE_GUID, "type": EvernoteEntityType.NOTE},
                    "type": EvernoteSyncInstanceType.ENTITY,
                    # missing ownerId
                },
                "operation": EvernoteSyncOperationType.UPDATE,
                "updated": 5,
            }
        ],
        current_user_id=LOCAL_USER_ID,
    )
    assert chunk.notes_to_sync == []


def test_parse_membership_and_note_entity_independent():
    """Membership alone is enough; entity does not enrich membership fields."""
    chunk = _parse_sync_event_data(
        [_membership(), _note_entity()],
        current_user_id=LOCAL_USER_ID,
    )

    assert len(chunk.shared_note_memberships) == 1
    m = chunk.shared_note_memberships[0]
    assert m.note_guid == NOTE_GUID
    assert m.shard_id == SHARD
    assert m.owner_id == OTHER_USER_ID
    assert set(m.__dataclass_fields__) == {"note_guid", "shard_id", "owner_id"}
    assert NOTE_GUID in chunk.notes_to_sync
