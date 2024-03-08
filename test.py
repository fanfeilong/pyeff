from src.pyfs_copy import copy
from src.pyfs_remove import remove
from src.pyfs_move import move

import os

def test_clear():
    # clear
    remove('./build')
    assert not os.path.exists('./build')

def test_copy_remove():
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
    
    # test remove with incldue mode
    copy("./test/data_1","./build/data_1_copytree_to_be_remove_2", 
             dirs_exist_ok=False)
    remove("./build/data_1_copytree_to_be_remove_2", 
           mode="include", 
           patterns=['*.md'])
    assert not os.path.exists("./build/data_1_copytree_to_be_remove_2/test.md")
    assert os.path.exists("./build/data_1_copytree_to_be_remove_2/test.txt")
    
    # test remove with ignore mode
    remove("./build/data_1_copytree_to_be_remove_2", 
           mode="ignore",
           patterns=['*.md'])
    assert not os.path.exists("./build/data_1_copytree_to_be_remove_2/test.txt")
    
def test_move():
    # test copytree 
    copy("./test/data_1", "./build/data_1_move_source_0")
    copy("./test/data_1", "./build/data_1_move_source_1")
    copy("./test/data_1", "./build/data_1_move_source_2")
    
    # test move file and dir 
    # remove("./build/data_1_move")
    
    move("./build/data_1_move_source_0/sub_1/test.md","./build/data_1_move/sub_1/test.md")
    assert os.path.exists('./build/data_1_move/sub_1/test.md')
    assert not os.path.exists('./build/data_1_move_source_0/sub_1/test.md')
    
    move("./build/data_1_move_source_0/sub_2","./build/data_1_move/sub_2")
    assert os.path.exists('./build/data_1_move/sub_2')
    assert os.path.exists('./build/data_1_move/sub_2/test.txt')
    assert os.path.exists('./build/data_1_move/sub_2/test.md')
    
    assert not os.path.exists('./build/data_1_move_source_0/sub_2')
    assert not os.path.exists('./build/data_1_move_source_0/sub_2/test.txt')
    assert not os.path.exists('./build/data_1_move_source_0/sub_2/test.md')
    
    # test move tree ignore
    # remove("./build/data_1_move_ignore")
    move("./build/data_1_move_source_1","./build/data_1_move_ignore", 
             mode='ignore', 
             patterns=['*.txt'])
    assert os.path.exists("./build/data_1_move_ignore")
    
    assert os.path.exists("./build/data_1_move_ignore/test.md")
    assert not os.path.exists("./build/data_1_move_source_1/test.md")
    
    assert not os.path.exists("./build/data_1_move_ignore/test.txt")
    assert os.path.exists("./build/data_1_move_source_1/test.txt")
    
    assert os.path.exists("./build/data_1_move_ignore/sub_1/test.md")
    assert not os.path.exists("./build/data_1_move_source_1/sub_1/test.md")
    
    assert not os.path.exists("./build/data_1_move_ignore/sub_1/test.txt")
    assert os.path.exists("./build/data_1_move_source_1/sub_1/test.txt")
    
    # test move tree include
    # remove("./build/data_1_move_include")
    move("./build/data_1_move_source_2","./build/data_1_move_include", 
             mode='include', 
             patterns=['*.txt'])
    
    assert os.path.exists("./build/data_1_move_include/test.txt")
    assert not os.path.exists("./build/data_1_move_source_2/test.txt")
    
    assert not os.path.exists("./build/data_1_move_include/test.md")
    assert os.path.exists("./build/data_1_move_source_2/test.md")
    
    assert os.path.exists("./build/data_1_move_include/sub_1/test.txt")
    assert not os.path.exists("./build/data_1_move_source_2/sub_1/test.txt")
    
    assert not os.path.exists("./build/data_1_move_include/sub_1/test.md")
    assert os.path.exists("./build/data_1_move_source_2/sub_1/test.md")
    
    
if __name__=="__main__":
    test_clear()
    test_copy_remove()
    test_move()
