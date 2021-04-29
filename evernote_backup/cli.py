import logging
import sys
import traceback
from typing import Optional

import click

from evernote_backup import cli_app
from evernote_backup.cli_app_util import (
    DIR_ONLY,
    FILE_ONLY,
    NaturalOrderGroup,
    ProgramTerminatedError,
    group_options,
    is_output_to_terminal,
)
from evernote_backup.version import __version__

logger = logging.getLogger()


opt_user = click.option(
    "--user",
    "-u",
    help="Account email or username.",
)

opt_password = click.option(
    "--password",
    "-p",
    help="Account password.",
)

opt_oauth = click.option(
    "--oauth",
    is_flag=True,
    help=(
        "OAuth login flow."
        " Use this if you signed up for Evernote with Google or Apple account."
        " (Ignores '--user' and '--password' when used."
        " Doesn't work for Yinxiang.)"
    ),
)

opt_token = click.option(
    "--token",
    "-t",
    help=(
        "Manually provide authentication token to use with Evernote API."
        " (Advanced option, ignores '--user', '--password' and '--oauth' when used.)"
    ),
)

opt_database = click.option(
    "--database",
    "-d",
    default="en_backup.db",
    show_default=True,
    required=True,
    type=FILE_ONLY,
    help="Database file where notes are stored.",
)


@click.group(cls=NaturalOrderGroup)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Quiet mode, output only in case of critical errors.",
)
@click.version_option(__version__)
def cli(quiet: bool) -> None:
    """Evernote backup & export

    \b
    On the first run, to export notes:
    evernote-backup init-db
    evernote-backup sync
    evernote-backup export output_dir/
    """

    if is_output_to_terminal():
        log_format = "%(message)s"
    else:
        log_format = "%(asctime)s | [%(levelname)s] | %(message)s"

    logging.basicConfig(
        format=log_format,
        force=True,
    )

    if quiet:
        logger.setLevel(logging.CRITICAL)
    else:
        logger.setLevel(logging.INFO)


@cli.command()
@opt_database
@group_options(opt_user, opt_password, opt_oauth, opt_token)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing database file.",
)
@click.option(
    "--backend",
    default="evernote",
    show_default=True,
    type=click.Choice(["evernote", "evernote:sandbox", "china", "china:sandbox"]),
    help="API backend to connect to. If you are using Yinxiang, select 'china'.",
)
def init_db(
    database: str,
    user: Optional[str],
    password: Optional[str],
    oauth: bool,
    token: Optional[str],
    force: bool,
    backend: str,
) -> None:
    """Initialize storage & log in to Evernote."""

    cli_app.init_db(
        database=database,
        auth_user=user,
        auth_password=password,
        auth_is_oauth=oauth,
        auth_token=token,
        force=force,
        backend=backend,
    )


@cli.command()
@opt_database
def sync(database: str) -> None:
    """Sync local database with Evernote, downloading all notes."""

    cli_app.sync(database=database)


@cli.command()
@opt_database
@click.option(
    "--single-notes",
    is_flag=True,
    help="Export single notes instead of notebooks.",
)
@click.option(
    "--include-trash",
    is_flag=True,
    help="Include notes from trash into export.",
)
@click.argument(
    "output_path",
    required=True,
    type=DIR_ONLY,
)
def export(
    database: str, single_notes: bool, include_trash: bool, output_path: str
) -> None:
    """Export all notes from local database into ENEX files."""

    cli_app.export(
        database=database,
        single_notes=single_notes,
        include_trash=include_trash,
        output_path=output_path,
    )


click.password_option()


@cli.command()
@opt_database
@group_options(opt_user, opt_password, opt_oauth, opt_token)
def reauth(
    database: str,
    user: Optional[str],
    password: Optional[str],
    oauth: bool,
    token: Optional[str],
) -> None:
    """Refresh login to Evernote, run when token expires."""

    cli_app.reauth(
        database=database,
        auth_user=user,
        auth_password=password,
        auth_is_oauth=oauth,
        auth_token=token,
    )


def main() -> None:
    try:
        cli()
    except ProgramTerminatedError as e:
        logger.critical(e)
        sys.exit(1)
    except Exception:
        logger.critical(traceback.format_exc())
        sys.exit(1)
