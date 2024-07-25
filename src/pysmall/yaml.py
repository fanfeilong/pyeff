import os

import yaml
import yaml_include


def load_yaml_full(yaml_file, base_path):
    assert os.path.exists(yaml_file)

    yaml.add_constructor("!inc", yaml_include.Constructor(base_dir=base_path))
    yaml.add_constructor("!include", yaml_include.Constructor(base_dir=base_path))
    # yaml_include.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=base_path)

    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.full_load(f)


def load_yaml_safe(yaml_file):
    assert os.path.exists(yaml_file)

    yaml.add_constructor("!include", lambda loader, node: None, Loader=yaml.SafeLoader)
    yaml.add_constructor("!inc", lambda loader, node: None, Loader=yaml.SafeLoader)

    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(obj, yaml_file):
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, sort_keys=False)


def override_yaml_top_key(yaml_file, key, value):
    with open(yaml_file, "r", encoding="utf-8") as f:
        yaml_lines = f.readlines()

    yaml_lines.append("".join(["\n", f"{key}: {value}", "\n"]))

    with open(yaml_file, "w", encoding="utf-8") as f:
        f.writelines(yaml_lines)
