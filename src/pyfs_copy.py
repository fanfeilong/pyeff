import os
import shutil
import fnmatch

def _copytree_by_shutils_ignores(src, dst, *patterns):
    def ignore_patterns(*patterns):
        def _ignore_patterns(path, names):
            ignored_names = []
            for pattern in patterns:
                ignored_names.extend(fnmatch.filter(names, pattern))
            return set(ignored_names)
        return _ignore_patterns
    shutil.copytree(src, dst, ignore=ignore_patterns(*patterns))

def _copytree_by_shutils_includes(src,dst,*patterns):
    def include_patterns(*patterns):
        """只包含匹配模式的文件."""
        def _ignore_patterns(path, names):
            keepers = set()
            for pattern in patterns:
                matched = fnmatch.filter(names, pattern)
                keepers.update(set(matched))
            ignore = set(name for name in names if name not in keepers and not os.path.isdir(os.path.join(path, name)))
            return ignore
        return _ignore_patterns

    shutil.copytree(src, dst, ignore=include_patterns(*patterns))
    
def _copytree_by_os_walk_includes(src, dst, *patterns):
    os.makedirs(dst, exist_ok=True)
    
    if patterns is None:
        patterns = ['*'] 
    
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

def _copytree_includes(src, dst, patterns=None,  dirs_exist_ok=False):
    if dirs_exist_ok:
        _copytree_by_os_walk_includes(src, dst, *patterns)
    else:
        _copytree_by_shutils_includes(src, dst, *patterns)

def _copytree(src, dst, mode='all', patterns=None, dirs_exist_ok=False):
    
    assert mode in ['ignore', 'include', 'all']
    
    if mode =='ignore':
        _copytree_ignores(src, dst, patterns=patterns, dirs_exist_ok=dirs_exist_ok)
    elif mode=='include':
        _copytree_includes(src, dst, patterns=patterns, dirs_exist_ok=dirs_exist_ok)
    else:
        _copytree_ignores(src, dst, patterns=[], dirs_exist_ok=dirs_exist_ok)

def copy(src, dst, mode='all', patterns=None, dirs_exist_ok=False, follow_symlinks: bool = True, copy_metadata=False):
    if os.path.isfile(src):
        if copy_metadata:
            shutil.copy(src,dst, follow_symlinks = follow_symlinks)
        else:
            shutil.copy2(src,dst, follow_symlinks = follow_symlinks)
    else:
        _copytree(src, dst, mode=mode, patterns=patterns, dirs_exist_ok=dirs_exist_ok)