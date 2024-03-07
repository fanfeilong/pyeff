# pyfs

advanced python filesystem

## copy

需求分析：
* Python 拷贝文件夹有 shutil.copytree, os.walk, 以及 os.listdir 递归遍历文件夹三种基本的方式
* 上述3个都或多或少有一些缺点
  * shutil.copytree 支持过滤，但是写起来费劲，此外必须目标文件夹不存在
  * os.walk 需要反复写重复代码
  * os.listdir 递归也需要反复拼接路径

解决方案：
* 实现一个通用的 copy，支持指定忽略或者过滤模式的文件通配符，支持指定是否允许目标文件夹存在
* 自动根据src是文件还是文件夹选择内部的不同实现

源代码：
src/pyfs_copy.py

函数原型：
* `copy(src, dst, mode='all', patterns=None, dirs_exist_ok=False, follow_symlinks: bool = True, copy_metadata=False)`
* 可选的 mode 有 `'ignore'`, `'include'`, `'all'`，默认值 `'all'`

用例：

```python
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
```

## remove
需求分析：
* Python 删除文件有 os.remove, shutil.rmtree, 以及 os.system("rm -f /a/d"), os.systme("rm -rf /a/d") 等各种方式
* 大部分时候，删除文件和文件夹，有一个简单统一的 remove 方法就可以了

解决方案：
* 实现一个通用的 remove
* 做一些必要的系统路径安全检查，避免误删
* 支持对删除目录树的过滤，匹配的文件，或者不匹配的文件

源代码：
src/pyfs_remove.py

函数原型：
* `remove(path, mode='all', patterns=[])`
* 可选的 mode 有 `'ignore'`, `'include'`, `'all'`，默认值 `'all'`

用例1：
```python
# test remove
remove('./build')
assert not os.path.exists('./build')

remove("./build/data_1_copytree_to_be_remove")
assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")

copytree("./test/data_1","./build/data_1_copytree_to_be_remove", 
            dirs_exist_ok=False)
remove("./build/data_1_copytree_to_be_remove/test.md")
assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")
assert os.path.exists("./build/data_1_copytree_to_be_remove/test.txt")
```

用例2
```python
# test remove with incldue mode
copy("./test/data_1","./build/data_1_copytree_to_be_remove_2", 
          dirs_exist_ok=False)
remove("./build/data_1_copytree_to_be_remove_2", 
        mode="include", 
        patterns=['*.md'])
assert not os.path.exists("./build/data_1_copytree_to_be_remove_2/test.md")
assert os.path.exists("./build/data_1_copytree_to_be_remove_2/test.txt")
```

用例3
```python
# test remove with ignore mode
remove("./build/data_1_copytree_to_be_remove_2", 
        mode="ignore",
        patterns=['*.md'])
assert not os.path.exists("./build/data_1_copytree_to_be_remove_2/test.txt")
```