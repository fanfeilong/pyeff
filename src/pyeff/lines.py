import os
import re

def load_all_text(file_name):
    with open(file_name, 'r') as f:
        return f.read()

def dump_all_text(content, file_name):
    with open(file_name, 'w') as f:
        f.write(content)

def load_lines(file_name, remove_new_line=False):
    with open(file_name, 'r') as f:
        lines = f.readlines()
    
    if remove_new_line:
        lines = [l.strip('\n') for l in lines]
    
    return lines

def dump_lines(lines, file_name, append_new_lines=False):
    if append_new_lines:
        lines = [l+'\n' for l in lines]
        
    with open(file_name, 'w') as f:
        f.writelines(lines)

def dump_all_text(content, file_name):
    with open(file_name, 'w') as f:
        f.write(content)

def split_lines(lines, *patterns):
    all_patterns = []
    for pattern in patterns:
        if isinstance(pattern, str):
            all_patterns.append(re.compile(pattern))
        else:
            all_patterns.extend(pattern)
    
    result = [[]]
    
    for line in lines:
        for pattern in all_patterns:
            if re.match(pattern, line):
                result.append([])
                result[-1].append(line)
                break
        else:
            result[-1].append(line)
    
    return [lines for lines in result if lines]

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
