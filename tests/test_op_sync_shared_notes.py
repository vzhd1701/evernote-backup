"""Tests for single-note shares via the v2 sync API."""

import pytest
from evernote.edam.type.ttypes import LinkedNotebook, Note, Notebook

from evernote_backup.config import (
    SHARED_WITH_ME_NOTEBOOK_GUID,
    SHARED_WITH_ME_NOTEBOOK_NAME,
)
from evernote_backup.evernote_types import (
    EvernoteEntityType,
    EvernoteMembershipType,
    EvernoteSyncInstanceType,
    EvernoteSyncOperationType,
)

# JWT mock user id is 111222333
LOCAL_USER_ID = 111222333
OTHER_USER_ID = 312066334
SHARED_NOTE_GUID = "c08bb5c3-f403-49fd-4a08-8259af50f18c"
SHARED_SHARD = "s532"


def _membership_event(
    note_guid=SHARED_NOTE_GUID,
    operation=EvernoteSyncOperationType.CREATE,
    owner_id=OTHER_USER_ID,
    sharer_id=OTHER_USER_ID,
    src_id=str(LOCAL_USER_ID),
    shard_id=SHARED_SHARD,
    share_type="EXPLICIT",
    ref_type=EvernoteMembershipType.SHARE,
    dst_type=EvernoteEntityType.NOTE,
    deleted=0,
    updated=1785679990321,
):
    return {
        "instance": {
            "created": 1785679990000,
            "deleted": deleted,
            "ownerId": owner_id,
            "ref": {
                "dst": {"id": note_guid, "type": dst_type},
                "src": {"id": src_id, "type": 2},
                "type": ref_type,
            },
            "role": "ADMIN",
            "roleV2": 5,
            "shardId": shard_id,
            "shareType": share_type,
            "sharerId": sharer_id,
            "type": EvernoteSyncInstanceType.MEMBERSHIP,
            "updated": updated,
            "version": updated,
        },
        "operation": operation,
        "updated": updated,
    }


def _note_entity_event(
    note_guid=SHARED_NOTE_GUID,
    operation=EvernoteSyncOperationType.UPDATE,
    owner_id=OTHER_USER_ID,
    label="shared title",
    shard_id=SHARED_SHARD,
    deleted=0,
    updated=1785679990567,
    parent_notebook="ed841f99-efc7-4ced-ab6d-64142bbd25ec",
):
    return {
        "instance": {
            "activeResourceCount": 0,
            "created": 1785679884000,
            "creator": owner_id,
            "deleted": deleted,
            "isUntitled": False,
            "label": label,
            "ownerId": owner_id,
            "parentEntity": {
                "id": parent_notebook,
                "type": EvernoteEntityType.NOTEBOOK,
            },
            "ref": {"id": note_guid, "type": EvernoteEntityType.NOTE},
            "shardId": shard_id,
            "snippet": "",
            "type": EvernoteSyncInstanceType.ENTITY,
            "updated": updated,
            "version": 23,
        },
        "operation": operation,
        "updated": updated,
    }


def _queue_shared_note_body(mock_evernote_client, note: Note) -> None:
    """Serve note body on foreign-shard getNote without EDAM USN listing it."""
    mock_evernote_client.fake_l_notes.append(note)


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_create(cli_invoker, mock_evernote_client, fake_storage):
    shared_note = Note(
        guid=SHARED_NOTE_GUID,
        title="shared title",
        content="shared body",
        notebookGuid="remote-nb",
        contentLength=100,
        active=True,
    )
    _queue_shared_note_body(mock_evernote_client, shared_note)
    mock_evernote_client.fake_updates = [
        _membership_event(),
        _note_entity_event(),
    ]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    assert fake_storage.shared_notes.get_shard_id(SHARED_NOTE_GUID) == SHARED_SHARD

    notes = list(fake_storage.notes.iter_notes(SHARED_WITH_ME_NOTEBOOK_GUID))
    assert len(notes) == 1
    assert notes[0].guid == SHARED_NOTE_GUID
    assert notes[0].content == "shared body"
    assert notes[0].notebookGuid == SHARED_WITH_ME_NOTEBOOK_GUID

    nb_names = {nb.name for nb in fake_storage.notebooks.iter_notebooks()}
    assert SHARED_WITH_ME_NOTEBOOK_NAME in nb_names


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_ignore_invitation(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_updates = [
        _membership_event(ref_type=EvernoteMembershipType.INVITATION, share_type=None),
    ]
    # shareType may be absent on invitations
    mock_evernote_client.fake_updates[0]["instance"].pop("shareType", None)

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    assert list(fake_storage.notes.iter_notes(SHARED_WITH_ME_NOTEBOOK_GUID)) == []


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_ignore_outgoing(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_updates = [
        _membership_event(
            owner_id=LOCAL_USER_ID,
            sharer_id=LOCAL_USER_ID,
            src_id="138688515",
        ),
    ]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_ignore_notebook_membership(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_updates = [
        _membership_event(dst_type=EvernoteEntityType.NOTEBOOK),
    ]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_update_redownload(
    cli_invoker, mock_evernote_client, fake_storage
):
    shared_note = Note(
        guid=SHARED_NOTE_GUID,
        title="shared title",
        content="v1",
        notebookGuid="remote-nb",
        contentLength=100,
        active=True,
    )
    _queue_shared_note_body(mock_evernote_client, shared_note)
    mock_evernote_client.fake_updates = [
        _membership_event(),
        _note_entity_event(label="shared title"),
    ]

    result1 = cli_invoker("sync", "--database", "fake_db")
    assert result1.exit_code == 0
    notes_v1 = list(fake_storage.notes.iter_notes(SHARED_WITH_ME_NOTEBOOK_GUID))
    assert notes_v1[0].content == "v1"

    # Second sync: note content changed, entity UPDATE only
    shared_note.content = "v2"
    mock_evernote_client.fake_usn = 100  # already synced notebooks
    mock_evernote_client.fake_notebooks = []
    mock_evernote_client.fake_l_notes = [shared_note]
    mock_evernote_client.fake_updates = [
        _note_entity_event(label="shared title", updated=1785680000000),
    ]

    result2 = cli_invoker("sync", "--database", "fake_db")
    assert result2.exit_code == 0
    notes_v2 = list(fake_storage.notes.iter_notes(SHARED_WITH_ME_NOTEBOOK_GUID))
    assert len(notes_v2) == 1
    assert notes_v2[0].content == "v2"


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_unshare_expunge(
    cli_invoker, mock_evernote_client, fake_storage
):
    shared_note = Note(
        guid=SHARED_NOTE_GUID,
        title="shared title",
        content="body",
        notebookGuid="remote-nb",
        contentLength=100,
        active=True,
    )
    _queue_shared_note_body(mock_evernote_client, shared_note)
    mock_evernote_client.fake_updates = [
        _membership_event(),
        _note_entity_event(),
    ]

    result1 = cli_invoker("sync", "--database", "fake_db")
    assert result1.exit_code == 0
    assert fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)

    mock_evernote_client.fake_usn = 100
    mock_evernote_client.fake_notebooks = []
    mock_evernote_client.fake_l_notes = []
    mock_evernote_client.fake_updates = [
        _membership_event(
            operation=EvernoteSyncOperationType.DELETE,
            deleted=1785677802579,
            updated=1785677802663,
        ),
    ]

    result2 = cli_invoker("sync", "--database", "fake_db")
    assert result2.exit_code == 0
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    assert list(fake_storage.notes.iter_notes(SHARED_WITH_ME_NOTEBOOK_GUID)) == []


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_survives_linked_notebook_expunge(
    cli_invoker, mock_evernote_client, fake_storage
):
    """Note that is both in a linked notebook and single-shared keeps local copy."""
    remote_nb_guid = "nbid-linked"
    l_nb_guid = "lnb1"

    mock_evernote_client.fake_l_notebooks.append(
        Notebook(guid=remote_nb_guid, name="Shared NB"),
    )
    linked_note = Note(
        guid=SHARED_NOTE_GUID,
        title="both paths",
        content="body",
        notebookGuid=remote_nb_guid,
        contentLength=100,
        active=True,
    )
    mock_evernote_client.fake_l_notes.append(linked_note)
    mock_evernote_client.fake_linked_notebooks.append(
        LinkedNotebook(guid=l_nb_guid, shardId="s100")
    )
    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=s200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )
    mock_evernote_client.fake_updates = [
        _membership_event(shard_id="s100"),
        _note_entity_event(label="both paths", shard_id="s100"),
    ]

    result1 = cli_invoker("sync", "--database", "fake_db")
    assert result1.exit_code == 0
    assert fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    assert fake_storage.notes.note_exists(SHARED_NOTE_GUID)

    # Expunge linked notebook; single-note share remains
    mock_evernote_client.fake_usn = 101
    mock_evernote_client.fake_notebooks = []
    mock_evernote_client.fake_l_notes = []
    mock_evernote_client.fake_linked_notebooks = []
    mock_evernote_client.fake_expunged_linked_notebooks = [l_nb_guid]
    mock_evernote_client.fake_updates = []

    result2 = cli_invoker("sync", "--database", "fake_db")
    assert result2.exit_code == 0
    assert fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    assert fake_storage.notes.note_exists(SHARED_NOTE_GUID)
    # Re-homed under Shared with me
    assert (
        fake_storage.notes.get_note_notebook_guid(SHARED_NOTE_GUID)
        == SHARED_WITH_ME_NOTEBOOK_GUID
    )


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_unshare_keeps_linked_copy(
    cli_invoker, mock_evernote_client, fake_storage
):
    remote_nb_guid = "nbid-linked"
    l_nb_guid = "lnb1"

    mock_evernote_client.fake_l_notebooks.append(
        Notebook(guid=remote_nb_guid, name="Shared NB"),
    )
    linked_note = Note(
        guid=SHARED_NOTE_GUID,
        title="both paths",
        content="body",
        notebookGuid=remote_nb_guid,
        contentLength=100,
        active=True,
    )
    mock_evernote_client.fake_l_notes.append(linked_note)
    mock_evernote_client.fake_linked_notebooks.append(
        LinkedNotebook(guid=l_nb_guid, shardId="s100")
    )
    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=s200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )
    mock_evernote_client.fake_updates = [
        _membership_event(shard_id="s100"),
        _note_entity_event(label="both paths", shard_id="s100"),
    ]

    result1 = cli_invoker("sync", "--database", "fake_db")
    assert result1.exit_code == 0

    mock_evernote_client.fake_usn = 100
    mock_evernote_client.fake_notebooks = []
    # Linked notebook still present
    mock_evernote_client.fake_updates = [
        _membership_event(
            operation=EvernoteSyncOperationType.DELETE,
            deleted=1785677802579,
            updated=1785677802663,
            shard_id="s100",
        ),
    ]

    result2 = cli_invoker("sync", "--database", "fake_db")
    assert result2.exit_code == 0
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    # Still available via linked notebook
    assert fake_storage.notes.note_exists(SHARED_NOTE_GUID)
    notes = list(fake_storage.notes.iter_notes(remote_nb_guid))
    assert len(notes) == 1


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_own_note_entity_ignored(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_updates = [
        _note_entity_event(
            note_guid="own-note-guid",
            owner_id=LOCAL_USER_ID,
            label="my own note",
        ),
    ]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert not fake_storage.notes.note_exists("own-note-guid")


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_membership_only_no_entity(
    cli_invoker, mock_evernote_client, fake_storage
):
    """Membership alone schedules download; entity event is not required in-chunk."""
    shared_note = Note(
        guid=SHARED_NOTE_GUID,
        title="from getNote",
        content="body only membership",
        notebookGuid="remote-nb",
        contentLength=100,
        active=True,
    )
    _queue_shared_note_body(mock_evernote_client, shared_note)
    mock_evernote_client.fake_updates = [_membership_event()]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    notes = list(fake_storage.notes.iter_notes(SHARED_WITH_ME_NOTEBOOK_GUID))
    assert len(notes) == 1
    assert notes[0].title == "from getNote"
    assert notes[0].content == "body only membership"


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_entity_before_membership_ignored(
    cli_invoker, mock_evernote_client, fake_storage
):
    """Foreign NOTE update without prior membership does not schedule the note.

    Note is not placed in fake_notes so EDAM USN sync cannot pick it up either;
    only v2 membership should ever introduce single shared notes.
    """
    mock_evernote_client.fake_updates = [_note_entity_event()]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)
    assert not fake_storage.notes.note_exists(SHARED_NOTE_GUID)
    assert fake_storage.notes.get_notes_for_sync() == ()


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_entity_expunge(
    cli_invoker, mock_evernote_client, fake_storage
):
    shared_note = Note(
        guid=SHARED_NOTE_GUID,
        title="shared title",
        content="body",
        notebookGuid="remote-nb",
        contentLength=100,
        active=True,
    )
    _queue_shared_note_body(mock_evernote_client, shared_note)
    mock_evernote_client.fake_updates = [
        _membership_event(),
        _note_entity_event(),
    ]

    result1 = cli_invoker("sync", "--database", "fake_db")
    assert result1.exit_code == 0
    assert fake_storage.notes.note_exists(SHARED_NOTE_GUID)

    mock_evernote_client.fake_usn = 100
    mock_evernote_client.fake_notebooks = []
    mock_evernote_client.fake_l_notes = []
    mock_evernote_client.fake_updates = [
        _note_entity_event(
            operation=EvernoteSyncOperationType.EXPUNGE,
            deleted=1785680000000,
            updated=1785680000001,
        ),
    ]

    result2 = cli_invoker("sync", "--database", "fake_db")
    assert result2.exit_code == 0
    assert not fake_storage.notes.note_exists(SHARED_NOTE_GUID)
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_ignore_non_explicit_share_type(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_updates = [_membership_event(share_type="LINK")]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert not fake_storage.shared_notes.is_shared_note(SHARED_NOTE_GUID)


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_notes_cursor_advances(
    cli_invoker, mock_evernote_client, fake_storage
):
    _queue_shared_note_body(
        mock_evernote_client,
        Note(
            guid=SHARED_NOTE_GUID,
            title="t",
            content="c",
            notebookGuid="remote-nb",
            contentLength=1,
            active=True,
        ),
    )
    mock_evernote_client.fake_updates = [
        _membership_event(updated=1785679990321),
    ]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    cursor = int(fake_storage.config.get_config_value("last_connection_shared_notes"))
    assert cursor == 1785679990321 + 1


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_reports_counts(
    cli_invoker, mock_evernote_client, fake_storage
):
    shared_note = Note(
        guid=SHARED_NOTE_GUID,
        title="shared title",
        content="body",
        notebookGuid="remote-nb",
        contentLength=100,
        active=True,
    )
    _queue_shared_note_body(mock_evernote_client, shared_note)
    mock_evernote_client.fake_updates = [
        _membership_event(),
        _note_entity_event(),
    ]

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert "Updated or added shared notes: 1" in result.output
    assert "Updated or added notes: 1" in result.output


@pytest.mark.usefixtures("fake_init_db_jwt")
def test_sync_shared_note_then_export(
    cli_invoker, mock_evernote_client, fake_storage, tmp_path
):
    shared_note = Note(
        guid=SHARED_NOTE_GUID,
        title="export me",
        content="shared export body",
        notebookGuid="remote-nb",
        contentLength=100,
        active=True,
    )
    _queue_shared_note_body(mock_evernote_client, shared_note)
    mock_evernote_client.fake_updates = [
        _membership_event(),
        _note_entity_event(label="export me"),
    ]

    sync_result = cli_invoker("sync", "--database", "fake_db")
    assert sync_result.exit_code == 0

    out = tmp_path / "export_out"
    export_result = cli_invoker("export", "--database", "fake_db", str(out))

    assert export_result.exit_code == 0
    enex = out / f"{SHARED_WITH_ME_NOTEBOOK_NAME}.enex"
    assert enex.is_file()
    text = enex.read_text(encoding="utf-8")
    assert "export me" in text
    assert "shared export body" in text
