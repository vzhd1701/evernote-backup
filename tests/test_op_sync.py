import struct
import time
from hashlib import md5

import pytest
from evernote.edam.type.ttypes import (
    Data,
    LinkedNotebook,
    Note,
    Notebook,
    Resource,
    Tag,
)

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
        contentLength=100,
    )

    mock_evernote_client.fake_notes.append(test_note)

    cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == [test_note]


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_note_with_res(cli_invoker, mock_evernote_client, fake_storage):
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
        contentLength=100,
        resources=[
            Resource(
                guid="rid2",
                noteGuid="id1",
                data=Data(bodyHash=md5(b"000").digest(), size=3, body=b"000"),
            )
        ],
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
            contentLength=100,
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
            contentLength=100,
            tagGuids=["tid1", "tid2"],
            tagNames=["tag1", "tag2"],
        )
    ]

    cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == expected_notes


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_linked_notebook(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )

    mock_evernote_client.fake_linked_notebooks.append(LinkedNotebook(guid="id3"))

    mock_evernote_client.fake_l_usn = 123

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_l_notebooks_asn = fake_storage.notebooks.get_linked_notebook_usn("id3")

    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_l_notebooks_asn == mock_evernote_client.fake_l_usn


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_linked_notebook_nothing_to_sync(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )

    mock_evernote_client.fake_linked_notebooks.append(LinkedNotebook(guid="id3"))

    mock_evernote_client.fake_l_usn = 100

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_l_notebooks_asn = fake_storage.notebooks.get_linked_notebook_usn("id3")

    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_l_notebooks_asn == mock_evernote_client.fake_l_usn

    cli_invoker("sync", "--database", "fake_db")


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_linked_notebook_stack(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )

    mock_evernote_client.fake_linked_notebooks.append(
        LinkedNotebook(guid="id3", stack="test_stack")
    )

    expected_notebooks = [
        Notebook(
            guid="nbid1",
            name="name1",
            stack="test_stack",
        )
    ]

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result_notebooks == expected_notebooks


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_linked_notebook_note(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )

    mock_evernote_client.fake_l_notes.append(
        Note(
            guid="id1",
            title="title1",
            content="body1",
            notebookGuid="nbid1",
            contentLength=100,
            active=True,
        )
    )

    mock_evernote_client.fake_linked_notebooks.append(
        LinkedNotebook(guid="id3", shardId="s100")
    )

    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_notes == mock_evernote_client.fake_l_notes


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_linked_notebook_note_public(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )

    mock_evernote_client.fake_l_notes.append(
        Note(
            guid="id1",
            title="title1",
            content="body1",
            notebookGuid="nbid1",
            contentLength=100,
            active=True,
        )
    )

    mock_evernote_client.fake_linked_notebooks.append(
        LinkedNotebook(guid="id3", shardId="s100", uri="public_uri")
    )

    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_notes == mock_evernote_client.fake_l_notes


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_linked_notebook_note_with_tag(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )

    mock_evernote_client.fake_l_tags = [
        Tag(guid="tid1", name="tag1"),
        Tag(guid="tid2", name="tag2"),
    ]

    mock_evernote_client.fake_l_notes.append(
        Note(
            guid="id1",
            title="title1",
            content="body1",
            notebookGuid="nbid1",
            active=True,
            contentLength=100,
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
            contentLength=100,
            tagGuids=["tid1", "tid2"],
            tagNames=["tag1", "tag2"],
        )
    ]

    mock_evernote_client.fake_linked_notebooks.append(
        LinkedNotebook(guid="id3", shardId="s100")
    )

    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notes == expected_notes


@pytest.mark.usefixtures("fake_init_db")
def test_sync_expunge_linked_notebook_note(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )
    mock_evernote_client.fake_l_notes.append(
        Note(
            guid="id1",
            title="title1",
            content="body1",
            notebookGuid="nbid1",
            contentLength=100,
            active=True,
        )
    )
    mock_evernote_client.fake_linked_notebooks.append(
        LinkedNotebook(guid="id3", shardId="s100")
    )
    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )
    mock_evernote_client.fake_usn = 100

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_notes == mock_evernote_client.fake_l_notes

    mock_evernote_client.fake_l_notebooks = []
    mock_evernote_client.fake_l_notes = []
    mock_evernote_client.fake_linked_notebooks = []
    mock_evernote_client.fake_usn = 101

    mock_evernote_client.fake_expunged_linked_notebooks = ["id3", "id4"]

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notebooks == []
    assert result_notes == []


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_linked_notebook_note_error_no_access(
    cli_invoker, mock_evernote_client, fake_storage
):
    mock_evernote_client.fake_l_notebooks.append(
        Notebook(
            guid="nbid1",
            name="name1",
        ),
    )

    mock_evernote_client.fake_l_notes.append(
        Note(
            guid="id1",
            title="title1",
            content="body1",
            notebookGuid="nbid1",
            contentLength=100,
            active=True,
        )
    )

    mock_evernote_client.fake_linked_notebooks.append(LinkedNotebook(guid="id3"))

    mock_evernote_client.fake_linked_notebook_auth_token = (
        "S=200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    mock_evernote_client.fake_auth_linked_notebook_error = True

    cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result_notebooks == []
    assert result_notes == []


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
            contentLength=100,
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="test",
            contentLength=100,
            active=True,
        ),
        Note(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="test",
            contentLength=100,
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
            contentLength=100,
            active=True,
        )

    mock_get_note = mocker.patch(
        "evernote_backup.evernote_client_sync.EvernoteClientSync.get_note"
    )
    mock_get_note.side_effect = fake_slow_get_note

    mock_add_note = mocker.patch("evernote_backup.note_storage.NoteStorage.add_note")
    mock_add_note.side_effect = interrupter

    cli_invoker("sync", "--database", "fake_db")


@pytest.mark.usefixtures("fake_init_db")
def test_sync_exception_while_download(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    test_notes = [Note(guid=f"id{i}", title="test") for i in range(100)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def fake_get_note(note_guid):
        if note_guid == "id10":
            raise RuntimeError("Test error")

        return Note(
            guid=note_guid,
            title="test",
            content="test",
            notebookGuid="test",
            contentLength=100,
            active=True,
        )

    mock_get_note = mocker.patch(
        "evernote_backup.evernote_client_sync.EvernoteClientSync.get_note"
    )
    mock_get_note.side_effect = fake_get_note

    with pytest.raises(RuntimeError) as excinfo:
        cli_invoker("sync", "--database", "fake_db")

    assert str(excinfo.value) == "Test error"


@pytest.mark.usefixtures("fake_init_db")
def test_sync_exception_while_download_retry_fail(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    test_notes = [Note(guid=f"id{i}", title="test") for i in range(100)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def fake_get_note(note_guid):
        if note_guid == "id10":
            raise struct.error

        return Note(
            guid=note_guid,
            title="test",
            content="test",
            notebookGuid="test",
            contentLength=100,
            active=True,
        )

    mock_get_note = mocker.patch(
        "evernote_backup.evernote_client_sync.EvernoteClientSync.get_note"
    )
    mock_get_note.side_effect = fake_get_note

    with pytest.raises(RuntimeError) as excinfo:
        cli_invoker("sync", "--database", "fake_db")

    assert "Failed to download note" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_sync_exception_while_download_retry(
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

    test_notes = [
        Note(
            guid=f"id{i}",
            title="test",
            content="test",
            notebookGuid="nbid1",
            contentLength=100,
            active=True,
        )
        for i in range(10)
    ]

    mock_evernote_client.fake_notes.extend(test_notes)

    retry_count = 3

    def fake_get_note(note_guid):
        nonlocal retry_count
        if note_guid == "id3" and retry_count > 0:
            retry_count -= 1
            raise struct.error

        return Note(
            guid=note_guid,
            title="test",
            content="test",
            notebookGuid="nbid1",
            contentLength=100,
            active=True,
        )

    mock_get_note = mocker.patch(
        "evernote_backup.evernote_client_sync.EvernoteClientSync.get_note"
    )
    mock_get_note.side_effect = fake_get_note

    cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert set(result_notes) == set(test_notes)


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
        contentLength=100,
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
        contentLength=100,
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
            contentLength=100,
            active=True,
        )

        mock_evernote_client.fake_notes.append(test_note)

    monkeypatch.setattr(note_synchronizer, "THREAD_CHUNK_SIZE", 2)

    cli_invoker("sync", "--database", "fake_db")

    result_notes = sorted(
        fake_storage.notes.iter_notes("nbid1"), key=lambda x: int(x.guid[2:])
    )

    assert result_notes == mock_evernote_client.fake_notes
