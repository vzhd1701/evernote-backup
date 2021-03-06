from pathlib import Path
from typing import Dict, Tuple

MAX_FILE_NAME_LEN = 255


class SafePath(object):
    """Ensures path for tuples of directory names that may contain bad symbols

    Use case:
    safe_path.get("test_dir") == base_dir/test_dir
    safe_path.get("test_dir?|") == base_dir/test_dir__
    safe_path.get("test_dir||") == base_dir/test_dir__ (1)
    """

    def __init__(self, base_dir: Path, overwrite: bool = False) -> None:
        self.safe_paths: Dict[Tuple[str, ...], Path] = {}

        self.main_base_dir = base_dir
        self.overwrite = overwrite

    def get_file(self, *paths: str) -> Path:
        return self._get(*paths, is_dir=False, overwrite=self.overwrite)

    def get(self, *paths: str) -> Path:
        return self._get(*paths, is_dir=True, overwrite=self.overwrite)

    def _get(self, *paths: str, is_dir: bool, overwrite: bool) -> Path:
        if paths in self.safe_paths:
            return self.safe_paths[paths]  # noqa: WPS529

        if len(paths) > 1:
            # Create all parent dirs
            parent_dir = paths[:-1]
            base_dir = self._get(*parent_dir, is_dir=True, overwrite=True)
        else:
            _ensure_path(self.main_base_dir)
            base_dir = self.main_base_dir

        this_path = paths[-1]

        safe_path = _get_safe_path(base_dir, this_path, overwrite)

        if is_dir:
            safe_path.mkdir(exist_ok=True)
            self.safe_paths[paths] = safe_path

        return safe_path


def _get_safe_path(target_dir: Path, new_name: str, overwrite: bool = False) -> Path:
    file_name = _replace_bad_characters(new_name)
    file_name = _trim_name(file_name)

    if not overwrite:
        file_name = _get_non_existant_name(file_name, target_dir)

    return target_dir / file_name


def _ensure_path(output_path: Path) -> None:
    if not output_path.is_dir():
        output_path.mkdir(parents=True)


def _replace_bad_characters(string: str) -> str:
    bad = r'<>:"/\|?*'

    result_string = string
    for b in bad:
        result_string = result_string.replace(b, "_")

    return result_string


def _get_non_existant_name(file_name: str, target_dir: Path) -> str:
    i = 0
    orig = Path(file_name)
    while (target_dir / file_name).exists():
        i += 1
        file_name = f"{orig.stem} ({i}){orig.suffix}"
        if len(file_name) > MAX_FILE_NAME_LEN:
            max_len = MAX_FILE_NAME_LEN - len(f" ({i}){orig.suffix}")

            trimmed_name = _trim_name(orig.stem, max_len)
            file_name = f"{trimmed_name} ({i}){orig.suffix}"

    return file_name


def _trim_name(file_name: str, max_len: int = MAX_FILE_NAME_LEN) -> str:
    """Trim file name to 255 characters while maintaining extension
    255 characters is max file name length on linux and macOS
    Windows has a path limit of 260 characters which includes
    the entire path (drive letter, path, and file name)
    This does not trim the path length, just the file name

    max_len: if provided, trims to this length otherwise MAX_FILE_NAME_LEN

    Raises: ValueError if the file name is too long and cannot be trimmed
    """
    if len(file_name) <= max_len:
        return file_name

    orig = Path(file_name)

    drop_chars = len(file_name) - max_len
    trimmed_name = orig.stem[:-drop_chars]

    if not orig.suffix:
        return trimmed_name
    if len(orig.stem) > drop_chars:
        return f"{trimmed_name}{orig.suffix}"

    raise ValueError(f"File name is too long but cannot be safely trimmed: {file_name}")
