from src.copytree import copytree
from src.remove import remove

import os

if __name__=="__main__":
    # clear
    remove('./build')
    assert not os.path.exists('./build')
    
    # test copytree ignore
    copytree("./test/data_1","./build/data_1_copytree_ignore", 
             mode='ignore', 
             patterns=['*.txt'], 
             dirs_exist_ok=True)
    assert os.path.exists("./build/data_1_copytree_ignore")
    assert os.path.exists("./build/data_1_copytree_ignore/test.md")
    assert not os.path.exists("./build/data_1_copytree_ignore/test.txt")
    
    # test copytree include
    copytree("./test/data_1","./build/data_1_copytree_include", 
             mode='include', 
             patterns=['*.txt'], 
             dirs_exist_ok=True)
    assert os.path.exists("./build/data_1_copytree_include")
    assert not os.path.exists("./build/data_1_copytree_include/test.md")
    assert os.path.exists("./build/data_1_copytree_include/test.txt")
    
    # test remove
    remove("./build/data_1_copytree_to_be_remove")
    assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")
    
    copytree("./test/data_1","./build/data_1_copytree_to_be_remove", 
             dirs_exist_ok=False)
    remove("./build/data_1_copytree_to_be_remove/test.md")
    assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")
    assert os.path.exists("./build/data_1_copytree_to_be_remove/test.txt")
    