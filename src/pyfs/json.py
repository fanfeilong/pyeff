import os
import json


def load_json(json_file):
    assert os.path.exists(json_file)
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, json_file):
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
