from src.pyfs_copy import copy
from src.pyfs_remove import remove

import os

def test_copy_remove():
    # clear
    remove('./build')
    assert not os.path.exists('./build')
    
    # test copytree ignore
    copy("./test/data_1","./build/data_1_copytree_ignore", 
             mode='ignore', 
             patterns=['*.txt'], 
             dirs_exist_ok=True)
    assert os.path.exists("./build/data_1_copytree_ignore")
    assert os.path.exists("./build/data_1_copytree_ignore/test.md")
    assert not os.path.exists("./build/data_1_copytree_ignore/test.txt")
    
    # test copytree include
    copy("./test/data_1","./build/data_1_copytree_include", 
             mode='include', 
             patterns=['*.txt'], 
             dirs_exist_ok=True)
    assert os.path.exists("./build/data_1_copytree_include")
    assert not os.path.exists("./build/data_1_copytree_include/test.md")
    assert os.path.exists("./build/data_1_copytree_include/test.txt")
    
    # test remove
    remove("./build/data_1_copytree_to_be_remove")
    assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")
    
    copy("./test/data_1","./build/data_1_copytree_to_be_remove", 
             dirs_exist_ok=False)
    remove("./build/data_1_copytree_to_be_remove/test.md")
    assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")
    assert os.path.exists("./build/data_1_copytree_to_be_remove/test.txt")
    
if __name__=="__main__":
    test_copy_remove()