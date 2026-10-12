"""Tests for pyeff.flow fluent API."""

import json
from pathlib import Path

import pytest

from pyeff.flow import Flow, FlowError, at
from pyeff import load_json, hash_file


@pytest.fixture
def cfg(tmp_path):
    path = tmp_path / "app.json"
    path.write_text(json.dumps({"env": "dev", "n": 1}))
    return path


class TestMentalModel:
    def test_at_returns_flow(self, cfg):
        f = at(cfg)
        assert isinstance(f, Flow)
        assert f.uri.startswith("local:")

    def test_load_edit_save(self, cfg):
        result = at(cfg).json().update(env="staging", release="r1").save()
        data = load_json(cfg)
        assert data["env"] == "staging"
        assert data["release"] == "r1"
        assert result.uri.endswith("app.json") or "app.json" in result.uri

    def test_edit_without_load_raises(self, cfg):
        with pytest.raises(FlowError, match="payload"):
            at(cfg).update(env="x")

    def test_dirty_fanout_auto_flush(self, cfg, tmp_path):
        d1 = tmp_path / "a.json"
        d2 = tmp_path / "b.json"
        (
            at(cfg)
            .json()
            .update(env="prod")
            .fanout(str(d1), str(d2))
            .assert_same_hash(str(d1), str(d2))
        )
        assert load_json(d1)["env"] == "prod"
        assert load_json(d2)["env"] == "prod"
        assert load_json(cfg)["env"] == "prod"

    def test_to_moves_finger(self, cfg, tmp_path):
        dst = tmp_path / "copy.json"
        f = at(cfg).to(str(dst))
        assert dst.exists()
        assert "copy.json" in f.uri

    def test_fanout_keeps_finger_on_source(self, cfg, tmp_path):
        d1 = tmp_path / "x.json"
        f = at(cfg).fanout(str(d1))
        assert f.uri == at(cfg).uri
        assert d1.exists()

    def test_assert_same_hash_mismatch(self, cfg, tmp_path):
        other = tmp_path / "other.json"
        other.write_text('{"different": true}')
        with pytest.raises(FlowError, match="Hash mismatch"):
            at(cfg).assert_same_hash(str(other))

    def test_assert_exists(self, cfg, tmp_path):
        at(cfg).assert_exists()
        with pytest.raises(FlowError, match="does not exist"):
            at(tmp_path / "missing.json").assert_exists()

    def test_yaml_roundtrip(self, tmp_path):
        path = tmp_path / "c.yml"
        path.write_text("a: 1\n")
        at(path).yaml().update(b=2).save()
        text = path.read_text()
        assert "a:" in text and "b:" in text

    def test_text_map(self, tmp_path):
        path = tmp_path / "t.txt"
        path.write_text("hello")
        at(path).text().map(str.upper).save()
        assert path.read_text() == "HELLO"

    def test_merge(self, cfg):
        at(cfg).json().merge({"nested": {"x": 1}}).save()
        assert load_json(cfg)["nested"]["x"] == 1

    def test_to_archive_and_tree(self, tmp_path):
        src = tmp_path / "dir"
        src.mkdir()
        (src / "a.txt").write_text("a")
        arc = tmp_path / "b.zip"
        at(src).to(f"archive:{arc}")
        assert arc.exists()
        t = at(f"archive:{arc}").tree()
        assert "a.txt" in t

    def test_inspect_helpers(self, cfg):
        f = at(cfg)
        assert f.exists()
        assert f.size() > 0
        assert len(f.hash()) == 64
        assert f.read()  # one-shot

    def test_chain_repr(self, cfg):
        f = at(cfg).json()
        assert "Flow(" in repr(f)
        assert "json" in repr(f)


class TestSaveTarget:
    def test_save_to_other_uri(self, cfg, tmp_path):
        dst = tmp_path / "out.json"
        f = at(cfg).json().update(env="x").save(str(dst))
        assert load_json(dst)["env"] == "x"
        assert load_json(cfg)["env"] == "dev"  # source untouched
        assert "out.json" in f.uri
