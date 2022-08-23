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
    file_name = _trim_name(Path(file_name).stem, Path(file_name).suffix)

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

        suffix = f" ({i}){orig.suffix}"
        file_name = f"{orig.stem}{suffix}"

        if len(file_name.encode("utf-8")) > MAX_FILE_NAME_LEN:
            max_len = MAX_FILE_NAME_LEN - len(suffix.encode("utf-8"))

            trimmed_name = _trim_name(orig.stem, "", max_len)
            file_name = f"{trimmed_name}{suffix}"

    return file_name


def _trim_name(file_name: str, file_ext: str, max_len: int = MAX_FILE_NAME_LEN) -> str:
    """Trim file name to 255 characters while maintaining extension
    255 characters is max file name length on linux and macOS
    Windows has a filename limit of 260 bytes

    Assuming character is one byte
    Trimming only stem, extensions stays untouched

    max_len: if provided, trims to this length otherwise MAX_FILE_NAME_LEN

    Raises: ValueError if the file name is too long and cannot be trimmed
    """
    orig_name = f"{file_name}{file_ext}"

    if len(orig_name.encode("utf-8")) <= max_len:
        return orig_name

    if file_ext:
        max_len_name = max_len - len(file_ext.encode("utf-8"))
    else:
        max_len_name = max_len

    trimmed_name = _trim_string(file_name, max_len_name)

    result_name = f"{trimmed_name}{file_ext}"

    if len(result_name.encode("utf-8")) > max_len:
        raise ValueError(
            f"File name is too long but cannot be safely trimmed: {file_name}"
        )

    return result_name


def _trim_string(string: str, max_len: int) -> str:
    if max_len <= 0:
        return ""

    chars = list(string)

    while sum(len(c.encode("utf-8")) for c in chars) > max_len:
        chars.pop(-1)

    return "".join(chars)
