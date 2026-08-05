import functools
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from ssl import SSLError
from typing import Any

import click
from click_option_group import MutuallyExclusiveOptionGroup, optgroup
from evernote.edam.error.ttypes import EDAMErrorCode, EDAMSystemException
from thrift.Thrift import TApplicationException

from evernote_backup import cli_app, config_defaults
from evernote_backup.cli_app_click_util import (
    DIR_ONLY,
    FILE_ONLY,
    DescribedChoice,
    DescribedChoiceCommand,
    NaturalOrderGroup,
    group_options,
)
from evernote_backup.errors import ProgramTerminatedError
from evernote_backup.log_util import get_time_from_now_txt, get_time_txt, init_logging
from evernote_backup.version import __version__

opt_user = click.option(
    "--user",
    "-u",
    help="Account email or username (works only for Yinxiang).",
)

opt_password = click.option(
    "--password",
    "-p",
    help="Account password (works only for Yinxiang).",
)

opt_oauth_port = click.option(
    "--oauth-port",
    default=config_defaults.OAUTH_LOCAL_PORT,
    show_default=True,
    help=(
        "OAuth local server port. (Advanced option, works only with"
        " --oauth-method mcp, ignored for Yinxiang.)"
    ),
)

opt_oauth_host = click.option(
    "--oauth-host",
    default=config_defaults.OAUTH_HOST,
    show_default=True,
    help=(
        "OAuth local server host. (Advanced option, works only with"
        " --oauth-method mcp, ignored for Yinxiang.)"
    ),
)


opt_oauth_method = click.option(
    "--oauth-method",
    type=click.Choice(["desktop", "import", "mcp"], case_sensitive=False),
    default="desktop",
    show_default=True,
    cls=DescribedChoice,
    choice_help={
        "desktop": "Start new OAuth session presenting as Evernote Desktop Client (default).",
        "import": (
            "Import existing OAuth session from a logged-in Evernote Desktop Client."
            " (Works only on Windows and macOS, recommended for free plan)"
        ),
        "mcp": (
            "Start new OAuth session using MCP interface API."
            " (Advanced option. Requires Evernote plan that allows MCP.)"
        ),
    },
    help="OAuth method to use. Ignored for Yinxiang.",
)

opt_oauth_en_user = click.option(
    "--oauth-en-user",
    help=(
        "Evernote user ID to import the refresh token from when multiple"
        " Desktop Client sessions exist. (Works only with --oauth-method import.)"
    ),
)

opt_oauth_en_config_dir = click.option(
    "--oauth-en-config-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help=(
        "Path to the Evernote Desktop Client config directory."
        " (Advanced option, works only with --oauth-method import.)"
    ),
)

opt_token = click.option(
    "--token",
    "-t",
    help=(
        "Manually provide authentication token to use with Evernote API."
        " (Advanced option, ignores '--user', '--password' and '--oauth-method' when used.)"
    ),
)

opt_token_one_off = click.option(
    "--token",
    "-t",
    help=(
        "Manually provide authentication token to use with Evernote API."
        " (Used only for this run, ignores existing one in the database.)"
    ),
)

opt_network_retry_count = click.option(
    "--network-retry-count",
    default=config_defaults.NETWORK_ERROR_RETRY_COUNT,
    show_default=True,
    type=click.IntRange(1),
    help=("Network error retry count. (Advanced option)"),
)

opt_database = click.option(
    "--database",
    "-d",
    default=config_defaults.DATABASE_NAME,
    show_default=True,
    required=True,
    type=FILE_ONLY,
    help="Database file where notes are stored.",
)

opt_backend = click.option(
    "--backend",
    default=config_defaults.BACKEND,
    show_default=True,
    type=click.Choice(["evernote", "china", "china:sandbox"]),
    help="API backend to connect to. If you are using Yinxiang, select 'china'.",
)

opt_use_system_ssl_ca = click.option(
    "--use-system-ssl-ca",
    is_flag=True,
    help="Use system provided Certificate Authority (CA) for SSL. (Advanced option)",
)

opt_api_data = click.option(
    "--api-data",
    help="Custom API data, use 'key:secret' format. (Advanced option)",
)


def handle_errors(f: Callable) -> Callable:
    logger = logging.getLogger(__name__)

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except ProgramTerminatedError as e:
            logger.critical(e)
        except SSLError as e:
            logger.critical(f"SSL error: {e}")
            logger.critical(
                "To debug this problem, run 'evernote-backup -v manage ping'"
            )
        except EDAMSystemException as e:
            if e.errorCode == EDAMErrorCode.RATE_LIMIT_REACHED:
                time_at = get_time_from_now_txt(e.rateLimitDuration)
                time_left = get_time_txt(e.rateLimitDuration)
                logger.critical(
                    f"Rate limit reached. Restart program at {time_at} (in {time_left})."
                )
            else:
                logger.exception("Evernote server error")
        except TApplicationException as e:
            message_txt = (
                e.message.decode("utf-8") if isinstance(e.message, bytes) else e.message
            )
            logger.exception(f"Thrift exception: {message_txt}")
        except Exception:
            logger.exception("Unknown exception")

        sys.exit(1)

    return wrapper


@click.group(cls=NaturalOrderGroup)
@optgroup.group("Verbosity", cls=MutuallyExclusiveOptionGroup)  # type: ignore
@optgroup.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Quiet mode, output only critical errors.",
)
@optgroup.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose mode, output debug information.",
)
@click.option(
    "--log",
    type=click.Path(file_okay=True, dir_okay=False, writable=True),
    help="Log file path.",
)
@click.version_option(__version__)
def cli(quiet: bool, verbose: bool, log: Path) -> None:
    """Evernote backup & export

    \b
    On the first run, to export notes:
    evernote-backup init-db
    evernote-backup sync
    evernote-backup export output_dir/
    """

    if quiet:
        log_level = "CRITICAL"
    elif verbose:
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    init_logging(log_level, log)


@cli.command(cls=DescribedChoiceCommand)
@opt_database
@group_options(
    opt_user,
    opt_password,
    opt_oauth_method,
    opt_oauth_port,
    opt_oauth_host,
    opt_oauth_en_user,
    opt_oauth_en_config_dir,
    opt_token,
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing database file.",
)
@opt_backend
@opt_network_retry_count
@opt_use_system_ssl_ca
@opt_api_data
@handle_errors
def init_db(
    database: Path,
    user: str | None,
    password: str | None,
    oauth_method: str,
    oauth_port: int,
    oauth_host: str,
    oauth_en_user: str | None,
    oauth_en_config_dir: Path | None,
    token: str | None,
    force: bool,
    backend: str,
    network_retry_count: int,
    use_system_ssl_ca: bool,
    api_data: str | None,
) -> None:
    """Initialize storage & log in to Evernote."""

    cli_app.init_db(
        database=database,
        auth_user=user,
        auth_password=password,
        auth_oauth_port=oauth_port,
        auth_oauth_host=oauth_host,
        auth_token=token,
        force=force,
        backend=backend,
        network_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
        custom_api_data=api_data,
        oauth_method=oauth_method,
        oauth_en_user=oauth_en_user,
        oauth_en_config_dir=oauth_en_config_dir,
    )


@cli.command()
@opt_database
@click.option(
    "--max-chunk-results",
    default=config_defaults.SYNC_CHUNK_MAX_RESULTS,
    type=click.IntRange(1, config_defaults.SYNC_CHUNK_MAX_RESULTS_SERVER_LIMIT),
    show_default=True,
    help="Max entries per sync chunk. (Advanced option)",
)
@click.option(
    "--max-download-workers",
    default=config_defaults.SYNC_MAX_DOWNLOAD_WORKERS,
    show_default=True,
    type=click.IntRange(1, config_defaults.SYNC_MAX_DOWNLOAD_WORKERS_SANE_LIMIT),
    help=(
        "Max number of parallel downloads. Don't set too high to avoid rate limits."
        " (Advanced option)"
    ),
)
@click.option(
    "--download-cache-memory-limit",
    default=config_defaults.SYNC_DOWNLOAD_CACHE_MEMORY_LIMIT,
    show_default=True,
    type=click.IntRange(1),
    help=(
        "Cache size in MB for notes stored in memory before writing to disk."
        " (Advanced option)"
    ),
)
@opt_network_retry_count
@opt_use_system_ssl_ca
@opt_token_one_off
@handle_errors
def sync(
    database: Path,
    max_chunk_results: int,
    max_download_workers: int,
    download_cache_memory_limit: int,
    network_retry_count: int,
    use_system_ssl_ca: bool,
    token: str | None,
) -> None:
    """Sync local database with Evernote, downloading all notes."""

    cli_app.sync(
        database=database,
        max_chunk_results=max_chunk_results,
        max_download_workers=max_download_workers,
        download_cache_memory_limit=download_cache_memory_limit,
        network_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
        token=token,
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
@click.option(
    "--no-export-date",
    is_flag=True,
    help=(
        "Don't timestamp exported ENEX files."
        " (e.g. to prevent backup chunking with zero changes)"
    ),
)
@click.option(
    "--add-guid",
    is_flag=True,
    help=(
        "Add GUID meta field to every exported note."
        " (GUID is a unique note identifier used internally by Evernote)"
    ),
)
@click.option(
    "--add-metadata",
    is_flag=True,
    help="Add <note-custom-metadata> block to every exported note. (Advanced option)",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite existing ENEX files.",
)
@click.option(
    "--notebook",
    "-n",
    "notebooks",
    help="Export notes from specific notebook(s). (Can be used multiple times)",
    multiple=True,
)
@click.option(
    "--tag",
    "-t",
    "tags",
    help="Export notes with specific tag(s). (Can be used multiple times)",
    multiple=True,
)
@click.argument(
    "output_path",
    required=True,
    type=DIR_ONLY,
)
@handle_errors
def export(
    database: Path,
    single_notes: bool,
    include_trash: bool,
    no_export_date: bool,
    add_guid: bool,
    add_metadata: bool,
    overwrite: bool,
    notebooks: tuple[str],
    tags: tuple[str],
    output_path: Path,
) -> None:
    """Export all notes from local database into ENEX files."""

    cli_app.export(
        database=database,
        single_notes=single_notes,
        include_trash=include_trash,
        no_export_date=no_export_date,
        add_guid=add_guid,
        add_metadata=add_metadata,
        overwrite=overwrite,
        notebooks=notebooks,
        tags=tags,
        output_path=output_path,
    )


@cli.command(cls=DescribedChoiceCommand)
@opt_database
@group_options(
    opt_user,
    opt_password,
    opt_oauth_method,
    opt_oauth_port,
    opt_oauth_host,
    opt_oauth_en_user,
    opt_oauth_en_config_dir,
    opt_token,
)
@opt_network_retry_count
@opt_use_system_ssl_ca
@opt_api_data
@handle_errors
def reauth(
    database: Path,
    user: str | None,
    password: str | None,
    oauth_method: str,
    oauth_port: int,
    oauth_host: str,
    oauth_en_user: str | None,
    oauth_en_config_dir: Path | None,
    token: str | None,
    network_retry_count: int,
    use_system_ssl_ca: bool,
    api_data: str | None,
) -> None:
    """Refresh login to Evernote, run when token expires."""

    cli_app.reauth(
        database=database,
        auth_user=user,
        auth_password=password,
        auth_oauth_port=oauth_port,
        auth_oauth_host=oauth_host,
        auth_token=token,
        network_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
        custom_api_data=api_data,
        oauth_method=oauth_method,
        oauth_en_user=oauth_en_user,
        oauth_en_config_dir=oauth_en_config_dir,
    )


@cli.group("manage")
@handle_errors
def manage() -> None:
    """Managing your backup database and other functions"""


@manage.command("ping")
@opt_backend
@opt_network_retry_count
@opt_use_system_ssl_ca
@handle_errors
def manage_ping(
    backend: str,
    network_retry_count: int,
    use_system_ssl_ca: bool,
) -> None:
    """Test connection to Evernote API server"""

    cli_app.manage_ping(
        backend=backend,
        network_retry_count=network_retry_count,
        use_system_ssl_ca=use_system_ssl_ca,
    )


@manage.command("check")
@opt_database
@click.option(
    "--mark-corrupted",
    is_flag=True,
    help=(
        "Mark corrupted notes for re-download."
        " (WARNING: This will delete bad note bodies from database)"
    ),
)
@handle_errors
def manage_check(
    database: Path,
    mark_corrupted: bool,
) -> None:
    """Check database and notes integrity without exporting them"""

    cli_app.manage_check(
        database=database,
        mark_corrupted=mark_corrupted,
    )


@manage.command("list")
@opt_database
@click.option(
    "--notebook",
    "-n",
    help=("List notes from specific notebook."),
)
@click.option(
    "--all",
    "is_list_all",
    is_flag=True,
    help=("List all notes, not just notebooks."),
)
@handle_errors
def manage_list(
    database: Path,
    notebook: str | None,
    is_list_all: bool,
) -> None:
    """List database content"""

    cli_app.manage_list(
        database=database,
        notebook=notebook,
        is_list_all=is_list_all,
    )


@manage.command("blacklist")
@opt_database
@click.option(
    "--add-note-id",
    multiple=True,
    help="Add note GUID(s) to blacklist. (Can be used multiple times)",
)
@click.option(
    "--del-note-id",
    multiple=True,
    help="Remove note GUID(s) from blacklist. (Can be used multiple times)",
)
@click.option(
    "--add-notebook-id",
    multiple=True,
    help="Add notebook GUID(s) to blacklist. (Can be used multiple times)",
)
@click.option(
    "--del-notebook-id",
    multiple=True,
    help="Remove notebook GUID(s) from blacklist. (Can be used multiple times)",
)
@click.option(
    "--reset-notes",
    is_flag=True,
    help="Clear all blacklisted notes.",
)
@click.option(
    "--reset-notebooks",
    is_flag=True,
    help="Clear all blacklisted notebooks.",
)
@handle_errors
def manage_blacklist(
    database: Path,
    add_note_id: tuple[str, ...],
    del_note_id: tuple[str, ...],
    add_notebook_id: tuple[str, ...],
    del_notebook_id: tuple[str, ...],
    reset_notes: bool,
    reset_notebooks: bool,
) -> None:
    """Manage blacklist of notes and notebooks to skip during sync

    \b
    Broken notes may still appear in sync listings but fail to download
    ("Failed to download note"). Add their GUIDs here to permanently skip them.
    """

    cli_app.manage_blacklist(
        database=database,
        add_note_id=add_note_id,
        del_note_id=del_note_id,
        add_notebook_id=add_notebook_id,
        del_notebook_id=del_notebook_id,
        reset_notes=reset_notes,
        reset_notebooks=reset_notebooks,
    )


def main() -> None:
    cli()
