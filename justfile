default:
    just --list

build:
    uv build

bench:
    uv run pytest -m slow -s tests/test_memory_benchmark.py

build-requirements:
    uv pip compile pyproject.toml -q --universal --no-annotate --no-header -o build/requirements.txt

changelog:
    conventional-changelog -p conventionalcommits -u -i /dev/null --stdout

changelog-all:
    conventional-changelog -u -i /dev/null --stdout

release:
    commit-and-tag-version

release-dry:
    commit-and-tag-version --dry-run

update-actions:
    actions-up --style preserve -y
