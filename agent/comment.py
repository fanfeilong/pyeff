import sys
import os
from typing import Any

from openai import OpenAI
from src import pyeff

from datetime import datetime

from loguru import logger


class FunctionComment:
    def __init__(self, client) -> None:
        self.client = client

    def run(self, lines):
        _input = "".join(lines)
        response = self.client.chat.completions.create(
            model="alibaba/Qwen1.5-110B-Chat",
            messages=[
                {
                    "role": "user",
                    "content": "\n".join(
                        [
                            f"1. 请阅读下面的python代码:",
                            f"```{_input}```",
                            f"2. 为每个函数添加必要的英文注释，不要生成中文注释",
                            f"3. 只需要在函数的开头添加注释即可，其他代码行不需要单独的注释",
                            f"4. 原始代码不做任何删减，例如不要自己添加 main 测试代码",
                            f"5. 接着，只返回代码，不要输出开头和结尾的解释文本",
                            f"6. 在返回前，请再次检查，确保已经剔除了非代码区的其他文本",
                        ]
                    ),
                }
            ],
            stream=True,
        )

        results = []
        for chunk in response:
            if chunk.choices[0].delta.content:
                results.append(chunk.choices[0].delta.content)

        lines = "".join(results).split("\n")
        codes = []
        enter = False
        for i in range(len(lines)):
            l = lines[i]

            is_code_line = False
            if enter:
                is_code_line = True

            if l.startswith("```"):
                if not enter:
                    enter = True
                else:
                    break

            if is_code_line:
                codes.append(l + "\n")

        return codes


class CommentAgent:
    def __init__(self) -> None:
        self.config = None
        self.options = None
        self.func_comment = None

    def run(self, config, options) -> Any:
        logger.info("run comment agent")

        self.config = config
        self.options = options

        client = OpenAI(
            api_key=self.options.token, base_url="https://api.siliconflow.cn/v1"
        )

        self.func_comment = FunctionComment(client)

        self.__loop()

    def __loop(self):
        source_dir = os.path.join(
            os.path.dirname(pyeff.fs.current_dir(__file__)), "src/pyeff"
        )

        self.__clean(source_dir)

        for source in pyeff.fs.listdir(
            source_dir, sort=True, extensions=[".py"], abs_path=True
        ):
            self.__iter(source)

        self.__save_point(source_dir)

    def __clean(self, source_dir):
        comment_files = pyeff.fs.search(
            source_dir, mode="include", patterns=["*.comment.py"]
        )

        print(comment_files)

        pyeff.fs.remove(comment_files)

    def __iter(self, source):

        file_collector = []

        # load
        source_lines = pyeff.lines.load_lines(source)

        # split funcs
        source_lines_groups, source_with_parts = self.__split_func(source, source_lines)
        file_collector.append(source_with_parts)

        # gen comment lines by llm
        comment_lines, source_with_comment = self.__gen_func_doc(
            source, source_lines_groups
        )
        file_collector.append(source_with_comment)

        # build func-doc dict
        func_doc_dict = self.__build_func_doc_index(source, comment_lines)

        # apply func doc to soruce
        source_with_doc_lines, source_with_append_comments = self.__apply_func_doc(
            source, source_lines_groups, func_doc_dict
        )
        file_collector.append(source_with_append_comments)

        # update
        pyeff.lines.dump_lines(source_with_doc_lines, source)

        # clean
        pyeff.fs.remove(file_collector)

    def __split_func(self, source, source_lines):
        logger.info(f"__split_func {source}")
        source_lines_groups = pyeff.lines.split(source_lines, ["def .*"])
        lines_with_part_comment = pyeff.lines.insert(
            source_lines,
            [
                "# ------------------------------------",
                "# dump part, for debug",
                "# ------------------------------------",
            ],
            patterns=["def .*"],
            append_new_line=True,
            insert_before=True,
        )
        source_with_parts = source + ".part.comment.py"
        pyeff.lines.dump_lines(lines_with_part_comment, source_with_parts)
        return source_lines_groups, source_with_parts

    def __gen_func_doc(self, source, source_lines_groups):
        logger.info(f"__gen_func_doc {source}")
        comment_lines = []
        for part_lines in source_lines_groups:
            is_py_func = False
            func = None
            for l in part_lines:
                if l.find("def ") >= 0:
                    is_py_func = True
                    func = l

            has_comment, _ = pyeff.lines.pair_match(
                part_lines,
                lambda l: l.strip("\n").strip().endswith("):"),
                lambda l: l.strip().startswith('"""'),
            )

            if not is_py_func or has_comment:
                # keep old lines
                # comment_lines.extend(part_lines)
                comment_lines.extend(["\n"])
            else:
                # gen comment lines with llm
                logger.info(f"call llm for func: {func}...")
                new_part_lines = self.func_comment.run(
                    lines=part_lines,
                )
                comment_lines.extend(new_part_lines)
                comment_lines.extend(["\n"])

        source_with_comment = source + ".comment.py"
        pyeff.lines.dump_lines(comment_lines, source_with_comment)

        return comment_lines, source_with_comment

    def __build_func_doc_index(self, source, comment_lines):
        logger.info(f"__build_func_doc_index {source}")
        func_doc_dict = {}
        for part_lines in pyeff.lines.split(comment_lines, ["def .*"]):
            l = part_lines[0]
            if l.startswith("def "):
                print(l)
                func_doc_lines, _ = pyeff.lines.extract(
                    part_lines,
                    lambda l: l.strip().startswith('"""'),
                    lambda l: l.strip().startswith('"""'),
                )
                func_doc_dict[l] = func_doc_lines
        return func_doc_dict

    def __apply_func_doc(self, source, source_lines_groups, func_doc_dict):
        logger.info(f"__apply_func_doc {source}")
        source_with_doc_lines = []
        for part_lines in source_lines_groups:
            l = part_lines[0]
            if l.startswith("def ") and func_doc_dict.get(l) is not None:
                func_has_no_comment, last_pos = pyeff.lines.continue_match(
                    part_lines,
                    lambda l: l.strip("\n").strip().endswith("):"),
                    lambda l: not l.strip().startswith('"""'),
                )
                if func_has_no_comment:
                    source_with_doc_lines.extend(part_lines[0 : last_pos + 1])
                    source_with_doc_lines.extend(func_doc_dict.get(l))
                    source_with_doc_lines.extend(part_lines[last_pos + 1 :])
            else:
                source_with_doc_lines.extend(part_lines)

        source_with_append_comments = source + ".new.comment.py"
        pyeff.lines.dump_lines(source_with_doc_lines, source_with_append_comments)
        return source_with_doc_lines, source_with_append_comments

    def __save_point(self, source_dir):
        y = input("safe auto comment? [y/n/i]")
        if y == "y":
            commit_name = f"agent_comment_{datetime.now()}"
            pyeff.shell.run_cmds(
                ["git add .", f'git commit -m "{commit_name}"'],
                cwd=source_dir,
                check=True,
            )
        elif y == "n":
            pyeff.shell.run_cmds(
                ["git clean -df .", "git checkout ."], cwd=source_dir, check=True
            )
        else:
            pass
