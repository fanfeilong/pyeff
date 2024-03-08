import os
import shutil
import fnmatch
from pathlib import Path

def _save_move(src, dst):
    if not os.path.exists(src):
        return

    if os.path.abspath(src) in ["/", os.path.expanduser("~")] or os.path.abspath(dst) in ["/", os.path.expanduser("~")]:
        print(
            "error: You are trying to move your root or home directory.")
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
        patterns = ['*']  # 默认复制所有文件
    
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

def move(src, dst, mode='all', patterns=None):
    
    assert mode in ['ignore', 'include', 'all']
    
    assert os.path.exists(src)
    
    if os.path.isfile(src):
        _save_move(src, dst)
    else:
        if mode =='ignore' and patterns is not None:
            _movetree_by_os_walk_ignores(src, dst, *patterns)
        elif mode=='include' and patterns is not None:
            _movetree_by_os_walk_includes(src, dst, *patterns)
        else:
            _movetree_by_os_walk_ignores(src, dst)
        