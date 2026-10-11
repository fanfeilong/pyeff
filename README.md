# pyeff

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A user-friendly Python utility library for daily coding tasks. Provides simplified APIs for file operations, JSON/YAML handling, shell commands, and more.

## Features

- **Unified API**: Consistent `copy(src, dst)` pattern across local, archive, Docker, and SSH
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

With SSH support:

```bash
pip install pyeff[ssh]
```

For development:

```bash
pip install pyeff[dev]
```

## Unified API with URI Paths

pyeff provides a **unified `copy()` function** that works across all backends using URI-style paths:

```python
from pyeff import ucopy  # Unified copy
from pyeff.uri import local, docker, ssh, archive

# URI strings (simple cases)
ucopy("local:./src", "local:./dst")
ucopy("docker:my-container:/app/logs", "local:./logs")
ucopy("local:./data", "archive:./backup.zip")
ucopy("archive:./backup.zip", "local:./restore")

# Path builders (complex cases with options)
ucopy(local("./src"), docker("container", "/app"))
ucopy(ssh("user@host", "/data", key="~/.ssh/id_rsa"), local("./backup"))

# Mixed usage
ucopy("local:./config", docker("my-container", "/app/config"))
```

### URI Format

| Scheme | Format | Example |
|--------|--------|---------|
| Local | `local:./path` or `local:/path` | `local:./data`, `local:/home/user` |
| Docker | `docker:container:/path` | `docker:my-app:/var/log` |
| SSH | `ssh:user@host:/path` | `ssh:admin@server:/etc/config` |
| SSH (port) | `ssh:user@host:port:/path` | `ssh:admin@server:2222:/data` |
| Archive | `archive:./path.zip` | `archive:./backup.tar.gz` |
| Archive (inner) | `archive:./path.zip:/inner` | `archive:./data.zip:/config.json` |

### Supported Operations

| Source | Destination | Operation |
|--------|-------------|-----------|
| local | local | Copy files |
| local | docker | Copy to container |
| local | ssh | Upload via SFTP |
| local | archive | Compress |
| docker | local | Copy from container |
| ssh | local | Download via SFTP |
| archive | local | Extract |
| docker | ssh | Copy (via temp) |
| ssh | docker | Copy (via temp) |

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

### pyeff.local / pyeff.fs - Local File System Operations

Use `local` module for consistency with `docker` and `ssh`, or `fs` module directly:

```python
from pyeff import local  # Unified interface
# or: from pyeff import fs  # Direct access

# Copy with pattern filtering
local.copy("./src", "./dst", mode="include", patterns=["*.py"])
local.copy("./src", "./dst", mode="ignore", patterns=["*.pyc", "__pycache__"])

# Remove files/directories
local.remove("./build")
local.remove("./src", mode="include", patterns=["*.tmp"])

# Move with patterns
local.move("./old", "./new", mode="include", patterns=["*.py"])

# Search for files
py_files = local.search("./src", mode="include", patterns=["*.py"])

# Directory operations
local.ensure("./path/to/dir")  # Create if not exists
files = local.listdir("./src")
print(local.tree("./project"))

# Read/write (matching docker/ssh interface)
content = local.read_text("./config.txt")
local.write_text("./output.txt", "Hello World")
lines = local.read_lines("./data.txt")
local.write_lines(["line1", "line2"], "./output.txt")
```

**All operations** (from `pyeff.fs`):

```python
from pyeff.fs import copy, move, remove, search, ensure, listdir, tree

# Generators for large directories
from pyeff.fs import search_iter, listdir_iter, walk_iter

for file in search_iter("./src", patterns=["*.py"]):
    process(file)

# Tree visualization
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

### pyeff.archive - Archive Operations (zip/tar)

pyeff.archive provides **unified naming** with `pack`/`unpack` aliases and auto-direction `copy()`:

```python
from pyeff import archive

# Unified copy() auto-detects direction
archive.copy("./src", "backup.zip")        # compress (directory → archive)
archive.copy("backup.zip", "./restore")    # extract (archive → directory)

# pack/unpack aliases (same as compress/extract)
archive.pack("./src", "backup.zip")
archive.unpack("backup.zip", "./restore")

# With pattern filtering
archive.copy("./src", "backup.zip", mode="ignore", patterns=["*.pyc"])
archive.copy("backup.zip", "./data", mode="include", patterns=["*.csv"])
```

**Full API**:

```python
from pyeff.archive import compress, extract, list_archive, archive_info

# Compress directory to zip (with pattern filtering)
compress("./src", "backup.zip")
compress("./src", "backup.zip", mode="ignore", patterns=["*.pyc", "__pycache__"])
compress("./docs", "docs.tar.gz", mode="include", patterns=["*.md"])

# Compress specific files
from pyeff.archive import compress_files
compress_files(["a.txt", "b.txt"], "files.zip")

# Extract archive
extract("backup.zip", "./restore")
extract("data.tar.gz", "./data", mode="include", patterns=["*.csv"])

# Extract single file
from pyeff.archive import extract_file
data = extract_file("archive.zip", "config.json")  # Returns bytes
extract_file("archive.zip", "config.json", "./config.json")  # Write to file

# List archive contents
members = list_archive("backup.zip")
for m in members:
    print(f"{m.name}: {m.size} bytes")

# Filter when listing
txt_files = list_archive("backup.zip", mode="include", patterns=["*.txt"])

# Get archive info
info = archive_info("backup.zip")
print(f"Files: {info['file_count']}, Total: {info['total_size']} bytes")

# Add files to existing zip
from pyeff.archive import add_to_archive
add_to_archive("backup.zip", ["new_file.txt"])

# Parallel compression (faster for many small files)
from pyeff.archive import compress_parallel
compress_parallel("./src", "backup.zip", workers=4)

# Progress callback
def on_progress(filename, current, total):
    print(f"[{current}/{total}] {filename}")

compress("./src", "backup.zip", progress=on_progress)
```

**Supported formats**: `.zip`, `.tar`, `.tar.gz`/`.tgz`, `.tar.bz2`/`.tbz2`, `.tar.xz`/`.txz`

### pyeff.remote - Remote File Operations (Docker/SSH)

pyeff.remote provides a **unified API** across Docker and SSH with automatic direction detection:

```python
from pyeff.remote import docker, ssh

# Docker operations with unified copy()
with docker("my-container") as d:
    # Direction auto-detected: absolute path (/) = container, relative (./) = local
    d.copy("/app/logs", "./logs")           # container → local
    d.copy("./config", "/app/config")       # local → container
    d.copy("/data", "./data", mode="include", patterns=["*.csv"])
    
    # Other operations
    d.search("/logs", patterns=["*.log"])
    d.remove("/tmp/cache")
    d.exists("/app/config.json")
    content = d.read_text("/app/config.json")
    d.write_text("/app/settings.json", '{"key": "value"}')

# SSH operations with the same API (requires: pip install pyeff[ssh])
with ssh("user@server.com", key_file="~/.ssh/id_rsa") as s:
    # Same unified copy() with direction auto-detection
    s.copy("/var/log", "./logs")            # remote → local
    s.copy("./config", "/etc/myapp/")       # local → remote
    s.copy("/var/log", "./logs", patterns=["*.log"])
    
    # Same operations as Docker
    files = s.search("/data", patterns=["*.csv"])
    items = s.listdir("/home/user")
    content = s.read_text("/etc/config")
    s.write_text("/tmp/output.txt", "Hello World")
    s.remove("/tmp/cache", recursive=True)

# Password authentication
with ssh("user@server.com", password="secret") as s:
    s.copy("/data", "./backup")
```

**Explicit direction** (if you prefer):

```python
# You can still use explicit copy_from/copy_to
with docker("my-container") as d:
    d.copy_from("/app/logs", "./logs")      # container → local
    d.copy_to("./config", "/app/config")    # local → container

with ssh("user@host") as s:
    s.copy_from("/var/log", "./logs")       # remote → local
    s.copy_to("./config", "/etc/app/")      # local → remote
```

**Legacy function-based API** (still supported):

```python
from pyeff.remote import docker_copy, docker_search, docker_remove

docker_copy("my-container:/app/logs", "./logs")
docker_copy("./config", "my-container:/app/config")
files = docker_search("my-container:/logs", patterns=["*.log"])
docker_remove("my-container:/tmp/cache")
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
