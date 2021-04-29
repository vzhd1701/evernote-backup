import base64
import logging
import os
import sys
from typing import Any, Callable, Iterable, List, Optional

import click

logger = logging.getLogger(__name__)

DIR_ONLY = click.Path(
    file_okay=False,
    writable=True,
    resolve_path=True,
)

FILE_ONLY = click.Path(
    dir_okay=False,
    writable=True,
    resolve_path=True,
)


class ProgramTerminatedError(Exception):
    """Terminate program with an error"""


class NaturalOrderGroup(click.Group):  # pragma: no cover
    def list_commands(self, ctx: Any) -> Iterable:
        return self.commands.keys()


def group_options(*options: Callable) -> Callable:
    def wrapper(function: Callable) -> Callable:
        for option in reversed(options):
            function = option(function)
        return function

    return wrapper


def unscramble(scrambled_data: bytes) -> List[str]:
    scrambled_data = base64.b64decode(scrambled_data)

    unscrambled = b""
    for i, char in enumerate(scrambled_data):
        xor = len(scrambled_data) - i
        unscrambled += (char ^ xor).to_bytes(1, byteorder="big")

    return unscrambled.decode().split()


def get_progress_output() -> Optional[str]:
    if not is_console_interactive():
        return os.devnull

    return None


def is_console_interactive() -> bool:
    is_quiet = click.get_current_context().find_root().params["quiet"]

    return is_output_to_terminal() and not is_quiet


def is_output_to_terminal() -> bool:
    return sys.stdout.isatty()
