import logging
import sys
import traceback
from typing import Optional

import click
from click_option_group import MutuallyExclusiveOptionGroup, optgroup

from evernote_backup import cli_app
from evernote_backup.cli_app_click_util import (
    DIR_ONLY,
    FILE_ONLY,
    NaturalOrderGroup,
    group_options,
)
from evernote_backup.cli_app_util import ProgramTerminatedError, is_output_to_terminal
from evernote_backup.config_defaults import (
    BACKEND,
    DATABASE_NAME,
    NETWORK_ERROR_RETRY_COUNT,
    OAUTH_LOCAL_PORT,
    SYNC_CHUNK_MAX_RESULTS,
    SYNC_CHUNK_MAX_RESULTS_SERVER_LIMIT,
    SYNC_MAX_DOWNLOAD_WORKERS,
    SYNC_MAX_DOWNLOAD_WORKERS_SANE_LIMIT,
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

opt_oauth_port = click.option(
    "--oauth-port",
    default=OAUTH_LOCAL_PORT,
    show_default=True,
    help="OAuth local server port. (Advanced option, use with --oauth.)",
)

opt_token = click.option(
    "--token",
    "-t",
    help=(
        "Manually provide authentication token to use with Evernote API."
        " (Advanced option, ignores '--user', '--password' and '--oauth' when used.)"
    ),
)

opt_network_retry_count = click.option(
    "--network-retry-count",
    default=NETWORK_ERROR_RETRY_COUNT,
    show_default=True,
    type=click.IntRange(1),
    help=("Network error retry count. (Advanced option)"),
)

opt_database = click.option(
    "--database",
    "-d",
    default=DATABASE_NAME,
    show_default=True,
    required=True,
    type=FILE_ONLY,
    help="Database file where notes are stored.",
)


@click.group(cls=NaturalOrderGroup)
@optgroup.group("Verbosity", cls=MutuallyExclusiveOptionGroup)  # type: ignore
@optgroup.option(  # type: ignore
    "--quiet",
    "-q",
    is_flag=True,
    help="Quiet mode, output only critical errors.",
)
@optgroup.option(  # type: ignore
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose mode, output debug information.",
)
@click.version_option(__version__)
def cli(quiet: bool, verbose: bool) -> None:
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

    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
        h.close()

    logging.basicConfig(format=log_format)

    if quiet:
        logger.setLevel(logging.CRITICAL)
    elif verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)


@cli.command()
@opt_database
@group_options(opt_user, opt_password, opt_oauth, opt_oauth_port, opt_token)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing database file.",
)
@click.option(
    "--backend",
    default=BACKEND,
    show_default=True,
    type=click.Choice(["evernote", "evernote:sandbox", "china", "china:sandbox"]),
    help="API backend to connect to. If you are using Yinxiang, select 'china'.",
)
@opt_network_retry_count
def init_db(
    database: str,
    user: Optional[str],
    password: Optional[str],
    oauth: bool,
    oauth_port: int,
    token: Optional[str],
    force: bool,
    backend: str,
    network_retry_count: int,
) -> None:
    """Initialize storage & log in to Evernote."""

    cli_app.init_db(
        database=database,
        auth_user=user,
        auth_password=password,
        auth_is_oauth=oauth,
        auth_oauth_port=oauth_port,
        auth_token=token,
        force=force,
        backend=backend,
        network_retry_count=network_retry_count,
    )


@cli.command()
@opt_database
@click.option(
    "--max-chunk-results",
    default=SYNC_CHUNK_MAX_RESULTS,
    type=click.IntRange(1, SYNC_CHUNK_MAX_RESULTS_SERVER_LIMIT),
    show_default=True,
    help="Max entries per sync chunk. (Advanced option)",
)
@click.option(
    "--max-download-workers",
    default=SYNC_MAX_DOWNLOAD_WORKERS,
    show_default=True,
    type=click.IntRange(1, SYNC_MAX_DOWNLOAD_WORKERS_SANE_LIMIT),
    help=(
        "Max number of parallel downloads."
        " (Advanced option, don't set too high to avoid rate limits.)"
    ),
)
@opt_network_retry_count
def sync(
    database: str,
    max_chunk_results: int,
    max_download_workers: int,
    network_retry_count: int,
) -> None:
    """Sync local database with Evernote, downloading all notes."""

    cli_app.sync(
        database=database,
        max_chunk_results=max_chunk_results,
        max_download_workers=max_download_workers,
        network_retry_count=network_retry_count,
    )


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
    database: str,
    single_notes: bool,
    include_trash: bool,
    output_path: str,
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
@group_options(opt_user, opt_password, opt_oauth, opt_oauth_port, opt_token)
@opt_network_retry_count
def reauth(
    database: str,
    user: Optional[str],
    password: Optional[str],
    oauth: bool,
    oauth_port: int,
    token: Optional[str],
    network_retry_count: int,
) -> None:
    """Refresh login to Evernote, run when token expires."""

    cli_app.reauth(
        database=database,
        auth_user=user,
        auth_password=password,
        auth_is_oauth=oauth,
        auth_oauth_port=oauth_port,
        auth_token=token,
        network_retry_count=network_retry_count,
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
