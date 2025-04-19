import pytest
from evernote.edam.type.ttypes import Note, Notebook


@pytest.mark.usefixtures("fake_init_db")
def test_manage_list_notebooks(cli_invoker, fake_storage):
    test_notebooks = [
        Notebook(guid="nbid1", name="Name1"),
        Notebook(guid="nbid2", name="Name2"),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    result = cli_invoker("manage", "list")

    assert result.exit_code == 0
    assert "Name1" in result.output
    assert "Name2" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_list_notebooks_with_notes(cli_invoker, fake_storage):
    test_notebooks = [
        Notebook(guid="nbid1", name="Name1"),
        Notebook(guid="nbid2", name="Name2"),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="Title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="Title2",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
        Note(
            guid="id3",
            title="Title3",
            content="test",
            notebookGuid="nbid2",
            active=False,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker("manage", "list", "--all")

    assert result.exit_code == 0
    assert "Name1" in result.output
    assert "Name2" in result.output
    assert "Trash" in result.output
    assert "Title1" in result.output
    assert "Title2" in result.output
    assert "Title3" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_list_single_notebook(cli_invoker, fake_storage):
    test_notebooks = [
        Notebook(guid="nbid1", name="Name1"),
        Notebook(guid="nbid2", name="Name2"),
    ]

    test_notes = [
        Note(
            guid="id1",
            title="Title1",
            content="test",
            notebookGuid="nbid1",
            active=True,
        ),
        Note(
            guid="id2",
            title="Title2",
            content="test",
            notebookGuid="nbid2",
            active=True,
        ),
        Note(
            guid="id3",
            title="Title3",
            content="test",
            notebookGuid="nbid1",
            active=False,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker("manage", "list", "--notebook", "Name1")

    assert result.exit_code == 0
    assert "Name1" in result.output
    assert "Name2" not in result.output
    assert "Title1" in result.output
    assert "Title2" not in result.output
    assert "Title3" not in result.output
