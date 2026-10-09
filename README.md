# pyeff

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A user-friendly Python utility library for daily coding tasks. Provides simplified APIs for file operations, JSON/YAML handling, shell commands, and more.

## Features

- **Type Hints**: Full type annotations for better IDE support
- **Pathlib Support**: All path arguments accept both `str` and `Path`
- **Proper Exceptions**: Clear error messages with appropriate exception types
- **Async Support**: Optional async versions for I/O operations
- **Pattern Matching**: Include/ignore patterns for file operations

## Installation

```bash
pip install pyeff
```

With async support:

```bash
pip install pyeff[async]
```

For development:

```bash
pip install pyeff[dev]
```

## Quick Start

```python
from pyeff import copy, remove, load_json, dump_yaml

# File operations with patterns
copy("./src", "./backup", mode="ignore", patterns=["*.pyc", "__pycache__"])
remove("./build", mode="include", patterns=["*.tmp"])

# JSON/YAML
config = load_json("config.json")
dump_yaml(config, "config.yml")
```

## Modules

### pyeff.fs - File System Operations

```python
from pyeff.fs import copy, move, remove, search, ensure, listdir, tree

# Copy with pattern filtering
copy("./src", "./dst", mode="include", patterns=["*.py"])
copy("./src", "./dst", mode="ignore", patterns=["*.pyc", "__pycache__"])

# Remove files/directories
remove("./build")
remove("./src", mode="include", patterns=["*.tmp"])
remove(["file1.txt", "file2.txt"])  # Remove multiple

# Move with patterns
move("./old", "./new", mode="include", patterns=["*.py"])

# Search for files
py_files = search("./src", mode="include", patterns=["*.py"])

# Directory operations
ensure("./path/to/dir")  # Create if not exists
files = listdir("./src", extensions=[".py", ".txt"])
print(tree("./project", max_depth=2))
```

### pyeff.json - JSON Operations

```python
from pyeff.json import load_json, dump_json, merge

# Load and save
data = load_json("config.json")
dump_json(data, "output.json", indent=2, sort_keys=True)

# Merge dictionaries
base = {"a": 1, "b": {"c": 2}}
update = {"b": {"d": 3}}
result = merge(base, update)  # {"a": 1, "b": {"c": 2, "d": 3}}

# Async support (requires pyeff[async])
from pyeff.json import load_json_async, dump_json_async
data = await load_json_async("config.json")
```

### pyeff.yaml - YAML Operations

```python
from pyeff.yaml import load_yaml, load_yaml_full, dump_yaml

# Simple loading
data = load_yaml("config.yml")

# Load with !include support
# config.yml: data: !include other.yml
data = load_yaml_full("config.yml", base_path="./configs")

# Save
dump_yaml(data, "output.yml")

# Multi-document YAML
from pyeff.yaml import load_yaml_all, dump_yaml_all
docs = load_yaml_all("multi.yml")
```

### pyeff.lines - Text Line Manipulation

```python
from pyeff.lines import load_lines, dump_lines, split, grep, replace, insert

# Load and save lines
lines = load_lines("file.txt", remove_newline=True)
dump_lines(lines, "output.txt", append_newline=True)

# Split by pattern
sections = split(lines, r"^## ")

# Filter lines
matches = grep(lines, r"^import")
non_matches = grep(lines, r"^#", invert=True)

# Replace in lines
new_lines = replace(lines, r"old_name", "new_name")

# Insert lines
new_lines = insert(lines, ["# inserted"], patterns=[r"^def "], insert_before=True)
```

### pyeff.shell - Shell Commands

```python
from pyeff.shell import run, run_cmds, run_output, which

# Run single command
result = run("ls -la", capture=True)
print(result.stdout)

# Get command output
output = run_output("git branch --show-current")

# Run multiple commands
run_cmds(["echo hello", "echo world"])
run_cmds(["cd /tmp", "ls"], join=True)  # Join with &&

# Check command availability
if which("docker"):
    print("Docker is installed")
```

### pyeff.hash - Hashing

```python
from pyeff.hash import hash_string, hash_file, md5, sha256

# Hash strings
digest = hash_string("hello", algorithm="sha256")
digest = sha256("hello")
digest = md5("hello")

# Hash files
file_hash = hash_file("large_file.bin")
```

### pyeff.git - Git Utilities

```python
from pyeff.git import (
    get_current_commit_info,
    get_branch_name,
    get_commit_hash,
    is_dirty,
    is_git_repo,
)

# Check if in git repo
if is_git_repo():
    print(f"Branch: {get_branch_name()}")
    print(f"Commit: {get_commit_hash(short=True)}")
    print(f"Dirty: {is_dirty()}")

# Get full commit info
info = get_current_commit_info()
print(f"Author: {info['author']}")
print(f"Message: {info['message']}")
```

### pyeff.logger - Structured Logging

```python
from pyeff.logger import (
    logger_section,
    logger_table_begin,
    logger_table_end,
    logger_file_info,
)

# Log with visual separators
logger_section("Processing started")

logger_table_begin("Configuration")
# ... log config items ...
logger_table_end()

# Log file contents
logger_file_info("config.json")
```

## API Reference

### Mode Parameter

Many file operations support a `mode` parameter:

| Mode | Description |
|------|-------------|
| `"all"` | Process all files (default) |
| `"include"` | Only process files matching patterns |
| `"ignore"` | Process files NOT matching patterns |

### Pattern Syntax

Patterns use glob/fnmatch syntax:

- `*.py` - Match Python files
- `*.{py,txt}` - Match .py or .txt files
- `test_*` - Match files starting with test_
- `**/*.py` - Match .py files in any subdirectory

## Development

```bash
# Clone repository
git clone https://github.com/fanfeilong/pyeff.git
cd pyeff

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=pyeff

# Type checking
mypy src/pyeff

# Linting
ruff check src/pyeff
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Fan Fei Long (fanfeilong@gmail.com)
