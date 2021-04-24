import base64
import logging
import os
import sys
from datetime import datetime as dt

import click

from evernote_backup.config import API_DATA
from evernote_backup.evernote_client import EvernoteClientAuth
from evernote_backup.evernote_client_sync import EvernoteClientSync
from evernote_backup.evernote_client_util import EvernoteAuthError
from evernote_backup.note_storage import SqliteStorage

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
    def list_commands(self, ctx):
        return self.commands.keys()


def group_options(*options):
    def wrapper(function):
        for option in reversed(options):
            function = option(function)
        return function

    return wrapper


def unscramble(scrambled_data):
    scrambled_data = base64.b64decode(scrambled_data)

    unscrambled = b""
    for i, char in enumerate(scrambled_data):
        xor = len(scrambled_data) - i
        unscrambled += (char ^ xor).to_bytes(1, byteorder="big")

    return unscrambled.decode().split()


def get_storage(database_path):
    logger.info("Reading database {0}...".format(os.path.basename(database_path)))

    try:
        return SqliteStorage(database_path)
    except FileNotFoundError:
        raise ProgramTerminatedError(
            f"Database file {database_path} does not exist."
            f" Initialize database first!"
        )


def get_token_expiration_date(token):
    hex_base = 16
    token_parts = token.split(":")
    token_expire_ts = int(token_parts[2][2:], base=hex_base) // 1000

    return dt.utcfromtimestamp(token_expire_ts)


def get_sync_client(auth_token, backend):
    logger.info(f"Authorizing auth token, {backend} backend...")

    client = EvernoteClientSync(token=auth_token, backend=backend)

    try:
        client.verify_token()
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)

    token_expiration = get_token_expiration_date(auth_token)

    logger.info(f"Successfully authenticated as {client.user}!")
    logger.info(f"Current login will expire at {token_expiration}.")

    return client


def get_auth_client(backend):
    key, secret = unscramble(API_DATA)

    return EvernoteClientAuth(
        consumer_key=key,
        consumer_secret=secret,
        backend=backend,
    )


def prompt_credentials(user, password):
    if not is_output_to_terminal() and not all([user, password]):
        raise ProgramTerminatedError("--user and --password are required!")

    if not user:
        user = click.prompt("Username or Email")
    if not password:
        password = click.prompt("Password", hide_input=True)

    return user, password


def prompt_ota(delivery_hint):
    if not is_output_to_terminal():
        raise ProgramTerminatedError("Two-factor authentication requires user input!")

    one_time_hint = ""
    if delivery_hint:
        one_time_hint = " ({0})".format(delivery_hint)

    return click.prompt(f"Enter one-time code{one_time_hint}")


def get_auth_token(auth_user, auth_password, backend):
    auth_user, auth_password = prompt_credentials(auth_user, auth_password)

    logger.info("Logging in to Evernote...")

    auth_client = get_auth_client(backend)

    try:
        auth_res = auth_client.login(auth_user, auth_password)
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)

    if auth_res.secondFactorRequired:
        auth_res = handle_two_factor_auth(
            auth_client,
            auth_res.authenticationToken,
            auth_res.secondFactorDeliveryHint,
        )

    return auth_res.authenticationToken


def handle_two_factor_auth(auth_client, token, delivery_hint):
    ota_code = prompt_ota(delivery_hint)

    try:
        return auth_client.two_factor_auth(token, ota_code)
    except EvernoteAuthError as e:
        raise ProgramTerminatedError(e)


def get_progress_output():
    if not is_console_interactive():
        return os.devnull

    return None


def is_console_interactive():
    is_quiet = click.get_current_context().find_root().params["quiet"]

    return is_output_to_terminal() and not is_quiet


def is_output_to_terminal():
    return sys.stdout.isatty()
