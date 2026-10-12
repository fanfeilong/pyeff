# Profile design — declare keys, map sources

## Two namespaces (this is the whole point)

| Namespace | Who owns the names | Used by |
|-----------|--------------------|---------|
| **Declared keys** | You, at Profile assembly time | `@staging_k8s:…`, `auth.ref("staging_k8s", …)`, flow |
| **Source names** | File / env / Nacos / system | only inside `.load(..., map=…)` |

They **may be identical** (identity map) or **different** (explicit `map`).

```text
.declare(API keys)  →  .load(source, map={api_key: source_name})  →  @api_key
```

## Why (your question about two k8s)

`fanout` never guesses “which k8s profile”. It only sees **declared** keys:

```python
auth = (
    Profile()
    .declare("staging_k8s", "prod_k8s")          # ← API contract
    .load(
        FileSource("profiles.yaml"),
        map={
            "staging_k8s": "clusters.staging",   # file can call it anything
            "prod_k8s": "clusters.prod",
        },
    )
)

at("./cfg.json", auth=auth).fanout(
    "@staging_k8s:app-pod:/etc/x",
    "@prod_k8s:app-pod:/etc/x",
)
```

File content (names do **not** need to match API keys):

```yaml
clusters:
  staging:
    scheme: k8s
    context: staging
  prod:
    scheme: k8s
    context: prod
```

## Assembly grammar

```python
auth = (
    Profile()
    .declare("staging_k8s", "prod_k8s", prod_s3={"scheme": "s3"})
    .load(FileSource("~/.pyeff/profiles.yaml"), map={
        "staging_k8s": "clusters.staging",
        "prod_k8s": "clusters.prod",
        # prod_s3 omitted → look up source key "prod_s3"
    })
    .load(EnvSource(), map={"prod_s3": "MINIO"})
    .load(SystemSource(), map={"staging_k8s": "default_k8s"})  # optional overlay
)
```

Rules:

1. **`.declare` first** — no declare ⇒ `.load` raises.
2. **`.load` only fills declared keys** — extra names in the source are ignored.
3. **`map` is `{declared → source}`** — dotted paths allowed (`clusters.staging`).
4. **Missing from map ⇒ identity** — declared name equals source name.
5. **Secrets never in URI strings**; Nacos connection also comes from sources, not literals.

## `load_profile` sugar

```python
auth = load_profile(
    ["staging_k8s", "prod_k8s", "prod_s3"],
    (FileSource("profiles.yaml"), {
        "staging_k8s": "clusters.staging",
        "prod_k8s": "clusters.prod",
    }),
    (EnvSource(), {"prod_s3": "MINIO"}),
)
```

## Sources (same interface, different trees)

| Source | Typical source names |
|--------|----------------------|
| `FileSource` | YAML/JSON/TOML keys or nested dotted paths |
| `EnvSource` | `PYEFF_PROFILES` JSON keys, or `PREFIX + NAME + __ + PARAM` |
| `CliSource` | `--pyeff-profile name.key=value` / `--pyeff-profile-file` |
| `SystemSource` | `default_k8s`, `default_s3`, … (ambient login) |
| `NacosSource` | remote JSON/YAML tree; **conn** from env/file |

### Env flat keys

```bash
# source name MINIO (mapped from declared prod_s3)
export PYEFF_PROFILE_MINIO__ACCESS_KEY=...
export PYEFF_PROFILE_MINIO__SECRET_KEY=...
```

### Nacos conn (also declare → map)

```python
nacos_conn = (
    Profile()
    .declare("nacos")
    .load(EnvSource(prefix="NACOS_", json_var="NACOS_CONFIG"), map={"nacos": "nacos"})
    # or FileSource with map
).as_conn_dict("nacos")

auth = (
    Profile()
    .declare("staging_k8s", "prod_k8s")
    .load(NacosSource(conn=nacos_conn), map={
        "staging_k8s": "k8s.staging",
        "prod_k8s": "k8s.prod",
    })
)
```

## What APIs see

Only declared keys:

- `@staging_k8s:pod:/path`
- `auth.ref("staging_k8s", "pod:/path")`
- Undeclared `@other:…` → `ProfileError: Key 'other' was not declared`
