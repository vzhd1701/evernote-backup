import base64
import logging
import os
import sys
from typing import List, Optional

import click

logger = logging.getLogger(__name__)


class ProgramTerminatedError(Exception):
    """Terminate program with an error"""


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


def is_inside_docker() -> bool:
    return os.environ.get("INSIDE_DOCKER_CONTAINER", False) is not False
