from evernote.edam.type.ttypes import Note, Notebook


def log_format_note(note: Note) -> str:  # pragma: no cover
    n_info = (
        f"'{note.title}' [{note.guid}], notebook_id {note.notebookGuid}"  # noqa: WPS221
    )
    if not note.active:
        n_info += ", DELETED"  # noqa: WPS336

    return n_info


def log_format_notebook(notebook: Notebook) -> str:  # pragma: no cover
    nb_info = f"'{notebook.name}' [{notebook.guid}]"
    if notebook.stack:
        nb_info += f", stack '{notebook.stack}'"  # noqa: WPS336

    return nb_info
