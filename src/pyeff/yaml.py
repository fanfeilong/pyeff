import os

import yaml
import yaml_include


def load_yaml_full(yaml_file, base_path):
    """
    Load a YAML file, supporting the inclusion of other YAML files via the '!inc' or '!include' tags.
    
    Args:
        yaml_file (str): The path to the YAML file to be loaded.
        base_path (str): The base directory used for resolving relative paths in '!inc' or '!include' directives.
        
    Returns:
        object: The data structure loaded from the YAML file, which could be a dict, list, or a scalar depending on the YAML content.
    
    Raises:
        AssertionError: If the specified yaml_file does not exist.
    """
    assert os.path.exists(yaml_file)

    yaml.add_constructor("!inc", yaml_include.Constructor(base_dir=base_path))
    yaml.add_constructor("!include", yaml_include.Constructor(base_dir=base_path))
    # yaml_include.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=base_path)

    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.full_load(f)


def load_yaml_safe(yaml_file):
    """
    Safely loads a YAML file, ensuring its existence and handles custom constructors for 'include' directives.
    
    This function performs a safety check by asserting the existence of the specified YAML file.
    It then adds custom constructors to the YAML SafeLoader to handle pseudotags like '!include' or '!inc',
    although they are currently implemented to do nothing (practically ignoring these tags).
    Finally, it opens the file and loads its content using the modified SafeLoader.
    
    Parameters:
    - yaml_file (str): The path to the YAML file to be loaded.
    
    Returns:
    - object: The parsed content of the YAML file.
    
    Raises:
    - AssertionError: If the specified YAML file does not exist.
    """
    assert os.path.exists(yaml_file)

    yaml.add_constructor("!include", lambda loader, node: None, Loader=yaml.SafeLoader)
    yaml.add_constructor("!inc", lambda loader, node: None, Loader=yaml.SafeLoader)

    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(obj, yaml_file):
    """
    Writes the given Python object to a YAML file.

    Args:
        obj: The Python object to be serialized into YAML format.
        yaml_file (str): The file path where the YAML data will be saved.

    This function opens the specified file in write mode ('w') with UTF-8 encoding,
    and uses yaml.dump to serialize 'obj' into YAML format, ensuring that the output
    keys are not sorted alphabetically by setting 'sort_keys' to False.
    """
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, sort_keys=False)


def override_yaml_top_key(yaml_file, key, value):
    """
    Append or update a key-value pair at the top level of a YAML file.
    
    This function reads a YAML file, detects its content, and then adds or overrides
    the specified key with the given value at the beginning of the file,
    ensuring the file's original content remains intact.

    :param yaml_file: Path to the YAML file to be modified.
    :param key: The key to be added or whose value is to be updated.
    :param value: The value associated with the key.
    """
    with open(yaml_file, "r", encoding="utf-8") as f:
        yaml_lines = f.readlines()

    yaml_lines.append("".join(["\n", f"{key}: {value}", "\n"]))

    with open(yaml_file, "w", encoding="utf-8") as f:
        f.writelines(yaml_lines)
