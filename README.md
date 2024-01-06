# pyfs
advanced python filesystem

## copytree

需求分析：
* Python 拷贝文件夹有 shutil.copytree, os.walk, 以及 os.listdir 递归遍历文件夹三种基本的方式
* 上述3个都或多或少有一些缺点
  * shutil.copytree 支持过滤，但是写起来费劲，此外必须目标文件夹不存在
  * os.walk 需要反复写重复代码
  * os.listdir 递归也需要反复拼接路径

解决方案：
* 实现一个通用的 copytree，支持指定忽略或者过滤模式的文件通配符，支持指定是否允许目标文件夹存在

源代码：
src/copytree.py

函数原型：
* `copytree(src, dst, mode='ignore', patterns=None, dirs_exist_ok=False)`
* 可选的 mode 有 `'ignore'`, `'include'`

用例：

```python
copytree("./test/data_1","./build/data_1_copytree_includes", 
            mode='ignore', 
            patterns=['*.txt'], 
            dirs_exist_ok=True)
    
copytree("./test/data_1","./build/data_1_copytree_ignores", 
            mode='include', 
            patterns=['*.txt'], 
            dirs_exist_ok=True)
```
