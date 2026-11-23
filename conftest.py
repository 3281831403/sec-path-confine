"""Make the repository root importable and provide a directory-link helper."""

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _make_dir_link(link: str, target: str) -> None:
    """Create a directory link, falling back to an NTFS junction.

    Windows only grants ``os.symlink`` to elevated or developer-mode
    processes.  A junction is an equally valid reparse-point escape for these
    tests and can be created without elevation.  Both forms are resolved by
    ``os.path.realpath``, so the path contract treats them the same way.
    """
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except OSError:
        if os.name != "nt":
            raise

    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", link, target],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("could not create a directory link for the test")


@pytest.fixture
def make_dir_link():
    """Return a helper that creates a symlink or junction to a directory."""
    return _make_dir_link
