"""Contract tests for the ten confinement defects.

Each test targets exactly one defect from the task statement.  All fixtures
are built under pytest's temporary directory; no real system file is read or
written.
"""

import os

import pytest

from conf import paths


def test_defect_01_normalize_collapses_dotdot():
    assert paths.normalize("reports/../../secret.txt") == "../secret.txt"
    assert paths.normalize("a/b/../../../etc") == "../etc"
    assert paths.normalize("a/b/../c") == "a/c"
    assert paths.normalize("Reports\\Q1.TXT") == "reports/q1.txt"


def test_defect_02_within_rejects_sibling_prefix(tmp_path):
    root = tmp_path / "upload"
    sibling = tmp_path / "upload_backup"
    root.mkdir()
    sibling.mkdir()
    assert paths.within(str(root), str(sibling / "secret.txt")) is False
    assert paths.within(str(root), str(tmp_path / "upload2" / "secret.txt")) is False


def test_defect_03_within_includes_root_itself(tmp_path):
    root = tmp_path / "upload"
    root.mkdir()
    assert paths.within(str(root), str(root)) is True
    assert paths.within(str(root), str(root / "nested" / "file.txt")) is True


def test_defect_04_resolve_follows_symlink_outside(tmp_path, make_dir_link):
    root = tmp_path / "upload"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    make_dir_link(str(root / "leak"), str(outside))

    resolved = paths.resolve(str(root), "leak/secret.txt")

    assert resolved == os.path.realpath(outside / "secret.txt")
    assert paths.within(str(root), resolved) is False


def test_defect_05_check_symlink_compares_target(tmp_path, make_dir_link):
    root = tmp_path / "upload"
    outside = tmp_path / "outside"
    root.mkdir()
    (outside / "same").mkdir(parents=True)
    (root / "inside.txt").write_text("inside", encoding="utf-8")
    make_dir_link(str(root / "same"), str(outside / "same"))

    assert paths.check_symlink(str(root), "same") is False
    assert paths.check_symlink(str(root), "inside.txt") is True


def test_defect_06_absolute_drive_escape_detected(tmp_path):
    (tmp_path / "upload").mkdir()
    assert paths.is_absolute_escape("/etc/passwd") is True
    assert paths.is_absolute_escape("\\\\server\\share\\secret.txt") is True
    assert paths.is_absolute_escape("C:\\Windows\\win.ini") is True
    assert paths.is_absolute_escape("D:relative.txt") is True
    assert paths.is_absolute_escape("safe/file.txt") is False
    with pytest.raises(ValueError):
        paths.safe_join(str(tmp_path / "upload"), "C:\\Windows\\win.ini")


def test_defect_07_normalize_folds_unicode_slash():
    assert paths.normalize("..／..／secret.txt") == "../../secret.txt"
    assert paths.normalize("..＼..＼secret.txt") == "../../secret.txt"
    assert paths.normalize("ＡＢＣ／ｒｅｐｏｒｔ．ｔｘｔ") == "abc/report.txt"


def test_defect_08_validate_policy_rejects_absolute_allowance(tmp_path):
    root = str(tmp_path / "uploads")
    good = {"root": root, "resolve_symlinks": True, "allow_absolute": False}
    assert paths.validate_policy(good) == []

    bad = dict(good, allow_absolute=True)
    assert paths.validate_policy(bad) == ["absolute paths are allowed"]

    broken = {"root": "", "resolve_symlinks": False, "allow_absolute": True}
    assert paths.validate_policy(broken) == [
        "symlinks are not resolved",
        "root is not restricted",
        "absolute paths are allowed",
    ]


def test_defect_09_join_batch_uses_each_calls_root(tmp_path):
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    root_b.mkdir()

    first = paths.join_batch(str(root_a), ["one.txt"])
    second = paths.join_batch(str(root_b), ["two.txt"])

    assert first == {"one.txt": os.path.realpath(root_a / "one.txt")}
    assert second == {"two.txt": os.path.realpath(root_b / "two.txt")}


def test_defect_10_safe_join_raises_on_escape(tmp_path):
    root = tmp_path / "upload"
    root.mkdir()
    with pytest.raises(ValueError):
        paths.safe_join(str(root), "../outside.txt")
