"""Tests for pyeff.json and pyeff.yaml modules."""

import pytest
from pathlib import Path

from pyeff.json import (
    load_json,
    dump_json,
    loads,
    dumps,
    merge,
)

from pyeff.yaml import (
    load_yaml,
    load_yaml_safe,
    dump_yaml,
    loads as yaml_loads,
    dumps as yaml_dumps,
    merge as yaml_merge,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


class TestJson:
    def test_dump_and_load_json(self, temp_dir):
        data = {"name": "test", "value": 42, "nested": {"key": "value"}}
        path = temp_dir / "test.json"

        dump_json(data, path)
        assert path.exists()

        loaded = load_json(path)
        assert loaded == data

    def test_load_json_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            load_json(temp_dir / "nonexistent.json")

    def test_loads_and_dumps(self):
        data = {"key": "value", "number": 123}
        json_str = dumps(data)
        assert isinstance(json_str, str)

        loaded = loads(json_str)
        assert loaded == data

    def test_dump_json_with_options(self, temp_dir):
        data = {"b": 2, "a": 1}
        path = temp_dir / "sorted.json"

        dump_json(data, path, sort_keys=True)
        content = path.read_text()
        assert content.index('"a"') < content.index('"b"')

    def test_merge(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        update = {"b": {"c": 20}, "e": 5}

        result = merge(base, update)
        assert result["a"] == 1
        assert result["b"]["c"] == 20
        assert result["b"]["d"] == 3
        assert result["e"] == 5

    def test_merge_shallow(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        update = {"b": {"c": 20}}

        result = merge(base, update, deep=False)
        assert result["a"] == 1
        assert result["b"] == {"c": 20}
        assert "d" not in result["b"]


class TestYaml:
    def test_dump_and_load_yaml(self, temp_dir):
        data = {"name": "test", "value": 42, "items": ["a", "b", "c"]}
        path = temp_dir / "test.yml"

        dump_yaml(data, path)
        assert path.exists()

        loaded = load_yaml(path)
        assert loaded == data

    def test_load_yaml_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            load_yaml(temp_dir / "nonexistent.yml")

    def test_loads_and_dumps(self):
        data = {"key": "value", "number": 123}
        yaml_str = yaml_dumps(data)
        assert isinstance(yaml_str, str)

        loaded = yaml_loads(yaml_str)
        assert loaded == data

    def test_yaml_merge(self):
        base = {"a": 1, "b": {"c": 2}}
        update = {"b": {"d": 3}}

        result = yaml_merge(base, update)
        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3

    def test_load_yaml_safe_ignores_include(self, temp_dir):
        yaml_content = """
name: test
data: !include other.yml
"""
        path = temp_dir / "test.yml"
        path.write_text(yaml_content)

        data = load_yaml_safe(path)
        assert data["name"] == "test"
        assert data["data"] is None
