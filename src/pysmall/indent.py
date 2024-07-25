def get_python_file_func_indent_spaces(filepath, func):
    with open(filepath, "r") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped and stripped.startswith(func):
            i += 1
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
        i += 1

    raise ValueError("No indented lines found.")
