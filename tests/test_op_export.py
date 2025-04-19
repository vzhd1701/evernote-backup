import pytest
from evernote.edam.type.ttypes import Note, Notebook

from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.evernote_types import Reminder, Task


@pytest.mark.usefixtures("fake_init_db")
def test_export_empty_db(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    result = cli_invoker("export", "--database", "fake_db", str(test_out_path))

    assert result.exit_code == 1
    assert "Database is empty" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_export_old_db(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.config.set_config_value("DB_VERSION", "0")

    result = cli_invoker("export", "--database", "fake_db", str(test_out_path))

    assert result.exit_code == 1
    assert "Full resync is required" in result.output
    assert fake_storage.config.get_config_value("DB_VERSION") == str(CURRENT_DB_VERSION)


@pytest.mark.usefixtures("fake_init_db")
def test_export_old_db_first(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    with fake_storage.db as con:
        con.execute("DELETE FROM config WHERE name=?", ("DB_VERSION",))

    result = cli_invoker("export", "--database", "fake_db", str(test_out_path))

    assert result.exit_code == 1
    assert "Full resync is required" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_export(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
        Notebook(guid="nbid3", name="name3", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker("export", "--database", "fake_db", str(test_out_path))

    book1_path = test_out_path / "stack1" / "name1.enex"
    book2_path = test_out_path / "name2.enex"

    assert result.exit_code == 0
    assert book1_path.is_file()
    assert book2_path.is_file()


@pytest.mark.usefixtures("fake_init_db")
def test_export_notebook(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
        Notebook(guid="nbid3", name="name3", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="title2",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
        Note(
            guid="id3",
            title="title3",
            content="test",
            notebookGuid="nbid3",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--notebook",
        "name1",
        "--notebook",
        "name2",
        str(test_out_path),
    )

    book1_path = test_out_path / "stack1" / "name1.enex"
    book2_path = test_out_path / "name2.enex"
    book3_path = test_out_path / "name3.enex"

    assert result.exit_code == 0
    assert book1_path.is_file()
    assert book2_path.is_file()
    assert not book3_path.exists()


@pytest.mark.usefixtures("fake_init_db")
def test_export_notebook_not_found(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
        Notebook(guid="nbid3", name="name3", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker(
        "export", "--database", "fake_db", "--notebook", "name4", str(test_out_path)
    )

    book1_path = test_out_path / "stack1" / "name1.enex"
    book2_path = test_out_path / "name2.enex"

    assert result.exit_code == 0
    assert "Notebook 'name4' not found in database" in result.output
    assert not test_out_path.exists()
    assert not book1_path.exists()
    assert not book2_path.exists()


@pytest.mark.usefixtures("fake_init_db")
def test_export_tag(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1"),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="title2",
            content="test",
            notebookGuid="nbid1",
            active=True,
            tagNames=["tag1"],
        ),
        Note(
            guid="id3",
            title="title3",
            content="test",
            notebookGuid="nbid1",
            active=True,
            tagNames=["tag2"],
        ),
        Note(
            guid="id4",
            title="title4",
            content="test",
            notebookGuid="nbid1",
            active=True,
            tagNames=["tag3"],
        ),
        Note(
            guid="id5",
            title="title5",
            content="test",
            notebookGuid="nbid1",
            active=False,
            tagNames=["tag1"],
        ),
        Note(
            guid="id6",
            title="title6",
            content="test",
            notebookGuid="nbid1",
            active=False,
            tagNames=["tag4"],
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--tag",
        "tag1",
        "--tag",
        "tag2",
        "--single-notes",
        str(test_out_path),
    )

    note1_path = test_out_path / "name1" / "title1.enex"
    note2_path = test_out_path / "name1" / "title2.enex"
    note3_path = test_out_path / "name1" / "title3.enex"
    note4_path = test_out_path / "name1" / "title4.enex"
    note5_path = test_out_path / "Trash" / "title5.enex"
    note6_path = test_out_path / "Trash" / "title6.enex"

    assert result.exit_code == 0
    assert not note1_path.exists()
    assert note2_path.is_file()
    assert note3_path.is_file()
    assert not note4_path.exists()
    assert not note5_path.exists()
    assert not note6_path.exists()


@pytest.mark.usefixtures("fake_init_db")
def test_export_tag_with_trash(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1"),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="title2",
            content="test",
            notebookGuid="nbid1",
            active=True,
            tagNames=["tag1"],
        ),
        Note(
            guid="id3",
            title="title3",
            content="test",
            notebookGuid="nbid1",
            active=True,
            tagNames=["tag2"],
        ),
        Note(
            guid="id4",
            title="title4",
            content="test",
            notebookGuid="nbid1",
            active=True,
            tagNames=["tag3"],
        ),
        Note(
            guid="id5",
            title="title5",
            content="test",
            notebookGuid="nbid1",
            active=False,
            tagNames=["tag1"],
        ),
        Note(
            guid="id6",
            title="title6",
            content="test",
            notebookGuid="nbid1",
            active=False,
            tagNames=["tag4"],
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--tag",
        "tag1",
        "--tag",
        "tag2",
        "--single-notes",
        "--include-trash",
        str(test_out_path),
    )

    note1_path = test_out_path / "name1" / "title1.enex"
    note2_path = test_out_path / "name1" / "title2.enex"
    note3_path = test_out_path / "name1" / "title3.enex"
    note4_path = test_out_path / "name1" / "title4.enex"
    note5_path = test_out_path / "Trash" / "title5.enex"
    note6_path = test_out_path / "Trash" / "title6.enex"

    assert result.exit_code == 0
    assert not note1_path.exists()
    assert note2_path.is_file()
    assert note3_path.is_file()
    assert not note4_path.exists()
    assert note5_path.is_file()
    assert not note6_path.exists()


@pytest.mark.usefixtures("fake_init_db")
def test_export_over_existing(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
        Notebook(guid="nbid3", name="name3", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    book1_existing_path = test_out_path / "stack1" / "name1.enex"
    book2_existing_path = test_out_path / "name2.enex"

    book1_existing_path.parent.mkdir(parents=True, exist_ok=True)
    book2_existing_path.parent.mkdir(parents=True, exist_ok=True)

    book1_existing_path.touch()
    book2_existing_path.touch()

    book1_expected_path = test_out_path / "stack1" / "name1 (1).enex"
    book2_expected_path = test_out_path / "name2 (1).enex"

    result = cli_invoker("export", "--database", "fake_db", str(test_out_path))

    assert result.exit_code == 0
    assert book1_expected_path.is_file()
    assert book2_expected_path.is_file()


@pytest.mark.usefixtures("fake_init_db")
def test_export_over_existing_overwrite(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
        Notebook(guid="nbid3", name="name3", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="test",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    book1_existing_path = test_out_path / "stack1" / "name1.enex"
    book2_existing_path = test_out_path / "name2.enex"

    book1_existing_path.parent.mkdir(parents=True, exist_ok=True)
    book2_existing_path.parent.mkdir(parents=True, exist_ok=True)

    book1_existing_path.touch()
    book2_existing_path.touch()

    result = cli_invoker(
        "export", "--database", "fake_db", "--overwrite", str(test_out_path)
    )

    assert result.exit_code == 0
    assert book1_existing_path.stat().st_size > 0
    assert book2_existing_path.stat().st_size > 0


@pytest.mark.usefixtures("fake_init_db")
def test_export_single_notes(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="title2",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker(
        "export", "--database", "fake_db", "--single-notes", str(test_out_path)
    )

    book1_path = test_out_path / "stack1" / "name1" / "title1.enex"
    book2_path = test_out_path / "name2" / "title2.enex"

    assert result.exit_code == 0
    assert book1_path.is_file()
    assert book2_path.is_file()


@pytest.mark.usefixtures("fake_init_db")
def test_export_single_notes_over_existing(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="title2",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    book1_existing_path = test_out_path / "stack1" / "name1" / "title1.enex"
    book2_existing_path = test_out_path / "name2" / "title2.enex"

    book1_existing_path.parent.mkdir(parents=True, exist_ok=True)
    book2_existing_path.parent.mkdir(parents=True, exist_ok=True)

    book1_existing_path.touch()
    book2_existing_path.touch()

    book1_expected_path = test_out_path / "stack1" / "name1" / "title1 (1).enex"
    book2_expected_path = test_out_path / "name2" / "title2 (1).enex"

    result = cli_invoker(
        "export", "--database", "fake_db", "--single-notes", str(test_out_path)
    )

    assert result.exit_code == 0
    assert book1_expected_path.is_file()
    assert book2_expected_path.is_file()


@pytest.mark.usefixtures("fake_init_db")
def test_export_single_notes_over_existing_overwrite(
    cli_invoker, fake_storage, tmp_path
):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack="stack1"),
        Notebook(guid="nbid2", name="name2", stack=None),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="title2",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    book1_existing_path = test_out_path / "stack1" / "name1" / "title1.enex"
    book2_existing_path = test_out_path / "name2" / "title2.enex"

    book1_existing_path.parent.mkdir(parents=True, exist_ok=True)
    book2_existing_path.parent.mkdir(parents=True, exist_ok=True)

    book1_existing_path.touch()
    book2_existing_path.touch()

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--single-notes",
        "--overwrite",
        str(test_out_path),
    )

    assert result.exit_code == 0
    assert book1_existing_path.stat().st_size > 0
    assert book2_existing_path.stat().st_size > 0


@pytest.mark.usefixtures("fake_init_db")
def test_export_single_notes_super_long_name(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_long_title = "😁" * 300
    expected_note_name = f"{'😁' * 62}.enex"

    test_notebooks = [Notebook(guid="nbid1", name="name1", stack=None)]

    test_notes = [
        Note(
            guid="id1",
            title=test_long_title,
            content="test",
            notebookGuid="nbid1",
            active=True,
        )
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker(
        "export", "--database", "fake_db", "--single-notes", str(test_out_path)
    )

    note_path = test_out_path / "name1" / expected_note_name

    assert result.exit_code == 0
    assert note_path.is_file()


@pytest.mark.usefixtures("fake_init_db")
def test_export_no_trash(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=False,
        )
    )

    result = cli_invoker("export", "--database", "fake_db", str(test_out_path))

    assert result.exit_code == 0
    assert not test_out_path.exists()


@pytest.mark.usefixtures("fake_init_db")
def test_export_yes_trash(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=False,
        )
    )

    result = cli_invoker(
        "export", "--database", "fake_db", "--include-trash", str(test_out_path)
    )

    book1_path = test_out_path / "Trash.enex"

    assert result.exit_code == 0
    assert book1_path.is_file()


@pytest.mark.usefixtures("fake_init_db")
def test_export_yes_trash_single_notes(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=False,
        )
    )

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--include-trash",
        "--single-notes",
        str(test_out_path),
    )

    book1_path = test_out_path / "Trash" / "title1.enex"

    assert result.exit_code == 0
    assert book1_path.is_file()


@pytest.mark.usefixtures("fake_init_db")
def test_export_yes_export_date(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack=None),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        )
    )

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        str(test_out_path),
    )

    book1_path = test_out_path / "name1.enex"

    book1_xml = book1_path.read_text()

    assert result.exit_code == 0
    assert "export-date" in book1_xml


@pytest.mark.usefixtures("fake_init_db")
def test_export_no_export_date(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack=None),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        )
    )

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--no-export-date",
        str(test_out_path),
    )

    book1_path = test_out_path / "name1.enex"

    book1_xml = book1_path.read_text()

    assert result.exit_code == 0
    assert "export-date" not in book1_xml


@pytest.mark.usefixtures("fake_init_db")
def test_export_add_guid(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack=None),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        )
    )

    result = cli_invoker(
        "export",
        "--add-guid",
        "--database",
        "fake_db",
        str(test_out_path),
    )

    book1_path = test_out_path / "name1.enex"

    book1_xml = book1_path.read_text()

    assert result.exit_code == 0
    assert "<guid>id1</guid>" in book1_xml


@pytest.mark.usefixtures("fake_init_db")
def test_export_add_metadata(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack=None),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        )
    )

    result = cli_invoker(
        "export",
        "--add-metadata",
        "--database",
        "fake_db",
        str(test_out_path),
    )

    book1_path = test_out_path / "name1.enex"

    book1_xml = book1_path.read_text()

    assert result.exit_code == 0
    assert "<guid>id1</guid>" in book1_xml
    assert "<notebook-guid>nbid1</notebook-guid>" in book1_xml


@pytest.mark.usefixtures("fake_init_db")
def test_export_note_with_tasks(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        Notebook(guid="nbid1", name="name1", stack=None),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    fake_storage.notes.add_note(
        Note(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        )
    )

    fake_storage.tasks.add_tasks(
        [
            Task(taskId="tid1", parentId="id1", label="test task1", sortWeight="Z"),
            Task(taskId="tid2", parentId="id1", label="test task2", sortWeight="A"),
        ]
    )

    fake_storage.reminders.add_reminder(
        Reminder(
            reminderId="rid1",
            sourceId="tid1",
            reminderDate=1744552247000,
        )
    )

    result = cli_invoker(
        "export",
        "--database",
        "fake_db",
        str(test_out_path),
    )

    expected_tasks_xml = """
    <task>
      <title>test task2</title>
      <sortWeight>A</sortWeight>
    </task>
    <task>
      <title>test task1</title>
      <sortWeight>Z</sortWeight>
      <reminder>
        <reminderDate>20250413T135047Z</reminderDate>
      </reminder>
    </task>"""

    book1_path = test_out_path / "name1.enex"

    book1_xml = book1_path.read_text()

    assert result.exit_code == 0
    assert expected_tasks_xml in book1_xml
