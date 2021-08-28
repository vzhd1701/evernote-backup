import logging
import time

from evernote.edam.type.ttypes import Note, Notebook

from evernote_backup.cli_app_util import is_output_to_terminal


def init_logging() -> None:
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
        h.close()


def init_logging_format() -> None:
    if is_output_to_terminal():
        log_format = "%(message)s"
    else:
        log_format = "%(asctime)s | [%(levelname)s] | %(thread)d | %(message)s"

    logging.basicConfig(format=log_format)


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


def get_time_txt(seconds: int) -> str:
    seconds_hour = 3600
    seconds_minute = 60

    if seconds > seconds_hour:
        return time.strftime("%H:%M:%S", time.gmtime(seconds))
    elif seconds > seconds_minute:
        return time.strftime("%M:%S", time.gmtime(seconds))

    return time.strftime("0:%S", time.gmtime(seconds))
