import os
import shutil
import fnmatch

import re
import json

import yaml
import yaml_include

from loguru import logger


# ----------------------------
# 文件读取/写入
# ----------------------------
def load_yaml_full(yaml_file, base_path):
    assert os.path.exists(yaml_file)

    yaml.add_constructor("!inc", yaml_include.Constructor(base_dir=base_path))
    yaml.add_constructor("!include", yaml_include.Constructor(base_dir=base_path))
    # yaml_include.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=base_path)

    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.full_load(f)


def load_yaml_safe(yaml_file):
    assert os.path.exists(yaml_file)

    yaml.add_constructor("!include", lambda loader, node: None, Loader=yaml.SafeLoader)
    yaml.add_constructor("!inc", lambda loader, node: None, Loader=yaml.SafeLoader)

    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(obj, yaml_file):
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, sort_keys=False)


def override_yaml_top_key(yaml_file, key, value):
    with open(yaml_file, "r", encoding="utf-8") as f:
        yaml_lines = f.readlines()

    yaml_lines.append("".join(["\n", f"{key}: {value}", "\n"]))

    with open(yaml_file, "w", encoding="utf-8") as f:
        f.writelines(yaml_lines)


def load_json(json_file):
    assert os.path.exists(json_file)
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, json_file):
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


# ----------------------------
# 日志分组
# ----------------------------
def logger_file_info(any_file):
    logger_table_begin(f"show file:{any_file}")
    assert os.path.exists(any_file)
    with open(any_file, "r") as f:
        for l in f.readlines():
            l = l.strip("\n")
            if l.strip() != "":
                logger.info(l)
    logger_table_end()


def logger_section(lines):
    logger.info("")
    logger.info("---------------")
    if type(lines) == type(""):
        logger.info(lines)
    else:
        for line in lines:
            logger.info(line)
    logger.info("---------------")


def logger_table_begin(title):
    logger.info("")
    logger.info("---------------")
    logger.info(title)
    logger.info("---------------")


def logger_table_end(tail_title=None):
    logger.info("---------------")
    if tail_title is not None:
        logger.info(tail_title)
    logger.info("")


# ----------------------------
# 执行命令
# ----------------------------
def run_cmds(cmds, cwd=None, tip=None, check=False, join=False):
    if join:
        _run_cmds_join(cmds, cwd=cwd, tip=tip, check=check)
    else:
        _run_cmds_split(cmds, cwd=cwd, tip=tip, check=check)


def _run_cmds_join(cmds, cwd=None, tip=None, check=False):
    head = f"{tip}: " if tip else ""

    cmd = " ".join(cmds)

    if cwd is not None:
        full_cmd = f"cd {cwd}&&{cmd}"
    else:
        full_cmd = cmd

    logger.info(f"{head}{full_cmd}")

    ret = os.system(full_cmd)

    if ret != 0:
        logger.warning(f"{head}run cmd failed, ret:{ret}, cmd:{full_cmd}")

    if check:
        assert ret == 0

    return ret


def _run_cmds_split(cmds, cwd=None, tip=None, check=False):
    head = f"{tip}: " if tip is not None else ""
    rets = []
    for cmd in cmds:
        if cwd is not None:
            full_cmd = f"cd {cwd}&&{cmd}"
        else:
            full_cmd = cmd

        logger.info(f"{head}{full_cmd}")

        ret = os.system(full_cmd)

        if ret != 0:
            logger.warning(f"{head}run cmd failed, ret:{ret}, cmd:{full_cmd}")

        if check:
            assert ret == 0

        rets.append(ret)
    return rets


# ----------------------------
# 文件/文件夹 创建，移除，拷贝，移动
# ----------------------------


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

    try:
        shutil.move(src, dst)
    except Exception as e:
        raise


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
            if not file in matched_files:
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
            if not file in matched_files:
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


# ----------------------------
# 文件追加
# ----------------------------
def append_lines(file_name, list_of_lines):
    with open(file_name, "a") as f:
        lines = [l + "\n" for l in list_of_lines]
        f.writelines(lines)


def insert_lines(file_name, list_of_lines, head=None, patterns=None):
    dummy_file = file_name + ".bak"
    has_changed = False
    new_lines = []
    with open(file_name, "r") as read_obj:
        for line in read_obj.readlines():
            new_lines.append(line)
            if head and line.startswith(head):
                if patterns is None:
                    is_match = True
                else:
                    is_match = False
                    for pattern in patterns:
                        match_obj = re.search(pattern, line)
                        if match_obj:
                            is_match = True
                            break
                if is_match:
                    for line in list_of_lines:
                        new_lines.append(line + "\n")
                    has_changed = True

    if has_changed:
        with open(dummy_file, "w") as write_obj:
            for line in new_lines:
                write_obj.write(line)
        os.remove(file_name)
        os.rename(dummy_file, file_name)

    return has_changed


def get_python_file_func_indent_spaces(filepath, func):
    with open(filepath, "r") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped and stripped.startswith(func):
            i += 1
            while i < len(lines):
                line = lines[i]
                stripped = line.lstrip()
                if stripped:
                    pos = line.find(stripped)
                    if pos >= 0:
                        tab_spaces = []
                        for i in range(0, pos):
                            if line[i] == " ":
                                tab_spaces.append(" ")
                            elif line[i] == "\t":
                                tab_spaces.append("\t")
                        return "".join(tab_spaces)
                i += 1
        i += 1

    raise ValueError("No indented lines found.")


def comment_line(file_name, head, patterns, commentor="#"):
    dummy_file = file_name + ".bak"
    has_changed = False
    new_lines = []
    with open(file_name, "r") as read_obj:
        for line in read_obj.readlines():

            if line.startswith(head):
                if patterns is None:
                    is_match = True
                else:
                    is_match = False
                    for pattern in patterns:
                        match_obj = re.search(pattern, line)
                        if match_obj:
                            is_match = True
                            break
                if is_match:
                    new_lines.append(f"{commentor} " + line)
                    has_changed = True
            else:
                new_lines.append(line)

    if has_changed:
        with open(dummy_file, "w") as write_obj:
            for line in new_lines:
                write_obj.write(line)
        os.remove(file_name)
        os.rename(dummy_file, file_name)

    return has_changed


def replace_line(file_name, head, patterns, replace):
    dummy_file = file_name + ".bak"
    has_changed = False
    new_lines = []
    with open(file_name, "r") as read_obj:
        for line in read_obj.readlines():

            if line.startswith(head):
                if patterns is None:
                    is_match = True
                else:
                    is_match = False
                    for pattern in patterns:
                        match_obj = re.search(pattern, line)
                        if match_obj:
                            is_match = True
                            break
                if is_match:
                    new_lines.append(replace + "\n")
                    has_changed = True
            else:
                new_lines.append(line)

    if has_changed:
        with open(dummy_file, "w") as write_obj:
            for line in new_lines:
                write_obj.write(line)
        os.remove(file_name)
        os.rename(dummy_file, file_name)

    return has_changed
