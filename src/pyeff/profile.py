"""Composable credential profiles for heterogeneous backends.

=================================================================
Mental model (two namespaces)
=================================================================

1. **Declared keys** — names *you* choose at assembly time.
   These are the **only** names ``@key`` / ``auth.ref("key")`` / flow APIs use.
2. **Source names** — whatever the file / env / Nacos / system actually calls them.
3. **map** — optional bridge ``{declared_key: source_name}``.
   Omit a key from map ⇒ identity (declared name == source name).

URI = where (never embeds passwords).
Declared key = who (API-facing).
Source = how that who is filled.

Example — two k8s clusters, file uses different names::

    # profiles.yaml
    # clusters:
    #   staging: {scheme: k8s, context: staging}
    #   prod:    {scheme: k8s, context: prod}

    auth = (
        Profile()
        .declare("staging_k8s", "prod_k8s", "prod_s3")   # API keys
        .load(
            FileSource("~/.pyeff/profiles.yaml"),
            map={
                "staging_k8s": "clusters.staging",       # declared → file path
                "prod_k8s": "clusters.prod",
                # prod_s3 omitted → look up source key "prod_s3"
            },
        )
        .load(
            EnvSource(),
            map={"prod_s3": "MINIO"},                    # env uses MINIO__*
        )
    )

    at("./cfg.json", auth=auth).fanout(
        "@staging_k8s:app-pod:/etc/app/config.json",
        "@prod_k8s:app-pod:/etc/app/config.json",
    )
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Union
from urllib.parse import urlparse

from .uri import (
    URIPath,
    LocalPath,
    DockerPath,
    SSHPath,
    K8sPath,
    S3Path,
    GCSPath,
    AzurePath,
    HTTPPath,
    SMBPath,
    WebDAVPath,
    ArchivePath,
    parse_uri,
    resolve_path_local,
    looks_like_uri,
)

PathLike = Union[str, Path]


class ProfileError(Exception):
    """Invalid profile configuration or named reference."""


class AuthError(ProfileError):
    """Authentication / authorization failure against a backend."""


# ---------------------------------------------------------------------------
# Active profile (for ops / bare copy("@name:…"))
# ---------------------------------------------------------------------------

_active_profile: ContextVar[Optional["Profile"]] = ContextVar(
    "pyeff_active_profile", default=None
)


def get_active_profile() -> Optional["Profile"]:
    return _active_profile.get()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

_REF_PATTERN = re.compile(r"^@([A-Za-z_][A-Za-z0-9_-]*)(?::(.*))?$")


@dataclass
class ProfileEntry:
    """One named identity.

    Attributes:
        name: Logical name (``staging_k8s``, not ``k8s``).
        scheme: Backend scheme (``k8s``, ``s3``, ``ssh``, …).
        params: Connection parameters merged onto the URIPath.
        path: Optional default path when ref is just ``@name``.
    """

    name: str
    scheme: str
    params: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any]) -> "ProfileEntry":
        data = dict(data)
        scheme = data.pop("scheme", None)
        if not scheme:
            raise ProfileError(f"Profile entry {name!r} missing required 'scheme'")
        default_path = data.pop("path", None)
        # Allow nested "params" or flat keys
        params = dict(data.pop("params", {}))
        params.update(data)
        return cls(name=name, scheme=str(scheme), params=params, path=default_path)

    def to_dict(self) -> Dict[str, Any]:
        out = {"scheme": self.scheme, **self.params}
        if self.path is not None:
            out["path"] = self.path
        return out


# ---------------------------------------------------------------------------
# Sources (composable)
# ---------------------------------------------------------------------------

class ProfileSource(ABC):
    """Load a raw config tree. Never hardcode secrets here.

    The tree may be flat (``{name: {scheme, …}}``) or nested
    (``{clusters: {staging: {…}}}``). Profile.declare + map selects
    which nodes fill which **declared** API keys.
    """

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """Return a mapping tree (possibly nested)."""


class DictSource(ProfileSource):
    """In-memory / already-parsed dict (useful for tests and composition)."""

    def __init__(self, entries: Mapping[str, Mapping[str, Any]]) -> None:
        self._entries = {k: dict(v) for k, v in entries.items()}

    def load(self) -> Dict[str, Dict[str, Any]]:
        return {k: dict(v) for k, v in self._entries.items()}


class EnvSource(ProfileSource):
    """Load from environment variables.

    Two supported shapes (both never require secrets in code):

    1. JSON blob::

           PYEFF_PROFILES='{"staging_k8s":{"scheme":"k8s","context":"staging"}}'

       (name configurable via ``json_var``)

    2. Flat keys (``__`` separates entry name from param — names may contain ``_``)::

           PYEFF_PROFILE_STAGING_K8S__SCHEME=k8s
           PYEFF_PROFILE_STAGING_K8S__CONTEXT=staging
           PYEFF_PROFILE_PROD_S3__ACCESS_KEY=...

       With ``prefix="PYEFF_PROFILE_"`` → entries ``staging_k8s``, ``prod_s3``.
    """

    def __init__(
        self,
        prefix: str = "PYEFF_PROFILE_",
        json_var: str = "PYEFF_PROFILES",
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.prefix = prefix
        self.json_var = json_var
        self._environ = environ if environ is not None else os.environ

    def load(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}

        raw = self._environ.get(self.json_var)
        if raw:
            try:
                blob = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ProfileError(f"Invalid JSON in {self.json_var}: {e}") from e
            if not isinstance(blob, dict):
                raise ProfileError(f"{self.json_var} must be a JSON object")
            for name, cfg in blob.items():
                if isinstance(cfg, dict):
                    result[name] = dict(cfg)

        # Flat: PREFIX + NAME + __ + PARAM
        pref = self.prefix
        for key, value in self._environ.items():
            if not key.startswith(pref) or key == self.json_var:
                continue
            rest = key[len(pref) :]
            if "__" not in rest:
                continue
            name_part, param = rest.split("__", 1)
            name = name_part.lower()
            param = param.lower()
            result.setdefault(name, {})
            result[name][param] = value

        return result


class FileSource(ProfileSource):
    """Load from JSON / YAML / TOML file.

    File layout (YAML/JSON)::

        staging_k8s:
          scheme: k8s
          context: staging
          namespace: app
        prod_k8s:
          scheme: k8s
          context: prod

    TOML uses tables with the same keys.
    """

    def __init__(self, path: PathLike, *, required: bool = False) -> None:
        self.path = Path(path).expanduser()
        self.required = required

    def load(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            if self.required:
                raise ProfileError(f"Profile file not found: {self.path}")
            return {}

        text = self.path.read_text(encoding="utf-8")
        suffix = self.path.suffix.lower()

        if suffix == ".json":
            data = json.loads(text)
        elif suffix in (".yaml", ".yml"):
            import yaml
            data = yaml.safe_load(text) or {}
        elif suffix == ".toml":
            try:
                import tomllib  # py3.11+
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore
                except ImportError as e:
                    raise ProfileError(
                        "TOML profiles require Python 3.11+ or the 'tomli' package"
                    ) from e
            data = tomllib.loads(text)
        else:
            # try json then yaml
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                import yaml
                data = yaml.safe_load(text) or {}

        if not isinstance(data, dict):
            raise ProfileError(f"Profile file root must be a mapping: {self.path}")

        # Optional top-level "profiles:" wrapper (still a tree for dotted map)
        if (
            "profiles" in data
            and isinstance(data["profiles"], dict)
            and len(data) == 1
        ):
            return dict(data["profiles"])
        return dict(data)


class CliSource(ProfileSource):
    """Parse CLI flags without hardcoding secrets in source.

    Recognized forms::

        --pyeff-profile-file=path.toml
        --pyeff-profile name.scheme=k8s
        --pyeff-profile name.context=staging
        --pyeff-profiles-json '{"staging_k8s":{"scheme":"k8s"}}'
    """

    def __init__(self, argv: Optional[List[str]] = None) -> None:
        self.argv = list(argv) if argv is not None else []

    def load(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        args = list(self.argv)
        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("--pyeff-profile-file="):
                path = a.split("=", 1)[1]
                result = _merge_dicts(result, FileSource(path, required=True).load())
            elif a == "--pyeff-profile-file" and i + 1 < len(args):
                i += 1
                result = _merge_dicts(result, FileSource(args[i], required=True).load())
            elif a.startswith("--pyeff-profiles-json="):
                blob = json.loads(a.split("=", 1)[1])
                result = _merge_dicts(result, DictSource(blob).load())
            elif a == "--pyeff-profiles-json" and i + 1 < len(args):
                i += 1
                blob = json.loads(args[i])
                result = _merge_dicts(result, DictSource(blob).load())
            elif a.startswith("--pyeff-profile="):
                self._apply_kv(result, a.split("=", 1)[1])
            elif a == "--pyeff-profile" and i + 1 < len(args):
                i += 1
                self._apply_kv(result, args[i])
            i += 1
        return result

    @staticmethod
    def _apply_kv(result: Dict[str, Dict[str, Any]], spec: str) -> None:
        # name.key=value
        if "=" not in spec or "." not in spec.split("=", 1)[0]:
            raise ProfileError(
                f"Invalid --pyeff-profile value {spec!r}; expected name.key=value"
            )
        left, value = spec.split("=", 1)
        name, key = left.split(".", 1)
        result.setdefault(name, {})
        result[name][key] = value


class SystemSource(ProfileSource):
    """Register ambient system credentials as well-known default names.

    Does **not** invent secrets — only advertises that a scheme can use the
    process environment / agent:

    - ``default_k8s`` → current kubeconfig context
    - ``default_s3``  → boto3 default credential chain
    - ``default_ssh`` → ssh-agent / default keys
    - ``default_gcs`` / ``default_azure`` similarly

    Explicit named entries from File/Env always override these for the same name.
    """

    def load(self) -> Dict[str, Dict[str, Any]]:
        return {
            "default_k8s": {"scheme": "k8s"},
            "default_s3": {"scheme": "s3"},
            "default_ssh": {"scheme": "ssh"},
            "default_gcs": {"scheme": "gs"},
            "default_azure": {"scheme": "az"},
            "default_docker": {"scheme": "docker"},
        }


class NacosSource(ProfileSource):
    """Load profile JSON/YAML from Nacos.

    **Nacos connection credentials must come from another source** — pass them
    via ``conn`` (a small dict or a Profile of connection-only keys), never
    literals in application code::

        nacos_conn = (
            Profile()
            .load(EnvSource(prefix="NACOS_", json_var="NACOS_CONFIG"))
            .load(FileSource("~/.pyeff/nacos.yaml"))
        )
        # expected keys on a synthetic entry or via conn dict:
        # server_addr / username / password / namespace / group / data_id

        auth = Profile().load(NacosSource(conn=nacos_conn.as_conn_dict()))

    Optional dependency: ``nacos-sdk-python``. Without it, ``load`` raises
    ``ProfileError`` explaining how to install — so CI without Nacos still works.
    """

    def __init__(
        self,
        conn: Optional[Mapping[str, Any]] = None,
        *,
        data_id: Optional[str] = None,
        group: Optional[str] = None,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        fetcher: Optional[Any] = None,
    ) -> None:
        c = dict(conn or {})
        # Explicit kwargs override conn (still caller-supplied, not hardcoded defaults for secrets)
        if data_id is not None:
            c["data_id"] = data_id
        if group is not None:
            c["group"] = group
        if server_addr is not None:
            c["server_addr"] = server_addr
        if username is not None:
            c["username"] = username
        if password is not None:
            c["password"] = password
        if namespace is not None:
            c["namespace"] = namespace
        self._conn = c
        self._fetcher = fetcher  # injectable for tests

    def load(self) -> Dict[str, Dict[str, Any]]:
        data_id = self._conn.get("data_id")
        if not data_id:
            raise ProfileError(
                "NacosSource requires data_id from conn/env/file — not hardcoded"
            )
        group = self._conn.get("group") or "DEFAULT_GROUP"
        content = self._fetch_content(data_id, group)
        if not content:
            return {}
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            import yaml
            data = yaml.safe_load(content) or {}
        if not isinstance(data, dict):
            raise ProfileError("Nacos profile content must be a mapping")
        if (
            "profiles" in data
            and isinstance(data["profiles"], dict)
            and len(data) == 1
        ):
            return dict(data["profiles"])
        return dict(data)

    def _fetch_content(self, data_id: str, group: str) -> str:
        if self._fetcher is not None:
            return self._fetcher(data_id, group, self._conn)

        server = self._conn.get("server_addr")
        if not server:
            raise ProfileError(
                "NacosSource requires server_addr from conn/env/file — not hardcoded"
            )
        try:
            from nacos import NacosClient  # type: ignore
        except ImportError as e:
            raise ProfileError(
                "Nacos support requires 'nacos-sdk-python'. "
                "Install with: pip install nacos-sdk-python"
            ) from e

        client = NacosClient(
            server,
            namespace=self._conn.get("namespace"),
            username=self._conn.get("username"),
            password=self._conn.get("password"),
        )
        return client.get_config(data_id, group) or ""


def _merge_dicts(
    base: Dict[str, Any],
    overlay: Dict[str, Any],
) -> Dict[str, Any]:
    """Shallow-merge top-level keys; dict values merged one level."""
    out = dict(base)
    for name, cfg in overlay.items():
        if name in out and isinstance(out[name], dict) and isinstance(cfg, dict):
            merged = dict(out[name])
            merged.update(cfg)
            out[name] = merged
        else:
            out[name] = cfg
    return out


def _dig(tree: Mapping[str, Any], source_key: str) -> Optional[Dict[str, Any]]:
    """Look up *source_key* in a (possibly nested) tree.

    ``source_key`` may be a top-level name or a dotted path
    (``clusters.staging``).
    """
    if not source_key:
        return None
    if source_key in tree and isinstance(tree[source_key], dict):
        return dict(tree[source_key])
    cur: Any = tree
    for part in source_key.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return None
        cur = cur[part]
    if isinstance(cur, dict):
        return dict(cur)
    return None


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class Profile:
    """Declared API keys + composable sources that fill them.

    Assembly order::

        Profile().declare(...).load(source, map=...).load(...)

    Only **declared** keys are visible to ``@name`` / ``ref`` / flow.
    """

    def __init__(self) -> None:
        # declared_key -> default fields (may include scheme)
        self._declared: Dict[str, Dict[str, Any]] = {}
        # declared_key -> filled ProfileEntry
        self._entries: Dict[str, ProfileEntry] = {}

    # -- composition --------------------------------------------------------

    def declare(self, *names: str, **specs: Any) -> "Profile":
        """Declare API-facing keys (required before load / ref).

        Forms::

            .declare("staging_k8s", "prod_k8s")
            .declare(staging_k8s={"scheme": "k8s"}, prod_s3={"scheme": "s3"})
            .declare("staging_k8s", prod_k8s={"scheme": "k8s"})  # mixed
            .declare(staging_k8s="k8s")  # shorthand: value is scheme string
        """
        for name in names:
            if not isinstance(name, str) or not name:
                raise ProfileError(f"Invalid declare name: {name!r}")
            self._declared.setdefault(name, {})
        for name, spec in specs.items():
            if isinstance(spec, str):
                defaults = {"scheme": spec}
            elif isinstance(spec, Mapping):
                defaults = dict(spec)
            else:
                raise ProfileError(
                    f"declare({name}=...) expects scheme str or dict, got {type(spec)}"
                )
            existing = self._declared.get(name, {})
            merged = dict(existing)
            merged.update(defaults)
            self._declared[name] = merged
        return self

    def load(
        self,
        source: ProfileSource,
        map: Optional[Mapping[str, str]] = None,  # noqa: A002 — intentional API name
        *,
        override: bool = True,
    ) -> "Profile":
        """Fill **declared** keys from *source*.

        Args:
            source: File / env / cli / system / nacos / dict source.
            map: ``{declared_key: source_key}``. Source key may be dotted
                (``clusters.staging``). Keys omitted from map use identity
                (declared name == source name). Only declared keys are
                considered — extra names in the source are ignored.
            override: If True (default), source values win over prior loads.
        """
        if not self._declared:
            raise ProfileError(
                "Call .declare(...) before .load(...). "
                "API keys must be declared at assembly time; "
                "source names are mapped onto those keys."
            )

        raw = source.load()
        if not isinstance(raw, Mapping):
            raise ProfileError(f"Source {source!r} must return a mapping tree")

        mapping = dict(map or {})
        for declared_key, defaults in self._declared.items():
            source_key = mapping.get(declared_key, declared_key)
            cfg = _dig(raw, source_key)
            if cfg is None:
                continue
            # declare defaults first, then source cfg
            merged = dict(defaults)
            merged.update(cfg)
            if "scheme" not in merged:
                raise ProfileError(
                    f"Declared key {declared_key!r} (source {source_key!r}) "
                    f"has no 'scheme' — set it in .declare() or in the source"
                )
            incoming = ProfileEntry.from_dict(declared_key, merged)
            if declared_key not in self._entries:
                self._entries[declared_key] = incoming
                continue
            if not override:
                continue
            old = self._entries[declared_key]
            params = dict(old.params)
            params.update(incoming.params)
            self._entries[declared_key] = ProfileEntry(
                name=declared_key,
                scheme=incoming.scheme or old.scheme,
                params=params,
                path=incoming.path if incoming.path is not None else old.path,
            )
        return self

    def extend(self, **entries: Mapping[str, Any]) -> "Profile":
        """Fill declared keys from an inline dict (tests / demos).

        Keys must already be declared. Equivalent to
        ``.load(DictSource(entries))`` with identity map.
        """
        unknown = set(entries) - set(self._declared)
        if unknown:
            raise ProfileError(
                f"extend() keys not declared: {sorted(unknown)}. "
                f"Declared: {self.declared_names()}"
            )
        return self.load(DictSource(entries))

    # -- query --------------------------------------------------------------

    def declared_names(self) -> List[str]:
        """API keys declared at assembly time (order stable / sorted)."""
        return sorted(self._declared)

    def names(self) -> List[str]:
        """Declared keys that have been filled by at least one source."""
        return sorted(self._entries)

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def get(self, name: str) -> ProfileEntry:
        if name not in self._declared:
            raise ProfileError(
                f"Key {name!r} was not declared. "
                f"Declared keys: {self.declared_names()}"
            )
        if name not in self._entries:
            raise ProfileError(
                f"Declared key {name!r} has no data from any source yet. "
                f"Filled: {self.names()}"
            )
        return self._entries[name]

    def as_conn_dict(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Flatten one entry (or all filled params) for nested sources (e.g. Nacos conn)."""
        if name is not None:
            e = self.get(name)
            return {"scheme": e.scheme, **e.params}
        if len(self._entries) == 1:
            e = next(iter(self._entries.values()))
            return {**e.params}
        out: Dict[str, Any] = {}
        for e in self._entries.values():
            out.update(e.params)
        return out

    # -- resolve ------------------------------------------------------------

    def ref(self, name: str, path: Optional[str] = None) -> URIPath:
        """Build a URIPath from a **declared** key + path suffix.

            auth.ref("staging_k8s", "app-pod:/etc/app/config.json")
        """
        entry = self.get(name)
        path_part = path if path is not None else (entry.path or "")
        if not path_part and entry.scheme not in ("local",):
            if entry.path:
                path_part = entry.path
            else:
                raise ProfileError(
                    f"Profile ref {name!r} needs a path "
                    f"(e.g. auth.ref({name!r}, 'pod:/path') or @{{name}}:pod:/path)"
                )
        return _build_path(entry, path_part)

    def resolve(self, spec: Union[str, URIPath]) -> URIPath:
        """Resolve ``@declared_key:…`` against this profile, or plain URI/path."""
        if isinstance(spec, URIPath):
            return _apply_entry_if_tagged(spec, self)
        s = str(spec)
        m = _REF_PATTERN.match(s)
        if m:
            name, path_part = m.group(1), m.group(2)
            return self.ref(name, path_part)
        return resolve_path_local(s)

    @contextmanager
    def activate(self) -> Iterator["Profile"]:
        """Context manager: make this profile active for ``resolve_path`` / ops."""
        token = _active_profile.set(self)
        try:
            yield self
        finally:
            _active_profile.reset(token)

    def __repr__(self) -> str:
        return (
            f"Profile(declared={self.declared_names()}, filled={self.names()})"
        )


def load_profile(
    declare: Union[List[str], Mapping[str, Any], str],
    *source_binds: Union[ProfileSource, tuple],
    **declare_specs: Any,
) -> Profile:
    """Assemble a profile: declare API keys, then bind sources.

    Example::

        auth = load_profile(
            ["staging_k8s", "prod_k8s", "prod_s3"],
            (FileSource("profiles.yaml"), {
                "staging_k8s": "clusters.staging",
                "prod_k8s": "clusters.prod",
            }),
            (EnvSource(), {"prod_s3": "MINIO"}),
        )

        # Or with scheme defaults in declare:
        auth = load_profile(
            {"staging_k8s": {"scheme": "k8s"}, "prod_s3": {"scheme": "s3"}},
            FileSource("profiles.yaml"),  # identity map
        )
    """
    p = Profile()
    if isinstance(declare, str):
        p.declare(declare, **declare_specs)
    elif isinstance(declare, Mapping):
        p.declare(**dict(declare), **declare_specs)
    else:
        p.declare(*list(declare), **declare_specs)

    for item in source_binds:
        if isinstance(item, tuple):
            if len(item) != 2:
                raise ProfileError(
                    "source bind must be ProfileSource or (ProfileSource, map)"
                )
            src, mapping = item
            p.load(src, map=mapping)
        else:
            p.load(item)
    return p


# Alias
profile = load_profile


# ---------------------------------------------------------------------------
# Path building / merge
# ---------------------------------------------------------------------------

_SCHEME_PREFIX = {
    "local": "local:",
    "docker": "docker:",
    "ssh": "ssh:",
    "k8s": "k8s:",
    "archive": "archive:",
    "s3": "s3://",
    "gs": "gs://",
    "gcs": "gs://",
    "az": "az://",
    "azure": "az://",
    "http": "http://",
    "https": "https://",
    "smb": "smb://",
    "webdav": "webdav://",
    "webdavs": "webdavs://",
}


def _build_path(entry: ProfileEntry, path_part: str) -> URIPath:
    scheme = entry.scheme
    path_part = path_part or ""

    # If caller already passed a full URI for the same scheme, parse directly
    if looks_like_uri(path_part):
        base = parse_uri(path_part)
    else:
        # Build scheme-specific URI string for parse_uri
        if scheme in ("s3", "gs", "gcs", "az", "azure", "smb"):
            # path_part: bucket/key or //bucket/key or bucket:/key
            if path_part.startswith("//"):
                uri = f"{'gs' if scheme == 'gcs' else scheme}:{path_part}"
            elif "://" in path_part:
                uri = path_part
            else:
                prefix = _SCHEME_PREFIX.get(scheme, f"{scheme}://")
                uri = f"{prefix}{path_part.lstrip('/')}"
        elif scheme in ("http", "https", "webdav", "webdavs", "dav", "davs"):
            if "://" in path_part:
                uri = path_part
            else:
                # entry may carry base_url in params
                base_url = entry.params.get("base_url") or entry.params.get("url")
                if base_url:
                    uri = base_url.rstrip("/") + "/" + path_part.lstrip("/")
                    # For webdav builders we still parse as http(s) URL then overlay
                    if scheme.startswith("webdav") or scheme in ("dav", "davs"):
                        # store as webdav URI if possible
                        parsed = urlparse(uri)
                        wd_scheme = "webdavs" if parsed.scheme == "https" else "webdav"
                        uri = f"{wd_scheme}://{parsed.netloc}{parsed.path}"
                        if parsed.query:
                            uri += "?" + parsed.query
                else:
                    uri = f"{scheme}://{path_part.lstrip('/')}"
        elif scheme == "local":
            uri = f"local:{path_part}"
        elif scheme == "docker":
            uri = f"docker:{path_part}"
        elif scheme == "ssh":
            # path_part: user@host:/path  OR host from entry + path
            if ":" in path_part and "@" in path_part.split(":")[0]:
                uri = f"ssh:{path_part}"
            elif entry.params.get("host"):
                host = entry.params["host"]
                port = entry.params.get("port")
                user = entry.params.get("username")
                if user and "@" not in host:
                    host = f"{user}@{host}"
                if port:
                    uri = f"ssh:{host}:{port}:{path_part}"
                else:
                    uri = f"ssh:{host}:{path_part}"
            else:
                uri = f"ssh:{path_part}"
        elif scheme == "k8s":
            uri = f"k8s:{path_part}"
        elif scheme == "archive":
            uri = f"archive:{path_part}"
        else:
            uri = f"{scheme}:{path_part}"

        base = parse_uri(uri)

    return _merge_params(base, entry.params)


def _merge_params(path: URIPath, params: Mapping[str, Any]) -> URIPath:
    """Overlay profile connection params onto a parsed URIPath."""
    if not params:
        return path

    # Map common aliases
    p = dict(params)
    if "key" in p and "key_file" not in p:
        pass  # SSHPath uses key=
    if "key_file" in p and isinstance(path, SSHPath):
        p["key"] = p.pop("key_file")

    valid = {f.name for f in fields(path)} if hasattr(path, "__dataclass_fields__") else set()
    overlay = {k: v for k, v in p.items() if k in valid and v is not None}
    if not overlay:
        return path
    return replace(path, **overlay)


def _apply_entry_if_tagged(path: URIPath, profile: Profile) -> URIPath:
    """If URIPath carries a _profile_name attr, merge — used by Flow."""
    name = getattr(path, "_profile_name", None)
    if not name:
        return path
    entry = profile.get(name)
    return _merge_params(path, entry.params)


def resolve_path(
    path: Union[str, Path, URIPath],
    profile: Optional[Profile] = None,
) -> URIPath:
    """Resolve path with optional / active Profile for ``@name`` refs."""
    if isinstance(path, URIPath):
        return path
    s = str(path) if not isinstance(path, Path) else str(path)
    if s.startswith("@"):
        auth = profile or get_active_profile()
        if auth is None:
            raise ProfileError(
                f"Named profile ref {s!r} requires a Profile "
                f"(pass auth= to at()/copy(), or use profile.activate())"
            )
        return auth.resolve(s)
    return _resolve_path_basic(path)


__all__ = [
    "Profile",
    "ProfileEntry",
    "ProfileError",
    "AuthError",
    "ProfileSource",
    "DictSource",
    "EnvSource",
    "FileSource",
    "CliSource",
    "SystemSource",
    "NacosSource",
    "load_profile",
    "profile",
    "get_active_profile",
    "resolve_path",
]
