import os
import re

def load_all_text(file_name):
    """
    Load and return the entire content of a text file.

    Args:
        file_name (str): The path to the text file to be read.

    Returns:
        str: The contents of the file as a single string.
    """
    with open(file_name, 'r') as f:
        return f.read()

def dump_all_text(content, file_name):
    """
    Write the entire content to a specified file.
    
    Args:
        content (str): The text content to be written to the file.
        file_name (str): The name of the file to which the content will be written.
    """
    with open(file_name, 'w') as f:
        f.write(content)

def load_lines(file_name, remove_new_line=False):
    """
    This function reads a text file and loads its content into a list of lines.
    
    Args:
        file_name (str): The name or path of the file to be read.
        remove_new_line (bool, optional): A flag indicating whether to remove newline characters from the end of each line. Defaults to False.
        
    Returns:
        list[str]: A list containing the lines of the file. If remove_new_line is True, newline characters are stripped from each line's end.
    """
    with open(file_name, 'r') as f:
        lines = f.readlines()
    
    if remove_new_line:
        lines = [l.strip('\n') for l in lines]
    
    return lines

def dump_lines(lines, file_name, append_new_lines=False):
    """
    Write a list of strings to a file, with an option to append newlines.

    Args:
        lines (list of str): The list of strings to be written to the file.
        file_name (str): The name of the file to write to.
        append_new_lines (bool, optional): If True, appends a newline character to each string in the list. Defaults to False.
    
    """
    if append_new_lines:
        lines = [l+'\n' for l in lines]
        
    with open(file_name, 'w') as f:
        f.writelines(lines)

def dump_all_text(content, file_name):
    """
    Write the entire content to a specified file.
    
    Args:
        content (str): The text content to be written to the file.
        file_name (str): The name of the file to which the content will be written.
    """
    with open(file_name, 'w') as f:
        f.write(content)

def split_lines(lines, *patterns):
    """
    Splits a list of strings ('lines') into sublists based on matching patterns.
    Patterns can be either string regex patterns or pre-compiled regex objects.
    
    Args:
    - lines: A list of strings to be split.
    - *patterns: Variable length argument list, where each argument can be a string regex or a regex pattern object.
    
    The function compiles string patterns into regex objects and then iterates through each line.
    If a line matches any of the patterns, it starts a new sublist in the result.
    All non-matching lines are appended to the current sublist.
    
    Returns:
    A list of sublists, where each sublist contains lines that don't match any following patterns
    from the start of the line.
    """
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
    """
    Appends a list of strings as new lines to the end of a specified file.
    
    Args:
        file_name (str): The name or path of the file to which lines will be appended.
        list_of_lines (list of str): The list of strings that will be written to the file,
                                   each followed by a newline character.
    """
    with open(file_name, "a") as f:
        lines = [l + "\n" for l in list_of_lines]
        f.writelines(lines)

def insert_lines(file_name, list_of_lines, head=None, patterns=None):
    """
    Insert lines into a file before a specified line that either starts with a 'head' string or matches patterns.
    
    Args:
        file_name (str): The name of the file to insert lines into.
        list_of_lines (list of str): The lines of text to insert.
        head (str, optional): A header string. Lines are inserted before any line starting with this string. Defaults to None.
        patterns (list of str, optional): A list of regex patterns. If specified, lines are inserted before any line matching any of these patterns. Defaults to None.
    
    Returns:
        bool: True if lines were inserted, False otherwise. The original file is backed up and then replaced with the modified content.
    """
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
    """
    This function comments out or modifies lines in a file starting with a specified header,
    based on a set of patterns using regular expressions. It creates a backup of the original
    file, processes the file to comment lines that meet the criteria, and then replaces the 
    original file if changes were made.

    Parameters:
    - file_name (str): The name of the file to process.
    - head (str): The header string that lines must start with to be considered for commenting.
    - patterns (list[str] or None): A list of regex patterns. If a line starting with 'head'
      matches any of these patterns, it will be commented out. If None, all lines starting with
      'head' will be commented.
    - commentor (str): The character used for commenting (default is '#').

    Returns:
    - bool: True if the file was changed, False otherwise.
    """
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
