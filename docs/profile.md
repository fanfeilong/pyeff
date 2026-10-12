# Profile design — `map` declares API keys

## One idea

```text
.load(source, map={api_key: source_name})
```

- **map keys** = names later APIs use (`@staging_k8s`, `auth.ref("staging_k8s")`)
- **map values** = names inside that source (file / env / Nacos / system)
- Same name in source? Use identity: `map=["staging_k8s", "prod_k8s"]`

No separate `declare` step — that would duplicate what `map` already says.

## Two k8s

```python
auth = (
    Profile()
    .load(FileSource("profiles.yaml"), map={
        "staging_k8s": "clusters.staging",
        "prod_k8s": "clusters.prod",
    })
)

at("./cfg.json", auth=auth).fanout(
    "@staging_k8s:app-pod:/etc/x",
    "@prod_k8s:app-pod:/etc/x",
)
```

File (source names do not need to match API keys):

```yaml
clusters:
  staging: {scheme: k8s, context: staging}
  prod:    {scheme: k8s, context: prod}
```

## Compose sources

```python
auth = (
    Profile()
    .load(FileSource("~/.pyeff/profiles.yaml"), map={
        "staging_k8s": "clusters.staging",
        "prod_k8s": "clusters.prod",
    })
    .load(EnvSource(), map={"prod_s3": "MINIO"})
    .load(SystemSource(), map={"staging_k8s": "default_k8s"})  # overlay
)
```

Each `map` adds/fills API keys. Extra names in a source are ignored.

## Identity shorthand

```python
# source top-level keys already are the API names
.load(FileSource("p.yaml"), map=["staging_k8s", "prod_k8s"])
# equivalent to map={"staging_k8s": "staging_k8s", "prod_k8s": "prod_k8s"}
```

## `load_profile` sugar

```python
auth = load_profile(
    (FileSource("profiles.yaml"), {
        "staging_k8s": "clusters.staging",
        "prod_k8s": "clusters.prod",
    }),
    (EnvSource(), {"prod_s3": "MINIO"}),
)
```

## Nacos (conn also via map)

```python
nacos_conn = (
    Profile()
    .load(EnvSource(prefix="NACOS_", json_var="NACOS_CONFIG"), map=["nacos"])
).as_conn_dict("nacos")

auth = (
    Profile()
    .load(NacosSource(conn=nacos_conn), map={
        "staging_k8s": "k8s.staging",
        "prod_k8s": "k8s.prod",
    })
)
```
