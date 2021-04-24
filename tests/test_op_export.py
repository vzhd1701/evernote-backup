import pytest
from evernote.edam.type.ttypes import Note as RawNote
from evernote.edam.type.ttypes import Notebook as RawNoteBook

from evernote_backup.cli_app_util import ProgramTerminatedError
from tests.utils import cli_invoker, fake_storage, mock_evernote_client, mock_formatter


def test_export_empty_db(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    with pytest.raises(ProgramTerminatedError):
        cli_invoker("export", "--database", "fake_db", str(test_out_path))


@pytest.mark.usefixtures("mock_formatter")
def test_export(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        RawNoteBook(guid="nbid1", name="name1", stack="stack1"),
        RawNoteBook(guid="nbid2", name="name2", stack=None),
        RawNoteBook(guid="nbid3", name="name3", stack=None),
    ]

    test_notes = [
        RawNote(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        RawNote(
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


@pytest.mark.usefixtures("mock_formatter")
def test_export_single_notes(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    test_notebooks = [
        RawNoteBook(guid="nbid1", name="name1", stack="stack1"),
        RawNoteBook(guid="nbid2", name="name2", stack=None),
    ]

    test_notes = [
        RawNote(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        RawNote(
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


@pytest.mark.usefixtures("mock_formatter")
def test_export_no_trash(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.notes.add_note(
        RawNote(
            guid="id1",
            title="title1",
            content="test",
            notebookGuid="nbid1",
            active=False,
        )
    )

    cli_invoker("export", "--database", "fake_db", str(test_out_path))

    assert not test_out_path.exists()


@pytest.mark.usefixtures("mock_formatter")
def test_export_yes_trash(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.notes.add_note(
        RawNote(
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


@pytest.mark.usefixtures("mock_formatter")
def test_export_yes_trash_single_notes(cli_invoker, fake_storage, tmp_path):
    test_out_path = tmp_path / "test_out"

    fake_storage.notes.add_note(
        RawNote(
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
