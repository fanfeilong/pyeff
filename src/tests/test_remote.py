"""Tests for pyeff.remote module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import subprocess

from pyeff.remote.base import (
    PatternFilter,
    RemoteFileInfo,
    RemoteError,
    RemoteConnectionError,
    RemoteFileNotFoundError,
)

from pyeff.remote.docker import (
    DockerRemote,
    docker,
    docker_copy,
    docker_search,
    docker_exists,
    docker_remove,
    _parse_container_path,
)


class TestPatternFilter:
    def test_filter_all(self):
        f = PatternFilter(mode="all")
        assert f.match("file.txt") is True
        assert f.match("file.py") is True

    def test_filter_include(self):
        f = PatternFilter(mode="include", patterns=["*.txt"])
        assert f.match("file.txt") is True
        assert f.match("file.py") is False

    def test_filter_ignore(self):
        f = PatternFilter(mode="ignore", patterns=["*.txt"])
        assert f.match("file.txt") is False
        assert f.match("file.py") is True

    def test_filter_multiple_patterns(self):
        f = PatternFilter(mode="include", patterns=["*.txt", "*.md"])
        assert f.match("file.txt") is True
        assert f.match("file.md") is True
        assert f.match("file.py") is False

    def test_filter_path_with_dir(self):
        f = PatternFilter(mode="include", patterns=["*.txt"])
        assert f.match("/path/to/file.txt") is True
        assert f.match("/path/to/file.py") is False

    def test_filter_generator(self):
        f = PatternFilter(mode="include", patterns=["*.txt"])
        names = ["a.txt", "b.py", "c.txt", "d.md"]
        result = list(f.filter(names))
        assert result == ["a.txt", "c.txt"]


class TestRemoteFileInfo:
    def test_create_file_info(self):
        info = RemoteFileInfo(
            name="test.txt",
            path="/path/to/test.txt",
            size=100,
            is_dir=False,
            is_file=True,
        )
        assert info.name == "test.txt"
        assert info.size == 100
        assert info.is_file is True
        assert info.is_dir is False


class TestParseContainerPath:
    def test_parse_container_path(self):
        container, path = _parse_container_path("my-container:/app/data")
        assert container == "my-container"
        assert path == "/app/data"

    def test_parse_local_path(self):
        container, path = _parse_container_path("/local/path")
        assert container is None
        assert path == "/local/path"

    def test_parse_relative_path(self):
        container, path = _parse_container_path("./local/path")
        assert container is None
        assert path == "./local/path"

    def test_parse_windows_style_ignored(self):
        container, path = _parse_container_path("C:/path")
        assert container is None


class TestDockerRemoteMocked:
    @pytest.fixture
    def mock_docker(self):
        """Create a mocked DockerRemote."""
        with patch("pyeff.remote.docker._run_docker") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="true\n",
                stderr="",
            )
            docker = DockerRemote("test-container")
            docker._verified = True
            yield docker, mock_run

    def test_exists_true(self, mock_docker):
        docker, mock_run = mock_docker
        mock_run.return_value = Mock(returncode=0)
        
        with patch.object(docker, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=0)
            assert docker.exists("/app/data") is True

    def test_exists_false(self, mock_docker):
        docker, mock_run = mock_docker
        
        with patch.object(docker, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=1)
            assert docker.exists("/nonexistent") is False

    def test_is_file(self, mock_docker):
        docker, mock_run = mock_docker
        
        with patch.object(docker, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=0)
            assert docker.is_file("/app/file.txt") is True

    def test_is_dir(self, mock_docker):
        docker, mock_run = mock_docker
        
        with patch.object(docker, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=0)
            assert docker.is_dir("/app/data") is True


class TestDockerFunctions:
    def test_docker_copy_invalid_paths(self):
        """Test that docker_copy raises error for invalid paths."""
        with pytest.raises(RemoteError, match="container path"):
            docker_copy("/local/path1", "/local/path2")

    def test_docker_copy_container_to_container(self):
        """Test that container-to-container copy raises error."""
        with pytest.raises(RemoteError, match="not supported"):
            docker_copy("container1:/path", "container2:/path")

    def test_docker_remove_invalid_path(self):
        """Test that docker_remove raises error for local path."""
        with pytest.raises(RemoteError, match="container:path"):
            docker_remove("/local/path")

    def test_docker_search_invalid_path(self):
        """Test that docker_search raises error for local path."""
        with pytest.raises(RemoteError, match="container:path"):
            docker_search("/local/path")

    def test_docker_exists_invalid_path(self):
        """Test that docker_exists raises error for local path."""
        with pytest.raises(RemoteError, match="container:path"):
            docker_exists("/local/path")


class TestDockerIntegration:
    """Integration tests that require Docker (skipped if Docker not available)."""

    @pytest.fixture
    def docker_available(self):
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("Docker not available")

    def test_docker_not_found_error(self):
        """Test error when container doesn't exist."""
        with patch("pyeff.remote.docker._run_docker") as mock_run:
            mock_run.side_effect = RemoteConnectionError("Container not found")
            
            with pytest.raises(RemoteConnectionError):
                with DockerRemote("nonexistent-container") as docker:
                    pass


class TestSSHImport:
    def test_ssh_import_without_paramiko(self):
        """Test that SSH module handles missing paramiko gracefully."""
        from pyeff.remote import SSH_AVAILABLE
        
        if SSH_AVAILABLE:
            from pyeff.remote.ssh import SSHRemote, ssh_connect
            assert SSHRemote is not None
            assert ssh_connect is not None


class TestRemoteExceptions:
    def test_remote_error(self):
        with pytest.raises(RemoteError):
            raise RemoteError("test error")

    def test_remote_connection_error(self):
        with pytest.raises(RemoteConnectionError):
            raise RemoteConnectionError("connection failed")

    def test_remote_file_not_found_error(self):
        with pytest.raises(RemoteFileNotFoundError):
            raise RemoteFileNotFoundError("file not found")

    def test_exception_inheritance(self):
        """Test that specific errors inherit from RemoteError."""
        with pytest.raises(RemoteError):
            raise RemoteConnectionError("test")
        
        with pytest.raises(RemoteError):
            raise RemoteFileNotFoundError("test")


class TestDockerFactory:
    """Test the docker() factory function."""
    
    def test_docker_factory_returns_docker_remote(self):
        """Test that docker() returns DockerRemote instance."""
        d = docker("my-container")
        assert isinstance(d, DockerRemote)
        assert d.container == "my-container"
    
    def test_docker_factory_usage_pattern(self):
        """Test the intended usage pattern with docker()."""
        from pyeff.remote import docker as docker_factory
        
        d = docker_factory("my-container")
        assert hasattr(d, "copy")
        assert hasattr(d, "copy_from")
        assert hasattr(d, "copy_to")
        assert hasattr(d, "remove")
        assert hasattr(d, "search")
        assert hasattr(d, "exists")


class TestUnifiedCopyMethod:
    """Test the unified copy() method on DockerRemote."""
    
    @pytest.fixture
    def mock_docker(self):
        """Create a mocked DockerRemote."""
        with patch("pyeff.remote.docker._run_docker") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            d = DockerRemote("test-container")
            d._verified = True
            yield d, mock_run
    
    def test_copy_detects_remote_to_local(self, mock_docker):
        """Test that copy() detects remote (absolute) → local (relative)."""
        d, mock_run = mock_docker
        
        with patch.object(d, "copy_from") as mock_copy_from:
            mock_copy_from.return_value = 5
            result = d.copy("/app/logs", "./logs")
            
            mock_copy_from.assert_called_once()
            args = mock_copy_from.call_args
            assert args[0][0] == "/app/logs"
            assert args[0][1] == "./logs"
    
    def test_copy_detects_local_to_remote(self, mock_docker):
        """Test that copy() detects local (relative) → remote (absolute)."""
        d, mock_run = mock_docker
        
        with patch.object(d, "copy_to") as mock_copy_to:
            mock_copy_to.return_value = 3
            result = d.copy("./config", "/app/config")
            
            mock_copy_to.assert_called_once()
            args = mock_copy_to.call_args
            assert args[0][0] == "./config"
            assert args[0][1] == "/app/config"
    
    def test_copy_both_remote_raises(self, mock_docker):
        """Test that copy() raises when both paths look remote."""
        d, mock_run = mock_docker
        
        with pytest.raises(RemoteError, match="Both paths appear to be container"):
            d.copy("/app/src", "/app/dst")
    
    def test_copy_both_local_raises(self, mock_docker):
        """Test that copy() raises when both paths look local."""
        d, mock_run = mock_docker
        
        with pytest.raises(RemoteError, match="Both paths appear to be local"):
            d.copy("./src", "./dst")


class TestSSHUnifiedAPI:
    """Test the unified SSH API if paramiko is available."""
    
    def test_ssh_factory_function_exists(self):
        """Test that ssh() factory function exists."""
        from pyeff.remote import SSH_AVAILABLE
        
        if SSH_AVAILABLE:
            from pyeff.remote.ssh import ssh
            
            assert callable(ssh)
    
    def test_ssh_remote_has_copy_method(self):
        """Test that SSHRemote has unified copy() method."""
        from pyeff.remote import SSH_AVAILABLE
        
        if SSH_AVAILABLE:
            from pyeff.remote.ssh import SSHRemote
            
            assert hasattr(SSHRemote, "copy")
            assert hasattr(SSHRemote, "copy_from")
            assert hasattr(SSHRemote, "copy_to")
