"""Unit tests for EvernoteClientSync."""

import logging

import pytest
from evernote.edam.type.ttypes import LinkedNotebook, Note, Tag
from requests_sse import MessageEvent

from evernote_backup.evernote_client_sync import (
    EvernoteClientSync,
    _parse_sync_event_data,
)
from evernote_backup.evernote_client_util import NoteStoreAccess
from evernote_backup.evernote_types import (
    EvernoteEntityType,
    EvernoteSyncInstanceType,
    EvernoteSyncOperationType,
)

FAKE_TOKEN = "S=s100:U=ff:E=fff:C=ff:P=1:A=test:V=2:H=ff"


@pytest.fixture
def sync_client(mock_evernote_client):
    mock_evernote_client.fake_user = "testuser"
    return EvernoteClientSync(
        backend="evernote",
        token=FAKE_TOKEN,
        network_error_retry_count=3,
        max_chunk_results=50,
        cafile=None,
        jwt_token="jwt-test",
    )


def test_get_remote_usn(sync_client, mock_evernote_client):
    mock_evernote_client.fake_usn = 123
    assert sync_client.get_remote_usn() == 123


def test_tags_property_cached(sync_client, mock_evernote_client):
    mock_evernote_client.fake_tags = [
        Tag(guid="t1", name="alpha"),
        Tag(guid="t2", name="beta"),
    ]

    assert sync_client.tags == {"t1": "alpha", "t2": "beta"}
    mock_evernote_client.fake_tags = []  # should not re-fetch
    assert sync_client.tags["t1"] == "alpha"


def test_list_notebook_tags_cached(sync_client, mock_evernote_client):
    mock_evernote_client.fake_l_tags = [
        Tag(guid="lt1", name="shared-tag"),
    ]

    tags1 = sync_client.list_notebook_tags("nb1")
    assert tags1 == {"lt1": "shared-tag"}

    mock_evernote_client.fake_l_tags = []
    tags2 = sync_client.list_notebook_tags("nb1")
    assert tags2 == {"lt1": "shared-tag"}  # cached per notebook


def test_linked_notebooks_property(sync_client, mock_evernote_client):
    mock_evernote_client.fake_linked_notebooks = [
        LinkedNotebook(guid="ln1", shardId="s200"),
        LinkedNotebook(guid="ln2", shardId="s201"),
    ]

    result = sync_client.linked_notebooks
    assert set(result) == {"ln1", "ln2"}
    assert result["ln1"].shardId == "s200"


def test_get_note_resolves_personal_tags(sync_client, mock_evernote_client):
    mock_evernote_client.fake_tags = [Tag(guid="tg1", name="Work")]
    mock_evernote_client.fake_notes = [
        Note(
            guid="n1",
            title="t",
            content="c",
            tagGuids=["tg1"],
            notebookGuid="nb",
            active=True,
        )
    ]

    note = sync_client.get_note("n1")
    assert note.tagNames == ["Work"]


def test_get_note_linked_mode_resolves_notebook_tags(sync_client, mock_evernote_client):
    mock_evernote_client.fake_l_tags = [
        Tag(guid="tg1", name="SharedTag"),
        Tag(guid="tg2", name="Other"),
    ]
    mock_evernote_client.fake_notes = [
        Note(
            guid="n1",
            title="t",
            content="c",
            tagGuids=["tg1", "tg2"],
            notebookGuid="nb-remote",
            active=True,
        )
    ]
    sync_client.access = NoteStoreAccess.LINKED_NOTEBOOK

    note = sync_client.get_note("n1")
    assert note.tagNames == ["SharedTag", "Other"]


def test_get_note_without_tags_leaves_tag_names_unset(
    sync_client, mock_evernote_client
):
    mock_evernote_client.fake_notes = [
        Note(
            guid="n1",
            title="t",
            content="c",
            tagGuids=None,
            notebookGuid="nb",
            active=True,
        )
    ]

    note = sync_client.get_note("n1")
    assert note.tagNames is None


def test_get_note_single_share_skips_tag_resolution(
    sync_client, mock_evernote_client, mocker
):
    """Single-note share access must not call listTags (permission denied)."""
    mock_evernote_client.fake_l_notes = [
        Note(
            guid="n1",
            title="t",
            content="c",
            tagGuids=["foreign-tag"],
            notebookGuid="remote-nb",
            active=True,
        )
    ]
    sync_client.shard = "s532"
    sync_client.access = NoteStoreAccess.SINGLE_NOTE_SHARE

    list_tags = mocker.patch.object(
        type(sync_client.note_store),
        "listTags",
        side_effect=AssertionError("listTags must not be called for single shares"),
    )
    list_nb_tags = mocker.patch.object(
        sync_client,
        "list_notebook_tags",
        side_effect=AssertionError("listTagsByNotebook must not be called"),
    )

    note = sync_client.get_note("n1")

    assert note.tagNames is None
    list_tags.assert_not_called()
    list_nb_tags.assert_not_called()


def test_iter_sync_chunks_single_page(sync_client, mock_evernote_client):
    mock_evernote_client.fake_usn = 10
    mock_evernote_client.fake_notes = [
        Note(guid="n1", title="t", content="c", active=True)
    ]

    chunks = list(sync_client.iter_sync_chunks(0))
    assert len(chunks) == 1
    assert chunks[0].chunkHighUSN == 10
    assert chunks[0].notes[0].guid == "n1"


def test_iter_linked_notebook_sync_chunks_ok(sync_client, mock_evernote_client):
    mock_evernote_client.fake_l_usn = 5
    mock_evernote_client.fake_l_notes = [
        Note(guid="ln1", title="t", content="c", active=True)
    ]
    l_nb = LinkedNotebook(guid="lnb", shardId="s100", shareName="Shared")

    chunks = list(sync_client.iter_linked_notebook_sync_chunks(l_nb, 0))
    assert len(chunks) == 1
    assert chunks[0].notes[0].guid == "ln1"


def test_iter_linked_notebook_sync_chunks_not_accessible(
    sync_client, mock_evernote_client, caplog
):
    mock_evernote_client.fake_auth_linked_notebook_error = True
    l_nb = LinkedNotebook(guid="lnb", shardId="s100", shareName="Gone")

    with caplog.at_level(logging.WARNING):
        chunks = list(sync_client.iter_linked_notebook_sync_chunks(l_nb, 0))

    assert chunks == []
    assert "not accessible" in caplog.text


def test_iter_linked_notebook_already_up_to_date(sync_client, mock_evernote_client):
    mock_evernote_client.fake_l_usn = 50
    l_nb = LinkedNotebook(guid="lnb", shardId="s100", shareName="Shared")

    chunks = list(sync_client.iter_linked_notebook_sync_chunks(l_nb, 50))
    assert chunks == []


def test_auth_linked_notebook_private(sync_client, mock_evernote_client):
    mock_evernote_client.fake_linked_notebooks = [
        LinkedNotebook(
            guid="lnb1",
            shardId="s200",
            sharedNotebookGlobalId="gid",
            shareName="Private",
        )
    ]
    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=s200:U=1:E=1:C=1:P=1:A=a:V=2:H=h"
    )

    # reset cache
    sync_client._linked_notebooks = None
    auth = sync_client.auth_linked_notebook("lnb1", "nb-guid")

    assert auth.token == mock_evernote_client.fake_linked_notebook_auth_token
    assert auth.shard == "s200"
    assert auth.access is NoteStoreAccess.LINKED_NOTEBOOK


def test_auth_linked_notebook_public(sync_client, mock_evernote_client):
    mock_evernote_client.fake_linked_notebooks = [
        LinkedNotebook(
            guid="lnb-pub",
            shardId="s200",
            uri="public-uri",
            sharedNotebookGlobalId=None,
            shareName="Public",
        )
    ]
    sync_client._linked_notebooks = None

    auth = sync_client.auth_linked_notebook("lnb-pub", "nb-guid")

    assert auth.token == FAKE_TOKEN
    assert auth.shard == "s200"
    assert auth.access is NoteStoreAccess.LINKED_NOTEBOOK


def test_iter_sync_chunks_v2_yields_parsed_chunks(sync_client, mock_evernote_client):
    mock_evernote_client.fake_updates = [
        {
            "instance": {
                "ref": {"id": "task1", "type": EvernoteEntityType.TASK},
                "type": 1,
                "parentEntity": {"id": "note1", "type": EvernoteEntityType.NOTE},
                "label": "Do it",
                "created": 1,
                "updated": 2,
                "ownerId": 1,
            },
            "operation": 2,
            "updated": 99,
        }
    ]

    chunks = list(
        sync_client.iter_sync_chunks_v2(
            last_connection=0,
            entity_filter=[EvernoteEntityType.TASK],
        )
    )

    assert len(chunks) == 1
    assert chunks[0].last_timestamp == 99
    assert len(chunks[0].tasks) == 1
    assert chunks[0].tasks[0].taskId == "task1"
    assert chunks[0].tasks[0].label == "Do it"


def test_iter_sync_chunks_v2_skips_bad_json_and_unknown_events(
    sync_client, mock_evernote_client, mocker, caplog
):
    """Exercise event-loop branches: empty data, bad JSON, empty sync, unknown, close."""
    events = [
        MessageEvent(
            last_event_id="1",
            origin="o",
            type="connection",
            data='{"connectionId":"c1"}',
        ),
        MessageEvent(last_event_id="1", origin="o", type="sync", data=""),
        MessageEvent(last_event_id="1", origin="o", type="sync", data=None),
        MessageEvent(last_event_id="1", origin="o", type="sync", data="not-json"),
        MessageEvent(last_event_id="1", origin="o", type="sync", data="[]"),
        MessageEvent(last_event_id="1", origin="o", type="weird", data="{}"),
        MessageEvent(
            last_event_id="1",
            origin="o",
            type="complete",
            data='{"documentCount":0}',
        ),
        MessageEvent(last_event_id="1", origin="o", type="close", data="{}"),
    ]

    class FakeES:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return events

        def __exit__(self, *a):
            return False

    mocker.patch("evernote_backup.evernote_client.EventSource", FakeES)

    with caplog.at_level(logging.WARNING):
        chunks = list(
            sync_client.iter_sync_chunks_v2(0, entity_filter=[EvernoteEntityType.NOTE])
        )

    assert chunks == []
    assert "Empty sync chunk data" in caplog.text
    assert "Failed to decode sync chunk data" in caplog.text
    assert "Unknown sync event type" in caplog.text


def _entity_item(
    *,
    guid: str,
    entity_type: EvernoteEntityType,
    parent_id: str,
    parent_type: EvernoteEntityType,
    operation: EvernoteSyncOperationType = EvernoteSyncOperationType.UPDATE,
    updated: int = 10,
    **extra,
):
    instance = {
        "ref": {"id": guid, "type": entity_type},
        "type": EvernoteSyncInstanceType.ENTITY,
        "parentEntity": {"id": parent_id, "type": parent_type},
        "updated": updated,
        **extra,
    }
    return {"instance": instance, "operation": operation, "updated": updated}


def test_parse_task_and_reminder_create():
    data = [
        _entity_item(
            guid="task1",
            entity_type=EvernoteEntityType.TASK,
            parent_id="note1",
            parent_type=EvernoteEntityType.NOTE,
            label="Buy milk",
            updated=50,
        ),
        _entity_item(
            guid="rem1",
            entity_type=EvernoteEntityType.REMINDER,
            parent_id="task1",
            parent_type=EvernoteEntityType.TASK,
            reminderDate=123,
            updated=60,
        ),
    ]

    chunk = _parse_sync_event_data(data, current_user_id=1)

    assert chunk.last_timestamp == 60
    assert len(chunk.tasks) == 1
    assert chunk.tasks[0].taskId == "task1"
    assert chunk.tasks[0].label == "Buy milk"
    assert len(chunk.reminders) == 1
    assert chunk.reminders[0].reminderId == "rem1"
    assert chunk.reminders[0].sourceId == "task1"


def test_parse_task_and_reminder_expunge():
    data = [
        _entity_item(
            guid="task1",
            entity_type=EvernoteEntityType.TASK,
            parent_id="note1",
            parent_type=EvernoteEntityType.NOTE,
            label="Keep me",
            operation=EvernoteSyncOperationType.CREATE,
            updated=10,
        ),
        _entity_item(
            guid="rem1",
            entity_type=EvernoteEntityType.REMINDER,
            parent_id="task1",
            parent_type=EvernoteEntityType.TASK,
            operation=EvernoteSyncOperationType.CREATE,
            updated=20,
        ),
        _entity_item(
            guid="task1",
            entity_type=EvernoteEntityType.TASK,
            parent_id="note1",
            parent_type=EvernoteEntityType.NOTE,
            operation=EvernoteSyncOperationType.EXPUNGE,
            updated=30,
        ),
        _entity_item(
            guid="rem1",
            entity_type=EvernoteEntityType.REMINDER,
            parent_id="task1",
            parent_type=EvernoteEntityType.TASK,
            operation=EvernoteSyncOperationType.DELETE,
            updated=40,
        ),
    ]

    chunk = _parse_sync_event_data(data, current_user_id=1)

    assert chunk.tasks == []
    assert chunk.reminders == []
    assert chunk.expunged_tasks == ["task1"]
    assert chunk.expunged_reminders == ["rem1"]


def test_parse_skips_unknown_operation_and_notify():
    data = [
        {"operation": 999, "updated": 1, "instance": {}},
        _entity_item(
            guid="task1",
            entity_type=EvernoteEntityType.TASK,
            parent_id="note1",
            parent_type=EvernoteEntityType.NOTE,
            operation=EvernoteSyncOperationType.NOTIFY,
            updated=2,
        ),
    ]

    chunk = _parse_sync_event_data(data, current_user_id=1)

    assert chunk.tasks == []
    assert chunk.last_timestamp == 2


def test_parse_task_outside_note_and_reminder_outside_task_skipped():
    data = [
        _entity_item(
            guid="task1",
            entity_type=EvernoteEntityType.TASK,
            parent_id="nb1",
            parent_type=EvernoteEntityType.NOTEBOOK,
            updated=1,
        ),
        _entity_item(
            guid="rem1",
            entity_type=EvernoteEntityType.REMINDER,
            parent_id="note1",
            parent_type=EvernoteEntityType.NOTE,
            updated=2,
        ),
    ]

    chunk = _parse_sync_event_data(data, current_user_id=1)

    assert chunk.tasks == []
    assert chunk.reminders == []


def test_auth_linked_notebook_falls_back_to_user_shard(
    sync_client, mock_evernote_client
):
    """When LinkedNotebook.shardId is missing, use the client user shard."""
    mock_evernote_client.fake_linked_notebooks = [
        LinkedNotebook(
            guid="lnb-noshard",
            shardId=None,
            sharedNotebookGlobalId="gid",
            shareName="Private",
        )
    ]
    mock_evernote_client.fake_linked_notebook_auth_token = "shared-token"
    sync_client._linked_notebooks = None
    sync_client.shard = "s100"

    auth = sync_client.auth_linked_notebook("lnb-noshard", "nb-guid")

    assert auth.token == "shared-token"
    assert auth.shard == "s100"
    assert auth.access is NoteStoreAccess.LINKED_NOTEBOOK
