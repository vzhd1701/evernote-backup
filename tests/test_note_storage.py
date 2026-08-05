import logging
from pathlib import Path

import pytest
from evernote.edam.type.ttypes import LinkedNotebook, Note, Notebook

from evernote_backup.config import (
    CURRENT_DB_VERSION,
    SHARED_WITH_ME_NOTEBOOK_GUID,
    SHARED_WITH_ME_NOTEBOOK_NAME,
)
from evernote_backup.evernote_types import Reminder, Task
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


def test_config_list_values(fake_storage):
    assert fake_storage.config.get_config_list("missing") == []

    fake_storage.config.set_config_list("items", ["a", "b", "a", "  ", ""])
    assert fake_storage.config.get_config_list("items") == ["a", "b"]

    fake_storage.config.set_config_list("items", [])
    assert fake_storage.config.get_config_list("items") == []


def test_blacklist_config(fake_storage):
    assert fake_storage.config.get_blacklist_notes() == []
    assert fake_storage.config.get_blacklist_notebooks() == []

    fake_storage.config.set_blacklist_notes(["n1", "n2"])
    fake_storage.config.set_blacklist_notebooks(["nb1"])

    assert fake_storage.config.get_blacklist_notes() == ["n1", "n2"]
    assert fake_storage.config.get_blacklist_notebooks() == ["nb1"]


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

    result_notes_titles_order = [
        n.title for n in fake_storage.notes.iter_notes("notebook1")
    ]

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


def test_notes_corrupt(fake_storage, caplog):
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

    with fake_storage.db as con:
        con.execute("UPDATE notes SET raw_note=? WHERE guid=?", (b"123", "id3"))

    with caplog.at_level(logging.DEBUG, logger="evernote_backup"):
        result_notes = list(fake_storage.notes.iter_notes("notebook1"))

    result_notes_for_sync = fake_storage.notes.get_notes_for_sync()

    assert result_notes == expected_notes
    assert len(result_notes_for_sync) == 0
    assert "Traceback" in caplog.text
    assert "Note 'test' [id3] is corrupt" in caplog.text


def test_task_corrupt(fake_storage, caplog):
    test_tasks = [
        Task(
            taskId="id1",
            parentId="nid1",
        ),
        Task(
            taskId="id2",
            parentId="nid1",
        ),
        Task(
            taskId="id3",
            parentId="nid1",
        ),
    ]

    expected_tasks = [
        Task(
            taskId="id1",
            parentId="nid1",
        ),
        Task(
            taskId="id2",
            parentId="nid1",
        ),
    ]

    fake_storage.tasks.add_tasks(test_tasks)

    with fake_storage.db as con:
        con.execute("UPDATE tasks SET raw_task=? WHERE guid=?", (b"123", "id3"))

    with caplog.at_level(logging.DEBUG, logger="evernote_backup"):
        result_tasks = list(fake_storage.tasks.iter_tasks("nid1"))

    assert result_tasks == expected_tasks
    assert "Traceback" in caplog.text
    assert "Task [id3] is corrupt" in caplog.text


def test_reminder_corrupt(fake_storage, caplog):
    test_reminders = [
        Reminder(
            reminderId="id1",
            sourceId="tid1",
        ),
        Reminder(
            reminderId="id2",
            sourceId="tid1",
        ),
        Reminder(
            reminderId="id3",
            sourceId="tid1",
        ),
    ]

    expected_reminders = [
        Reminder(
            reminderId="id1",
            sourceId="tid1",
        ),
        Reminder(
            reminderId="id2",
            sourceId="tid1",
        ),
    ]

    fake_storage.reminders.add_reminders(test_reminders)

    with fake_storage.db as con:
        con.execute("UPDATE reminders SET raw_reminder=? WHERE guid=?", (b"123", "id3"))

    with caplog.at_level(logging.DEBUG, logger="evernote_backup"):
        result_reminders = list(fake_storage.reminders.iter_reminders("tid1"))

    assert result_reminders == expected_reminders
    assert "Traceback" in caplog.text
    assert "Reminder [id3] is corrupt" in caplog.text


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
        NoteForSync(
            guid=n.guid,
            title=n.title,
            notebook_guid=n.notebookGuid,
            linked_notebook_guid=None,
            shard_id=None,
        )
        for n in test_notes
    )
    result = fake_storage.notes.get_notes_for_sync()

    assert expected == result


def test_get_notes_for_export_with_incomplete_sync(fake_storage):
    test_notes_for_sync = [
        Note(
            guid="id1",
            title="name1",
            content="test",
            notebookGuid="notebook1",
        ),
        Note(
            guid="id2",
            title="name2",
            content="test",
            notebookGuid="notebook1",
        ),
        Note(
            guid="id3",
            title="name3",
            content="test",
            notebookGuid="notebook1",
        ),
    ]

    expected_notes = [
        Note(
            guid="id4",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
        Note(
            guid="id5",
            title="test",
            content="test",
            notebookGuid="notebook1",
            active=True,
        ),
    ]

    fake_storage.notes.add_notes_for_sync(test_notes_for_sync)

    for note in expected_notes:
        fake_storage.notes.add_note(note)

    result_notes = list(fake_storage.notes.iter_notes("notebook1"))

    assert len(result_notes) == 2
    assert result_notes == expected_notes


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

    deleted = fake_storage.notes.expunge_notes_by_notebook("notebook1")

    result1 = list(fake_storage.notes.iter_notes("notebook1"))
    result2 = list(fake_storage.notes.iter_notes("notebook2"))

    assert set(deleted) == {"id1", "id2"}
    assert len(result1) == 0
    assert len(result2) == 1
    assert result2[0].guid == "id3"


def test_expunge_notes_by_notebook_exclude(fake_storage):
    for guid in ("keep", "drop"):
        fake_storage.notes.add_note(
            Note(
                guid=guid,
                title=guid,
                content="x",
                notebookGuid="nb1",
                active=True,
            )
        )

    deleted = fake_storage.notes.expunge_notes_by_notebook(
        "nb1", exclude_guids=["keep"]
    )

    assert deleted == ["drop"]
    assert fake_storage.notes.note_exists("keep")
    assert not fake_storage.notes.note_exists("drop")


def test_shared_notes_storage_crud(fake_storage):
    fake_storage.shared_notes.add_shared_note("n1", "s532", owner_id=99)
    fake_storage.shared_notes.add_shared_note("n2", "s100", owner_id=100)

    assert fake_storage.shared_notes.is_shared_note("n1")
    assert fake_storage.shared_notes.get_shard_id("n1") == "s532"
    assert fake_storage.shared_notes.get_shard_id("missing") is None
    assert fake_storage.shared_notes.get_shared_note_guids() == {"n1", "n2"}

    fake_storage.shared_notes.remove_shared_notes(["n1"])
    assert not fake_storage.shared_notes.is_shared_note("n1")
    assert fake_storage.shared_notes.is_shared_note("n2")


def test_get_notes_for_sync_includes_shard_id(fake_storage):
    fake_storage.notes.add_notes_for_sync(
        [Note(guid="shared1", title="s", notebookGuid="nb")]
    )
    fake_storage.shared_notes.add_shared_note("shared1", "s532", owner_id=1)

    result = fake_storage.notes.get_notes_for_sync()

    assert len(result) == 1
    assert result[0].guid == "shared1"
    assert result[0].shard_id == "s532"
    assert result[0].linked_notebook_guid is None


def test_is_note_in_linked_notebook(fake_storage):
    nb = Notebook(guid="nb-linked", name="LN")
    fake_storage.notebooks.add_notebooks([nb])
    fake_storage.notebooks.add_linked_notebook(LinkedNotebook(guid="ln1"), nb)
    fake_storage.notes.add_note(
        Note(guid="n1", title="t", content="c", notebookGuid="nb-linked", active=True)
    )
    fake_storage.notes.add_note(
        Note(
            guid="n2",
            title="t2",
            content="c",
            notebookGuid=SHARED_WITH_ME_NOTEBOOK_GUID,
            active=True,
        )
    )

    assert fake_storage.notes.is_note_in_linked_notebook("n1") is True
    assert fake_storage.notes.is_note_in_linked_notebook("n2") is False
    assert fake_storage.notes.is_note_in_linked_notebook("missing") is False


def test_rehome_notes_from_notebook(fake_storage):
    for guid in ("a", "b", "c"):
        fake_storage.notes.add_note(
            Note(
                guid=guid,
                title=guid,
                content="x",
                notebookGuid="from-nb",
                active=True,
            )
        )

    moved = fake_storage.notes.rehome_notes_from_notebook(
        "from-nb", "to-nb", only_guids=["a", "c"]
    )

    assert set(moved) == {"a", "c"}
    assert fake_storage.notes.get_note_notebook_guid("a") == "to-nb"
    assert fake_storage.notes.get_note_notebook_guid("b") == "from-nb"
    assert fake_storage.notes.get_note_notebook_guid("c") == "to-nb"


def test_mark_notes_for_redownload(fake_storage):
    note = Note(
        guid="id1",
        title="t",
        content="body",
        notebookGuid="nb",
        active=True,
    )
    fake_storage.notes.add_note(note)
    assert fake_storage.notes.get_notes_for_sync() == ()

    fake_storage.notes.mark_notes_for_redownload(["id1"])

    pending = fake_storage.notes.get_notes_for_sync()
    assert len(pending) == 1
    assert pending[0].guid == "id1"


def test_note_exists_and_get_notebook_guid(fake_storage):
    assert fake_storage.notes.note_exists("x") is False
    assert fake_storage.notes.get_note_notebook_guid("x") is None

    fake_storage.notes.add_note(
        Note(guid="x", title="t", content="c", notebookGuid="nb", active=True)
    )

    assert fake_storage.notes.note_exists("x") is True
    assert fake_storage.notes.get_note_notebook_guid("x") == "nb"


def test_ensure_shared_with_me_notebook(fake_storage):
    fake_storage.notebooks.ensure_shared_with_me_notebook()

    names = {nb.guid: nb.name for nb in fake_storage.notebooks.iter_notebooks()}
    assert names[SHARED_WITH_ME_NOTEBOOK_GUID] == SHARED_WITH_ME_NOTEBOOK_NAME


def test_upgrade_db_v6_to_v7_shared_notes(fake_storage):
    """Upgrade path creates shared_notes table and bootstrap cursor."""
    with fake_storage.db as con:
        con.execute("DROP TABLE IF EXISTS shared_notes")
    fake_storage.config.set_config_value("DB_VERSION", "6")

    fake_storage.check_version()

    assert fake_storage.config.get_config_value("DB_VERSION") == str(CURRENT_DB_VERSION)
    assert fake_storage.config.get_config_value("last_connection_shared_notes") == "0"

    # Table usable
    fake_storage.shared_notes.add_shared_note("n1", "s1")
    assert fake_storage.shared_notes.is_shared_note("n1")

    names = {nb.name for nb in fake_storage.notebooks.iter_notebooks()}
    assert SHARED_WITH_ME_NOTEBOOK_NAME in names


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


def test_note_count_before_sync(fake_storage):
    test_notes = [
        Note(
            guid="id1",
            title="test",
            notebookGuid="test",
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

    fake_storage.notes.add_notes_for_sync([test_notes[0]])
    fake_storage.notes.add_note(test_notes[1])
    fake_storage.notes.add_note(test_notes[2])

    result_active = fake_storage.notes.get_notes_count()
    result_trash = fake_storage.notes.get_notes_count(is_active=False)

    assert result_active == 1
    assert result_trash == 1
