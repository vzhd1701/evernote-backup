# AGENTS.md

`evernote-backup`: a Click CLI that syncs Evernote/Yinxiang notes into a local SQLite database and exports them as ENEX.

## Setup and checks

Use `uv` for everything; do not use bare `pip` or `python`.

```sh
uv sync --all-groups          # install
uv run pytest                 # tests (slow benchmarks are deselected by default)
uv run ruff format            # format
uv run ruff check             # lint
uv run ty check               # type check
just bench                    # memory/throughput benchmarks (marked `slow`)
```

Run tests, `ruff check` and `ty check` before calling a change done; pre-commit runs the same set.

## Layout

- `evernote_backup/cli.py`: Click command definitions and options. `cli_app.py` holds the logic behind each command (`init-db`, `reauth`, `sync`, `export`, `manage ...`).
- `evernote_client*.py`, `desktop_session.py`, `token_util.py`: Evernote API access and auth (password, OAuth, JWT, desktop session import).
- `note_synchronizer.py`: sync from the API into storage. `note_exporter.py` and `note_formatter.py`: storage to ENEX.
- `note_storage.py`: the SQLite schema (`DB_SCHEMA`) and data access. Notes are stored as lzma-compressed pickles.
- `evernote_client_api_tokenized.py` is generated boilerplate, excluded from lint and coverage. Don't hand-edit or reformat it.

## Conventions

- Target Python 3.11+ and use absolute imports only (relative imports are banned by ruff).
- Changing the DB schema means bumping `CURRENT_DB_VERSION` in `config.py` and adding an upgrade step to `SqliteStorage.upgrade_db`. Existing user databases must keep working.
- Export must stay streaming: never build a whole note or attachment in memory. The benchmarks in `tests/test_memory_benchmark.py` guard this.
- Tests must never hit the network. Use the fakes and fixtures in `tests/conftest.py` (`fake_storage`, `mock_evernote_client`, `cli_invoker`, ...). Command-level tests live in `tests/test_op_*.py`.
- Pin new runtime dependencies to exact versions in `pyproject.toml`, then run `uv lock`.

## Git

- Never commit unless the user explicitly asks for it. Leave changes uncommitted in the working tree.
- Use Conventional Commits with a scope where it fits: `fix(export): ...`, `perf(export): ...`, `test(bench): ...`, `build: ...`, `ci(github): ...`.
- Work on `develop` or a feature branch. Commits to `master` are blocked.
- User-facing changes go under `## [Unreleased]` in `CHANGELOG.md` (Keep a Changelog format). Don't edit versions or run release tooling (`just release`); the maintainer does that.
