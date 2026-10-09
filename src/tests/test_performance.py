"""Performance-related tests for pyeff."""

import pytest
from pathlib import Path

from pyeff.fs import (
    search_iter,
    listdir_iter,
    walk_iter,
    clear_pattern_cache,
    PatternMatcher,
)

from pyeff.lines import (
    load_lines_iter,
    grep_iter,
    replace_iter,
    clear_regex_cache,
    CompiledPatterns,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def sample_tree(temp_dir):
    """Create a sample directory structure."""
    for i in range(10):
        (temp_dir / f"file{i}.txt").write_text(f"content{i}")
        (temp_dir / f"file{i}.md").write_text(f"markdown{i}")

    sub = temp_dir / "subdir"
    sub.mkdir()
    for i in range(5):
        (sub / f"sub_file{i}.py").write_text(f"python{i}")

    return temp_dir


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample text file."""
    path = temp_dir / "sample.txt"
    lines = [f"line {i}: content\n" for i in range(100)]
    path.write_text("".join(lines))
    return path


class TestPatternMatcher:
    def test_pattern_matcher_match(self):
        matcher = PatternMatcher(["*.txt", "*.md"])
        assert matcher.match("file.txt") is True
        assert matcher.match("file.md") is True
        assert matcher.match("file.py") is False

    def test_pattern_matcher_filter_matching(self):
        matcher = PatternMatcher(["*.txt"])
        files = ["a.txt", "b.md", "c.txt", "d.py"]
        result = matcher.filter_matching(files)
        assert result == {"a.txt", "c.txt"}

    def test_pattern_matcher_filter_not_matching(self):
        matcher = PatternMatcher(["*.txt"])
        files = ["a.txt", "b.md", "c.txt", "d.py"]
        result = list(matcher.filter_not_matching(files))
        assert set(result) == {"b.md", "d.py"}


class TestCompiledPatterns:
    def test_compiled_patterns_match_any(self):
        compiled = CompiledPatterns([r"^#", r"^//"])
        assert compiled.match_any("# comment") is True
        assert compiled.match_any("// comment") is True
        assert compiled.match_any("code") is False

    def test_compiled_patterns_search_any(self):
        compiled = CompiledPatterns([r"TODO", r"FIXME"])
        assert compiled.search_any("# TODO: fix this") is True
        assert compiled.search_any("normal code") is False


class TestGenerators:
    def test_search_iter(self, sample_tree):
        """Test that search_iter returns a generator."""
        result = search_iter(sample_tree, mode="include", patterns=["*.txt"])
        assert hasattr(result, "__next__")

        files = list(result)
        assert len(files) == 10
        assert all(f.suffix == ".txt" for f in files)

    def test_listdir_iter(self, sample_tree):
        """Test that listdir_iter returns a generator."""
        result = listdir_iter(sample_tree, extensions=[".txt"])
        assert hasattr(result, "__next__")

        files = list(result)
        assert len(files) == 10

    def test_walk_iter(self, sample_tree):
        """Test that walk_iter returns a generator."""
        result = walk_iter(sample_tree)
        assert hasattr(result, "__next__")

        files = list(result)
        assert len(files) == 25

    def test_load_lines_iter(self, sample_file):
        """Test that load_lines_iter returns a generator."""
        result = load_lines_iter(sample_file, remove_newline=True)
        assert hasattr(result, "__next__")

        lines = list(result)
        assert len(lines) == 100

    def test_grep_iter(self, sample_file):
        """Test that grep_iter returns a generator."""
        lines = list(load_lines_iter(sample_file, remove_newline=True))
        result = grep_iter(lines, r"line [0-9]+:")
        assert hasattr(result, "__next__")

        matches = list(result)
        assert len(matches) == 100

    def test_replace_iter(self, sample_file):
        """Test that replace_iter returns a generator."""
        lines = list(load_lines_iter(sample_file, remove_newline=True))
        result = replace_iter(lines, r"content", "replaced")
        assert hasattr(result, "__next__")

        replaced = list(result)
        assert len(replaced) == 100
        assert all("replaced" in line for line in replaced)


class TestCaching:
    def test_pattern_cache_clear(self, sample_tree):
        """Test that pattern cache can be cleared."""
        search_iter(sample_tree, mode="include", patterns=["*.txt"])
        search_iter(sample_tree, mode="include", patterns=["*.md"])

        clear_pattern_cache()

    def test_regex_cache_clear(self):
        """Test that regex cache can be cleared."""
        compiled = CompiledPatterns([r"test1", r"test2", r"test3"])
        compiled.match_any("test1")

        clear_regex_cache()


class TestMemoryEfficiency:
    def test_generator_does_not_load_all(self, sample_tree):
        """Test that generators don't eagerly load all results."""
        gen = search_iter(sample_tree, mode="include", patterns=["*.txt"])

        first = next(gen)
        assert first is not None

    def test_grep_iter_lazy(self, sample_file):
        """Test that grep_iter is lazy."""
        lines = load_lines_iter(sample_file, remove_newline=True)
        result = grep_iter(lines, r"line 0:")

        first = next(result)
        assert "line 0:" in first
