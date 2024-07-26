import sys
import os

from openai import OpenAI
from src import pyeff

from loguru import logger

class FunctionComment:
    def __init__(self, client) -> None:
        self.client = client
    
    def run(self, lines):
        _input = ''.join(lines)
        response = self.client.chat.completions.create(
            model='alibaba/Qwen1.5-110B-Chat',
            messages=[
                {
                    'role': 'user', 
                    'content': '\n'.join([
                        f"1. 请阅读下面的python代码:",
                        f"```{_input}```",
                        f"2. 为每个函数添加必要的英文注释，不要生成中文注释",
                        f"3. 只需要在函数的开头添加注释即可，其他代码行不需要单独的注释",
                        f"4. 原始代码不做任何删减，例如不要自己添加 main 测试代码",
                        f"5. 接着，只返回代码，不要输出开头和结尾的解释文本",
                        f"6. 在返回前，请再次检查，确保已经剔除了非代码区的其他文本",
                    ])
                }
            ],
            stream=True
        )

        results = []
        for chunk in response:
            if chunk.choices[0].delta.content:
                results.append(chunk.choices[0].delta.content)

        lines = ''.join(results).split('\n')
        codes = []
        enter = False
        for i in range(len(lines)):
            l = lines[i]
            
            is_code_line = False
            if enter:
                is_code_line = True
            
            if l.startswith('```'):
                if not enter:
                    enter = True
                else:
                    break
            
            if is_code_line:
                codes.append(l+'\n')
       
        return codes

if __name__=="__main__":
    dir = pyeff.fs.current_dir(__file__)
    source_dir = os.path.join(dir, "src/pyeff")
    
    pyeff.shell.run_cmds([
            "git clean -df .",
            "git checkout ."
        ],
        cwd=source_dir, 
        check=True
    )
    
    client = OpenAI(
        api_key=sys.argv[1], 
        base_url="https://api.siliconflow.cn/v1"
    )
    
    func_comment = FunctionComment(client)
    
    comment_files = pyeff.fs.search(source_dir, mode='include', patterns=["*.comment.py"])
    
    print(comment_files)
    
    pyeff.fs.remove(comment_files)
    
    for source in pyeff.fs.listdir(source_dir, sort=True, extensions=['.py'], abs_path=True):
        lines = pyeff.lines.load_lines(source)
        
        lines_groups = pyeff.lines.split_lines(lines, ["def "])
        
        source_with_comment = source+'.comment.py'
        
        source_parts = source+'.part.comment.py'
        merge_part = []
        for part in lines_groups:
            merge_part.append('# -------\n')
            merge_part.append('# part\n')
            merge_part.append('# -------\n')
            merge_part.extend(part)
        pyeff.lines.dump_lines(merge_part, source_parts)
        
        new_lines = []
        
        for part_lines in lines_groups:
            has_def = False
            for l in part_lines:
                if l.find('def ')>=0:
                    has_def = True
            if not has_def:
                new_lines.extend(part_lines)
                new_lines.extend(["\n"])
            else:
                new_part_lines = func_comment.run(
                    lines= part_lines,
                )
                new_lines.extend(new_part_lines)
                new_lines.extend(["\n"])

        pyeff.lines.dump_lines(new_lines, source_with_comment)
        
        logger.info(f'source_with_comment: {source_with_comment}')
        
        source_lines = pyeff.lines.load_lines(source)
        comment_lines = pyeff.lines.load_lines(source_with_comment)
        
        func_doc_dict = {}
        i=0
        while i<len(comment_lines):
            l = comment_lines[i]
            if l.startswith('def ')>=0:
                j = i+1
                func_doc_lines = []
                ddd_count = 0
                while j<len(comment_lines):
                    ll = comment_lines[j]
                    if ll.strip().startswith('"""'):
                        ddd_count+=1
                    
                    if ddd_count>0:
                        func_doc_lines.append(ll)
                        
                    if ddd_count==2:
                        break
                    
                    j+=1

                func_doc_dict[l] = func_doc_lines
                i=j+1
            else:
                i+=1
        
        source_with_doc_lines = []
        i=0
        while i<len(source_lines):
            l = source_lines[i]
            source_with_doc_lines.append(l)
            if l.startswith('def ')>=0:
                ll = source_lines[i+1]
                if not ll.strip().startswith('"""'):
                    func_doc_lines = func_doc_dict.get(l)
                    if func_doc_lines is not None:
                        source_with_doc_lines.extend(func_doc_lines)
        
        pyeff.lines.dump_lines(source_with_doc_lines, source)
        
        pyeff.fs.remove([
            source_with_comment,
            source_parts,
        ])