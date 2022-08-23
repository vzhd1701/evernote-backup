import pytest

from evernote_backup.note_exporter_util import MAX_FILE_NAME_LEN, SafePath


def test_safe_path_dir(tmp_path):
    test_dir = tmp_path / "test"
    expected_dir = tmp_path / "test" / "test1" / "test2"

    safe_path = SafePath(test_dir)
    result_dir = safe_path.get("test1", "test2")

    assert expected_dir.is_dir()
    assert result_dir == expected_dir


def test_safe_path_dir_existing(tmp_path):
    test_dir = tmp_path / "test"

    existing_dir = tmp_path / "test" / "test1" / "test2"
    existing_dir.mkdir(parents=True)

    expected_dir = tmp_path / "test" / "test1" / "test2 (1)"

    safe_path = SafePath(test_dir)
    result_dir = safe_path.get("test1", "test2")

    assert expected_dir.is_dir()
    assert result_dir == expected_dir


def test_safe_path_dir_existing_overwrite(tmp_path):
    test_dir = tmp_path / "test"

    existing_dir = tmp_path / "test" / "test1" / "test2"
    existing_dir.mkdir(parents=True)

    safe_path = SafePath(test_dir, overwrite=True)
    result_dir = safe_path.get("test1", "test2")

    assert result_dir == existing_dir


def test_safe_path_file(tmp_path):
    test_dir = tmp_path / "test"
    expected_file = tmp_path / "test" / "test1" / "test2" / "test3.txt"

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file("test1", "test2", "test3.txt")

    assert expected_file.parent.is_dir()
    assert not expected_file.exists()
    assert result_file_path == expected_file


def test_safe_path_file_existing(tmp_path):
    test_dir = tmp_path / "test"

    existing_file = tmp_path / "test" / "test1" / "test2" / "test3.txt"
    existing_file.parent.mkdir(parents=True)
    existing_file.touch()

    expected_file = tmp_path / "test" / "test1" / "test2" / "test3 (1).txt"

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file("test1", "test2", "test3.txt")

    assert expected_file.parent.is_dir()
    assert not expected_file.exists()
    assert result_file_path == expected_file


def test_safe_path_file_existing_overwrite(tmp_path):
    test_dir = tmp_path / "test"

    existing_file = tmp_path / "test" / "test1" / "test2" / "test3.txt"
    existing_file.parent.mkdir(parents=True)
    existing_file.touch()

    safe_path = SafePath(test_dir, overwrite=True)
    result_file_path = safe_path.get_file("test1", "test2", "test3.txt")

    assert result_file_path == existing_file


def test_safe_path_bad_names(tmp_path):
    test_dir = tmp_path / "test"

    expected_dir1 = tmp_path / "test" / "test1" / "test2_________"
    expected_dir2 = tmp_path / "test" / "test1" / "test2_________ (1)"

    safe_path = SafePath(test_dir)
    result_path1 = safe_path.get("test1", r'test2<>:"/\|?*')
    result_path2 = safe_path.get("test1", r'test2/\|?*<>:"')

    assert expected_dir1.is_dir()
    assert result_path1 == expected_dir1
    assert expected_dir2.is_dir()
    assert result_path2 == expected_dir2


def test_safe_path_long_file_name(tmp_path):
    """Test that SafePath trims a long file name with extension"""
    test_dir = tmp_path / "test"

    test_ext = ".ext"
    long_file_name = "X" * MAX_FILE_NAME_LEN + test_ext
    expected_file_name = "X" * (MAX_FILE_NAME_LEN - len(test_ext)) + test_ext
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file("test1", long_file_name)

    result_file_path.touch()

    assert expected_file.is_file()
    assert result_file_path == expected_file


def test_safe_path_long_file_name_existing(tmp_path):
    """Test that SafePath trims an existing long file name with extension"""
    test_dir = tmp_path / "test"

    test_ext = ".ext"
    long_file_name = "X" * (MAX_FILE_NAME_LEN - len(test_ext)) + test_ext
    long_file = tmp_path / "test" / long_file_name

    expected_file_name = (
        "X" * (MAX_FILE_NAME_LEN - len(test_ext) - 4) + " (1)" + test_ext
    )
    expected_file = tmp_path / "test" / expected_file_name

    long_file.parent.mkdir(parents=True)
    long_file.touch()

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file(long_file_name)

    result_file_path.touch()

    assert expected_file.is_file()
    assert result_file_path == expected_file


def test_safe_path_long_file_name_no_ext(tmp_path):
    """Test that SafePath trims a long file name with no extension"""
    test_dir = tmp_path / "test"

    slightly_longer_than_supported = MAX_FILE_NAME_LEN + 10

    long_file_name = "X" * slightly_longer_than_supported
    expected_file_name = "X" * MAX_FILE_NAME_LEN
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file("test1", long_file_name)

    result_file_path.touch()

    assert expected_file.is_file()
    assert result_file_path == expected_file


def test_safe_path_long_file_name_existing_unicode(tmp_path):
    """Test that SafePath trims a long file name with no extension"""
    test_dir = tmp_path / "test"

    slightly_longer_than_supported = MAX_FILE_NAME_LEN * 2

    long_file_name = ("😁" * slightly_longer_than_supported) + ".enex"

    expected_file_name = ("😁" * 61) + " (1).enex"
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file("test1", long_file_name)
    result_file_path.touch()

    result_file_path_repeat = safe_path.get_file("test1", long_file_name)
    result_file_path_repeat.touch()

    assert expected_file.is_file()
    assert result_file_path_repeat == expected_file


def test_safe_path_long_file_name_no_ext_unicode(tmp_path):
    """Test that SafePath trims a long file name with no extension"""
    test_dir = tmp_path / "test"

    slightly_longer_than_supported = MAX_FILE_NAME_LEN * 2

    long_file_name = "😁" * slightly_longer_than_supported
    expected_file_name = "😁" * 63
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file("test1", long_file_name)

    result_file_path.touch()

    assert expected_file.is_file()
    assert result_file_path == expected_file


def test_safe_path_long_file_name_invalid(tmp_path):
    """Test that SafePath raises ValueError if path is too long but cannot be trimmed"""
    test_dir = tmp_path / "test"
    bad_file_name = "X" + "." + "x" * MAX_FILE_NAME_LEN

    safe_path = SafePath(test_dir)
    with pytest.raises(ValueError):
        safe_path.get_file("test1", bad_file_name)


def test_safe_path_no_trim(tmp_path):
    """Test that the SafePath does not trim the path if the path is not too long"""
    test_dir = tmp_path / "test"
    max_file_name = "X" * 251 + ".ext"
    expected_file_name = max_file_name
    expected_file = tmp_path / "test" / "test1" / expected_file_name

    safe_path = SafePath(test_dir)
    result_file_path = safe_path.get_file("test1", max_file_name)

    expected_file.touch()

    assert expected_file.is_file()
    assert result_file_path == expected_file
