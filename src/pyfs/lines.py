import os
import re


def append_lines(file_name, list_of_lines):
    with open(file_name, "a") as f:
        lines = [l + "\n" for l in list_of_lines]
        f.writelines(lines)


def insert_lines(file_name, list_of_lines, head=None, patterns=None):
    dummy_file = file_name + ".bak"
    has_changed = False
    new_lines = []
    with open(file_name, "r") as read_obj:
        for line in read_obj.readlines():
            new_lines.append(line)
            if head and line.startswith(head):
                if patterns is None:
                    is_match = True
                else:
                    is_match = False
                    for pattern in patterns:
                        match_obj = re.search(pattern, line)
                        if match_obj:
                            is_match = True
                            break
                if is_match:
                    for line in list_of_lines:
                        new_lines.append(line + "\n")
                    has_changed = True

    if has_changed:
        with open(dummy_file, "w") as write_obj:
            for line in new_lines:
                write_obj.write(line)
        os.remove(file_name)
        os.rename(dummy_file, file_name)

    return has_changed


def comment_line(file_name, head, patterns, commentor="#"):
    dummy_file = file_name + ".bak"
    has_changed = False
    new_lines = []
    with open(file_name, "r") as read_obj:
        for line in read_obj.readlines():

            if line.startswith(head):
                if patterns is None:
                    is_match = True
                else:
                    is_match = False
                    for pattern in patterns:
                        match_obj = re.search(pattern, line)
                        if match_obj:
                            is_match = True
                            break
                if is_match:
                    new_lines.append(f"{commentor} " + line)
                    has_changed = True
            else:
                new_lines.append(line)

    if has_changed:
        with open(dummy_file, "w") as write_obj:
            for line in new_lines:
                write_obj.write(line)
        os.remove(file_name)
        os.rename(dummy_file, file_name)

    return has_changed


def replace_line(file_name, head, patterns, replace):
    dummy_file = file_name + ".bak"
    has_changed = False
    new_lines = []
    with open(file_name, "r") as read_obj:
        for line in read_obj.readlines():

            if line.startswith(head):
                if patterns is None:
                    is_match = True
                else:
                    is_match = False
                    for pattern in patterns:
                        match_obj = re.search(pattern, line)
                        if match_obj:
                            is_match = True
                            break
                if is_match:
                    new_lines.append(replace + "\n")
                    has_changed = True
            else:
                new_lines.append(line)

    if has_changed:
        with open(dummy_file, "w") as write_obj:
            for line in new_lines:
                write_obj.write(line)
        os.remove(file_name)
        os.rename(dummy_file, file_name)

    return has_changed
