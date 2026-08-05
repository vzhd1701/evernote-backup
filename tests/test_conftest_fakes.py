"""Unit tests for FakeEvernoteNoteStore helpers in conftest (esp. foreign-shard getNote)."""

import pytest
from evernote.edam.type.ttypes import Note

from evernote_backup.token_util import EvernoteToken
from tests.conftest import FakeEvernoteNoteStore, FakeEvernoteValues

HOME_TOKEN = "S=s100:U=ff:E=fff:C=ff:P=1:A=test:V=2:H=ff"
# Same user token; NoteStore constructed for a different shard
FOREIGN_SHARD = "s532"


@pytest.fixture
def note_store():
    values = FakeEvernoteValues()
    FakeEvernoteNoteStore.fake_values = values
    store = FakeEvernoteNoteStore(
        auth_token=HOME_TOKEN,
        store_url=f"https://www.evernote.com/edam/note/{FOREIGN_SHARD}",
        user_agent="test",
    )
    return store, values


def test_get_note_home_shard_from_fake_notes():
    values = FakeEvernoteValues()
    FakeEvernoteNoteStore.fake_values = values
    note = Note(guid="home1", title="t", content="c", active=True)
    values.fake_notes.append(note)

    store = FakeEvernoteNoteStore(
        auth_token=HOME_TOKEN,
        store_url="https://www.evernote.com/edam/note/s100",
        user_agent="test",
    )

    assert EvernoteToken.from_string(HOME_TOKEN).shard == store.shard
    assert store.getNote("home1", True, True, True, True) is note


def test_get_note_foreign_shard_from_fake_l_notes(note_store):
    store, values = note_store
    note = Note(guid="ln1", title="linked", content="c", active=True)
    values.fake_l_notes.append(note)

    assert store.getNote("ln1", True, True, True, True) is note


def test_get_note_foreign_shard_falls_back_to_fake_notes(note_store):
    """New path: single-note share body can live in fake_notes when not in fake_l_notes."""
    store, values = note_store
    note = Note(guid="shared1", title="shared", content="c", active=True)
    values.fake_notes.append(note)

    assert store.getNote("shared1", True, True, True, True) is note


def test_get_note_foreign_shard_prefers_fake_l_notes(note_store):
    store, values = note_store
    from_l = Note(guid="same", title="from l", content="c", active=True)
    from_n = Note(guid="same", title="from n", content="c", active=True)
    values.fake_l_notes.append(from_l)
    values.fake_notes.append(from_n)

    assert store.getNote("same", True, True, True, True) is from_l


def test_get_note_foreign_shard_missing_raises(note_store):
    store, _ = note_store

    with pytest.raises(StopIteration, match="not found on shard s532"):
        store.getNote("missing", True, True, True, True)
