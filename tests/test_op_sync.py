import struct
import time
from hashlib import md5

import pytest
from evernote.edam.error.ttypes import EDAMErrorCode, EDAMSystemException
from evernote.edam.type.ttypes import (
    Data,
    LinkedNotebook,
    Note,
    Notebook,
    Resource,
    Tag,
)

from evernote_backup import note_synchronizer
from evernote_backup.evernote_types import Reminder, Task


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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_l_notebooks_usn = fake_storage.notebooks.get_linked_notebook_usn("id3")

    assert result.exit_code == 0
    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_l_notebooks_usn == mock_evernote_client.fake_l_usn


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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_l_notebooks_usn = fake_storage.notebooks.get_linked_notebook_usn("id3")

    assert result.exit_code == 0
    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_l_notebooks_usn == mock_evernote_client.fake_l_usn

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert "nothing to sync" in result.output


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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result.exit_code == 0
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
        "S=s200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    result = cli_invoker("-v", "sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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
        "S=s200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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
        "S=s200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    result = cli_invoker("sync", "--database", "fake_db")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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
        "S=s200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )
    mock_evernote_client.fake_usn = 100

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
    assert result_notebooks == mock_evernote_client.fake_l_notebooks
    assert result_notes == mock_evernote_client.fake_l_notes

    mock_evernote_client.fake_l_notebooks = []
    mock_evernote_client.fake_l_notes = []
    mock_evernote_client.fake_linked_notebooks = []
    mock_evernote_client.fake_usn = 101

    mock_evernote_client.fake_expunged_linked_notebooks = ["id3", "id4"]

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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
        "S=s200:U=ff:E=fff:C=ff:P=1:A=test222:V=2:H=ff"
    )

    mock_evernote_client.fake_auth_linked_notebook_error = True

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())
    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
    assert result_notebooks == []
    assert result_notes == []


@pytest.mark.usefixtures("fake_init_db")
def test_sync_wrong_user(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_user = "user1"

    fake_storage.config.set_config_value("user", "user2")

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 1
    assert "Current user of this database is user2, not user1" in result.output


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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notes.iter_notes("test"))

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 1
    assert "Aborting, please wait" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_sync_unknown_exception_while_download(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    test_notes = [Note(guid=f"id{i}", title="test") for i in range(10)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def fake_get_note(note_guid):
        if note_guid == "id3":
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

    result = cli_invoker("-v", "sync", "--database", "fake_db")

    assert result.exit_code == 0
    assert "Test error" in result.output
    assert "Failed to download note [id3] after" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_sync_edam_exception_while_download(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    test_notes = [Note(guid=f"id{i}", title="test") for i in range(10)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def fake_get_note(note_guid):
        if note_guid == "id3":
            raise EDAMSystemException(
                errorCode=EDAMErrorCode.INTERNAL_ERROR, message="Test error"
            )

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

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0

    assert (
        "Remote server returned system error (INTERNAL_ERROR - Test error) while downloading note [id3]"
        in result.output
    )
    assert (
        "Note 'test' will be skipped for this run and retried during the next sync"
        in result.output
    )


@pytest.mark.usefixtures("fake_init_db")
def test_sync_edam_rate_limit_exception_while_download(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    test_notes = [Note(guid=f"id{i}", title="test") for i in range(10)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def fake_get_note(note_guid):
        if note_guid == "id3":
            raise EDAMSystemException(
                errorCode=EDAMErrorCode.RATE_LIMIT_REACHED,
                message="Test rate limit",
                rateLimitDuration=10,
            )

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

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 1
    assert "Rate limit reached. Restart program in 0:10" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_sync_exception_while_download_retry_fail(
    cli_invoker, mock_evernote_client, fake_storage, mocker
):
    test_notes = [Note(guid=f"id{i}", title="test") for i in range(10)]

    mock_evernote_client.fake_notes.extend(test_notes)

    def fake_get_note(note_guid):
        if note_guid == "id3":
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

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0

    assert "Failed to download note [id3] after 5 attempts" in result.output
    assert (
        "Note 'test' will be skipped for this run and retried during the next sync"
        in result.output
    )


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

    result = cli_invoker("sync", "--database", "fake_db")

    result_notes = sorted(fake_storage.notes.iter_notes("nbid1"), key=lambda n: n.guid)

    assert result.exit_code == 0
    assert result_notes == test_notes


@pytest.mark.usefixtures("mock_evernote_client")
@pytest.mark.usefixtures("fake_init_db")
def test_old_db_error(cli_invoker, mock_evernote_client, fake_storage):
    fake_storage.config.set_config_value("DB_VERSION", "0")

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 1
    assert "Full resync is required" in result.output


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

    result = cli_invoker(
        "sync", "--database", "fake_db", "--max-chunk-results", test_max_chunk_results
    )

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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

    result = cli_invoker(
        "sync",
        "--database",
        "fake_db",
        "--max-download-workers",
        test_max_download_workers,
    )

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))

    assert result.exit_code == 0
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

    result = cli_invoker("sync", "--database", "fake_db")

    assert result.exit_code == 0
    result_notes = sorted(
        fake_storage.notes.iter_notes("nbid1"), key=lambda x: int(x.guid[2:])
    )

    assert result_notes == mock_evernote_client.fake_notes


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_task(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_jwt_token = "fake_jwt"

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

    test_task = Task(
        taskId="c16d6ec7-9a4f-4860-b490-12d93774897c",
        parentId=test_note.guid,
        parentType=0,
        noteLevelID="nl-abcdef123456",
        taskGroupNoteLevelID="be9a14f8-06f8-44df-bcd3-945adf5b282a",
        label="Test Label",
        description="Test Description",
        dueDate=1713129600000,
        dueDateUIOption="date_only",
        timeZone="America/New_York",
        status="open",
        statusUpdated=1712692800000,
        inNote=True,
        flag=True,
        taskFlag=2,
        priority=3,
        idClock=1,
        sortWeight="A",
        creator=5678901,
        lastEditor=5678901,
        ownerId=5678901,
        created=1712261000000,
        updated=1712692800000,
        assigneeEmail="test@test.com",
        assigneeUserId=9012345,
        assignedByUserId=5678901,
        recurrence="RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO",
        repeatAfterCompletion=False,
    )

    mock_evernote_client.fake_updates.append(
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": test_task.taskId, "type": 15},
                "type": 1,
                "version": test_task.updated,
                "created": test_task.created,
                "updated": test_task.updated,
                "deleted": 0,
                "shardId": "",
                "ownerId": test_task.ownerId,
                "noteLevelID": test_task.noteLevelID,
                "taskGroupNoteLevelID": test_task.taskGroupNoteLevelID,
                "label": test_task.label,
                "dueDate": test_task.dueDate,
                "dueDateUIOption": test_task.dueDateUIOption,
                "timeZone": test_task.timeZone,
                "status": test_task.status,
                "statusUpdated": test_task.statusUpdated,
                "inNote": test_task.inNote,
                "flag": test_task.flag,
                "sortWeight": test_task.sortWeight,
                "creator": test_task.creator,
                "lastEditor": test_task.lastEditor,
                "assigneeUserID": test_task.assigneeUserId,
                "assigneeEmail": test_task.assigneeEmail,
                "assigneeIdentityId": test_task.assigneeIdentityId,
                "assignedByUserID": test_task.assignedByUserId,
                "recurrence": test_task.recurrence,
                "repeatAfterCompletion": test_task.repeatAfterCompletion,
                "priority": test_task.priority,
                "sourceOfChange": "RTE",
                "taskFlag": test_task.taskFlag,
                "featureVersion": [0, 1, 0],
                "embeddedOutliers": [],
                "idClock": test_task.idClock,
                "description": test_task.description,
                "parentEntity": {"id": test_note.guid, "type": 0},
            },
            "operation": 2,
            "updated": 1744277698547,
        },
    )

    result = cli_invoker("sync", "--database", "fake_db", "--include-tasks")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))
    result_tasks = list(fake_storage.tasks.iter_tasks("id1"))

    assert result.exit_code == 0
    assert result_notes == [test_note]
    assert result_tasks == [test_task]


@pytest.mark.usefixtures("fake_init_db")
def test_sync_add_task_with_reminder(cli_invoker, mock_evernote_client, fake_storage):
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

    test_task = Task(
        taskId="c16d6ec7-9a4f-4860-b490-12d93774897c",
        parentId=test_note.guid,
        parentType=0,
        noteLevelID="nl-abcdef123456",
        taskGroupNoteLevelID="be9a14f8-06f8-44df-bcd3-945adf5b282a",
        label="Test Label",
        status="open",
        statusUpdated=1712692800000,
        idClock=1,
        sortWeight="A",
        creator=5678901,
        lastEditor=5678901,
        ownerId=5678901,
        created=1712261000000,
        updated=1712692800000,
    )

    test_reminder = Reminder(
        reminderId="5d48e464-1dad-4624-9523-24f2bd8f8fe3",
        sourceId=test_task.taskId,
        sourceType=15,
        noteLevelID="38e93c9d-f34e-4754-bb08-5f5ceb62154a",
        reminderDate=1713042000000,
        reminderDateUIOption="date_time",
        timeZone="America/New_York",
        dueDateOffset=86400,
        status="active",
        ownerId=5678901,
        created=1712175600000,
        updated=1712520000000,
    )

    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": test_task.taskId, "type": 15},
                "type": 1,
                "version": test_task.updated,
                "created": test_task.created,
                "updated": test_task.updated,
                "deleted": 0,
                "shardId": "",
                "ownerId": test_task.ownerId,
                "noteLevelID": test_task.noteLevelID,
                "taskGroupNoteLevelID": test_task.taskGroupNoteLevelID,
                "label": test_task.label,
                "status": test_task.status,
                "statusUpdated": test_task.statusUpdated,
                "sortWeight": test_task.sortWeight,
                "creator": test_task.creator,
                "lastEditor": test_task.lastEditor,
                "sourceOfChange": "RTE",
                "featureVersion": [0, 1, 0],
                "embeddedOutliers": [],
                "idClock": test_task.idClock,
                "parentEntity": {"id": test_note.guid, "type": 0},
            },
            "operation": 2,
            "updated": 1744277698547,
        },
        {
            "acl": {"agentIds": ["123:;2"], "updated": 0},
            "instance": {
                "ref": {"id": test_reminder.reminderId, "type": 16},
                "type": 1,
                "version": test_reminder.updated,
                "created": test_reminder.created,
                "updated": test_reminder.updated,
                "deleted": 0,
                "shardId": "",
                "ownerId": test_reminder.ownerId,
                "reminderDate": test_reminder.reminderDate,
                "reminderDateUIOption": test_reminder.reminderDateUIOption,
                "timeZone": test_reminder.timeZone,
                "status": test_reminder.status,
                "noteLevelID": test_reminder.noteLevelID,
                "dueDateOffset": test_reminder.dueDateOffset,
                "parentEntity": {
                    "id": test_task.taskId,
                    "type": 15,
                },
            },
            "operation": 1,
            "updated": 1744275073798,
        },
    ]

    result = cli_invoker("sync", "--database", "fake_db", "--include-tasks")

    result_notes = list(fake_storage.notes.iter_notes("nbid1"))
    result_tasks = list(fake_storage.tasks.iter_tasks("id1"))
    result_reminders = list(fake_storage.reminders.iter_reminders(test_task.taskId))

    assert result.exit_code == 0
    assert result_notes == [test_note]
    assert len(result_tasks) == 1
    assert result_reminders == [test_reminder]


@pytest.mark.usefixtures("fake_init_db")
def test_sync_expunge_task(cli_invoker, mock_evernote_client, fake_storage):
    test_task = Task(
        taskId="c16d6ec7-9a4f-4860-b490-12d93774897c",
        parentId="nid1",
        parentType=0,
    )

    fake_storage.tasks.add_task(test_task)

    mock_evernote_client.fake_updates.append(
        {
            "acl": {"agentIds": ["123:;2"], "updated": 0},
            "instance": {
                "ref": {"id": test_task.taskId, "type": 15},
                "type": 1,
                "version": 9007199254740991,
                "created": 1744264744284,
                "updated": 9007199254740991,
                "deleted": 0,
                "shardId": "",
                "ownerId": 123,
                "parentEntity": {
                    "id": "nid1",
                    "type": 0,
                },
            },
            "operation": 4,
            "updated": 1744275036349,
        },
    )

    result_tasks_before = list(fake_storage.tasks.iter_tasks("nid1"))

    result = cli_invoker("sync", "--database", "fake_db", "--include-tasks")

    result_tasks = list(fake_storage.tasks.iter_tasks("nid1"))

    assert result.exit_code == 0
    assert "Expunged tasks: 1" in result.output
    assert len(result_tasks) == 0
    assert len(result_tasks_before) == 1


@pytest.mark.usefixtures("fake_init_db")
def test_sync_expunge_reminder(cli_invoker, mock_evernote_client, fake_storage):
    test_reminder = Reminder(
        reminderId="c16d6ec7-9a4f-4860-b490-12d93774897c",
        sourceId="tid1",
        sourceType=0,
    )

    fake_storage.reminders.add_reminder(test_reminder)

    mock_evernote_client.fake_updates.append(
        {
            "acl": {"agentIds": ["123:;2"], "updated": 0},
            "instance": {
                "ref": {"id": test_reminder.reminderId, "type": 16},
                "type": 1,
                "version": 9007199254740991,
                "created": 1744264744284,
                "updated": 9007199254740991,
                "deleted": 0,
                "shardId": "",
                "ownerId": 123,
                "parentEntity": {
                    "id": "nid1",
                    "type": 0,
                },
            },
            "operation": 4,
            "updated": 1744275036349,
        },
    )

    result_reminders_before = list(fake_storage.reminders.iter_reminders("tid1"))

    result = cli_invoker("sync", "--database", "fake_db", "--include-tasks")

    result_reminders = list(fake_storage.reminders.iter_reminders("tid1"))

    assert result.exit_code == 0
    assert "Expunged reminders: 1" in result.output
    assert len(result_reminders_before) == 1
    assert len(result_reminders) == 0


@pytest.mark.usefixtures("fake_init_db")
def test_sync_bad_token_for_jwt(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_is_token_bad_for_jwt = True

    result = cli_invoker("sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 1
    assert (
        "This auth token does not have permission to use the new Evernote API"
        in result.output
    )


@pytest.mark.usefixtures("fake_init_db")
def test_sync_unknown_error_on_jwt(cli_invoker, mock_evernote_client, fake_storage):
    mock_evernote_client.fake_auth_get_jwt_unexpected_error = True

    result = cli_invoker("sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 1
    assert "EDAMUserException" in result.output
