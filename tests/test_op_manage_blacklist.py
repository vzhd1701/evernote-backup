import pytest
from evernote.edam.type.ttypes import Note, Notebook

NOTE_1 = "01234567-89ab-cdef-0123-456789abcdef"
NOTE_2 = "11234567-89ab-cdef-0123-456789abcdef"
NOTE_3 = "21234567-89ab-cdef-0123-456789abcdef"
NOTEBOOK_1 = "a1234567-89ab-cdef-0123-456789abcdef"
NOTEBOOK_2 = "b1234567-89ab-cdef-0123-456789abcdef"


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_list_empty(cli_invoker):
    result = cli_invoker("manage", "blacklist")

    assert result.exit_code == 0
    assert "Blacklist is empty." in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_add_and_list(cli_invoker, fake_storage):
    result = cli_invoker(
        "manage",
        "blacklist",
        "--add-note-id",
        NOTE_1,
        "--add-note-id",
        NOTE_2.upper(),
        "--add-notebook-id",
        NOTEBOOK_1,
    )

    assert result.exit_code == 0
    assert f"Added note [{NOTE_1}] to blacklist." in result.output
    assert f"Added note [{NOTE_2}] to blacklist." in result.output
    assert f"Added notebook [{NOTEBOOK_1}] to blacklist." in result.output

    assert fake_storage.config.get_blacklist_notes() == [NOTE_1, NOTE_2]
    assert fake_storage.config.get_blacklist_notebooks() == [NOTEBOOK_1]

    result = cli_invoker("manage", "blacklist")

    assert result.exit_code == 0
    assert "Blacklisted notes:" in result.output
    assert f"- {NOTE_1}" in result.output
    assert f"- {NOTE_2}" in result.output
    assert "Blacklisted notebooks:" in result.output
    assert f"- {NOTEBOOK_1}" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_add_invalid_guid(cli_invoker, fake_storage):
    result = cli_invoker(
        "manage",
        "blacklist",
        "--add-note-id",
        "not-a-real-guid",
    )

    assert result.exit_code == 1
    assert "Invalid GUID 'not-a-real-guid'" in result.output
    assert fake_storage.config.get_blacklist_notes() == []


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_add_guid_without_hyphens(cli_invoker, fake_storage):
    result = cli_invoker(
        "manage",
        "blacklist",
        "--add-note-id",
        "0123456789abcdef0123456789abcdef",
    )

    assert result.exit_code == 1
    assert "Invalid GUID" in result.output
    assert fake_storage.config.get_blacklist_notes() == []


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_add_duplicate_note(cli_invoker, fake_storage):
    fake_storage.config.set_blacklist_notes([NOTE_1])

    result = cli_invoker(
        "manage",
        "blacklist",
        "--add-note-id",
        NOTE_1,
    )

    assert result.exit_code == 0
    assert f"Note [{NOTE_1}] is already blacklisted." in result.output
    assert fake_storage.config.get_blacklist_notes() == [NOTE_1]


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_add_duplicate_notebook(cli_invoker, fake_storage):
    fake_storage.config.set_blacklist_notebooks([NOTEBOOK_1])

    result = cli_invoker(
        "manage",
        "blacklist",
        "--add-notebook-id",
        NOTEBOOK_1,
    )

    assert result.exit_code == 0
    assert f"Notebook [{NOTEBOOK_1}] is already blacklisted." in result.output
    assert fake_storage.config.get_blacklist_notebooks() == [NOTEBOOK_1]


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_del(cli_invoker, fake_storage):
    fake_storage.config.set_blacklist_notes([NOTE_1, NOTE_2])
    fake_storage.config.set_blacklist_notebooks([NOTEBOOK_1, NOTEBOOK_2])

    result = cli_invoker(
        "manage",
        "blacklist",
        "--del-note-id",
        NOTE_1,
        "--del-notebook-id",
        NOTEBOOK_2,
    )

    assert result.exit_code == 0
    assert f"Removed note [{NOTE_1}] from blacklist." in result.output
    assert f"Removed notebook [{NOTEBOOK_2}] from blacklist." in result.output
    assert fake_storage.config.get_blacklist_notes() == [NOTE_2]
    assert fake_storage.config.get_blacklist_notebooks() == [NOTEBOOK_1]


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_del_missing(cli_invoker, fake_storage):
    result = cli_invoker(
        "manage",
        "blacklist",
        "--del-note-id",
        NOTE_3,
        "--del-notebook-id",
        NOTEBOOK_2,
    )

    assert result.exit_code == 0
    assert f"Note [{NOTE_3}] is not blacklisted." in result.output
    assert f"Notebook [{NOTEBOOK_2}] is not blacklisted." in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_del_invalid_guid(cli_invoker):
    result = cli_invoker(
        "manage",
        "blacklist",
        "--del-note-id",
        "missing-note",
    )

    assert result.exit_code == 1
    assert "Invalid GUID 'missing-note'" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_reset(cli_invoker, fake_storage):
    fake_storage.config.set_blacklist_notes([NOTE_1])
    fake_storage.config.set_blacklist_notebooks([NOTEBOOK_1])

    result = cli_invoker(
        "manage",
        "blacklist",
        "--reset-notes",
        "--reset-notebooks",
    )

    assert result.exit_code == 0
    assert "Cleared blacklisted notes." in result.output
    assert "Cleared blacklisted notebooks." in result.output
    assert fake_storage.config.get_blacklist_notes() == []
    assert fake_storage.config.get_blacklist_notebooks() == []


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_reset_notes_then_add(cli_invoker, fake_storage):
    fake_storage.config.set_blacklist_notes([NOTE_1])

    result = cli_invoker(
        "manage",
        "blacklist",
        "--reset-notes",
        "--add-note-id",
        NOTE_2,
    )

    assert result.exit_code == 0
    assert fake_storage.config.get_blacklist_notes() == [NOTE_2]


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_list_notes_only(cli_invoker, fake_storage):
    fake_storage.config.set_blacklist_notes([NOTE_1])

    result = cli_invoker("manage", "blacklist")

    assert result.exit_code == 0
    assert "Blacklisted notes:" in result.output
    assert f"- {NOTE_1}" in result.output
    assert "Blacklisted notebooks:" in result.output
    assert result.output.index("Blacklisted notebooks:") < result.output.index(
        "- (none)"
    )


@pytest.mark.usefixtures("fake_init_db")
def test_manage_blacklist_list_notebooks_only(cli_invoker, fake_storage):
    fake_storage.config.set_blacklist_notebooks([NOTEBOOK_1])

    result = cli_invoker("manage", "blacklist")

    assert result.exit_code == 0
    assert "Blacklisted notes:" in result.output
    assert result.output.index("Blacklisted notes:") < result.output.index("- (none)")
    assert result.output.index("- (none)") < result.output.index(
        "Blacklisted notebooks:"
    )
    assert f"- {NOTEBOOK_1}" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_sync_skips_blacklisted_note(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    mock_evernote_client.fake_notebooks.append(
        Notebook(guid="nbid1", name="name1", stack="stack1", serviceUpdated=1000)
    )

    mock_evernote_client.fake_notes.extend(
        [
            Note(guid="id1", title="keep", notebookGuid="nbid1"),
            Note(guid="id2", title="skip-me", notebookGuid="nbid1"),
            Note(guid="id3", title="keep2", notebookGuid="nbid1"),
        ]
    )

    fake_storage.config.set_blacklist_notes(["id2"])

    mock_get_note = mocker.patch(
        "evernote_backup.evernote_client_sync.EvernoteClientSync.get_note"
    )
    mock_get_note.side_effect = lambda note_guid: Note(
        guid=note_guid,
        title="test",
        content="test",
        notebookGuid="nbid1",
        contentLength=100,
        active=True,
    )

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert "Skipped 1 blacklisted note(s)." in result.output
    assert "2 note(s) to download..." in result.output

    downloaded_guids = {call.args[0] for call in mock_get_note.call_args_list}
    assert downloaded_guids == {"id1", "id3"}


@pytest.mark.usefixtures("fake_init_db")
def test_sync_skips_notes_from_blacklisted_notebook(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    mock_evernote_client.fake_notebooks.extend(
        [
            Notebook(guid="nbid1", name="name1", stack="stack1", serviceUpdated=1000),
            Notebook(guid="nbid2", name="name2", stack="stack1", serviceUpdated=1000),
        ]
    )

    mock_evernote_client.fake_notes.extend(
        [
            Note(guid="id1", title="keep", notebookGuid="nbid1"),
            Note(guid="id2", title="skip-nb", notebookGuid="nbid2"),
            Note(guid="id3", title="skip-nb2", notebookGuid="nbid2"),
        ]
    )

    fake_storage.config.set_blacklist_notebooks(["nbid2"])

    mock_get_note = mocker.patch(
        "evernote_backup.evernote_client_sync.EvernoteClientSync.get_note"
    )
    mock_get_note.side_effect = lambda note_guid: Note(
        guid=note_guid,
        title="test",
        content="test",
        notebookGuid="nbid1",
        contentLength=100,
        active=True,
    )

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert "Skipped 2 blacklisted note(s)." in result.output
    assert "1 note(s) to download..." in result.output

    downloaded_guids = {call.args[0] for call in mock_get_note.call_args_list}
    assert downloaded_guids == {"id1"}
