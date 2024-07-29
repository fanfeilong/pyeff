import os
import json


def load_json(json_file):
    """
    Loads a JSON file and returns its content as a Python object.
    
    Args:
        json_file (str): The path to the JSON file to be loaded.
        
    Returns:
        object: The Python representation of the JSON data.
    
    Raises:
        AssertionError: If the specified file does not exist.
    """
    assert os.path.exists(json_file)
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, json_file):
    """
    Dumps a Python object into a JSON file with indentation and UTF-8 encoding.
    
    Args:
        obj: The Python object to be converted into JSON format.
        json_file: The file path where the JSON data will be saved. 
                   The file will be created if it doesn't exist, and overwritten if it does.
    """
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
