import base64
import io
import os
import sys
from collections.abc import Iterable, Iterator, Sequence
from typing import Optional, TextIO

import click

from evernote_backup.config import API_DATA_EVERNOTE, API_DATA_YINXIANG


class ProgramTerminatedError(Exception):
    """Terminate program with an error"""


class DatabaseEmptyError(Exception):
    """Raise when database is empty"""


class DatabaseCorruptError(Exception):
    """Raise when database is corrupt"""


def get_api_data(backend: str, custom_api_data: Optional[str]) -> tuple[str, str]:
    if not custom_api_data:
        if backend.startswith("china"):
            return unscramble(API_DATA_YINXIANG)
        return unscramble(API_DATA_EVERNOTE)

    try:
        key, secret = custom_api_data.split(":", maxsplit=1)
    except ValueError:
        raise ProgramTerminatedError(
            "Could not parse custom API data. Use 'key:secret' format."
        )

    return key, secret


def unscramble(scrambled_data: bytes) -> tuple[str, str]:
    scrambled_data = base64.b64decode(scrambled_data)

    unscrambled = b""
    for i, char in enumerate(scrambled_data):
        xor = len(scrambled_data) - i
        unscrambled += (char ^ xor).to_bytes(1, byteorder="big")

    key, secret = unscrambled.decode().split(maxsplit=1)

    return key, secret


def get_progress_output() -> Optional[TextIO]:
    is_verbose_mode = click.get_current_context().find_root().params["verbose"]

    if not is_console_interactive() or is_verbose_mode:
        return io.StringIO()

    return None


def is_console_interactive() -> bool:
    is_quiet = click.get_current_context().find_root().params["quiet"]

    return is_output_to_terminal() and not is_quiet


def is_output_to_terminal() -> bool:
    return sys.stdout.isatty()


def is_inside_docker() -> bool:
    return os.environ.get("INSIDE_DOCKER_CONTAINER", False) is not False


def chunks(lst: Sequence, n: int) -> Iterator[Iterable]:
    """Yield successive n-sized chunks from lst."""

    yield from (lst[i : i + n] for i in range(0, len(lst), n))  # noqa: WPS221
