# pyeff

a small python library, which include user friendly api, includes fs, json, yaml, logger, and so on.

## Install

```bash
pip install pyeff
```

## module: pyeff.fs

all API in pyeff.fs:

* `remove` remove file, files or dir
* `copy` copy source file or dir to dest file or dir
* `move` move source file or dir to dest file or dir
* `search` search file dir in source dir
* `ensure` remove dir if exists and create new
* `current_dir` find current dir by file path, like `current_dir(__file__)`
* `listdir` list sub path in source dir, filter by extensions, sort and return abs path

### API: pyeff.fs.remove

* `remove(path, mode='all', patterns=[])`
* option mode  `'ignore'`, `'include'`, `'all'`, default is `'all'`

example-1：

```python
from pyeff.fs import remove, copy

# test remove
remove('./build')
assert not os.path.exists('./build')

remove("./build/data_1_copytree_to_be_remove")
assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")

copy("./test/data_1","./build/data_1_copytree_to_be_remove", 
            dirs_exist_ok=False)
remove("./build/data_1_copytree_to_be_remove/test.md")
assert not os.path.exists("./build/data_1_copytree_to_be_remove/test.md")
assert os.path.exists("./build/data_1_copytree_to_be_remove/test.txt")
```

example-2

```python
from pyeff.fs import remove, copy

# test remove with incldue mode
copy("./test/data_1","./build/data_1_copytree_to_be_remove_2", 
          dirs_exist_ok=False)
remove("./build/data_1_copytree_to_be_remove_2", 
        mode="include", 
        patterns=['*.md'])
assert not os.path.exists("./build/data_1_copytree_to_be_remove_2/test.md")
assert os.path.exists("./build/data_1_copytree_to_be_remove_2/test.txt")
```

example-3

```python
from pyeff.fs import remove, copy

# test remove with ignore mode
remove("./build/data_1_copytree_to_be_remove_2", 
        mode="ignore",
        patterns=['*.md'])
assert not os.path.exists("./build/data_1_copytree_to_be_remove_2/test.txt")
```

### API: pyeff.fs.copy

* `copy(src, dst, mode='all', patterns=None, dirs_exist_ok=False, follow_symlinks: bool = True, copy_metadata=False)`
* option mode `'ignore'`, `'include'`, `'all'`, default is `'all'`

example:

```python
from pyeff.fs import remove, copy

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

### API: pyeff.fs.move

* `move(src, dst, mode='all', patterns=None)`
* option modes `'ignore'`, `'include'`, `'all'`, default is `'all'`

example-1:

```python
from pyeff.fs import move

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
```

example-2

```python
from pyeff.fs import move

# test move tree ignore
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
```

example-3:

```python
from pyeff.fs import move

# test move tree include
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
```

## module: pyeff.json

```python
# src/tests/test.py

from pyeff.json import load_json, dump_json

j1 = load_json("./data_2/json/1.json")
dump_json(j1, "../../build/1.json")

```

## module: pyeff.yaml

```python
# src/tests/test.py

from pyeff.yaml import load_yaml_full, load_yaml_safe

y = load_yaml_full("./data_2/yaml/0.yml", "./data_2/yaml")
assert y["name"] == "0"
assert y["file1"]["name"] == "1"
assert y["file2"]["name"] == "2"

dump_yaml(y, "../../build/0.full.yml")
y_full = load_yaml_safe("../../build/0.full.yml")
assert y_full["name"] == "0"
assert y_full["file1"]["name"] == "1"
assert y_full["file2"]["name"] == "2"

y = load_yaml_safe("./data_2/yaml/0.yml")
assert y["name"] == "0"
assert y["file1"] == None
assert y["file2"] == None

```

## module: pyeff.shell

```python
from pyeff.fs import current_dir
from pyeff.shell import run_cmds

run_cmds(
    [
        "cd data_1", 
        "cat test.txt"
    ],
    cwd=current_dir(__file__),
    tip="test",
    check=True,
    join=True,
)

```

## module: pyeff.lines

* `load_all_text` load all text from file
* `dump_all_text` dump all text to file
* `load_lines` load all lines from file, support remove '\n' by remove_new_line option
* `dump_lines` dump all lines to file, support append '\n' by append_new_lines option
* `split_lines` load and split lines in to group by regex pattern
