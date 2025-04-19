from pathlib import Path

import pytest
from evernote.edam.type.ttypes import Note, Notebook


@pytest.mark.usefixtures("fake_init_db")
def test_manage_check_empty_db(cli_invoker, fake_storage):
    result = cli_invoker("manage", "check", "--database", "fake_db")

    assert result.exit_code == 1
    assert "Database is empty" in result.output


@pytest.mark.usefixtures("mock_evernote_client")
def test_manage_check_corrupt_file(tmp_path, cli_invoker, fake_token):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    result = cli_invoker(
        "init-db", "--database", test_db_path, "--token", fake_token, "--force"
    )

    assert result.exit_code == 0
    assert test_db_path.stat().st_size > 0

    with test_db_path.open("r+b") as f:
        f.seek(4096)
        f.write(b"1")

    result = cli_invoker("manage", "check", "--database", test_db_path)

    assert result.exit_code == 1
    assert "database disk image is malformed" in result.output
    assert "Database integrity check failed" in result.output


@pytest.mark.usefixtures("mock_evernote_client")
def test_manage_check_corrupt_file_integrity(tmp_path, cli_invoker, fake_token):
    test_db_path = tmp_path / "test.db"
    Path.touch(test_db_path)

    result = cli_invoker(
        "init-db", "--database", test_db_path, "--token", fake_token, "--force"
    )

    assert result.exit_code == 0
    assert test_db_path.stat().st_size > 0

    with test_db_path.open("r+b") as f:
        f.seek(4100)
        f.write(b"\xff\xff\xff\xff")

    result = cli_invoker("manage", "check", "--database", test_db_path)

    assert result.exit_code == 1
    assert "Database integrity check failed" in result.output
    assert "free space corruption" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_check(cli_invoker, fake_storage):
    test_notebooks = [Notebook(guid="nbid1", name="name1")]

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
            notebookGuid="nbid1",
            active=False,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    result = cli_invoker("manage", "check", "--database", "fake_db")

    assert result.exit_code == 0
    assert "Checked notes: 2" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_check_corrupt(cli_invoker, fake_storage):
    test_notebooks = [Notebook(guid="nbid1", name="name1")]

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
            notebookGuid="nbid1",
            active=False,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    with fake_storage.db as con:
        con.execute("UPDATE notes SET raw_note=? WHERE guid=?", (b"123", "id2"))

    result = cli_invoker("-v", "manage", "check", "--database", "fake_db")

    result_notes_for_sync = fake_storage.notes.get_notes_for_sync()

    assert result.exit_code == 0
    assert len(result_notes_for_sync) == 0
    assert "Checked notes: 2" in result.output
    assert "Note 'test' [id2] is corrupt" in result.output


@pytest.mark.usefixtures("fake_init_db")
def test_manage_check_corrupt_mark(cli_invoker, fake_storage):
    test_notebooks = [Notebook(guid="nbid1", name="name1")]

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
            notebookGuid="nbid1",
            active=False,
        ),
    ]

    fake_storage.notebooks.add_notebooks(test_notebooks)

    for note in test_notes:
        fake_storage.notes.add_note(note)

    with fake_storage.db as con:
        con.execute("UPDATE notes SET raw_note=? WHERE guid=?", (b"123", "id2"))

    result = cli_invoker(
        "-v", "manage", "check", "--database", "fake_db", "--mark-corrupted"
    )

    result_notes_for_sync = fake_storage.notes.get_notes_for_sync()

    assert result.exit_code == 0
    assert len(result_notes_for_sync) == 1
    assert result_notes_for_sync[0].guid == "id2"
    assert "Checked notes: 2" in result.output
    assert "Note 'test' [id2] is corrupt" in result.output
    assert "Marking 'test' [id2] note for re-download" in result.output
