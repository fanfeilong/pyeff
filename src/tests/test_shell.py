"""Tests for pyeff.shell module."""

import pytest
import subprocess
from pathlib import Path

from pyeff.shell import (
    run,
    run_cmds,
    run_output,
    which,
    is_command_available,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


class TestRun:
    def test_run_simple_command(self):
        result = run("echo hello", capture=True)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_run_with_cwd(self, temp_dir):
        result = run("pwd", cwd=temp_dir, capture=True)
        assert result.returncode == 0
        assert str(temp_dir) in result.stdout

    def test_run_failing_command(self):
        result = run("exit 1", capture=True)
        assert result.returncode == 1

    def test_run_check_raises(self):
        with pytest.raises(subprocess.CalledProcessError):
            run("exit 1", check=True)


class TestRunCmds:
    def test_run_cmds_single(self, temp_dir):
        (temp_dir / "test.txt").write_text("hello")
        result = run_cmds("ls", cwd=temp_dir)
        assert result == [0]

    def test_run_cmds_list(self, temp_dir):
        results = run_cmds(["echo a", "echo b"], cwd=temp_dir)
        assert results == [0, 0]

    def test_run_cmds_join(self, temp_dir):
        result = run_cmds(["echo a", "echo b"], cwd=temp_dir, join=True)
        assert result == 0

    def test_run_cmds_check_raises(self, temp_dir):
        with pytest.raises(subprocess.CalledProcessError):
            run_cmds("exit 1", check=True)


class TestRunOutput:
    def test_run_output(self):
        result = run_output("echo hello")
        assert result == "hello"

    def test_run_output_with_cwd(self, temp_dir):
        result = run_output("pwd", cwd=temp_dir)
        assert str(temp_dir) in result


class TestWhich:
    def test_which_existing(self):
        result = which("ls")
        assert result is not None
        assert result.exists()

    def test_which_nonexistent(self):
        result = which("nonexistent_command_xyz")
        assert result is None


class TestIsCommandAvailable:
    def test_is_command_available_existing(self):
        assert is_command_available("ls") is True

    def test_is_command_available_nonexistent(self):
        assert is_command_available("nonexistent_command_xyz") is False
