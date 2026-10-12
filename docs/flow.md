# Flow design — minimizing cognitive load

## The problem

Unified `copy` / `load_json` / `hash_file` already work across URIs, but scripts stay procedural:

```python
cfg = load_json(src)
cfg["env"] = "staging"
dump_json(cfg, src)
copy(src, dst1)
copy(src, dst2)
assert hash_file(src) == hash_file(dst1)
```

Users juggle **many verbs** and **temporary variables**. That is cognitive load.

## Design goal

One sentence to remember:

> **Point at a place → optionally edit its content → send it → check it.**

## Grammar (only this)

```text
at(WHERE) → [LOAD] → [EDIT] → [SAVE] → [SEND] → [CHECK]
```

| Family | Nodes (methods) | What the user thinks |
|--------|-----------------|----------------------|
| WHERE  | `at` | “我指着这里” |
| LOAD   | `json` `yaml` `text` `bytes` | “拿出内容” |
| EDIT   | `update` `merge` `map` | “改一下” |
| SAVE   | `save` | “写回去 / 写到别处” |
| SEND   | `to` `fanout` `move_to` | “送到别处（1 / N / 剪切）” |
| CHECK  | `assert_exists` `assert_same_hash` | “确认没错” |

Inspect helpers (`exists` `hash` `size` `tree` `search` `listdir` `read`) **do not change** where the finger points.

## Why not a big node catalog?

| Temptation | Why we rejected it |
|------------|--------------------|
| Separate `Loc` / `Doc` / `Pipeline` types | Users must learn type transitions |
| Plugin “node graph” (ReadNode, HashNode, …) | Looks powerful, feels like Airflow |
| Backend-specific methods (`to_docker`, `to_s3`) | Defeats URI abstraction |
| Auto-magic `pipe \|` operator soup | Hard to debug, opaque errors |

**Rule:** if a new method does not fit WHERE/LOAD/EDIT/SAVE/SEND/CHECK, do not add it to Flow — keep it as a plain function in `ops` / modules.

## State the user must track

Only two bits of state, both optional to think about:

1. **uri** — where the finger points (always set)
2. **payload** — in-memory content after LOAD; `dirty` if EDIT happened

`fanout` / `to` auto-flush dirty payload to the current uri before copying. Users who prefer explicitness call `.save()` first.

## Pointer movement rules (predictable)

| Method | Finger moves to |
|--------|-----------------|
| `at(u)` | `u` |
| `json/yaml/text/bytes` | unchanged |
| `update/merge/map` | unchanged |
| `save()` | unchanged (or `dst` if given) |
| `save(dst)` | `dst` |
| `to(dst)` | `dst` |
| `fanout(*dsts)` | **unchanged (source)** |
| `move_to(dst)` | `dst` |
| `assert_*` | unchanged |

`fanout` keeps the finger on the source on purpose: “broadcast from here, then verify from here.”

## Example (release)

```python
from pyeff import at

(
    at("./configs/app.json")
    .json()
    .update(env="staging", release="2026-10-12")
    .save()
    .fanout(
        "docker:app-dev:/etc/app/config.json",
        "ssh:deploy@test-01:/opt/app/config.json",
        "s3://configs/app/staging/config.json",
    )
    .assert_same_hash(
        "docker:app-dev:/etc/app/config.json",
        "ssh:deploy@test-01:/opt/app/config.json",
        "s3://configs/app/staging/config.json",
    )
)
```

## Relationship to `ops`

Flow is **sugar over** `ops` / `json` / `yaml` / `hash`.  
Low-level APIs remain for one-liners and library integration. Flow is for multi-step human scripts.
