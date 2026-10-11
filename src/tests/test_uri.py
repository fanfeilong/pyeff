"""Tests for pyeff.uri module."""

import pytest

from pyeff.uri import (
    URIPath,
    LocalPath,
    DockerPath,
    SSHPath,
    ArchivePath,
    local,
    docker,
    ssh,
    archive,
    parse_uri,
    resolve_path,
)


class TestLocalPath:
    def test_create_local_path(self):
        p = LocalPath("./data")
        assert p.path == "./data"
        assert p.scheme == "local"
    
    def test_to_uri(self):
        p = LocalPath("./data")
        assert p.to_uri() == "local:./data"
    
    def test_str(self):
        p = LocalPath("./data")
        assert str(p) == "./data"
    
    def test_absolute_path(self):
        p = LocalPath("/home/user/data")
        assert p.to_uri() == "local:/home/user/data"


class TestDockerPath:
    def test_create_docker_path(self):
        p = DockerPath("my-container", "/app/data")
        assert p.container == "my-container"
        assert p.path == "/app/data"
        assert p.scheme == "docker"
    
    def test_to_uri(self):
        p = DockerPath("my-container", "/app/data")
        assert p.to_uri() == "docker:my-container:/app/data"
    
    def test_str(self):
        p = DockerPath("my-container", "/app/data")
        assert str(p) == "my-container:/app/data"


class TestSSHPath:
    def test_create_ssh_path(self):
        p = SSHPath("user@host", "/var/log")
        assert p.host == "user@host"
        assert p.path == "/var/log"
        assert p.scheme == "ssh"
    
    def test_to_uri(self):
        p = SSHPath("user@host", "/var/log")
        assert p.to_uri() == "ssh:user@host:/var/log"
    
    def test_to_uri_with_port(self):
        p = SSHPath("user@host", "/var/log", port=2222)
        assert p.to_uri() == "ssh:user@host:2222:/var/log"
    
    def test_get_connection_params(self):
        p = SSHPath("user@host", "/var/log", port=2222, key="~/.ssh/id_rsa")
        params = p.get_connection_params()
        assert params["host"] == "user@host"
        assert params["port"] == 2222
        assert params["key_file"] == "~/.ssh/id_rsa"


class TestArchivePath:
    def test_create_archive_path(self):
        p = ArchivePath("./backup.zip")
        assert p.archive_path == "./backup.zip"
        assert p.inner_path is None
        assert p.scheme == "archive"
    
    def test_to_uri(self):
        p = ArchivePath("./backup.zip")
        assert p.to_uri() == "archive:./backup.zip"
    
    def test_to_uri_with_inner_path(self):
        p = ArchivePath("./backup.zip", "/config.json")
        assert p.to_uri() == "archive:./backup.zip:/config.json"


class TestPathBuilders:
    def test_local_builder(self):
        p = local("./data")
        assert isinstance(p, LocalPath)
        assert p.path == "./data"
    
    def test_docker_builder(self):
        p = docker("my-container", "/app/data")
        assert isinstance(p, DockerPath)
        assert p.container == "my-container"
        assert p.path == "/app/data"
    
    def test_ssh_builder(self):
        p = ssh("user@host", "/var/log")
        assert isinstance(p, SSHPath)
        assert p.host == "user@host"
        assert p.path == "/var/log"
    
    def test_ssh_builder_with_options(self):
        p = ssh("user@host", "/var/log", port=2222, key="~/.ssh/id_rsa")
        assert p.port == 2222
        assert p.key == "~/.ssh/id_rsa"
    
    def test_archive_builder(self):
        p = archive("./backup.zip")
        assert isinstance(p, ArchivePath)
        assert p.archive_path == "./backup.zip"
    
    def test_archive_builder_with_inner_path(self):
        p = archive("./backup.zip", "/config.json")
        assert p.inner_path == "/config.json"


class TestParseUri:
    def test_parse_local(self):
        p = parse_uri("local:./data")
        assert isinstance(p, LocalPath)
        assert p.path == "./data"
    
    def test_parse_local_absolute(self):
        p = parse_uri("local:/home/user/data")
        assert isinstance(p, LocalPath)
        assert p.path == "/home/user/data"
    
    def test_parse_docker(self):
        p = parse_uri("docker:my-container:/app/data")
        assert isinstance(p, DockerPath)
        assert p.container == "my-container"
        assert p.path == "/app/data"
    
    def test_parse_ssh(self):
        p = parse_uri("ssh:user@host:/var/log")
        assert isinstance(p, SSHPath)
        assert p.host == "user@host"
        assert p.path == "/var/log"
    
    def test_parse_ssh_with_port(self):
        p = parse_uri("ssh:user@host:2222:/var/log")
        assert isinstance(p, SSHPath)
        assert p.host == "user@host"
        assert p.port == 2222
        assert p.path == "/var/log"
    
    def test_parse_archive(self):
        p = parse_uri("archive:./backup.zip")
        assert isinstance(p, ArchivePath)
        assert p.archive_path == "./backup.zip"
    
    def test_parse_archive_with_inner_path(self):
        p = parse_uri("archive:./backup.zip:/config.json")
        assert isinstance(p, ArchivePath)
        assert p.archive_path == "./backup.zip"
        assert p.inner_path == "/config.json"
    
    def test_parse_archive_tar_gz(self):
        p = parse_uri("archive:./backup.tar.gz:/data/file.txt")
        assert isinstance(p, ArchivePath)
        assert p.archive_path == "./backup.tar.gz"
        assert p.inner_path == "/data/file.txt"
    
    def test_parse_invalid_uri(self):
        with pytest.raises(ValueError, match="Invalid URI format"):
            parse_uri("invalid")
    
    def test_parse_invalid_scheme(self):
        with pytest.raises(ValueError, match="Unknown URI scheme"):
            parse_uri("ftp:./path")
    
    def test_parse_invalid_docker(self):
        with pytest.raises(ValueError, match="Invalid docker URI"):
            parse_uri("docker:invalid")
    
    def test_parse_invalid_ssh(self):
        with pytest.raises(ValueError, match="Invalid ssh URI"):
            parse_uri("ssh:invalid")


class TestResolvePath:
    def test_resolve_uri_string(self):
        p = resolve_path("local:./data")
        assert isinstance(p, LocalPath)
        assert p.path == "./data"
    
    def test_resolve_uri_path_object(self):
        original = LocalPath("./data")
        p = resolve_path(original)
        assert p is original
    
    def test_resolve_bare_path(self):
        p = resolve_path("./data")
        assert isinstance(p, LocalPath)
        assert p.path == "./data"
    
    def test_resolve_docker_uri(self):
        p = resolve_path("docker:container:/app")
        assert isinstance(p, DockerPath)
