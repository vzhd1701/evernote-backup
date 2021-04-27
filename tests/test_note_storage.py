import pytest
from evernote.edam.type.ttypes import Note as RawNote
from evernote.edam.type.ttypes import Notebook as RawNoteBook

from evernote_backup.note_storage import Note, NoteBook, SqliteStorage, initialize_db


def test_database_file_missing():
    with pytest.raises(FileNotFoundError):
        SqliteStorage("fake_file")


def test_database_file_opened(tmp_path):
    test_db_path = str(tmp_path / "test.db")

    initialize_db(test_db_path)

    test_db = SqliteStorage(test_db_path)

    assert test_db.db


def test_init_existing_file(tmp_path):
    test_db_path = str(tmp_path / "test.db")

    initialize_db(test_db_path)

    with pytest.raises(FileExistsError):
        initialize_db(test_db_path)


def test_init_existing_file_force(tmp_path):
    test_db_path = str(tmp_path / "test.db")

    initialize_db(test_db_path)

    initialize_db(test_db_path, force=True)


def test_init_db(tmp_path):
    test_db_path = tmp_path / "test.db"

    initialize_db(str(test_db_path))

    assert test_db_path.is_file()
    assert test_db_path.stat().st_size > 0


def test_config_values(fake_storage):
    expected_val = "test_val"
    fake_storage.config.set_config_value("test", expected_val)

    test_result = fake_storage.config.get_config_value("test")

    assert test_result == expected_val


def test_config_values_missing(fake_storage):
    with pytest.raises(KeyError):
        fake_storage.config.get_config_value("test")


def test_notebooks(fake_storage):
    test_notebooks = [
        RawNoteBook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        RawNoteBook(
            guid="id2",
            name="name2",
            stack="stack2",
        ),
    ]

    expected_notebooks = [
        NoteBook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        NoteBook(
            guid="id2",
            name="name2",
            stack="stack2",
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    # Output without updated timestamp
    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result_notebooks == expected_notebooks


@pytest.mark.usefixtures("mock_formatter")
def test_notebook_note_count(fake_storage, mocker):
    expected_notebooks = [
        RawNoteBook(
            guid="notebook1",
            name="name1",
            stack="stack1",
        ),
        RawNoteBook(
            guid="notebook2",
            name="name2",
            stack="stack2",
        ),
    ]

    test_notes = [
        RawNote(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        RawNote(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=False,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    fake_storage.notebooks.add_notebooks(expected_notebooks)

    result = fake_storage.notebooks.get_notebook_notes_count("notebook1")

    assert result == 1


@pytest.mark.usefixtures("mock_formatter")
def test_notes(fake_storage, mocker):
    test_notes = [
        RawNote(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        RawNote(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        RawNote(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=False,
        ),
        RawNote(
            guid="id4",
            title="test",
            content="test",
            notebookGuid="notebook2",
            active=True,
        ),
    ]

    expected_notes = [
        Note(
            guid="id1",
            title="test",
            body="test",
            notebook_guid="notebook1",
            is_active=True,
        ),
        Note(
            guid="id2",
            title="test",
            body="test",
            notebook_guid="notebook1",
            is_active=True,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result_notes = list(fake_storage.notes.iter_notes("notebook1"))

    assert result_notes == expected_notes


@pytest.mark.usefixtures("mock_formatter")
def test_notes_trash(fake_storage, mocker):
    test_notes = [
        RawNote(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=False,
        ),
        RawNote(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook2",
            active=False,
        ),
        RawNote(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
    ]

    expected_notes = [
        Note(
            guid="id1",
            title="test",
            body="test",
            notebook_guid="notebook1",
            is_active=False,
        ),
        Note(
            guid="id2",
            title="test",
            body="test",
            notebook_guid="notebook2",
            is_active=False,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result_notes = list(fake_storage.notes.iter_notes_trash())

    assert result_notes == expected_notes


def test_get_notes_for_sync(fake_storage):
    test_notes = [
        RawNote(
            guid="id1",
            title="name1",
        ),
        RawNote(
            guid="id2",
            title="name2",
        ),
        RawNote(
            guid="id3",
            title="name3",
        ),
    ]

    fake_storage.notes.add_notes_for_sync(test_notes)

    expected = tuple((n.guid, n.title) for n in test_notes)
    result = fake_storage.notes.get_notes_for_sync()

    assert expected == result


def test_notebook_deleted(fake_storage):
    test_notebooks = [
        RawNoteBook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        RawNoteBook(
            guid="id2",
            name="name2",
            stack="stack2",
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    fake_storage.notebooks.expunge_notebooks(["id2"])

    result = list(fake_storage.notebooks.iter_notebooks())

    assert len(result) == 1
    assert result[0].guid == "id1"


@pytest.mark.usefixtures("mock_formatter")
def test_note_deleted(fake_storage, mocker):
    test_notes = [
        RawNote(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        RawNote(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    fake_storage.notes.expunge_notes(["id2"])

    result = list(fake_storage.notes.iter_notes("notebook1"))

    assert len(result) == 1
    assert result[0].guid == "id1"


@pytest.mark.usefixtures("mock_formatter")
def test_note_count(fake_storage):
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
            active=False,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = fake_storage.notes.get_notes_count()

    assert result == 2


@pytest.mark.usefixtures("mock_formatter")
def test_trash_notes_count(fake_storage):
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
            active=False,
        ),
        RawNote(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="test",
            active=False,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = fake_storage.notes.get_notes_count(is_active=False)

    assert result == 2
