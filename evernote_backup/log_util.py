from evernote.edam.type.ttypes import Note, Notebook


def log_format_note(note: Note) -> str:  # pragma: no cover
    n_info = [
        f"'{note.title}' [{note.guid}]",
        f"notebook_id [{note.notebookGuid}]",
    ]

    if not note.active:
        n_info.append("DELETED")

    return ", ".join(n_info)


def log_format_notebook(notebook: Notebook) -> str:  # pragma: no cover
    nb_info = [f"'{notebook.name}' [{notebook.guid}]"]

    if notebook.stack:
        nb_info.append(f"stack '{notebook.stack}'")

    return ", ".join(nb_info)
