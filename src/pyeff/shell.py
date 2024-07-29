import os

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
