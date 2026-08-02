import base64
import io
import os
import re
import sys
import uuid
from collections.abc import Iterable, Iterator, Sequence
from typing import Optional, TextIO

import click

from evernote_backup.config import API_DATA_YINXIANG

# Evernote EDAM Guid: 36-char UUID string, e.g. 01234567-89ab-cdef-0123-456789abcdef
_GUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ProgramTerminatedError(Exception):
    """Terminate program with an error"""


class DatabaseEmptyError(Exception):
    """Raise when database is empty"""


class DatabaseCorruptError(Exception):
    """Raise when database is corrupt"""


def parse_guid(value: str) -> str:
    """Validate and normalize an Evernote GUID to lowercase UUID form."""
    value = value.strip()

    if not _GUID_RE.fullmatch(value):
        raise ValueError(
            f"Invalid GUID '{value}'. Expected format:"
            " 01234567-89ab-cdef-0123-456789abcdef"
        )

    return str(uuid.UUID(value))


def get_api_data(custom_api_data: Optional[str]) -> tuple[str, str]:
    if not custom_api_data:
        return unscramble(API_DATA_YINXIANG)

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
