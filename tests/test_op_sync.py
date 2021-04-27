import time

import pytest
from evernote.edam.type.ttypes import Note as RawNote
from evernote.edam.type.ttypes import Notebook as RawNoteBook
from evernote.edam.type.ttypes import Tag as RawTag

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.note_storage import Note, NoteBook


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_notebook(cli_invoker, mock_evernote_client, fake_storage):
    expected_notebooks = [
        NoteBook(
            guid="id1",
            name="name1",
            stack="stack1",
        )
    ]
    mock_evernote_client.fake_notebooks.append(
        RawNoteBook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
    )

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result_notebooks == expected_notebooks


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_note(cli_invoker, mock_evernote_client, fake_storage, mock_formatter):
    mock_evernote_client.fake_notebooks.append(
        RawNoteBook(
            guid="nbid1",
            name="name1",
            stack="stack1",
            serviceUpdated=1000,
        ),
    )

    mock_evernote_client.fake_notes.append(
        RawNote(
            guid="id1",
            title="title1",
            content="body1",
            notebookGuid="nbid1",
            active=True,
        )
    )

    expected_notes = [
        Note(
            guid="id1",
            title="title1",
            body="body1",
            notebook_guid="nbid1",
            is_active=True,
        )
    ]

    mock_formatter.fake_body = "body1"

    cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == expected_notes


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_note_with_tags(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_tags = [
        RawTag(guid="tid1", name="tag1"),
        RawTag(guid="tid2", name="tag2"),
    ]

    mock_evernote_client.fake_notebooks.append(
        RawNoteBook(
            guid="nbid1",
            name="name1",
            stack="stack1",
            serviceUpdated=1000,
        ),
    )

    mock_evernote_client.fake_notes.append(
        RawNote(
            guid="id1",
            title="title1",
            content="body1",
            notebookGuid="nbid1",
            active=True,
            tagGuids=["tid1", "tid2"],
        )
    )

    expected_notes = [
        Note(
            guid="id1",
            title="title1",
            body="  <note>\n"
            "    <title>title1</title>\n"
            "    <tag>tag1</tag>\n"
            "    <tag>tag2</tag>\n"
            "    <content>\n"
            '      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
            "body1]]>\n"
            "    </content>\n"
            "  </note>\n",
            notebook_guid="nbid1",
            is_active=True,
        )
    ]

    cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == expected_notes


@pytest.mark.usefixtures("fake_init_db")
def test_sync_wrong_user(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_user = "user1"

    fake_storage.config.set_config_value("user", "user2")

    with pytest.raises(ProgramTerminatedError):
        cli_invoker("sync", "--database", "fake_db")


@pytest.mark.usefixtures("fake_init_db")
def test_sync_expunge_notebooks(cli_invoker, mock_evernote_client, fake_storage):
    test_notebooks = [
        RawNoteBook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        RawNoteBook(
            guid="id2",
            name="name1",
            stack="stack1",
        ),
        RawNoteBook(
            guid="id3",
            name="name1",
            stack="stack1",
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)
    fake_storage.config.set_config_value("USN", 1)

    mock_evernote_client.fake_expunged_notebooks = ["id1", "id3"]

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert len(result_notebooks) == 1
    assert result_notebooks[0].guid == "id2"


@pytest.mark.usefixtures("mock_formatter")
@pytest.mark.usefixtures("fake_init_db")
def test_sync_expunge_notes(cli_invoker, mock_evernote_client, fake_storage):
    test_notes = [
        RawNote(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="test",
            active=True,
        ),
        RawNote(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="test",
            active=True,
        ),
        RawNote(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="test",
            active=True,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)
    fake_storage.config.set_config_value("USN", 1)

    mock_evernote_client.fake_expunged_notes = ["id1", "id3"]

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notes.iter_notes("test"))

    assert len(result_notebooks) == 1
    assert result_notebooks[0].guid == "id2"


@pytest.mark.usefixtures("fake_init_db")
def test_sync_nothing_to_sync(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_notebooks.append(
        RawNoteBook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
    )

    fake_storage.config.set_config_value("USN", mock_evernote_client.fake_usn)

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert not result_notebooks


@pytest.mark.usefixtures("fake_init_db")
def test_sync_interrupt_download(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    test_notes = [RawNote(guid=f"id{i}", title="test") for i in range(100)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def interrupter(note):
        if note.guid == "id10":
            raise KeyboardInterrupt

    def fake_slow_get_note(note_guid):
        time.sleep(0.1)
        return RawNote(
            guid=note_guid,
            title="test",
            content="test",
            notebookGuid="test",
            active=True,
        )

    mock_get_note = mocker.patch(
        "evernote_backup.evernote_client_sync.EvernoteClientSync.get_note"
    )
    mock_get_note.side_effect = fake_slow_get_note

    mock_add_note = mocker.patch("evernote_backup.note_storage.NoteStorage.add_note")
    mock_add_note.side_effect = interrupter

    cli_invoker("sync", "--database", "fake_db")
