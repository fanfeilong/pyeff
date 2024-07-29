import hashlib


def hash_string(input_string, algorithm="sha256"):
    """
    Generate a hash of an input string using the specified hashing algorithm.

    Args:
        input_string (str): The string to be hashed.
        algorithm (str): The hashing algorithm to use (e.g., 'sha256', 'md5').
                          Defaults to 'sha256'.

    Returns:
        str: The hexadecimal digest of the hashed string.
    """
    hasher = hashlib.new(algorithm)
    hasher.update(input_string.encode("utf-8"))
    return hasher.hexdigest()
