import os
from typing import Dict


class SafePath(object):
    """Ensures path for tuples of directory names that may contain bad symbols

    Use case:
    safe_path.get("test_dir") == base_dir/test_dir
    safe_path.get("test_dir?|") == base_dir/test_dir__
    safe_path.get("test_dir||") == base_dir/test_dir__ (1)
    """

    def __init__(self, base_dir: str) -> None:
        self.main_base_dir = base_dir
        self.safe_paths: Dict[tuple, str] = {}

    def get_file(self, *paths: str) -> str:
        return self.get(*paths, is_dir=False)

    def get(self, *paths: str, is_dir: bool = True) -> str:
        if paths in self.safe_paths:
            return self.safe_paths[paths]  # noqa: WPS529

        if len(paths) > 1:
            parent_dir = paths[:-1]
            base_dir = self.get(*parent_dir)
        else:
            base_dir = _verify_path(self.main_base_dir)

        this_dir = paths[-1]

        safe_path = _get_safe_path(base_dir, this_dir)

        if is_dir:
            os.mkdir(safe_path)
            self.safe_paths[paths] = safe_path

        return safe_path


def _get_safe_path(target_dir: str, new_name: str) -> str:
    safe_name = _replace_bad_characters(new_name)

    safe_name = _get_non_existant_name(safe_name, target_dir)

    return os.path.join(target_dir, safe_name)


def _verify_path(output_path: str) -> str:
    output_path = os.path.normpath(output_path)
    if not os.path.exists(output_path) or not os.path.isdir(output_path):
        os.makedirs(output_path)
    return output_path


def _replace_bad_characters(string: str) -> str:
    bad = r'<>:"/\|?*'

    result_string = string
    for b in bad:
        result_string = result_string.replace(b, "_")

    return result_string


def _get_non_existant_name(safe_name: str, target_dir: str) -> str:
    i = 0
    o_name, o_ext = os.path.splitext(safe_name)
    while os.path.exists(os.path.join(target_dir, safe_name)):
        i += 1
        safe_name = f"{o_name} ({i}){o_ext}"
    return safe_name
