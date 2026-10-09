"""Pytest configuration and shared fixtures."""

import os
import sys
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def test_data_dir():
    """Return the test data directory."""
    return Path(__file__).parent / "data_1"


@pytest.fixture
def clean_build_dir(project_root):
    """Create a clean build directory for tests."""
    build_dir = project_root / "build"
    if build_dir.exists():
        import shutil
        shutil.rmtree(build_dir)
    build_dir.mkdir(exist_ok=True)
    yield build_dir
    if build_dir.exists():
        import shutil
        shutil.rmtree(build_dir)
