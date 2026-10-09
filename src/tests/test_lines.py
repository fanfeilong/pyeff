"""Tests for pyeff.lines module."""

import pytest
from pathlib import Path

from pyeff.lines import (
    load_all_text,
    dump_all_text,
    load_lines,
    dump_lines,
    split,
    find,
    find_index,
    grep,
    replace,
    insert,
    extract,
    count_indent,
    dedent,
    indent,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


class TestLoadDumpText:
    def test_dump_and_load_all_text(self, temp_dir):
        content = "Hello\nWorld\nTest"
        path = temp_dir / "test.txt"

        dump_all_text(content, path)
        loaded = load_all_text(path)
        assert loaded == content

    def test_load_all_text_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            load_all_text(temp_dir / "nonexistent.txt")


class TestLoadDumpLines:
    def test_dump_and_load_lines(self, temp_dir):
        lines = ["line1", "line2", "line3"]
        path = temp_dir / "test.txt"

        dump_lines(lines, path, append_newline=True)
        loaded = load_lines(path, remove_newline=True)
        assert loaded == lines

    def test_load_lines_with_newlines(self, temp_dir):
        path = temp_dir / "test.txt"
        path.write_text("line1\nline2\nline3\n")

        loaded = load_lines(path, remove_newline=False)
        assert all(line.endswith("\n") for line in loaded[:3])

    def test_load_lines_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            load_lines(temp_dir / "nonexistent.txt")


class TestSplit:
    def test_split_by_header(self):
        lines = ["# Header 1", "content 1", "# Header 2", "content 2"]
        result = split(lines, r"^#.*")

        assert len(result) == 2
        assert result[0] == ["# Header 1", "content 1"]
        assert result[1] == ["# Header 2", "content 2"]

    def test_split_no_match(self):
        lines = ["line1", "line2", "line3"]
        result = split(lines, r"^#.*")

        assert len(result) == 1
        assert result[0] == lines


class TestFind:
    def test_find_match(self):
        lines = ["apple", "banana", "cherry"]
        assert find(lines, r"^ban.*") is True

    def test_find_no_match(self):
        lines = ["apple", "banana", "cherry"]
        assert find(lines, r"^xyz.*") is False

    def test_find_multiple_patterns(self):
        lines = ["apple", "banana", "cherry"]
        assert find(lines, r"^xyz.*", r"^cher.*") is True


class TestFindIndex:
    def test_find_index_match(self):
        lines = ["apple", "banana", "cherry"]
        assert find_index(lines, r"^ban.*") == 1

    def test_find_index_no_match(self):
        lines = ["apple", "banana", "cherry"]
        assert find_index(lines, r"^xyz.*") == -1


class TestGrep:
    def test_grep_match(self):
        lines = ["apple", "apricot", "banana", "cherry"]
        result = grep(lines, r"^ap")

        assert len(result) == 2
        assert "apple" in result
        assert "apricot" in result

    def test_grep_invert(self):
        lines = ["apple", "apricot", "banana", "cherry"]
        result = grep(lines, r"^ap", invert=True)

        assert len(result) == 2
        assert "banana" in result
        assert "cherry" in result


class TestReplace:
    def test_replace(self):
        lines = ["Hello World", "Hello Python", "Goodbye World"]
        result = replace(lines, r"Hello", "Hi")

        assert result[0] == "Hi World"
        assert result[1] == "Hi Python"
        assert result[2] == "Goodbye World"


class TestInsert:
    def test_insert_after(self):
        lines = ["line1", "# marker", "line3"]
        result = insert(lines, ["inserted"], patterns=[r"^# marker"])

        assert result == ["line1", "# marker", "inserted", "line3"]

    def test_insert_before(self):
        lines = ["line1", "# marker", "line3"]
        result = insert(lines, ["inserted"], patterns=[r"^# marker"], insert_before=True)

        assert result == ["line1", "inserted", "# marker", "line3"]


class TestExtract:
    def test_extract(self):
        lines = ["before", "START", "content1", "content2", "END", "after"]
        result, end_idx = extract(
            lines,
            start=lambda l: l == "START",
            finish=lambda l: l == "END",
        )

        assert result == ["START", "content1", "content2", "END"]
        assert end_idx == 4


class TestIndent:
    def test_count_indent_spaces(self):
        assert count_indent("    text") == 4
        assert count_indent("text") == 0
        assert count_indent("  text") == 2

    def test_dedent(self):
        lines = ["    line1", "    line2", "      line3"]
        result = dedent(lines)

        assert result == ["line1", "line2", "  line3"]

    def test_dedent_with_spaces(self):
        lines = ["    line1", "    line2"]
        result = dedent(lines, spaces=2)

        assert result == ["  line1", "  line2"]

    def test_indent_lines(self):
        lines = ["line1", "line2", ""]
        result = indent(lines, "  ")

        assert result == ["  line1", "  line2", ""]
