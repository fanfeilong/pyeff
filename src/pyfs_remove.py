import os
import shutil
import fnmatch

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
        print(
            "error: You are trying to delete your root or home directory.")
        return

    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)

def removetree(src, mode='all', patterns=None):
    
    assert mode in ['ignore', 'include', 'all']
    
    if mode =='ignore' and patterns is not None:
        _removetree_by_os_walk_ignores(src, *patterns)
    elif mode=='include' and patterns is not None:
        _removetree_by_os_walk_includes(src, *patterns)
    else:
        _save_remove(src)

def remove(path, mode='all', patterns=None):
    assert mode in ['ignore', 'include', 'all']
    
    removetree(path, mode, patterns)
