import os
import shutil
import fnmatch

def copytree_by_shutils_ignores(src, dst, *patterns):
    def ignore_patterns(*patterns):
        def _ignore_patterns(path, names):
            ignored_names = []
            for pattern in patterns:
                ignored_names.extend(fnmatch.filter(names, pattern))
            return set(ignored_names)
        return _ignore_patterns
    shutil.copytree(src, dst, ignore=ignore_patterns(*patterns))

def copytree_by_shutils_includes(src,dst,*patterns):
    def include_patterns(*patterns):
        """只包含匹配模式的文件."""
        def _ignore_patterns(path, names):
            # 将所有名称初始化为忽略集合
            keepers = set()
            # 遍历每个模式
            for pattern in patterns:
                # 使用 fnmatch.filter 匹配当前目录下的文件名
                matched = fnmatch.filter(names, pattern)
                # 将匹配的文件从忽略集合中移除
                keepers.update(set(matched))
            # 计算最终忽略集合：所有文件 - 保留的文件
            ignore = set(name for name in names if name not in keepers and not os.path.isdir(os.path.join(path, name)))
            # 返回忽略集合
            return ignore
        return _ignore_patterns

    # 现在使用 shutil.copytree 并传递这个自定义的忽略函数
    shutil.copytree(src, dst, ignore=include_patterns(*patterns))
    
def copytree_by_os_walk_includes(src, dst, *patterns):
    # 确保目标目录存在
    os.makedirs(dst, exist_ok=True)
    
    if patterns is None:
        patterns = ['*']  # 默认复制所有文件
    
    for root, dirs, files in os.walk(src):
        # 计算目标目录的路径
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        # 过滤出匹配指定一组模式的文件列表
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))
        
        # 复制所有符合条件的文件
        for file in matched_files:
            src_file_path = os.path.join(root, file)
            dest_file_path = os.path.join(dest_dir, file)
            shutil.copy2(src_file_path, dest_file_path)  # 使用 copy2 以保留元数据

def copytree_by_os_walk_ignores(src, dst, *patterns):
    # 确保目标目录存在
    os.makedirs(dst, exist_ok=True)
    
    if patterns is None:
        patterns = ['*']  # 默认复制所有文件
    
    for root, dirs, files in os.walk(src):
        # 计算目标目录的路径
        dest_dir = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(dest_dir, exist_ok=True)

        # 过滤出匹配指定一组模式的文件列表
        matched_files = []
        for pattern in patterns:
            matched_files.extend(fnmatch.filter(files, pattern))
        
        # 复制所有符合条件的文件
        for file in files:
            if not file in matched_files:
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(dest_dir, file)
                shutil.copy2(src_file_path, dest_file_path)  # 使用 copy2 以保留元数据

def copytree_ignores(src, dst, patterns=None, dirs_exist_ok=False):
    if dirs_exist_ok:
        copytree_by_os_walk_ignores(src, dst, *patterns)
    else:
        copytree_by_shutils_ignores(src, dst, *patterns)                

def copytree_includes(src, dst, patterns=None,  dirs_exist_ok=False):
    if dirs_exist_ok:
        copytree_by_os_walk_includes(src, dst, *patterns)
    else:
        copytree_by_shutils_includes(src, dst, *patterns)

def copytree(src, dst, mode='all', patterns=None, dirs_exist_ok=False):
    
    assert mode in ['ignore', 'include', 'all']
    
    if mode =='ignore':
        copytree_ignores(src, dst, patterns=patterns, dirs_exist_ok=dirs_exist_ok)
    elif mode=='include':
        copytree_includes(src, dst, patterns=patterns, dirs_exist_ok=dirs_exist_ok)
    else:
        copytree_ignores(src, dst, patterns=[], dirs_exist_ok=dirs_exist_ok)

def copy(src, dst, mode='all', patterns=None, dirs_exist_ok=False, follow_symlinks: bool = True, copy_metadata=False):
    if os.path.isfile(src):
        if copy_metadata:
            shutil.copy(src,dst, follow_symlinks = follow_symlinks)
        else:
            shutil.copy2(src,dst, follow_symlinks = follow_symlinks)
    else:
        copytree(src, dst, mode=mode, patterns=patterns, dirs_exist_ok=dirs_exist_ok)