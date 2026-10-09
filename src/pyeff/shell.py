"""Shell command execution utilities.

This module provides utilities for executing shell commands:
- Running single or multiple commands
- Working directory support
- Exit code checking
- Tar compression/extraction helpers
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from loguru import logger

PathLike = Union[str, Path]


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def run_cmds(
    cmds: Union[List[str], str],
    cwd: Optional[PathLike] = None,
    tip: Optional[str] = None,
    check: bool = False,
    join: bool = False,
) -> Union[int, List[int]]:
    """Execute shell commands.

    Args:
        cmds: Command(s) to execute. String or list of strings.
        cwd: Working directory for command execution.
        tip: Prefix message for logging.
        check: If True, raise on non-zero exit code.
        join: If True, join commands with && and run as one.

    Returns:
        Exit code (if join=True) or list of exit codes.

    Raises:
        AssertionError: If check=True and command fails.
    """
    if isinstance(cmds, str):
        cmds = [cmds]

    if join:
        return _run_cmds_join(cmds, cwd=cwd, tip=tip, check=check)
    else:
        return _run_cmds_split(cmds, cwd=cwd, tip=tip, check=check)


def _run_cmds_join(
    cmds: List[str],
    cwd: Optional[PathLike] = None,
    tip: Optional[str] = None,
    check: bool = False,
) -> int:
    """Execute commands joined together."""
    head = f"{tip}: " if tip else ""
    cmd = " && ".join(cmds)

    if cwd is not None:
        full_cmd = f"cd {cwd} && {cmd}"
    else:
        full_cmd = cmd

    logger.info(f"{head}{full_cmd}")

    ret = os.system(full_cmd)

    if ret != 0:
        logger.warning(f"{head}Command failed with code {ret}: {full_cmd}")

    if check and ret != 0:
        raise subprocess.CalledProcessError(ret, full_cmd)

    return ret


def _run_cmds_split(
    cmds: List[str],
    cwd: Optional[PathLike] = None,
    tip: Optional[str] = None,
    check: bool = False,
) -> List[int]:
    """Execute commands one by one."""
    head = f"{tip}: " if tip else ""
    results: List[int] = []

    for cmd in cmds:
        if cwd is not None:
            full_cmd = f"cd {cwd} && {cmd}"
        else:
            full_cmd = cmd

        logger.info(f"{head}{full_cmd}")

        ret = os.system(full_cmd)

        if ret != 0:
            logger.warning(f"{head}Command failed with code {ret}: {full_cmd}")

        if check and ret != 0:
            raise subprocess.CalledProcessError(ret, full_cmd)

        results.append(ret)

    return results


def run(
    cmd: str,
    cwd: Optional[PathLike] = None,
    check: bool = False,
    capture: bool = False,
    shell: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a single shell command using subprocess.

    Args:
        cmd: Command to execute.
        cwd: Working directory.
        check: If True, raise on non-zero exit code.
        capture: If True, capture stdout and stderr.
        shell: If True, run through shell (default).

    Returns:
        CompletedProcess object with returncode, stdout, stderr.

    Raises:
        subprocess.CalledProcessError: If check=True and command fails.
    """
    cwd_str = str(cwd) if cwd else None

    result = subprocess.run(
        cmd,
        shell=shell,
        cwd=cwd_str,
        capture_output=capture,
        text=True,
        check=check,
    )

    return result


def run_output(
    cmd: str,
    cwd: Optional[PathLike] = None,
    check: bool = True,
) -> str:
    """Run a command and return its stdout.

    Args:
        cmd: Command to execute.
        cwd: Working directory.
        check: If True, raise on non-zero exit code.

    Returns:
        Command stdout as string (stripped).

    Raises:
        subprocess.CalledProcessError: If check=True and command fails.
    """
    result = run(cmd, cwd=cwd, check=check, capture=True)
    return result.stdout.strip()


def compress_to_tar_gz(
    target_directory: PathLike,
    file_list: List[str],
    output_tar_gz: PathLike,
) -> None:
    """Compress files to a tar.gz archive.

    Args:
        target_directory: Base directory containing files.
        file_list: List of files (relative or absolute paths).
        output_tar_gz: Output archive path.

    Raises:
        ValueError: If directory doesn't exist, output exists, or files invalid.
        subprocess.CalledProcessError: If tar command fails.
    """
    target_dir = _to_path(target_directory)
    output_path = _to_path(output_tar_gz)

    if not target_dir.is_dir():
        raise ValueError(f"Target directory does not exist: {target_directory}")

    if output_path.exists():
        raise ValueError(f"Output file already exists: {output_tar_gz}")

    relative_paths: List[str] = []

    for file in file_list:
        file_path = Path(file)

        if not file_path.is_absolute():
            file_path = target_dir / file

        if not file_path.is_file():
            raise ValueError(f"File does not exist: {file}")

        try:
            common = os.path.commonpath([str(target_dir), str(file_path)])
        except ValueError:
            raise ValueError(
                f"File '{file}' is not within target directory '{target_directory}'"
            )

        if common != str(target_dir):
            raise ValueError(
                f"File '{file}' is not within target directory '{target_directory}'"
            )

        relative_path = file_path.relative_to(target_dir)
        relative_paths.append(str(relative_path))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        temp_file = f.name
        for rel_path in relative_paths:
            f.write(f"{rel_path}\n")

    try:
        subprocess.run(
            ["tar", "-czf", str(output_path), "-T", temp_file, "-C", str(target_dir)],
            check=True,
        )
        logger.info(f"Compression successful: '{output_tar_gz}'")
    finally:
        os.unlink(temp_file)


def extract_from_tar(
    tar_file: PathLike,
    output_directory: PathLike,
    file_patterns: Optional[List[str]] = None,
) -> List[str]:
    """Extract files from a tar archive.

    Args:
        tar_file: Path to the tar archive.
        output_directory: Directory to extract to.
        file_patterns: Optional glob patterns to filter files.

    Returns:
        List of extracted file paths.

    Raises:
        ValueError: If tar file or output directory doesn't exist.
        subprocess.CalledProcessError: If tar command fails.
    """
    tar_path = _to_path(tar_file)
    output_dir = _to_path(output_directory)

    if not tar_path.is_file():
        raise ValueError(f"Tar file does not exist: {tar_file}")

    if not output_dir.is_dir():
        raise ValueError(f"Output directory does not exist: {output_directory}")

    result = subprocess.run(
        ["tar", "-tf", str(tar_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    all_files = result.stdout.splitlines()

    if file_patterns:
        files_to_extract = [
            f for f in all_files
            if any(fnmatch.fnmatch(f, pattern) for pattern in file_patterns)
        ]
    else:
        files_to_extract = all_files

    if not files_to_extract:
        logger.warning("No files matched the patterns")
        return []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        temp_file = f.name
        for file in files_to_extract:
            f.write(f"{file}\n")

    try:
        subprocess.run(
            ["tar", "-xvf", str(tar_path), "-T", temp_file, "-C", str(output_dir)],
            check=True,
        )
        logger.info(f"Extraction successful to '{output_directory}'")
    finally:
        os.unlink(temp_file)

    return files_to_extract


def which(program: str) -> Optional[Path]:
    """Find the full path of an executable.

    Args:
        program: Name of the program to find.

    Returns:
        Path to the executable, or None if not found.
    """
    import shutil
    path = shutil.which(program)
    return Path(path) if path else None


def is_command_available(program: str) -> bool:
    """Check if a command is available in PATH.

    Args:
        program: Name of the program to check.

    Returns:
        True if the program is available.
    """
    return which(program) is not None
