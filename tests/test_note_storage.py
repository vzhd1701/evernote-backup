from pathlib import Path

import pytest
from evernote.edam.type.ttypes import LinkedNotebook, Note, Notebook

from evernote_backup.note_storage import NoteForSync, SqliteStorage, initialize_db


def test_database_file_missing():
    with pytest.raises(FileNotFoundError):
        SqliteStorage(Path("fake_file"))


def test_database_file_opened(tmp_path):
    test_db_path = tmp_path / "test.db"

    initialize_db(test_db_path)

    test_db = SqliteStorage(test_db_path)

    assert test_db.db


def test_init_existing_file(tmp_path):
    test_db_path = tmp_path / "test.db"

    initialize_db(test_db_path)

    with pytest.raises(FileExistsError):
        initialize_db(test_db_path)


def test_init_db(tmp_path):
    test_db_path = tmp_path / "test.db"

    initialize_db(test_db_path)

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
        Notebook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        Notebook(
            guid="id2",
            name="name2",
            stack="stack2",
        ),
    ]

    expected_notebooks = [
        Notebook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        Notebook(
            guid="id2",
            name="name2",
            stack="stack2",
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    # Output without updated timestamp
    result_notebooks = list(fake_storage.notebooks.iter_notebooks())

    assert result_notebooks == expected_notebooks


def test_linked_notebook(fake_storage):
    test_notebooks = [
        Notebook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        Notebook(
            guid="id2",
            name="name2",
            stack="stack2",
        ),
    ]

    test_l_notebook = LinkedNotebook(guid="id3")

    expected_notebook = test_notebooks[0]

    fake_storage.notebooks.add_notebooks(test_notebooks)
    fake_storage.notebooks.add_linked_notebook(test_l_notebook, test_notebooks[0])

    result_notebook = fake_storage.notebooks.get_notebook_by_linked_guid(
        test_l_notebook.guid
    )

    assert result_notebook == expected_notebook


def test_linked_notebook_asn(fake_storage):
    test_notebook = Notebook(guid="id1", name="name1", stack="stack1")
    test_l_notebook = LinkedNotebook(guid="id3")

    fake_storage.notebooks.add_notebooks([test_notebook])
    fake_storage.notebooks.add_linked_notebook(test_l_notebook, test_notebook)

    fake_storage.notebooks.set_linked_notebook_usn(test_l_notebook.guid, 100)

    result = fake_storage.notebooks.get_linked_notebook_usn(test_l_notebook.guid)

    assert result == 100


def test_missing_linked_notebook_asn(fake_storage):
    result = fake_storage.notebooks.get_linked_notebook_usn("fake_id")

    assert result == 0


def test_linked_notebook_deleted(fake_storage):
    test_notebook = Notebook(guid="id1", name="name1", stack="stack1")
    test_l_notebook = LinkedNotebook(guid="id3")

    fake_storage.notebooks.add_notebooks([test_notebook])
    fake_storage.notebooks.add_linked_notebook(test_l_notebook, test_notebook)

    fake_storage.notebooks.expunge_linked_notebooks([test_l_notebook.guid])

    with pytest.raises(ValueError):
        fake_storage.notebooks.get_notebook_by_linked_guid(test_l_notebook.guid)


def test_notebook_note_count(fake_storage):
    expected_notebooks = [
        Notebook(
            guid="notebook1",
            name="name1",
            stack="stack1",
        ),
        Notebook(
            guid="notebook2",
            name="name2",
            stack="stack2",
        ),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
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


def test_notes(fake_storage):
    test_notes = [
        Note(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=False,
        ),
        Note(
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
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result_notes = list(fake_storage.notes.iter_notes("notebook1"))

    assert result_notes == expected_notes


def test_notes_order(fake_storage):
    test_notes = [
        Note(
            guid="id5",
            title="test5",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id4",
            title="test4",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test1",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id1",
            title="test2",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
    ]

    expected_notes_titles_order = ["test1", "test2", "test4", "test5"]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result_notes_titles_order = list(
        n.title for n in fake_storage.notes.iter_notes("notebook1")
    )

    assert result_notes_titles_order == expected_notes_titles_order


def test_notes_trash(fake_storage):
    test_notes = [
        Note(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=False,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook2",
            active=False,
        ),
        Note(
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
            content="test",
            notebookGuid="notebook1",
            active=False,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook2",
            active=False,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result_notes = list(fake_storage.notes.iter_notes_trash())

    assert result_notes == expected_notes


def test_get_notes_for_sync(fake_storage):
    test_notes = [
        Note(
            guid="id1",
            title="name1",
        ),
        Note(
            guid="id2",
            title="name2",
        ),
        Note(
            guid="id3",
            title="name3",
        ),
    ]

    fake_storage.notes.add_notes_for_sync(test_notes)

    expected = tuple(
        NoteForSync(guid=n.guid, title=n.title, linked_notebook_guid=None)
        for n in test_notes
    )
    result = fake_storage.notes.get_notes_for_sync()

    assert expected == result


def test_notebook_deleted(fake_storage):
    test_notebooks = [
        Notebook(
            guid="id1",
            name="name1",
            stack="stack1",
        ),
        Notebook(
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


def test_note_deleted(fake_storage):
    test_notes = [
        Note(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
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


def test_note_deleted_by_notebook(fake_storage):
    test_notes = [
        Note(
            guid="id1",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id3",
            title="test",
            content="test",
            notebookGuid="notebook2",
            active=True,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    fake_storage.notes.expunge_notes_by_notebook("notebook1")

    result1 = list(fake_storage.notes.iter_notes("notebook1"))
    result2 = list(fake_storage.notes.iter_notes("notebook2"))

    assert len(result1) == 0
    assert len(result2) == 1
    assert result2[0].guid == "id3"


def test_note_count(fake_storage):
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
            active=False,
        ),
    ]

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = fake_storage.notes.get_notes_count()

    assert result == 2


def test_trash_notes_count(fake_storage):
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
            active=False,
        ),
        Note(
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
