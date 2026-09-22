"""Memory benchmarks for the export path.

Everything here except the equivalence tests is marked `slow` and deselected by
default, since the fixtures build multi-gigabyte notes. Run them with:

    just bench

Peaks are measured with `tracemalloc` rather than RSS. RSS depends on how the
allocator hands arenas back to the OS and is far too noisy to assert on;
tracemalloc counts the allocations themselves and is reproducible across
platforms.
"""

import io
import lzma
import os
import pickle
import sqlite3
import tracemalloc
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
from evernote.edam.type.ttypes import (
    Data,
    Note,
    NoteAttributes,
    Resource,
    ResourceAttributes,
)

from evernote_backup import note_exporter
from evernote_backup.config import CURRENT_DB_VERSION
from evernote_backup.note_exporter import NoteExporter
from evernote_backup.note_formatter import NoteFormatter
from evernote_backup.note_formatter_util import (
    BINARY_CHUNK_SIZE,
    fmt_binary,
    iter_binary,
)
from evernote_backup.note_storage import DB_SCHEMA, SqliteStorage

MB = 1024 * 1024

# One random block, repeated to reach the requested size. Random so base64 has
# no shortcuts to take, repeated so generating a 200 MiB body stays instant.
RANDOM_BLOCK = os.urandom(MB)

NOTE_CONTENT = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'
    "<en-note>" + "<div>lorem ipsum dolor sit amet</div>" * 100 + "</en-note>"
)


def measure_peak(action: Callable[[], None]) -> int:
    """Peak bytes allocated by `action`, in bytes."""
    tracemalloc.start()
    tracemalloc.reset_peak()

    try:
        action()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class NullWriter(io.StringIO):
    """Counts what it is given and keeps none of it."""

    def __init__(self) -> None:
        super().__init__()
        self.written = 0

    def write(self, text: str) -> int:
        self.written += len(text)
        return len(text)


def make_body(size: int) -> bytes:
    return (RANDOM_BLOCK * (size // MB + 1))[:size]


def make_note(
    resource_sizes: Iterable[int],
    guid: str = "note-1",
    notebook_guid: str = "notebook-1",
    title: str = "Test Note",
) -> Note:
    resources = [
        Resource(
            guid=f"{guid}-resource-{i}",
            noteGuid=guid,
            mime="video/avi",
            width=0,
            height=0,
            duration=0,
            data=Data(bodyHash=b"x" * 16, size=size, body=make_body(size)),
            attributes=ResourceAttributes(fileName=f"clip{i}.avi", attachment=True),
        )
        for i, size in enumerate(resource_sizes)
    ]

    return Note(
        guid=guid,
        title=title,
        created=1612902877000,
        updated=1617813805000,
        active=True,
        notebookGuid=notebook_guid,
        content=NOTE_CONTENT,
        resources=resources,
        attributes=NoteAttributes(author="test@example.com"),
    )


def make_database(
    database_path: Path,
    notebooks: int,
    notes_per_notebook: int,
    resource_sizes: Callable[[int, int], list[int]],
) -> None:
    """Build a database directly, bypassing the sync path.

    `resource_sizes(notebook_index, note_index)` gives the resource sizes of
    each note. Compression uses preset 0 so that building stays quick; the
    export path does not care which preset was used.
    """
    con = sqlite3.connect(database_path)
    con.executescript(DB_SCHEMA)
    con.execute(
        "replace into config(name, value) values (?, ?)",
        ("DB_VERSION", str(CURRENT_DB_VERSION)),
    )

    for nb in range(notebooks):
        notebook_guid = f"notebook-{nb}"
        con.execute(
            "replace into notebooks(guid, name, stack) values (?, ?, ?)",
            (notebook_guid, f"Notebook {nb:03d}", None),
        )

        for i in range(notes_per_notebook):
            note = make_note(
                resource_sizes(nb, i),
                guid=f"note-{nb}-{i}",
                notebook_guid=notebook_guid,
                title=f"Note {nb:03d}-{i:03d}",
            )

            con.execute(
                "replace into notes(guid, title, notebook_guid, is_active, raw_note)"
                " values (?, ?, ?, ?, ?)",
                (
                    note.guid,
                    note.title,
                    notebook_guid,
                    True,
                    lzma.compress(pickle.dumps(note), preset=0),
                ),
            )

        con.commit()

    con.close()


@pytest.fixture
def quiet_progress(monkeypatch):
    """`get_progress_output` needs a click context; benchmarks have none."""
    monkeypatch.setattr(note_exporter, "get_progress_output", lambda: io.StringIO())


def export_to(database_path: Path, target_dir: Path) -> None:
    NoteExporter(
        storage=SqliteStorage(database_path),
        target_dir=target_dir,
        single_notes=False,
        export_trash=False,
        no_export_date=True,
        add_guid=False,
        add_metadata=False,
        overwrite=True,
        filter_notebooks=(),
        filter_tags=(),
    ).export_notebooks()


def report(label: str, peak: int, payload: int = 0) -> None:
    line = f"[bench] {label:<46} peak {peak / MB:9.1f} MiB"

    if payload:
        line += f"  ({peak / payload:6.3f}x of {payload / MB:.0f} MiB payload)"

    print(line)


# --- equivalence -----------------------------------------------------------
# Not slow: these guard the chunking arithmetic and run on every test pass.


@pytest.mark.parametrize(
    "size",
    [
        0,
        1,
        89,
        90,
        91,
        119,
        120,
        121,
        359,
        360,
        361,
        BINARY_CHUNK_SIZE - 1,
        BINARY_CHUNK_SIZE,
        BINARY_CHUNK_SIZE + 1,
        BINARY_CHUNK_SIZE * 2 + 7,
    ],
)
def test_iter_binary_matches_fmt_binary(size):
    body = os.urandom(size)

    assert "".join(iter_binary(body)) == fmt_binary(body)


def test_iter_note_matches_format_note():
    formatter = NoteFormatter()

    for sizes in ([], [0], [1], [BINARY_CHUNK_SIZE + 1], [1000, 2000, 3000]):
        note = make_note(sizes)

        assert "".join(formatter.iter_note(note, "Notebook", [])) == (
            formatter.format_note(note, "Notebook", [])
        )


# --- benchmarks ------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("payload", [16 * MB, 64 * MB, 192 * MB])
def test_writer_peak_is_independent_of_resource_size(payload):
    """One big resource must not cost more than one chunk of working memory."""
    note = make_note([payload])
    sink = NullWriter()

    peak = measure_peak(
        lambda: [sink.write(chunk) for chunk in NoteFormatter().iter_note(note, "", [])]
    )

    report(f"iter_note, 1 x {payload // MB} MiB", peak, payload)

    assert sink.written > payload
    assert peak < 8 * MB


@pytest.mark.slow
def test_writer_peak_is_independent_of_resource_count():
    """Many resources must not accumulate either."""
    note = make_note([4 * MB] * 48)
    sink = NullWriter()

    peak = measure_peak(
        lambda: [sink.write(chunk) for chunk in NoteFormatter().iter_note(note, "", [])]
    )

    report("iter_note, 48 x 4 MiB", peak, 192 * MB)

    assert peak < 8 * MB


@pytest.mark.slow
def test_format_note_still_builds_the_whole_note():
    """`format_note` is the eager wrapper; it is expected to cost the note."""
    note = make_note([16 * MB])

    peak = measure_peak(lambda: NoteFormatter().format_note(note, "", []))

    report("format_note, 1 x 16 MiB", peak, 16 * MB)

    assert peak > 16 * MB


@pytest.mark.slow
@pytest.mark.usefixtures("quiet_progress")
def test_export_peak_scales_with_largest_note(tmp_path):
    """Export peak is bounded by the largest note, not by the export size."""
    payload = 192 * MB
    database_path = tmp_path / "large_note.db"

    make_database(
        database_path,
        notebooks=1,
        notes_per_notebook=4,
        resource_sizes=lambda nb, i: [payload] if i == 2 else [MB],
    )

    peak = measure_peak(lambda: export_to(database_path, tmp_path / "out"))

    report("export, notebook with one 192 MiB note", peak, payload)

    # Nothing beyond the note itself: it is read straight out of its blob and
    # written out in pieces.
    assert peak < 1.5 * payload


@pytest.mark.slow
@pytest.mark.usefixtures("quiet_progress")
def test_export_peak_with_adjacent_large_notes(tmp_path):
    """Consecutive large notes must not be held at the same time."""
    payload = 96 * MB
    database_path = tmp_path / "adjacent_notes.db"

    make_database(
        database_path,
        notebooks=1,
        notes_per_notebook=4,
        resource_sizes=lambda nb, i: [payload] if i < 3 else [MB],
    )

    peak = measure_peak(lambda: export_to(database_path, tmp_path / "out"))

    report("export, three 96 MiB notes in a row", peak, payload)

    assert peak < 1.5 * payload


@pytest.mark.slow
@pytest.mark.usefixtures("quiet_progress")
def test_export_peak_does_not_grow_over_a_long_run(tmp_path):
    """Guards against state accumulating across notebooks."""
    database_path = tmp_path / "many_notebooks.db"

    make_database(
        database_path,
        notebooks=20,
        notes_per_notebook=5,
        resource_sizes=lambda nb, i: [8 * MB],
    )

    peaks: list[int] = []
    original = NoteExporter._write_export_file

    def record(self, file_path, notebook_name, note_source):
        peaks.append(
            measure_peak(lambda: original(self, file_path, notebook_name, note_source))
        )
        file_path.unlink()

    NoteExporter._write_export_file = record
    try:
        export_to(database_path, tmp_path / "out")
    finally:
        NoteExporter._write_export_file = original

    first_half = max(peaks[:10])
    second_half = max(peaks[10:])

    report(f"export, first 10 of {len(peaks)} notebooks", first_half)
    report(f"export, last 10 of {len(peaks)} notebooks", second_half)

    assert second_half < first_half * 1.2


@pytest.mark.slow
def test_check_peak_scales_with_largest_note(tmp_path):
    """`manage check` walks every note, so it has the same ceiling as export."""
    payload = 96 * MB
    database_path = tmp_path / "check.db"

    make_database(
        database_path,
        notebooks=2,
        notes_per_notebook=4,
        resource_sizes=lambda nb, i: [payload] if i == 1 else [MB],
    )

    storage = SqliteStorage(database_path)
    checked = []

    peak = measure_peak(
        lambda: checked.extend(
            note is not None for note in storage.notes.check_notes(mark_corrupt=False)
        )
    )

    report("manage check, two 96 MiB notes", peak, payload)

    assert all(checked)
    assert len(checked) == 8
    assert peak < 1.5 * payload


@pytest.mark.slow
def test_store_note_peak(tmp_path):
    """The sync side still pays ~2.5x; recorded here so a fix can be measured."""
    payload = 64 * MB
    note = make_note([payload])
    database_path = tmp_path / "store.db"
    sqlite3.connect(database_path).executescript(DB_SCHEMA)
    storage = SqliteStorage(database_path)

    peak = measure_peak(lambda: storage.notes.add_note(note))

    report("add_note, 1 x 64 MiB", peak, payload)
