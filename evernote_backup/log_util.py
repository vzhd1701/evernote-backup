import logging
import logging.config
import sys
import time
from pathlib import Path
from typing import Optional

from evernote.edam.type.ttypes import Note, Notebook

from evernote_backup.cli_app_util import is_output_to_terminal

IS_TESTING = "pytest" in sys.modules


def init_logging(log_level: str, log_file: Optional[Path] = None) -> None:
    main_logger = "evernote_backup"

    format_short = "%(message)s"
    format_long = "%(asctime)s | %(levelname)s | %(message)s"

    log_format_cli = format_short if is_output_to_terminal() else format_long
    log_format_file = format_long

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {"format": log_format_cli},
            "file": {"format": log_format_file},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "console",
            }
        },
        "loggers": {
            main_logger: {
                "level": log_level,
                "handlers": ["console"],
                "propagate": IS_TESTING,
            }
        },
    }

    if log_file:
        config["handlers"]["file"] = {
            "class": "logging.FileHandler",
            "level": log_level,
            "formatter": "file",
            "filename": str(log_file),
            "encoding": "utf-8",
            "delay": True,
        }
        config["loggers"][main_logger]["handlers"].append("file")

    logging.config.dictConfig(config)


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
