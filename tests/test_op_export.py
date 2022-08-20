import pytest
from evernote.edam.type.ttypes import Note, Notebook

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.config import CURRENT_DB_VERSION


@pytest.mark.usefixtures("fake_init_db")
def test_export_empty_db(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("export", "--database", "fake_db", str(test_out_path))
    assert "Database is empty" in str(excinfo.value)


@pytest.mark.usefixtures("fake_init_db")
def test_export_old_db(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.config.set_config_value("DB_VERSION", "0")

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("export", "--database", "fake_db", str(test_out_path))
    assert "Full resync is required" in str(excinfo.value)
    assert fake_storage.config.get_config_value("DB_VERSION") == str(CURRENT_DB_VERSION)


@pytest.mark.usefixtures("fake_init_db")
def test_export_old_db_first(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    with fake_storage.db as con:
        con.execute("DELETE FROM config WHERE name=?", ("DB_VERSION",))

    with pytest.raises(ProgramTerminatedError) as excinfo:
        cli_invoker("export", "--database", "fake_db", str(test_out_path))
    assert "Full resync is required" in str(excinfo.value)


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

    cli_invoker("export", "--database", "fake_db", str(test_out_path))

    book1_path = test_out_path / "stack1" / "name1.enex"
    book2_path = test_out_path / "name2.enex"

    assert book1_path.is_file()
    assert book2_path.is_file()


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

    cli_invoker("export", "--database", "fake_db", str(test_out_path))

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

    cli_invoker("export", "--database", "fake_db", "--overwrite", str(test_out_path))

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

    cli_invoker("export", "--database", "fake_db", "--single-notes", str(test_out_path))

    book1_path = test_out_path / "stack1" / "name1" / "title1.enex"
    book2_path = test_out_path / "name2" / "title2.enex"

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

    cli_invoker("export", "--database", "fake_db", "--single-notes", str(test_out_path))

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

    cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--single-notes",
        "--overwrite",
        str(test_out_path),
    )

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

    cli_invoker("export", "--database", "fake_db", "--single-notes", str(test_out_path))

    note_path = test_out_path / "name1" / expected_note_name

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

    cli_invoker("export", "--database", "fake_db", str(test_out_path))

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

    cli_invoker(
        "export", "--database", "fake_db", "--include-trash", str(test_out_path)
    )

    book1_path = test_out_path / "Trash.enex"

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

    cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--include-trash",
        "--single-notes",
        str(test_out_path),
    )

    book1_path = test_out_path / "Trash" / "title1.enex"

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

    cli_invoker(
        "export",
        "--database",
        "fake_db",
        str(test_out_path),
    )

    book1_path = test_out_path / "name1.enex"

    with open(book1_path, "r") as f:
        book1_xml = f.read()

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

    cli_invoker(
        "export",
        "--database",
        "fake_db",
        "--no-export-date",
        str(test_out_path),
    )

    book1_path = test_out_path / "name1.enex"

    with open(book1_path, "r") as f:
        book1_xml = f.read()

    assert "export-date" not in book1_xml
