from pyeff.lines import split_struct
from pyeff.lines import load_lines, dump_lines
from pyeff.lines import py_tabspaces


def print_block(block, depth=0):
    s = "    " * depth
    print(f"{s}-----")
    for l in block["lines"]:
        print(l.strip("\n"))

    for sub_block in block["body"]:
        print_block(sub_block, depth + 1)


if __name__ == "__main__":
    lines = load_lines("./test_block_sample.py")

    def calc_indent(block, pre_blocks, cur_indent):
        lines = block["lines"]
        if len(lines) == 0:
            return -1
        first_line = block["lines"][0]
        tab_space = py_tabspaces([first_line])
        print(f'space: {len(tab_space)}"{tab_space}",first_line:{first_line}')
        return len(tab_space)

    top_blocks = split_struct(
        lines,
        pattern_dict={
            "function": {"pattern": ["^def\s+.*", "^async\s+def\s+"]},
            "class": {"pattern": "^class .*"},
            "method": {"pattern": ["^\s+def\s+.*", "^\s+async\s+def\s+"]},
            "global": {"pattern": "^[^\s]"},
        },
        calc_indent=calc_indent,
    )

    for top_block in top_blocks:
        print_block(top_block)
