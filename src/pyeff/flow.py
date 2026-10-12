"""Fluent location pipeline — reduce path I/O to one mental model.

=================================================================
Mental model (memorize this, nothing else)
=================================================================

    at(WHERE) → [LOAD] → [EDIT] → [SAVE] → [SEND] → [CHECK]

One object: ``Flow`` (returned by ``at``).
Five verb families — that is the whole grammar.

| Family | Verbs                         | Meaning                          |
|--------|-------------------------------|----------------------------------|
| WHERE  | ``at``                        | Point at a URI / local path      |
| LOAD   | ``json`` ``yaml`` ``text`` ``bytes`` | Pull content into the flow |
| EDIT   | ``update`` ``merge`` ``map``  | Transform in-memory content      |
| SAVE   | ``save``                      | Write content back (or to a URI) |
| SEND   | ``to`` ``fanout`` ``move_to`` | Move/copy the *place* elsewhere  |
| CHECK  | ``exists`` ``same_hash``      | Confirm presence / equality      |

Auth (who) is a separate, composable ``Profile`` — never embedded in URI strings.
Two clusters of the same scheme use **logical names**::

    at("./cfg.json", auth=auth).fanout(
        "@staging_k8s:app-pod:/etc/app/config.json",
        "@prod_k8s:app-pod:/etc/app/config.json",
    )
    # or: auth.ref("staging_k8s", "app-pod:/etc/app/config.json")

See ``docs/profile.md`` and ``docs/flow.md``.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Union

from .uri import URIPath, resolve_path

PathLike = Union[str, URIPath]


class FlowError(Exception):
    """Raised when a flow step is used in the wrong state."""


class Flow:
    """Location-centered fluent pipeline.

    Holds a resolved ``URIPath`` (credentials preserved from Profile) and an
    optional payload after LOAD/EDIT.
    """

    __slots__ = ("_path", "_data", "_kind", "_dirty", "_auth")

    def __init__(
        self,
        uri: PathLike,
        data: Any = None,
        kind: Optional[str] = None,
        dirty: bool = False,
        auth: Any = None,
        _path: Optional[URIPath] = None,
    ) -> None:
        self._auth = auth
        if _path is not None:
            self._path = _path
        else:
            self._path = self._resolve(uri)
        self._data = data
        self._kind = kind  # "json" | "yaml" | "text" | "bytes" | None
        self._dirty = dirty

    def _resolve(self, uri: PathLike) -> URIPath:
        if isinstance(uri, URIPath):
            return uri
        if self._auth is not None:
            return self._auth.resolve(uri)
        return resolve_path(uri)

    # ------------------------------------------------------------------
    # Construction / identity
    # ------------------------------------------------------------------

    @property
    def uri(self) -> str:
        """Current location as URI string (secrets never appear here)."""
        return self._path.to_uri()

    @property
    def path(self) -> URIPath:
        """Resolved URIPath (may carry connection params from Profile)."""
        return self._path

    @property
    def auth(self) -> Any:
        return self._auth

    def __repr__(self) -> str:
        payload = f", kind={self._kind!r}, dirty={self._dirty}" if self._kind else ""
        auth = f", auth={self._auth!r}" if self._auth is not None else ""
        return f"Flow({self.uri!r}{payload}{auth})"

    def __str__(self) -> str:
        return self.uri

    def _clone(
        self,
        data: Any = ...,
        kind: Any = ...,
        dirty: Any = ...,
        auth: Any = ...,
        path: Any = ...,
    ) -> "Flow":
        new_path = self._path if path is ... else path
        new_auth = self._auth if auth is ... else auth
        return Flow(
            new_path.to_uri(),
            data=self._data if data is ... else data,
            kind=self._kind if kind is ... else kind,
            dirty=self._dirty if dirty is ... else dirty,
            auth=new_auth,
            _path=new_path,
        )

    # ------------------------------------------------------------------
    # LOAD
    # ------------------------------------------------------------------

    def json(self) -> "Flow":
        from .json import loads
        from .ops import read

        text = read(self._path, encoding="utf-8")
        assert isinstance(text, str)
        return self._clone(data=loads(text), kind="json", dirty=False)

    def yaml(self) -> "Flow":
        from .yaml import loads
        from .ops import read

        text = read(self._path, encoding="utf-8")
        assert isinstance(text, str)
        return self._clone(data=loads(text), kind="yaml", dirty=False)

    def text(self) -> "Flow":
        from .ops import read

        text = read(self._path, encoding="utf-8")
        return self._clone(data=text, kind="text", dirty=False)

    def bytes(self) -> "Flow":  # noqa: A003
        from .ops import read

        data = read(self._path, binary=True)
        return self._clone(data=data, kind="bytes", dirty=False)

    @property
    def data(self) -> Any:
        if self._kind is None:
            raise FlowError(
                "No payload loaded. Call .json() / .yaml() / .text() / .bytes() first."
            )
        return self._data

    # ------------------------------------------------------------------
    # EDIT
    # ------------------------------------------------------------------

    def _require_payload(self, op: str) -> None:
        if self._kind is None:
            raise FlowError(f".{op}() needs a payload. Call .json()/.yaml()/.text() first.")

    def update(self, **kwargs: Any) -> "Flow":
        self._require_payload("update")
        if not isinstance(self._data, dict):
            raise FlowError(".update() requires a dict payload (use .json()/.yaml()).")
        new_data = dict(self._data)
        new_data.update(kwargs)
        return self._clone(data=new_data, dirty=True)

    def merge(self, other: dict, deep: bool = True) -> "Flow":
        self._require_payload("merge")
        if not isinstance(self._data, dict):
            raise FlowError(".merge() requires a dict payload.")
        from .json import merge as json_merge

        return self._clone(data=json_merge(self._data, other, deep=deep), dirty=True)

    def map(self, fn: Callable[[Any], Any]) -> "Flow":  # noqa: A003
        self._require_payload("map")
        return self._clone(data=fn(self._data), dirty=True)

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------

    def save(self, dst: Optional[PathLike] = None) -> "Flow":
        self._require_payload("save")
        if dst is None:
            target_path = self._path
        else:
            target_path = self._resolve(dst)
        self._write_payload(target_path)
        return Flow(
            target_path.to_uri(),
            data=self._data,
            kind=self._kind,
            dirty=False,
            auth=self._auth,
            _path=target_path,
        )

    def _write_payload(self, target: URIPath) -> None:
        from .ops import write

        if self._kind == "json":
            from .json import dumps
            write(target, dumps(self._data, indent=2), encoding="utf-8")
        elif self._kind == "yaml":
            from .yaml import dumps
            write(target, dumps(self._data), encoding="utf-8")
        elif self._kind == "text":
            write(target, str(self._data), encoding="utf-8")
        elif self._kind == "bytes":
            data = self._data if isinstance(self._data, bytes) else bytes(self._data)
            write(target, data)
        else:
            raise FlowError(f"Unknown payload kind: {self._kind!r}")

    def _flush_if_dirty(self) -> None:
        if self._dirty and self._kind is not None:
            self._write_payload(self._path)
            self._dirty = False

    # ------------------------------------------------------------------
    # SEND
    # ------------------------------------------------------------------

    def to(self, dst: PathLike, **copy_kw: Any) -> "Flow":
        from .ops import copy

        self._flush_if_dirty()
        dst_path = self._resolve(dst)
        copy(self._path, dst_path, **copy_kw)
        return Flow(
            dst_path.to_uri(),
            auth=self._auth,
            _path=dst_path,
        )

    def fanout(self, *dsts: PathLike, **copy_kw: Any) -> "Flow":
        """Copy to many destinations.

        Each dst may be:
        - a plain URI / path
        - a named profile ref ``@staging_k8s:pod:/path``
        - a pre-built ``auth.ref("staging_k8s", "pod:/path")`` URIPath

        Finger stays on the **source**.
        """
        if not dsts:
            raise FlowError(".fanout() requires at least one destination")
        from .ops import copy

        self._flush_if_dirty()
        for dst in dsts:
            copy(self._path, self._resolve(dst), **copy_kw)
        return self._clone(dirty=False)

    def move_to(self, dst: PathLike, **move_kw: Any) -> "Flow":
        from .ops import move

        self._flush_if_dirty()
        dst_path = self._resolve(dst)
        move(self._path, dst_path, **move_kw)
        return Flow(
            dst_path.to_uri(),
            auth=self._auth,
            _path=dst_path,
        )

    def write(self, content: Union[str, bytes], encoding: str = "utf-8") -> "Flow":
        from .ops import write

        write(self._path, content, encoding=encoding)
        kind = "bytes" if isinstance(content, bytes) else "text"
        return self._clone(data=content, kind=kind, dirty=False)

    def remove(self, **remove_kw: Any) -> "Flow":
        from .ops import remove

        remove(self._path, **remove_kw)
        return self._clone(data=None, kind=None, dirty=False)

    # ------------------------------------------------------------------
    # INSPECT / CHECK
    # ------------------------------------------------------------------

    def exists(self) -> bool:
        from .ops import exists
        return exists(self._path)

    def hash(self, algorithm: str = "sha256") -> str:  # noqa: A003
        from .hash import hash_file
        return hash_file(self._path, algorithm=algorithm)  # type: ignore[arg-type]

    def size(self) -> int:
        from .ops import file_size
        return file_size(self._path)

    def tree(self, **kw: Any) -> str:
        from .ops import tree
        return tree(self._path, **kw)

    def search(self, *patterns: str, mode: str = "include", recursive: bool = True) -> List[str]:
        from .ops import search
        pats = list(patterns) if patterns else None
        return search(
            self._path, mode=mode if pats else "all", patterns=pats, recursive=recursive
        )

    def listdir(self, **kw: Any) -> list:
        from .ops import listdir
        return listdir(self._path, **kw)

    def read(self, encoding: str = "utf-8", binary: bool = False) -> Union[str, bytes]:
        from .ops import read
        return read(self._path, encoding=encoding, binary=binary)

    def ensure(self) -> "Flow":
        from .ops import ensure
        ensure(self._path)
        return self

    def same_hash(self, *others: PathLike, algorithm: str = "sha256") -> "Flow":
        if not others:
            raise FlowError(".same_hash() requires at least one other URI")
        base = self.hash(algorithm=algorithm)
        from .hash import hash_file

        for other in others:
            other_path = self._resolve(other)
            h = hash_file(other_path, algorithm=algorithm)  # type: ignore[arg-type]
            if h != base:
                raise FlowError(
                    f"Hash mismatch: {self.uri} ({base[:12]}…) "
                    f"!= {other_path.to_uri()} ({h[:12]}…)"
                )
        return self


def at(uri: PathLike, auth: Any = None) -> Flow:
    """Start a flow at ``uri``.

    Args:
        uri: Bare path, URI, ``@name:…`` profile ref, or URIPath.
        auth: Optional :class:`pyeff.profile.Profile` for resolving ``@name``
            refs and attaching connection credentials.
    """
    return Flow(uri, auth=auth)


__all__ = [
    "Flow",
    "FlowError",
    "at",
]
