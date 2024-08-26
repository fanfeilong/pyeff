import os
import subprocess
import fnmatch

from loguru import logger

def run_cmds(cmds, cwd=None, tip=None, check=False, join=False):
    """
    Executes a list of commands based on the specified parameters.
    
    Parameters:
    - cmds (list or str): A list of commands or a single string command to be executed.
    - cwd (str, optional): The working directory in which to execute the commands. Defaults to None.
    - tip (str, optional): A tip or message associated with the command execution. Defaults to None.
    - check (bool, optional): If True, the function will check the exit status of the commands. Defaults to False.
    - join (bool, optional): If True, commands are treated as a single string to be executed together. If False, they are executed separately. Defaults to False.
    
    This function chooses between _run_cmds_join and _run_cmds_split based on the 'join' flag.
    """
    if join:
        _run_cmds_join(cmds, cwd=cwd, tip=tip, check=check)
    else:
        _run_cmds_split(cmds, cwd=cwd, tip=tip, check=check)


def _run_cmds_join(cmds, cwd=None, tip=None, check=False):
    """
    Executes a sequence of commands joined into a single string, optionally in a specified directory.
    
    Args:
        cmds (list of str): A list of commands to be executed.
        cwd (str, optional): The current working directory to execute the commands in. Defaults to None.
        tip (str, optional): A prefix message for logging purposes. Defaults to None.
        check (bool, optional): If True, asserts that the command execution was successful. Defaults to False.
    
    Returns:
        int: The return code of the command execution.
    
    Logs:
        - Info: The command being run, prefixed by the tip if provided.
        - Warning: If the command fails, logs the return code and the command.
    """
    head = f"{tip}: " if tip else ""

    cmd = " ".join(cmds)

    if cwd is not None:
        full_cmd = f"cd {cwd}&&{cmd}"
    else:
        full_cmd = cmd

    logger.info(f"{head}{full_cmd}")

    ret = os.system(full_cmd)

    if ret != 0:
        logger.warning(f"{head}run cmd failed, ret:{ret}, cmd:{full_cmd}")

    if check:
        assert ret == 0

    return ret


def _run_cmds_split(cmds, cwd=None, tip=None, check=False):
    """
    Executes a list of shell commands, optionally changing the current working directory (cwd),
    providing a prefix tip for log messages, and checking for command success.

    Args:
        cmds (list of str): The commands to be executed.
        cwd (str, optional): The directory to change to before running each command. Defaults to None.
        tip (str, optional): A string to be prepended to each log message. Defaults to None.
        check (bool, optional): If True, asserts that each command returns a success exit code (0). Defaults to False.

    Returns:
        list of int: The exit codes of the commands that were run.
    """
    head = f"{tip}: " if tip is not None else ""
    rets = []
    for cmd in cmds:
        if cwd is not None:
            full_cmd = f"cd {cwd}&&{cmd}"
        else:
            full_cmd = cmd

        logger.info(f"{head}{full_cmd}")

        ret = os.system(full_cmd)

        if ret != 0:
            logger.warning(f"{head}run cmd failed, ret:{ret}, cmd:{full_cmd}")

        if check:
            assert ret == 0

        rets.append(ret)
    return rets

def compress_to_tar_gz(target_directory, file_list, output_tar_gz):
    if not os.path.isdir(target_directory):
        raise ValueError(f"Target directory '{target_directory}' does not exist or is not a directory.")
    
    if os.path.exists(output_tar_gz):
        raise ValueError(f"Output file '{output_tar_gz}' already exists.")

    temp_file_list = 'temp_files.txt'

    temp_file_list = []
    for file in file_list:
        if not os.path.isabs(file):
            file = os.path.join(target_directory, file)
        if not os.path.isfile(file):
            raise ValueError(f"File '{file}' does not exist.")
        
        if not os.path.commonpath([target_directory]) == os.path.commonpath([target_directory, file]):
            raise ValueError(f"File '{file}' is not within the target directory '{target_directory}'.")

        relative_path = os.path.relpath(file, start=target_directory)
        temp_file_list.append(relative_path)
    
    with open(temp_file_list, 'w') as f:
        for file in temp_file_list:
            f.write(f"{file}\n")

    try:
        subprocess.run(['tar', '-czf', output_tar_gz, '-T', temp_file_list, '-C', target_directory], check=True)
    finally:
        os.remove(temp_file_list)

    print(f"Compression successful: '{output_tar_gz}'")
    
def extract_from_tar(tar_file, output_directory, file_patterns=None):
    if not os.path.isfile(tar_file):
        raise ValueError(f"Tar file '{tar_file}' does not exist or is not a file.")

    if not os.path.isdir(output_directory):
        raise ValueError(f"Output directory '{output_directory}' does not exist or is not a directory.")
    
    if file_patterns is None:
        file_patterns = []

    temp_file_list = 'temp_files.txt'

    result = subprocess.run(['tar', '-tf', tar_file], capture_output=True, text=True, check=True)
    all_files = result.stdout.splitlines()

    if file_patterns:
        matching_files = [file for file in all_files if any(fnmatch.fnmatch(file, pattern) for pattern in file_patterns)]
        files_to_extract = matching_files
    else:
        files_to_extract = all_files

    with open(temp_file_list, 'w') as f:
        for file in files_to_extract:
            f.write(f"{file}\n")

    try:
        subprocess.run(['tar', '-xvf', tar_file, '-T', temp_file_list, '-C', output_directory], check=True)
    finally:
        os.remove(temp_file_list)

    print(f"Extraction successful to '{output_directory}'")