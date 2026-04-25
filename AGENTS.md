# Repository Guidelines

## Project Structure & Module Organization

`evernote_backup/` contains the Python package and CLI implementation. Entry points are `evernote_backup/cli.py` and `evernote_backup/__main__.py`; command helpers live in `cli_app*.py`; Evernote API clients live in `evernote_client*.py`; note persistence, formatting, export, sync, and checking logic use `note_*.py` modules. `tests/` mirrors user operations with files such as `test_op_sync.py` and focused unit tests. Root-level files include `pyproject.toml`, `poetry.lock`, `Dockerfile`, `evernote-backup.spec`, `README.md`, and release/history docs.

## Build, Test, and Development Commands

- `uv sync --group dev`: install runtime, development, and test dependencies.
- `uv run evernote-backup --help`: run the CLI from the working tree.
- `uv run --group test pytest`: run the full test suite.
- `uv run --group test pytest --cov=evernote_backup`: run tests with coverage.
- `uv run --group dev ruff format evernote_backup tests`: format Python files.
- `uv run --group dev ruff check evernote_backup tests`: lint Python files.
- `uv run --group dev pre-commit run --all-files`: run validation hooks.

## Coding Style & Naming Conventions

Target Python `>=3.9`. Use Ruff formatting with LF line endings and the Black-compatible 88-column style in `pyproject.toml`. Use absolute imports; relative imports are banned. Keep module names lowercase with underscores, matching files like `note_storage.py`. Name tests `test_*.py`, and test functions `test_*`. Prefer typed function definitions in package code; mypy rejects untyped and incomplete definitions.

## Testing Guidelines

The suite uses pytest, `pytest-mock`, and `pytest-cov`. Add regression tests near the behavior being changed: operation-level CLI flows belong in `tests/test_op_*.py`, while focused module behavior should use `tests/test_<module>.py`. Avoid live Evernote calls; use fixtures and mocks from `tests/conftest.py`. Run `poetry run pytest` before submitting changes, and use coverage when touching sync, export, auth, or storage code.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit style, for example `fix: skip parsing unused token parameters`, `build: update pre-commit config`, and `ci(github): add separate x64 and arm64 builds for macos`. Use short imperative subjects with a type such as `fix`, `feat`, `chore`, `build`, or `ci`, and add a scope when helpful. Pull requests should describe the change, user-visible impact, related issues, and test results. Include CLI output or screenshots only when they clarify behavior.

## Security & Configuration Tips

Never commit Evernote credentials, auth tokens, local SQLite backups, exported `.enex` files, or generated output directories. Prefer mocked credentials in tests and document any new environment variables or network requirements in `README.md`.
