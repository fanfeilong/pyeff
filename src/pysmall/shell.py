import os

from loguru import logger


def run_cmds(cmds, cwd=None, tip=None, check=False, join=False):
    if join:
        _run_cmds_join(cmds, cwd=cwd, tip=tip, check=check)
    else:
        _run_cmds_split(cmds, cwd=cwd, tip=tip, check=check)


def _run_cmds_join(cmds, cwd=None, tip=None, check=False):
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
