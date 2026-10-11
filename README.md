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

pyeff provides **unified operations** that work across all backends using URI-style paths:

```python
from pyeff import copy, remove, search, exists, read, write, move, listdir
from pyeff.uri import local, docker, ssh, k8s, s3, gs, az, smb_uri, webdav_uri, archive

# Copy
copy("local:./src", "local:./dst")
copy("docker:my-container:/logs", "local:./logs")
copy("local:./data", "archive:./backup.zip")
copy("ssh:user@host:/data", "local:./backup")

# Remove
remove("local:./temp")
remove("docker:my-container:/tmp/cache")
remove("ssh:user@host:/var/log", mode="include", patterns=["*.tmp"])

# Search
files = search("local:./src", mode="include", patterns=["*.py"])
files = search("docker:my-container:/logs", mode="include", patterns=["*.log"])
files = search("ssh:user@host:/data", mode="include", patterns=["*.csv"])

# Exists
if exists("docker:my-container:/app/config.json"):
    print("Config exists")

# Read / Write
content = read("ssh:user@host:/etc/config")
write("docker:my-container:/app/config.json", '{"key": "value"}')
data = read("archive:./backup.zip:/config.json")

# List directory
items = listdir("local:./src")
items = listdir("docker:my-container:/app")

# Move (cross-backend = copy + remove)
move("local:./old", "local:./new")
move("docker:my-container:/tmp/data", "local:./data")

# Path builders (with options)
copy(ssh("user@host", "/data", key="~/.ssh/id_rsa"), local("./backup"))
copy(k8s("my-pod", "/data", namespace="prod"), local("./backup"))

# Kubernetes
copy("k8s:prod/my-pod:/app/logs", "local:./logs")
copy("local:./config", "k8s:prod/my-pod/app:/app/config")
remove("k8s:my-pod:/tmp/cache")

# S3 / MinIO (pip install pyeff[s3])
copy("s3://my-bucket/logs/", "local:./logs")
copy("local:./data.csv", "s3://my-bucket/uploads/data.csv")
copy(s3("bucket", "data/", endpoint_url="http://localhost:9000",
        access_key="minio", secret_key="minio123"), local("./data"))

# GCS / Azure (pip install pyeff[gcs] / pyeff[azure])
copy("gs://my-bucket/data/", "local:./data")
copy("az://my-container/logs/", "local:./logs")

# HTTP(S) download (stdlib, no extra deps)
copy("https://example.com/file.zip", "local:./file.zip")
content = read("https://example.com/api/data.json")

# SMB/CIFS NAS (pip install pyeff[smb])
copy("smb://nas.local/shared/docs/", "local:./docs")
copy(smb_uri("nas.local", "shared", "docs/", username="user", password="pass"),
     local("./docs"))

# WebDAV NAS (stdlib, no extra deps) — Synology / Nextcloud / etc.
copy("webdavs://nas.local/webdav/docs/", "local:./docs")
copy(webdav_uri("https://cloud/remote.php/dav/files/user", "Documents/",
                username="user", password="pass"), local("./docs"))
```

### URI Format

| Scheme | Format | Example |
|--------|--------|---------|
| Local | `local:./path` | `local:./data` |
| Docker | `docker:container:/path` | `docker:my-app:/var/log` |
| SSH | `ssh:user@host:/path` | `ssh:admin@server:/etc` |
| SSH (port) | `ssh:user@host:port:/path` | `ssh:admin@server:2222:/data` |
| K8s | `k8s:pod:/path` | `k8s:my-pod:/app/logs` |
| K8s (ns) | `k8s:ns/pod:/path` | `k8s:prod/my-pod:/app/logs` |
| K8s (container) | `k8s:ns/pod/ctr:/path` | `k8s:prod/my-pod/app:/var/log` |
| S3 / MinIO | `s3://bucket/key` | `s3://my-bucket/logs/` |
| GCS | `gs://bucket/path` | `gs://my-bucket/data/` |
| Azure Blob | `az://container/blob` | `az://my-container/logs/` |
| HTTP(S) | `https://host/path` | `https://example.com/file.zip` |
| SMB/CIFS (NAS) | `smb://host/share/path` | `smb://nas.local/shared/docs/` |
| WebDAV (NAS) | `webdavs://host/path` | `webdavs://nas.local/webdav/docs/` |
| Archive | `archive:./path.zip` | `archive:./backup.tar.gz` |
| Archive (inner) | `archive:./path.zip:/inner` | `archive:./data.zip:/config.json` |

### Unified Operations

| Operation | Description | Supported Backends |
|-----------|-------------|-------------------|
| `copy(src, dst)` | Copy files | all |
| `remove(path)` | Remove files/dirs | local, docker, ssh, k8s, s3, gs, az, http, smb, webdav |
| `search(path)` | Search files | local, docker, ssh, k8s, s3, gs, az, smb, webdav, archive |
| `exists(path)` | Check existence | all |
| `listdir(path)` | List directory | local, docker, ssh, k8s, s3, gs, az, smb, webdav, archive |
| `read(path)` | Read file content | all |
| `write(path, content)` | Write file content | local, docker, ssh, k8s, s3, gs, az, http, smb, webdav |
| `move(src, dst)` | Move files | all (cross-backend via copy+remove) |

Optional installs: `pip install pyeff[s3]`, `pyeff[gcs]`, `pyeff[azure]`, `pyeff[smb]` / `pyeff[nas]`, or `pyeff[cloud]`. WebDAV needs no extra package.

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

### pyeff.remote - Remote File Operations (Docker/SSH/K8s)

pyeff.remote provides a **unified API** across Docker, SSH, and Kubernetes:

```python
from pyeff.remote import docker, ssh, k8s

# Docker
with docker("my-container") as d:
    d.copy("/app/logs", "./logs")           # container → local
    d.copy("./config", "/app/config")       # local → container

# SSH (requires: pip install pyeff[ssh])
with ssh("user@server.com", key_file="~/.ssh/id_rsa") as s:
    s.copy("/var/log", "./logs")            # remote → local
    s.copy("./config", "/etc/myapp/")       # local → remote

# Kubernetes (requires kubectl in PATH)
with k8s("my-pod", namespace="prod") as k:
    k.copy("/app/logs", "./logs")           # pod → local
    k.copy("./config", "/app/config")       # local → pod
    files = k.search("/data", patterns=["*.csv"])
    content = k.read_text("/app/config.json")

# Compact pod specs: namespace/pod or namespace/pod/container
with k8s("prod/my-pod/app") as k:
    k.copy("/var/log", "./logs")
```

Or via unified URI API:

```python
from pyeff import copy, remove, search, read
from pyeff.uri import k8s, local

copy("k8s:prod/my-pod:/app/logs", "local:./logs")
copy("local:./config", "k8s:prod/my-pod/app:/app/config")
copy(k8s("my-pod", "/data", namespace="prod", container="app"), local("./backup"))
remove("k8s:my-pod:/tmp/cache")
search("k8s:prod/my-pod:/logs", mode="include", patterns=["*.log"])
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
