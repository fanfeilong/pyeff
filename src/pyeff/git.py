import subprocess


def get_current_commit_info():
    """
    Retrieves the details of the most recent commit from the local git repository.
    This includes the commit hash, author, date, and commit message.
    
    Returns:
        A dictionary with commit details if successful, or None if a git command fails.
    """
    try:
        commit_hash = (
            subprocess.check_output(["git", "rev-parse", "HEAD"])
            .decode("utf-8")
            .strip()
        )

        author = (
            subprocess.check_output(["git", "log", "-1", "--pretty=format:%an"])
            .decode("utf-8")
            .strip()
        )

        date = (
            subprocess.check_output(["git", "log", "-1", "--pretty=format:%ad"])
            .decode("utf-8")
            .strip()
        )

        message = (
            subprocess.check_output(["git", "log", "-1", "--pretty=format:%s"])
            .decode("utf-8")
            .strip()
        )

        return {
            "commit_hash": commit_hash,
            "author": author,
            "date": date,
            "message": message,
        }
    except subprocess.CalledProcessError as e:
        print(f"Error executing git command: {e}")
        return None
