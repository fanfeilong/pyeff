import os

from loguru import logger


def logger_file_info(any_file):
    """
    Logs the content of the specified file, excluding empty lines.
    
    This function begins by logging a message indicating the file to be shown,
    then asserts that the file exists to prevent runtime errors. It proceedes to read
    the file line by line, stripping newline characters and any leading/trailing whitespace.
    Non-empty lines are then logged using the `logger.info` method.

    Args:
        any_file (str): The path to the file whose content needs to be logged.

    Raises:
        AssertionError: If the provided file does not exist.
    """
    logger_table_begin(f"show file:{any_file}")
    assert os.path.exists(any_file)
    with open(any_file, "r") as f:
        for l in f.readlines():
            l = l.strip("\n")
            if l.strip() != "":
                logger.info(l)
    logger_table_end()


def logger_section(lines):
    """
    This function logs a section with a defined header and footer using a logger.
    It handles both string inputs and iterable inputs (like lists), logging each element individually.
    
    Args:
    lines (str or iterable): The content to be logged. If it's a string, it's logged as a single entry.
                             If it's an iterable, each item is logged on a separate line.
    """
    logger.info("")
    logger.info("---------------")
    if type(lines) == type(""):
        logger.info(lines)
    else:
        for line in lines:
            logger.info(line)
    logger.info("---------------")


def logger_table_begin(title):
    """
    Begin logging a section with a title in a table-like format.
    
    This function prints an empty line, two dashes to demarcate, the title,
    and then another line of dashes to structure log output visually.

    Parameters:
    title (str): The title to be displayed for the log section.
    """
    logger.info("")
    logger.info("---------------")
    logger.info(title)
    logger.info("---------------")


def logger_table_end(tail_title=None):
    """
    Ends a logging section with a separator and optional tail title.
    
    This function is designed to provide a standardized way to conclude logging
    for a table-like section in a log file. It prints a separator line to demarcate
    the end of a section, optionally adds a title at the end, and then adds a newline
    for readability.

    :param tail_title: Optional title to be logged after the separator, defaults to None
    :type tail_title: str, optional
    """
    logger.info("---------------")
    if tail_title is not None:
        logger.info(tail_title)
    logger.info("")
