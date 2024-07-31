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
    with open(file_name, "r") as f:
        return f.read()


def dump_all_text(content, file_name):
    """
    Write the entire content to a specified file.

    Args:
        content (str): The text content to be written to the file.
        file_name (str): The name of the file to which the content will be written.
    """
    with open(file_name, "w") as f:
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
    with open(file_name, "r") as f:
        lines = f.readlines()

    if remove_new_line:
        lines = [l.strip("\n") for l in lines]

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
        lines = [l + "\n" for l in lines]

    with open(file_name, "w") as f:
        f.writelines(lines)


def split(lines, *patterns):
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


def split_struct(lines, pattern_dict, calc_indent):
    """
    Parse a list of lines into structured blocks based on patterns and indentation.
    
    This function iterates through each line of input, identifying blocks that match
    patterns defined in `pattern_dict`. It organizes these blocks hierarchically 
    according to their indentation level, calculated by `calc_indent` function.
    
    Args:
    - lines (list of str): The input lines of text to be parsed.
    - pattern_dict (dict): A dictionary where keys are block names and values are
      patterns (either a string or a list of strings) used to match block start.
    - calc_indent (function): A function that takes a block and preceding blocks
      to calculate the indentation level of the block.
      
    Returns:
    - list of dict: A list of block dictionaries, each representing a structured block
      with details like 'name', 'pattern', 'lines', 'body', and calculated 'indent'.
    """
    current_block = {"name": "top", "pattern": None, "lines": [], "body": []}
    block_stack = [current_block]

    # parse blocks
    for line in lines:
        for name in pattern_dict:
            item = pattern_dict[name]
            pattern = item["pattern"]
            patterns = []
            if type(pattern) == type(""):
                patterns.append(pattern)
            elif type(pattern) == type([]):
                patterns.extend(pattern)

            has_match = False
            for p in patterns:
                if re.match(p, line):
                    current_block = {
                        "name": name,
                        "pattern": pattern,
                        "lines": [],
                        "body": [],
                    }
                    block_stack.append(current_block)
                    has_match = True
                    break
            if has_match:
                break
        current_block["lines"].append(line)

    # chain blocks by indent
    i = 0
    cur_indent = 0
    cur_depth = 0
    indent_depth_map = {}
    pre_indent_last_block_stack = []
    pre_indent_last_block = None
    cur_indent_last_block = None

    top_indent = None
    top_blocks = []
    while i < len(block_stack):
        pre_blocks = block_stack[0:i]

        block = block_stack[i]
        block_indent = calc_indent(block, pre_blocks, cur_indent)
        block["indent"] = block_indent

        if block_indent < 0:
            i += 1
            continue

        if top_indent is None:
            top_indent = block_indent
            cur_depth = 0
            indent_depth_map[block_indent] = cur_depth
            cur_indent = block_indent

        if block_indent > cur_indent:
            # indent step
            if pre_indent_last_block:
                pre_indent_last_block["body"].append(block)
            else:
                cur_indent_last_block["body"].append(block)

            # cur_indent_last_block is the new pre indent last block
            pre_indent_last_block_stack.append(pre_indent_last_block)
            pre_indent_last_block = cur_indent_last_block
            cur_indent_last_block = block

            cur_depth += 1
            indent_depth_map[block_indent] = cur_depth
        elif block_indent < cur_indent:
            # indent back
            target_depth = indent_depth_map[block_indent]
            offset = cur_depth - target_depth
            k = 0
            while k < offset:
                pre_indent_last_block = (
                    pre_indent_last_block_stack.pop()
                    if len(pre_indent_last_block_stack) > 0
                    else None
                )
                k += 1
                cur_depth -= 1

            cur_indent_last_block = block

            if pre_indent_last_block:
                pre_indent_last_block["body"].append(block)
        else:
            # indent keep
            cur_indent_last_block = block

            if pre_indent_last_block:
                pre_indent_last_block["body"].append(block)

        # update cur indent
        cur_indent = block_indent

        if block_indent == top_indent:
            top_blocks.append(block)

        i += 1

    return top_blocks


def py_tabspaces(lines):
    """
    This function examines a list of strings (`lines`) to identify the leading whitespace
    (spaces and tabs) of the first non-empty line. It returns a string representing this
    indentation, composed of either spaces or tabs. If no indented lines are found, it raises
    a ValueError.

    Args:
        lines (list[str]): A list of strings representing lines of code or text.

    Returns:
        str: The whitespace indentation of the first non-empty line.

    Raises:
        ValueError: If the provided list does not contain any indented lines.
    """
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped:
            pos = line.find(stripped)
            if pos >= 0:
                tab_spaces = []
                for i in range(0, pos):
                    if line[i] == " ":
                        tab_spaces.append(" ")
                    elif line[i] == "\t":
                        tab_spaces.append("\t")
                return "".join(tab_spaces)
        i += 1

    raise ValueError("No indented lines found.")


def insert(
    source_lines,
    insert_lines,
    patterns=None,
    append_new_line=False,
    insert_before=False,
):
    """
    Modifies a list of source code lines by inserting new lines before or after lines that match given regex patterns.

    :param source_lines: List of strings representing the source code.
    :param insert_lines: Lines to insert into the source code.
    :param patterns: List of regex patterns used to identify lines where insertion should occur.
    :param append_new_line: Boolean indicating whether to append a newline to each inserted line.
    :param insert_before: Boolean to control insertion position (before or after the matching line).
    :return: A new list of source code lines with the insertions applied, or the original list if no changes were made.
    """
    has_changed = False
    new_lines = []

    for line in source_lines:

        is_match = False
        for pattern in patterns:
            match_obj = re.search(pattern, line)
            if match_obj:
                is_match = True
                break
        if is_match:
            if not insert_before:
                new_lines.append(line)
            for insert_line in insert_lines:
                if append_new_line:
                    insert_line = insert_line + "\n"
                new_lines.append(insert_line)
            if insert_before:
                new_lines.append(line)
            has_changed = True
        else:
            new_lines.append(line)

    return new_lines if has_changed else source_lines


def find(lines, *patterns):
    """
    Search for any of the given patterns in the provided lines of text.

    This function iterates over each line in the 'lines' iterable and checks
    if it matches any of the regex patterns provided in 'patterns' using
    Python's `re.match`. If a match is found, it immediately returns True.
    If no matches are found after checking all lines and patterns, it returns False.

    Parameters:
    - lines (iterable of str): The lines of text to search through.
    - patterns (str): Variable number of regex patterns to search for.

    Returns:
    - bool: True if any pattern matches a line, False otherwise.
    """
    for l in lines:
        for pattern in patterns:
            if re.match(pattern, l):
                return True
    return False


def pair_match(lines, first, second):
    """
    Check if there exists a pair of consecutive elements in 'lines'
    where 'first' condition is true for the first element and 'second' condition is true for the second element.

    Args:
    lines (list): A list of elements to be checked.
    first (function): A function that takes an element from 'lines' and returns a boolean.
    second (function): A function that also takes an element from 'lines' and returns a boolean.

    Returns:
    tuple: A tuple (bool, int) where bool indicates if a matching pair was found, and int is the index of the first element of the pair.
           If no pair is found, returns (False, 0).
    """
    i = 0
    while i < len(lines) and (i + 1) < len(lines):
        if first(lines[i]) and second(lines[i]):
            return True, i

        if first(lines[i]) and second(lines[i + 1]):
            return True, i + 1

        i += 1
    return False, 0


def continue_match(lines, first, second):
    """
    Checks a sequence of lines to find if there's an occurrence where `first` condition is met,
    immediately followed by another occurrence where `second` condition is met at exact next line.

    Args:
        lines (list): A list of strings, representing lines of text to be examined.
        first (function): A function that takes a string and returns a boolean indicating if the condition is met.
        second (function): A function similar to `first`, but for the subsequent condition.

    Returns:
        tuple: A tuple (bool, int) where the bool indicates if the pattern was found, and int is the index of the last matched line.
               If not found, returns (False, 0).
    """
    i = 0
    match_count = 0

    while i < len(lines):
        l = lines[i]
        if first(l):
            match_count += 1

        if second(l):
            if match_count == 1:
                return True, i
            else:
                match_count = 0

        i += 1
    return False, 0


def extract(lines, start, finish):
    """
    Extracts lines from a list 'lines' starting from the line where the 'start' function returns True
    until the line where the 'finish' function returns True, inclusive of the lines where these conditions are met.

    Args:
        lines (list of str): The list of lines to be processed.
        start (function): A function that takes a string (line) and returns a boolean, indicating the start condition.
        finish (function): A function that takes a string (line) and returns a boolean, indicating the finish condition.

    Returns:
        tuple: A tuple containing two elements:
            - list of str: The extracted lines meeting the criteria.
            - int: The index after the last extracted line in the 'lines' list.
    """
    results = []
    j = 0
    enter = False

    while j < len(lines):
        l = lines[j]

        is_enter = False
        if not enter and start(l):
            enter = True
            is_enter = True

        if enter:
            results.append(l)

        if not is_enter and enter and finish(l):
            break

        j += 1

    return results, j
