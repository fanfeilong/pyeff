import os
import shutil
import fnmatch


def ensure(target_dir):
    """
    Ensure that the specified directory exists. If it does not exist, create it.
    This function uses `os.makedirs` which creates all necessary parent directories as well.

    Args:
        target_dir (str): The directory path to ensure existence of.

    Returns:
        None
    """
    os.makedirs(target_dir, exist_ok=True)


def current_dir(file):
    """
    Returns the current directory of the given file path.

    This function obtains the absolute path of the file provided and then
    retrieves the directory portion of that path.

    Parameters:
    file (str): The file path for which the directory is to be found.

    Returns:
    str: The directory path of the given file.
    """
    return os.path.dirname(os.path.abspath(file))


def _save_move(src, dst):
    """
    Moves a file or directory from a source location to a destination.
    Ensures the source exists and neither source nor destination are system-level directories.

    Parameters:
    src (str): The source file or directory path.
    dst (str): The destination file or directory path.

    Returns:
    None

    Raises:
    FileNotFoundError: If the source path does not exist.
    Exception: If attempting to move root or home directories.

    Ensures destination directory exists before moving and handles the moving process securely.
    """
    if not os.path.exists(src):
        return

    if os.path.abspath(src) in ["/", os.path.expanduser("~")] or os.path.abspath(
        dst
    ) in ["/", os.path.expanduser("~")]:
        print("error: You are trying to move your root or home directory.")
        return

    dst_dir = os.path.dirname(dst)
    os.makedirs(dst_dir)

    shutil.move(src, dst)


def _is_directory_empty(directory):
    """
    Check if the specified directory is empty.

    This function uses `os.scandir` to examine the directory's contents.
    It returns `True` if the directory is empty, meaning it contains no files or directories,
    and `False` otherwise.

    :param directory: The path to the directory to check.
    :type directory: str or os.PathLike
    :return: True if the directory is empty, False otherwise.
    :rtype: bool
    """
    with os.scandir(directory) as scan:
        return not any(scan)


def _movetree_by_os_walk_includes(src, dst, *patterns):
    """
    Recursively moves files from source to destination directory based on provided patterns.
    It ensures that directories are created as needed, matches files using fnmatch, moves them,
    and optionally removes empty source directories.

    :param src: Source directory path from which files are to be moved.
    :param dst: Destination directory path where files will be moved to.
    :param patterns: Wildcard patterns used to select files to move. Defaults to ["*"], which moves all files.
    """
    os.makedirs(dst, exist_ok=True)

    if patterns is None:
        patterns = ["*"]

    for root, dirs, files in os.walk(src):
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        moved = False
        for file in matched_files:
            src_file_path = os.path.join(root, file)
            dest_file_path = os.path.join(dest_dir, file)
            shutil.move(src_file_path, dest_file_path)
            moved = True

        if moved and _is_directory_empty(root):
            os.rmdir(root)


def _movetree_by_os_walk_ignores(src, dst, *patterns):
    """
    Recursively moves files from source to destination directory, excluding files
    that match specified patterns. Empty directories are removed after all their
    contents have been successfully moved.

    :param src: The source directory path.
    :param dst: The destination directory path.
    :param patterns: A variable number of wildcard patterns to ignore files.
                      If none provided, all files are considered.
    """
    os.makedirs(dst, exist_ok=True)

    if patterns is None:
        patterns = []

    for root, dirs, files in os.walk(src):
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        moved = False
        for file in files:
            if file not in matched_files:
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(dest_dir, file)
                shutil.move(src_file_path, dest_file_path)
                moved = True

        if moved and _is_directory_empty(root):
            os.rmdir(root)


def move(src, dst, mode="all", patterns=None):
    """
    Moves files or directories from a source to a destination based on a mode and optional patterns.

    :param src: The source path (file or directory) to move.
    :param dst: The destination path where the source will be moved.
    :param mode: Specifies the handling of files based on patterns. Options are "ignore", "include", or "all".
    :param patterns: A list of patterns to include or ignore files, depending on the mode.
    :raise AssertionError: If the mode is not one of the specified options or if the source path does not exist.
    :return: None
    """

    assert mode in ["ignore", "include", "all"]

    assert os.path.exists(src)

    if os.path.isfile(src):
        _save_move(src, dst)
    else:
        if mode == "ignore" and patterns is not None:
            _movetree_by_os_walk_ignores(src, dst, *patterns)
        elif mode == "include" and patterns is not None:
            _movetree_by_os_walk_includes(src, dst, *patterns)
        else:
            _movetree_by_os_walk_ignores(src, dst)


def _copytree_by_shutils_ignores(src, dst, *patterns):
    """
    Copies a directory tree from `src` to `dst`, ignoring files and directories
    that match any of the glob-style patterns provided in `patterns`.

    This function utilizes the `shutil.copytree` method and extends it by creating
    a custom ignore function which filters out files based on the specified patterns.

    Args:
        src (str): The source directory to copy from.
        dst (str): The destination directory where the files will be copied.
        *patterns (str): Variable length argument list of glob-style patterns to ignore.

    Raises:
        shutil.Error: If there is an error during the copy process.
    """

    def ignore_patterns(*patterns):
        def _ignore_patterns(path, names):
            ignored_names = []
            for pattern in patterns:
                ignored_names.extend(fnmatch.filter(names, pattern))
            return set(ignored_names)

        return _ignore_patterns

    shutil.copytree(src, dst, ignore=ignore_patterns(*patterns))


def _copytree_by_shutils_includes(src, dst, *patterns):
    """
    Recursively copies a directory tree to a new location, including only those files
    that match the provided filename patterns. Patterns not provided are excluded from the copy.

    :param src: Source directory to copy from.
    :param dst: Destination directory.
    :param patterns: Variable number of string patterns to include files; uses fnmatch for matching.
    """

    def include_patterns(*patterns):
        def _ignore_patterns(path, names):
            keepers = set()
            for pattern in patterns:
                matched = fnmatch.filter(names, pattern)
                keepers.update(set(matched))
            ignore = set(
                name
                for name in names
                if name not in keepers and not os.path.isdir(os.path.join(path, name))
            )
            return ignore

        return _ignore_patterns

    shutil.copytree(src, dst, ignore=include_patterns(*patterns))


def _copytree_by_os_walk_includes(src, dst, *patterns):
    """
    Recursively copies the contents of the source directory to the destination directory,
    including only files that match the provided patterns. If no patterns are provided,
    it copies all files. It uses `os.walk` to traverse the source directory and `shutil.copy2`
    to copy files, creating destination directories as needed.

    Parameters:
    - src (str): The source directory path.
    - dst (str): The destination directory path.
    - *patterns (str): Variable length argument list of file name patterns to include in the copy.
                       Wildcards can be used (e.g., "*txt", "image.*").
    """
    os.makedirs(dst, exist_ok=True)

    if patterns is None:
        patterns = ["*"]

    for root, dirs, files in os.walk(src):
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        for file in matched_files:
            src_file_path = os.path.join(root, file)
            dest_file_path = os.path.join(dest_dir, file)
            shutil.copy2(src_file_path, dest_file_path)


def _copytree_by_os_walk_ignores(src, dst, *patterns):
    """
    Recursively copies the content of the source directory to the destination directory,
    excluding files that match the specified patterns. The function uses `os.walk` to traverse
    through all subdirectories and files in the source directory.

    :param src: The source directory path.
    :param dst: The destination directory path.
    :param patterns: Optional, a sequence of glob-style patterns specifying files to ignore.
                    If not specified, no files are ignored.
    """
    os.makedirs(dst, exist_ok=True)

    if patterns is None:
        patterns = []

    for root, dirs, files in os.walk(src):
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        for file in files:
            if not file in matched_files:
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(dest_dir, file)
                shutil.copy2(src_file_path, dest_file_path)


def _copytree_ignores(src, dst, patterns=None, dirs_exist_ok=False):
    """
    Recursively copy a directory tree using copy2(), ignoring files and directories
    that match any of the patterns provided. This function chooses the copying strategy
    based on whether or not destination directories are allowed to exist.

    :param src: Source directory path.
    :param dst: Destination directory path.
    :param patterns: Optional sequence of patterns specifying files to ignore.
    :param dirs_exist_ok: If True, destination directories can already exist without raising an error.
    :return: None
    """
    if dirs_exist_ok:
        _copytree_by_os_walk_ignores(src, dst, *patterns)
    else:
        _copytree_by_shutils_ignores(src, dst, *patterns)


def _copytree_includes(src, dst, patterns=None, dirs_exist_ok=False):
    """
    Recursively copies a directory tree to a destination, including only files
    that match the given patterns. This function selects the copying mechanism
    based on whether directories at the destination are allowed to exist.

    :param src: Source directory path.
    :param dst: Destination directory path.
    :param patterns: Optional patterns to match files to be copied. Files not matching these patterns are ignored.
    :param dirs_exist_ok: If True, the operation will not raise an error if directories in the destination already exist.
    :return: None
    """
    if dirs_exist_ok:
        _copytree_by_os_walk_includes(src, dst, *patterns)
    else:
        _copytree_by_shutils_includes(src, dst, *patterns)


def _copytree(src, dst, mode="all", patterns=None, dirs_exist_ok=False):
    """
    Recursively copies a directory tree from `src` to `dst`.

    Args:
        src (str): The source directory to copy from.
        dst (str): The destination directory to copy to.
        mode (str, optional): Determines copy behavior:
            - "ignore": Copies only files not matching `patterns`.
            - "include": Only copies files matching `patterns`.
            - "all": Copies all files, ignoring `patterns`.
            Defaults to "all".
        patterns (list of str, optional): List of patterns to include or exclude based on `mode`.
        dirs_exist_ok (bool, optional): If True, ignore error if directories in `dst` already exist. Defaults to False.

    Raises:
        AssertionError: If `mode` is not one of "ignore", "include", or "all".
    """

    assert mode in ["ignore", "include", "all"]

    if mode == "ignore":
        _copytree_ignores(src, dst, patterns=patterns, dirs_exist_ok=dirs_exist_ok)
    elif mode == "include":
        _copytree_includes(src, dst, patterns=patterns, dirs_exist_ok=dirs_exist_ok)
    else:
        _copytree_ignores(src, dst, patterns=[], dirs_exist_ok=dirs_exist_ok)


def copy(
    src,
    dst,
    mode="all",
    patterns=None,
    dirs_exist_ok=False,
    follow_symlinks: bool = True,
    copy_metadata=False,
):
    """
    Copies a file or directory from the source to the destination.

    If the source is a file, this function copies it directly to the destination,
    optionally copying metadata if `copy_metadata` is set to True.
    If it is a directory, `_copytree` is called to recursively copy its contents,
    respecting the `mode`, `patterns`, and `dirs_exist_ok` parameters.

    Parameters:
    - src (str): The source path.
    - dst (str): The destination path.
    - mode (str, optional): Copy mode, not directly used but provided for interface consistency.
    - patterns (list or None, optional): Patterns to include in the copy if src is a directory.
    - dirs_exist_ok (bool, optional): If True, destination dirs can already exist.
    - follow_symlinks (bool, optional): Follow symbolic links when copying.
    - copy_metadata (bool, optional): Whether to copy file metadata along with the file.
    """
    if os.path.isfile(src):
        if copy_metadata:
            shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
        else:
            shutil.copy(src, dst, follow_symlinks=follow_symlinks)
    else:
        _copytree(src, dst, mode=mode, patterns=patterns, dirs_exist_ok=dirs_exist_ok)


def _removetree_by_os_walk_includes(src, *patterns):
    """
    Removes files matching specified patterns from a directory tree starting at `src`.

    This function uses `os.walk` to traverse the directory `src` and `fnmatch` to find files
    that match any of the given patterns. Each matched file is then deleted.

    Parameters:
    - src (str): The root directory from where to start removing files.
    - patterns (*str): Variable number of string patterns that the file names should match to be removed.

    Raises:
    - AssertionError: If `patterns` is None.
    - OSError: If there is an error deleting a file.
    """
    assert patterns is not None

    for root, dirs, files in os.walk(src):
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        for file in matched_files:
            src_file_path = os.path.join(root, file)
            os.remove(src_file_path)


def _removetree_by_os_walk_ignores(src, *patterns):
    """
    Removes files from the given directory `src` that do not match any of the
    specified `patterns` provided. Walks through `src` using `os.walk`, filters
    out files that do match the patterns, and then removes the remaining files.

    Parameters:
    - src (str): The source directory path from which files are to be removed.
    - *patterns (str): Variable length argument list of patterns to ignore. Files
                       not matching any of these patterns will be deleted.

    Assumes:
    - `patterns` is not None, ensuring the function expects at least one pattern.
    - The user has the necessary permissions to delete files in `src`.

    Examples:
    _removetree_by_os_walk_ignores("/path/to/directory", "*.log", "*.tmp")
    """
    assert patterns is not None

    for root, dirs, files in os.walk(src):
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        for file in files:
            if file not in matched_files:
                src_file_path = os.path.join(root, file)
                os.remove(src_file_path)


def _save_remove(path):
    """
    Removes a specified file or directory.

    This function checks if the given path exists and is not a root or home directory,
    then safely deletes it. It distinguishes between files and directories, using
    `os.remove` for files and `shutil.rmtree` for directories.

    Parameters:
    - path (str): The file or directory path to be deleted.

    Returns:
    - None

    Raises:
    - DoesNotExistError: If the path does not exist.
    - OSError: If an error occurs during the removal.

    Note:
    - Attempting to delete the root or home directory will result in an error message.
    """
    if not os.path.exists(path):
        return

    if os.path.abspath(path) in ["/", os.path.expanduser("~")]:
        print("error: You are trying to delete your root or home directory.")
        return

    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def _remove_once(src, mode="all", patterns=None):
    """
    Removes files or directories from a source folder based on a specified mode and patterns.

    Args:
        src (str): The source directory path from which elements are to be removed.
        mode (str): The operation mode. Options are:
            - "ignore": Removes all except the specified patterns.
            - "include": Removes only the specified patterns.
            - "all": Removes everything without considering patterns.
        patterns (tuple[str], optional): A tuple of patterns to include or ignore based on the mode.

    Raises:
        AssertionError: If the mode provided is not one of the specified options.
    """

    assert mode in ["ignore", "include", "all"]

    if mode == "ignore" and patterns is not None:
        _removetree_by_os_walk_ignores(src, *patterns)
    elif mode == "include" and patterns is not None:
        _removetree_by_os_walk_includes(src, *patterns)
    else:
        _save_remove(src)


def remove(src, mode="all", patterns=None):
    """
    Removes elements from a list or a single element based on specified patterns.

    If `src` is a list, iterates over it and applies _remove_once to each element.
    If it's a single item, applies _remove_once directly.

    Parameters:
    - src: The source to remove from, can be a list or a single value.
    - mode (str): The removal mode, defaults to "all". Not used here but implied for further extension.
    - patterns: Patterns to remove, not implemented directly in this snippet. Expected to be used in _remove_once.

    Note: The functionsignature suggests recursive or iterative processing but the actual pattern removal logic is not provided.
    """
    if type(src) == type([]):
        for item in src:
            _remove_once(item, mode, patterns)
    else:
        _remove_once(src, mode, patterns)


def _search_by_os_walk_includes(src, results, *patterns):
    """
    Recursively searches for files in a directory tree that match any of the given patterns.

    This function uses `os.walk` to traverse the directory `src` and `fnmatch.filter` to find files
    that match the patterns provided. If no patterns are provided, it defaults to matching all files (`*`).
    The file paths of the matched files are then added to the `results` list.

    Args:
    - src (str): The root directory to start the search from.
    - results (list): A list to append the matched file paths to.
    - patterns (*str): Variable number of string patterns used to filter files. Defaults to ['*'] if not provided.

    Returns:
    - None: The function modifies the `results` list in place.
    """
    if patterns is None:
        patterns = ["*"]

    for root, dirs, files in os.walk(src):
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        for file in matched_files:
            src_file_path = os.path.join(root, file)
            results.append((src_file_path))


def _search_by_os_walk_ignores(src, results, *patterns):
    """
    This function searches for files within a directory tree starting from `src`,
    excluding any files that match the patterns provided in `patterns`.

    It uses `os.walk` to traverse the directory tree and `fnmatch.filter` to match
    the file names against the given glob patterns. Files not matching any of the
    patterns are added to the `results` list.

    Parameters:
    - src (str): The source directory to start the search.
    - results (list): A list to store the paths of files that do not match the ignore patterns.
    - *patterns (str): Variable length argument list of glob patterns to exclude files.

    Note:
    If no patterns are provided, it defaults to an empty list, effectively including all files.
    """
    if patterns is None:
        patterns = []

    for root, dirs, files in os.walk(src):
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        for file in files:
            if file not in matched_files:
                src_file_path = os.path.join(root, file)
                results.append((src_file_path))


def search(src, mode="all", patterns=None):
    """
    Recursively searches through a directory (`src`) based on the specified search `mode`
    and optional `patterns`.

    - `mode` can be "ignore", "include", or "all":
        - "ignore": Ignores files matching the given patterns.
        - "include": Only includes files matching the given patterns.
        - "all": Does not filter by patterns, including all files.
    - `patterns` is a tuple of file name patterns to include or ignore, depending on `mode`.

    :param src: The source directory path to search.
    :param mode: The search mode determining how patterns are applied.
    :param patterns: Optional tuple of file patterns for inclusion or exclusion.
    :return: A list of files that match the search criteria.
    """
    results = []

    assert mode in ["ignore", "include", "all"]

    if mode == "ignore" and patterns is not None:
        _search_by_os_walk_ignores(src, results, *patterns)
    elif mode == "include" and patterns is not None:
        _search_by_os_walk_includes(src, results, *patterns)
    else:
        _search_by_os_walk_ignores(src, results)

    return results


def listdir(source_dir, extensions=[], sort=True, abs_path=True):
    """
    Returns a list of files in the specified directory, optionally filtered by file extensions,
    sorted, and with absolute paths.

    Parameters:
    - source_dir (str): The directory path to list files from.
    - extensions (list of str, optional): A list of file extensions to filter by. Defaults to an empty list, which includes all files.
    - sort (bool, optional): Whether to sort the list of files alphabetically. Defaults to True.
    - abs_path (bool, optional): Whether to return the full absolute paths of the files. Defaults to True.

    Returns:
    - list of str: A list of file names or paths, filtered and processed according to the given parameters.
    """
    file_list = os.listdir(source_dir)

    if len(extensions) > 0:
        file_list = [
            file for file in file_list if any(file.endswith(ext) for ext in extensions)
        ]

    if abs_path:
        file_list = [os.path.join(source_dir, file) for file in file_list]

    if sort:
        file_list = sorted(file_list)

    return file_list
