import os

import pytest

from evernote_backup import note_exporter_util
from evernote_backup.note_exporter_util import (
    SafePath,
    _get_non_existant_name,
    _get_safe_path,
    _replace_bad_characters,
    _verify_path,
)


def test_safe_path_dir(tmp_path):
    test_dir = tmp_path / "test"
    expected_dir = tmp_path / "test" / "test1" / "test2"

    safe_path = SafePath(str(test_dir))
    result_dir = safe_path.get("test1", "test2")

    assert expected_dir.is_dir()
    assert result_dir == str(expected_dir)


def test_safe_path_file(tmp_path):
    test_dir = tmp_path / "test"
    expected_file = tmp_path / "test" / "test1" / "test2" / "test3.txt"

    safe_path = SafePath(str(test_dir))
    result_file_path = safe_path.get_file("test1", "test2", "test3.txt")

    expected_file.touch()

    assert expected_file.is_file()
    assert result_file_path == str(expected_file)


def test_safe_path_bad_names(tmp_path):
    test_dir = tmp_path / "test"

    expected_dir1 = tmp_path / "test" / "test1" / "test2_"
    expected_dir2 = tmp_path / "test" / "test1" / "test2_ (1)"

    safe_path = SafePath(str(test_dir))
    result_path1 = safe_path.get("test1", "test2|")
    result_path2 = safe_path.get("test1", "test2?")

    assert expected_dir1.is_dir()
    assert result_path1 == str(expected_dir1)
    assert expected_dir2.is_dir()
    assert result_path2 == str(expected_dir2)


def test_get_safe_path():
    test_path = ("test1", "test2")
    expected_result = os.path.join(*test_path)
    result = _get_safe_path(*test_path)

    assert expected_result == result


def test_safe_path_long_file_name(tmp_path):
    """Test that SafePath trims a long file name with extension"""
    test_dir = tmp_path / "test"
    long_file_name = "X" * 255 + ".ext"
    expected_file_name = "X" * 251 + ".ext"
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(str(test_dir))
    result_file_path = safe_path.get_file("test1", long_file_name)

    expected_file.touch()

    assert expected_file.is_file()
    assert result_file_path == str(expected_file)


def test_safe_path_long_file_name_no_ext(tmp_path):
    """Test that SafePath trims a long file name with no extension"""
    test_dir = tmp_path / "test"
    long_file_name = "X" * 260
    expected_file_name = "X" * 255
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(str(test_dir))
    result_file_path = safe_path.get_file("test1", long_file_name)

    expected_file.touch()

    assert expected_file.is_file()
    assert result_file_path == str(expected_file)


def test_safe_path_long_file_name_invalid(tmp_path):
    """Test that SafePath raises ValueError if path is too long but cannot be trimmed"""
    test_dir = tmp_path / "test"
    bad_file_name = "X" + "." + "x" * 255

    safe_path = SafePath(str(test_dir))
    with pytest.raises(ValueError):
        safe_path.get_file("test1", bad_file_name)


def test_safe_path_no_trim(tmp_path):
    """Test that the SafePath does not trim the path if the path is not too long"""
    test_dir = tmp_path / "test"
    max_file_name = "X" * 251 + ".ext"
    expected_file_name = max_file_name
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(str(test_dir))
    result_file_path = safe_path.get_file("test1", max_file_name)

    expected_file.touch()

    assert expected_file.is_file()
    assert result_file_path == str(expected_file)


def test_get_non_existant_name_first(mocker):
    mock_file_check = mocker.patch("evernote_backup.note_exporter_util.os.path.exists")
    mock_file_check.return_value = False

    initial_name = "test"
    expected_filename = initial_name
    result_filename = _get_non_existant_name(initial_name, "fake_dir")

    assert expected_filename == result_filename


def test_get_non_existant_name(mocker):
    mock_file_check = mocker.patch("evernote_backup.note_exporter_util.os.path.exists")
    mock_file_check.side_effect = [True, True, False]

    initial_name = "test"
    expected_filename = initial_name + " (2)"
    result_filename = _get_non_existant_name(initial_name, "fake_dir")

    assert expected_filename == result_filename


def test_get_non_existant_name_trim(mocker):
    """Test _get_non_existant_name() trims the file name if it is too long"""
    initial_name = "X" * 255 + ".ext"
    expected_filename = "X" * 251 + ".ext"
    result_filename = _get_non_existant_name(initial_name, "fake_dir")

    assert expected_filename == result_filename


def test_get_non_existant_name_trim_bad_name(mocker):
    """Test _get_non_existant_name() trims the file name if it is too long after incrementing"""
    mock_file_check = mocker.patch("evernote_backup.note_exporter_util.os.path.exists")
    mock_file_check.side_effect = [True, True, False]
    initial_name = "X" * 251 + ".ext"
    expected_filename = "X" * 247 + " (2).ext"
    result_filename = _get_non_existant_name(initial_name, "fake_dir")

    assert expected_filename == result_filename


def test_replace_bad_characters():
    initial_name = r'test<>:"/\|?*'
    expected_filename = r"test_________"
    result_filename = _replace_bad_characters(initial_name)

    assert expected_filename == result_filename


def test_verify_path(monkeypatch, mocker):
    monkeypatch.setattr(note_exporter_util.os.path, "exists", lambda x: False)
    monkeypatch.setattr(note_exporter_util.os.path, "isdir", lambda x: False)

    mock_makedirs = mocker.patch("evernote_backup.note_exporter_util.os.makedirs")

    expected_path = "fake_path"
    result_path = _verify_path(expected_path)

    assert expected_path == result_path
    mock_makedirs.assert_called_once_with(expected_path)
