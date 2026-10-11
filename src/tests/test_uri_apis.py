"""Tests for URI support across all public path APIs."""

import zipfile
from pathlib import Path

import pytest

from pyeff import (
    copy,
    remove,
    search,
    exists,
    listdir,
    read,
    write,
    move,
    file_size,
    ensure,
    is_empty_dir,
    tree,
    walk,
    load_json,
    dump_json,
    load_yaml,
    dump_yaml,
    load_all_text,
    dump_all_text,
    load_lines,
    dump_lines,
    hash_file,
)
from pyeff.uri import resolve_path, looks_like_uri, join_uri, LocalPath, ArchivePath


@pytest.fixture
def sample_tree(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("aaa")
    (src / "b.json").write_text('{"k": 1}')
    (src / "c.yml").write_text("k: 1\n")
    sub = src / "sub"
    sub.mkdir()
    (sub / "d.txt").write_text("ddd")
    return src


class TestResolvePathBare:
    def test_bare_relative(self):
        p = resolve_path("./data")
        assert isinstance(p, LocalPath)
        assert p.path == "./data"

    def test_path_object(self):
        p = resolve_path(Path("data"))
        assert isinstance(p, LocalPath)

    def test_windows_drive_not_scheme(self):
        assert not looks_like_uri("c:/windows")
        p = resolve_path("c:/windows")
        assert isinstance(p, LocalPath)

    def test_join_uri_local(self):
        assert join_uri("local:./cfg", "a.yml") == "local:./cfg/a.yml"


class TestContentApis:
    def test_json_uri_roundtrip(self, tmp_path):
        path = tmp_path / "cfg.json"
        dump_json({"x": 2}, f"local:{path}")
        assert load_json(f"local:{path}") == {"x": 2}
        assert load_json(path) == {"x": 2}

    def test_json_archive(self, tmp_path):
        arc = tmp_path / "d.zip"
        with zipfile.ZipFile(arc, "w") as zf:
            zf.writestr("cfg.json", '{"a": 3}')
        assert load_json(f"archive:{arc}:/cfg.json") == {"a": 3}
        dump_json({"b": 4}, f"archive:{arc}:/cfg.json")
        assert load_json(f"archive:{arc}:/cfg.json") == {"b": 4}

    def test_yaml_uri_roundtrip(self, tmp_path):
        path = tmp_path / "cfg.yml"
        dump_yaml({"x": 2}, f"local:{path}")
        assert load_yaml(f"local:{path}") == {"x": 2}

    def test_text_and_lines(self, tmp_path):
        path = tmp_path / "t.txt"
        dump_all_text("hello\nworld\n", f"local:{path}")
        assert load_all_text(f"local:{path}") == "hello\nworld\n"
        dump_lines(["a", "b"], f"local:{path}", append_newline=True)
        assert load_lines(f"local:{path}", remove_newline=True) == ["a", "b"]

    def test_hash_file_uri(self, tmp_path):
        path = tmp_path / "h.txt"
        path.write_text("hashme")
        h1 = hash_file(path)
        h2 = hash_file(f"local:{path}")
        assert h1 == h2


class TestDiscoveryApis:
    def test_tree_walk_file_size(self, sample_tree):
        t = tree(f"local:{sample_tree}")
        assert "a.txt" in t
        assert "sub" in t
        files = walk(f"local:{sample_tree}")
        assert any(str(f).endswith("a.txt") for f in files)
        assert file_size(f"local:{sample_tree / 'a.txt'}") == 3

    def test_ensure_and_empty(self, tmp_path):
        d = tmp_path / "newdir"
        ensured = ensure(f"local:{d}")
        assert Path(ensured).exists() or d.exists()
        assert is_empty_dir(f"local:{d}") is True
        (d / "f").write_text("x")
        assert is_empty_dir(f"local:{d}") is False

    def test_archive_tree_and_ops(self, sample_tree, tmp_path):
        arc = tmp_path / "pack.zip"
        copy(f"local:{sample_tree}", f"archive:{arc}")
        t = tree(f"archive:{arc}")
        assert "a.txt" in t
        assert "sub" in t
        assert exists(f"archive:{arc}:/a.txt")
        assert "a.txt" in search(f"archive:{arc}", mode="include", patterns=["*.txt"])
        write(f"archive:{arc}:/extra.txt", "e")
        assert read(f"archive:{arc}:/extra.txt") == "e"
        remove(f"archive:{arc}:/extra.txt")
        assert not exists(f"archive:{arc}:/extra.txt")


class TestCopyMatrix:
    def test_all_schemes_to_archive_handler_registered(self):
        from pyeff.ops import _get_copy_handler
        from pyeff.uri import parse_uri

        remotes = [
            "docker:c:/x",
            "ssh:u@h:/x",
            "k8s:pod:/x",
            "s3://b/k",
            "gs://b/k",
            "az://c/k",
            "https://h/f",
            "smb://h/s/p",
            "webdavs://h/p",
        ]
        dst = parse_uri("archive:./out.zip")
        for r in remotes:
            handler = _get_copy_handler(parse_uri(r), dst)
            assert handler is not None

        # archive -> archive
        handler = _get_copy_handler(parse_uri("archive:./a.zip"), dst)
        assert handler is not None
