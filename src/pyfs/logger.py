import os

from loguru import logger


def logger_file_info(any_file):
    logger_table_begin(f"show file:{any_file}")
    assert os.path.exists(any_file)
    with open(any_file, "r") as f:
        for l in f.readlines():
            l = l.strip("\n")
            if l.strip() != "":
                logger.info(l)
    logger_table_end()


def logger_section(lines):
    logger.info("")
    logger.info("---------------")
    if type(lines) == type(""):
        logger.info(lines)
    else:
        for line in lines:
            logger.info(line)
    logger.info("---------------")


def logger_table_begin(title):
    logger.info("")
    logger.info("---------------")
    logger.info(title)
    logger.info("---------------")


def logger_table_end(tail_title=None):
    logger.info("---------------")
    if tail_title is not None:
        logger.info(tail_title)
    logger.info("")
