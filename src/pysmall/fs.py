import os
import shutil
import fnmatch


def ensure(target_dir):
    os.makedirs(target_dir, exist_ok=True)


def _save_move(src, dst):
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
    with os.scandir(directory) as scan:
        return not any(scan)  # 如果目录为空，返回True，否则返回False


def _movetree_by_os_walk_includes(src, dst, *patterns):
    # 确保目标目录存在
    os.makedirs(dst, exist_ok=True)

    if patterns is None:
        patterns = ["*"]  # 默认复制所有文件

    for root, dirs, files in os.walk(src):
        # 计算目标目录的路径
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        # 过滤出匹配指定一组模式的文件列表
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        # 移动所有符合条件的文件
        moved = False  # 标识是否移动过文件
        for file in matched_files:
            src_file_path = os.path.join(root, file)
            dest_file_path = os.path.join(dest_dir, file)
            shutil.move(src_file_path, dest_file_path)
            moved = True  # 发生了移动

        if moved and _is_directory_empty(root):
            os.rmdir(root)


def _movetree_by_os_walk_ignores(src, dst, *patterns):
    # 确保目标目录存在
    os.makedirs(dst, exist_ok=True)

    if patterns is None:
        patterns = []

    # 使用os.walk遍历所有文件和文件夹
    for root, dirs, files in os.walk(src):
        # 计算目标目录的路径
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        # 过滤出匹配指定一组模式的文件列表
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        # 移动所有不符合条件的文件
        moved = False  # 标识是否移动过文件
        for file in files:
            if file not in matched_files:
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(dest_dir, file)
                shutil.move(src_file_path, dest_file_path)
                moved = True  # 发生了移动

        # 如果当前目录移动了文件，并且目录现在为空，则删除空目录
        if moved and _is_directory_empty(root):
            os.rmdir(root)


def move(src, dst, mode="all", patterns=None):

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
    def ignore_patterns(*patterns):
        def _ignore_patterns(path, names):
            ignored_names = []
            for pattern in patterns:
                ignored_names.extend(fnmatch.filter(names, pattern))
            return set(ignored_names)

        return _ignore_patterns

    shutil.copytree(src, dst, ignore=ignore_patterns(*patterns))


def _copytree_by_shutils_includes(src, dst, *patterns):
    def include_patterns(*patterns):
        """只包含匹配模式的文件."""

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
    if dirs_exist_ok:
        _copytree_by_os_walk_ignores(src, dst, *patterns)
    else:
        _copytree_by_shutils_ignores(src, dst, *patterns)


def _copytree_includes(src, dst, patterns=None, dirs_exist_ok=False):
    if dirs_exist_ok:
        _copytree_by_os_walk_includes(src, dst, *patterns)
    else:
        _copytree_by_shutils_includes(src, dst, *patterns)


def _copytree(src, dst, mode="all", patterns=None, dirs_exist_ok=False):

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
    if os.path.isfile(src):
        if copy_metadata:
            shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
        else:
            shutil.copy(src, dst, follow_symlinks=follow_symlinks)
    else:
        _copytree(src, dst, mode=mode, patterns=patterns, dirs_exist_ok=dirs_exist_ok)


def _removetree_by_os_walk_includes(src, *patterns):
    assert patterns is not None

    for root, dirs, files in os.walk(src):
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))

        for file in matched_files:
            src_file_path = os.path.join(root, file)
            os.remove(src_file_path)


def _removetree_by_os_walk_ignores(src, *patterns):
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
    if not os.path.exists(path):
        return

    if os.path.abspath(path) in ["/", os.path.expanduser("~")]:
        print("error: You are trying to delete your root or home directory.")
        return

    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def remove(src, mode="all", patterns=None):

    assert mode in ["ignore", "include", "all"]

    if mode == "ignore" and patterns is not None:
        _removetree_by_os_walk_ignores(src, *patterns)
    elif mode == "include" and patterns is not None:
        _removetree_by_os_walk_includes(src, *patterns)
    else:
        _save_remove(src)


def current_dir(file):
    return os.path.dirname(os.path.abspath(file))
