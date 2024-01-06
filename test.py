from src.copytree import copytree

if __name__=="__main__":
    copytree("./test/data_1","./build/data_1_copytree_includes", mode='ignore', patterns=['*.txt'], dirs_exist_ok=True)
    copytree("./test/data_1","./build/data_1_copytree_ignores", mode='include', patterns=['*.txt'], dirs_exist_ok=True)