"""Behavioural edge tests for the path-confinement boundary.

These five cases complement the ten defect tests.  Every fixture lives under
pytest's temporary directory, and no real system file is used.
"""

import os

import pytest

from conf import paths


def test_inside_relative_path_is_allowed(tmp_path):
    root = tmp_path / "upload"
    report = root / "reports" / "2026.txt"
    report.parent.mkdir(parents=True)
    report.write_text("preview", encoding="utf-8")

    assert paths.safe_join(str(root), "reports/2026.txt") == os.path.realpath(report)


def test_two_level_dotdot_is_rejected(tmp_path):
    root = tmp_path / "upload"
    root.mkdir()
    with pytest.raises(ValueError):
        paths.safe_join(str(root), "../../etc/passwd")


def test_symlink_to_outside_is_rejected(tmp_path, make_dir_link):
    root = tmp_path / "upload"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    make_dir_link(str(root / "leak"), str(outside))

    with pytest.raises(ValueError):
        paths.safe_join(str(root), "leak/secret.txt")


def test_fullwidth_slash_is_rejected_after_normalization(tmp_path):
    root = tmp_path / "upload"
    root.mkdir()
    with pytest.raises(ValueError):
        paths.safe_join(str(root), "..／..／secret.txt")


def test_two_batches_match_individual_joins(tmp_path):
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    root_b.mkdir()

    paths_a = ["one.txt", "sub/two.txt"]
    paths_b = ["three.txt"]

    batch_a = paths.join_batch(str(root_a), paths_a)
    batch_b = paths.join_batch(str(root_b), paths_b)

    expected_a = {item: paths.safe_join(str(root_a), item) for item in paths_a}
    expected_b = {item: paths.safe_join(str(root_b), item) for item in paths_b}

    assert batch_a == expected_a
    assert batch_b == expected_b
