# Profile design — credentials without hardcoding

## The problem you called out

If `fanout` has **two Kubernetes** targets, scheme-keyed auth cannot work:

```python
# WRONG mental model — one "k8s" key, two destinations
profile(k8s={...})  # which cluster?
.fanout("k8s:pod-a:/x", "k8s:pod-b:/y")
```

## Rule: logical names, not schemes

| Concept | Meaning | Example |
|---------|---------|---------|
| URI | **where** | `k8s:app-pod:/etc/app/config.json` |
| Profile entry name | **who** | `staging_k8s`, `prod_k8s` |
| Source | **how who is loaded** | env / file / cli / system / nacos |

Binding at fanout time:

```python
auth = load_profile(
    FileSource("~/.pyeff/profiles.yaml"),
    EnvSource(),
)

at("./cfg.json", auth=auth).fanout(
    "@staging_k8s:app-pod:/etc/app/config.json",
    "@prod_k8s:app-pod:/etc/app/config.json",
)

# Typed equivalent (same binding rule):
at("./cfg.json", auth=auth).fanout(
    auth.ref("staging_k8s", "app-pod:/etc/app/config.json"),
    auth.ref("prod_k8s", "app-pod:/etc/app/config.json"),
)
```

Grammar: `@<entry_name>:<scheme-specific-path>`

The entry supplies `scheme` + connection params; the suffix is the path as if you wrote `k8s:…` / `s3:…` without repeating the scheme.

## Composable sources (same interface)

Every source implements `ProfileSource.load() -> Dict[str, dict]`.

```python
auth = (
    Profile()
    .load(SystemSource())                      # default_k8s / default_s3 / …
    .load(FileSource("~/.pyeff/profiles.yaml"))
    .load(EnvSource(prefix="PYEFF_PROFILE_"))
    .load(CliSource(sys.argv))
    .load(NacosSource(conn=nacos_conn))        # see below
)
```

Later sources **override** earlier keys by default (`override=True`).

### File (`profiles.yaml`)

```yaml
staging_k8s:
  scheme: k8s
  context: staging
  namespace: app
prod_k8s:
  scheme: k8s
  context: prod
  namespace: app
prod_s3:
  scheme: s3
  endpoint_url: https://minio.example.com
  # access_key / secret_key from env overlay — not committed
```

### Environment

```bash
# JSON blob
export PYEFF_PROFILES='{"staging_k8s":{"scheme":"k8s","context":"staging"}}'

# Or flat keys (`__` separates entry name from param)
export PYEFF_PROFILE_STAGING_K8S__SCHEME=k8s
export PYEFF_PROFILE_STAGING_K8S__CONTEXT=staging
export PYEFF_PROFILE_PROD_S3__ACCESS_KEY=...
export PYEFF_PROFILE_PROD_S3__SECRET_KEY=...
```

### CLI

```bash
python app.py \
  --pyeff-profile-file=./profiles.yaml \
  --pyeff-profile prod_s3.access_key="$AK" \
  --pyeff-profile prod_s3.secret_key="$SK"
```

### System credentials

`SystemSource` only registers well-known names that mean “use ambient login”:

- `default_k8s` → kubeconfig
- `default_s3` → boto3 chain
- `default_ssh` → ssh-agent

No secrets are stored in code.

### Nacos (nested credentials)

Nacos **connection** itself must come from env/file/cli — never literals in app code:

```python
nacos_conn = (
    Profile()
    .load(EnvSource(prefix="NACOS_", json_var="NACOS_CONFIG"))
    .load(FileSource("~/.pyeff/nacos.yaml"))
).as_conn_dict()
# expects server_addr, data_id, optional username/password/namespace/group

auth = Profile().load(NacosSource(conn=nacos_conn))
```

`NacosSource` accepts an injectable `fetcher` for tests; production uses `nacos-sdk-python` when installed.

## Activation for low-level ops

```python
with auth.activate():
    copy("@staging_k8s:pod:/x", "local:./x")
```

Or always pass `auth=` into `at(...)`.

## What never happens

- Passwords inside `s3://…` / `ssh:…` URI strings
- Hardcoded Nacos addresses or keys in library or app source
- Guessing which of two `k8s` entries to use by scheme alone
