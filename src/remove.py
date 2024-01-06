import os
import shutil

def remove(path):
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
