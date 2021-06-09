import time

import pytest
from evernote.edam.type.ttypes import Note, Notebook, Tag

from evernote_backup import note_synchronizer
from evernote_backup.cli_app_util import ProgramTerminatedError


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_notebook(cli_invoker, mock_evernote_client, fake_storage):
    test_notebooks = [
        Notebook(
            guid="id1",
            name="name1",
            stack="stack1",
        )
    ]
    mock_evernote_client.fake_notebooks = test_notebooks

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result_notebooks == test_notebooks


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_note(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
            stack="stack1",
            serviceUpdated=1000,
        ),
    )

    test_note = Note(
        guid="id1",
        title="title1",
        content="body1",
        notebookGuid="nbid1",
        active=True,
    )

    mock_evernote_client.fake_notes.append(test_note)

    cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == [test_note]


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_note_with_tags(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_tags = [
        Tag(guid="tid1", name="tag1"),
        Tag(guid="tid2", name="tag2"),
    ]

    mock_evernote_client.fake_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
            stack="stack1",
            serviceUpdated=1000,
        ),
    )

    mock_evernote_client.fake_notes.append(
        Note(
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
            content="body1",
            notebookGuid="nbid1",
            active=True,
            tagGuids=["tid1", "tid2"],
            tagNames=["tag1", "tag2"],
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
        Notebook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        Notebook(
            guid="id2",
            name="name1",
            stack="stack1",
        ),
        Notebook(
            guid="id3",
            name="name1",
            stack="stack1",
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)
    fake_storage.config.set_config_value("USN", "1")

    mock_evernote_client.fake_expunged_notebooks = ["id1", "id3"]

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert len(result_notebooks) == 1
    assert result_notebooks[0].guid == "id2"


@pytest.mark.usefixtures("fake_init_db")
def test_sync_expunge_notes(cli_invoker, mock_evernote_client, fake_storage):
    test_notes = [
        Note(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="test",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="test",
            active=True,
        ),
        Note(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="test",
            active=True,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)
    fake_storage.config.set_config_value("USN", "1")

    mock_evernote_client.fake_expunged_notes = ["id1", "id3"]

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notes.iter_notes("test"))

    assert len(result_notebooks) == 1
    assert result_notebooks[0].guid == "id2"


@pytest.mark.usefixtures("fake_init_db")
def test_sync_nothing_to_sync(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_notebooks.append(
        Notebook(
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
    test_notes = [Note(guid=f"id{i}", title="test") for i in range(100)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def interrupter(note):
        if note.guid == "id10":
            raise KeyboardInterrupt

    def fake_slow_get_note(note_guid):
        time.sleep(0.1)
        return Note(
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


@pytest.mark.usefixtures("mock_evernote_client")
@pytest.mark.usefixtures("fake_init_db")
def test_old_db_error(cli_invoker, mock_evernote_client, fake_storage):
    fake_storage.config.set_config_value("DB_VERSION", "0")

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("sync", "--database", "fake_db")
    assert "Full resync is required" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_sync_custom_max_chunk_results(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
            stack="stack1",
            serviceUpdated=1000,
        ),
    )

    test_note = Note(
        guid="id1",
        title="title1",
        content="body1",
        notebookGuid="nbid1",
        active=True,
    )

    mock_evernote_client.fake_notes.append(test_note)
    test_max_chunk_results = 100

    cli_invoker(
        "sync", "--database", "fake_db", "--max-chunk-results", test_max_chunk_results
    )

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == [test_note]
    assert mock_evernote_client.last_maxEntries == test_max_chunk_results


@pytest.mark.usefixtures("fake_init_db")
def test_sync_custom_max_download_workers(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    mock_evernote_client.fake_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
            stack="stack1",
            serviceUpdated=1000,
        ),
    )

    test_note = Note(
        guid="id1",
        title="title1",
        content="body1",
        notebookGuid="nbid1",
        active=True,
    )

    mock_evernote_client.fake_notes.append(test_note)

    test_max_download_workers = 1
    thread_pool_spy = mocker.spy(note_synchronizer, "ThreadPoolExecutor")

    cli_invoker(
        "sync",
        "--database",
        "fake_db",
        "--max-download-workers",
        test_max_download_workers,
    )

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == [test_note]
    thread_pool_spy.assert_called_once_with(max_workers=test_max_download_workers)


@pytest.mark.usefixtures("fake_init_db")
@pytest.mark.usefixtures("mock_output_to_terminal")
def test_sync_massive_note_count(
    cli_invoker, mock_evernote_client, fake_storage, monkeypatch
):
    mock_evernote_client.fake_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
            stack="stack1",
            serviceUpdated=1000,
        ),
    )

    for i in range(10):
        test_note = Note(
            guid=f"id{i}",
            title=f"title{i}",
            content="body1",
            notebookGuid="nbid1",
            active=True,
        )

        mock_evernote_client.fake_notes.append(test_note)

    monkeypatch.setattr(note_synchronizer, "THREAD_CHUNK_SIZE", 2)

    cli_invoker("sync", "--database", "fake_db")

    result_notes = sorted(
        fake_storage.notes.iter_notes("nbid1"), key=lambda x: int(x.guid[2:])
    )

    assert result_notes == mock_evernote_client.fake_notes
