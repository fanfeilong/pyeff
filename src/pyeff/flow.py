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
| CHECK  | ``exists`` ``same_hash``              | Confirm (bool / fail-fast) |

Inspect without changing the chain position:
``exists``, ``hash``, ``size``, ``tree``, ``search``, ``listdir``, ``read``.

Why this lowers cognitive load
------------------------------
1. **One entry point** — only ``at(...)``. No separate builders per backend.
2. **One object type** — always ``Flow``. No Loc vs Doc vs Pipeline classes.
3. **URI is opaque** — docker/ssh/s3/archive look the same; ops already know how.
4. **Two kinds of data only**:
   - *place* (``.uri``) — where we point
   - *payload* (optional) — content after LOAD; cleared/synced by SAVE/SEND
5. **SEND vs SAVE are distinct on purpose**:
   - ``save`` writes the *payload* (edited JSON/YAML/text)
   - ``to`` / ``fanout`` copies the *file/dir at uri* (or payload if dirty)

Typical release script
----------------------
>>> from pyeff.flow import at
>>> (
...     at("./configs/app.json")
...     .json()
...     .update(env="staging", release="1")
...     .save()
...     .fanout(
...         "docker:app:/etc/app/config.json",
...         "s3://configs/app/config.json",
...     )
...     .same_hash(
...         "docker:app:/etc/app/config.json",
...         "s3://configs/app/config.json",
...     )
... )
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Union

from .uri import URIPath, resolve_path

PathLike = Union[str, URIPath]


class FlowError(Exception):
    """Raised when a flow step is used in the wrong state."""


class Flow:
    """Location-centered fluent pipeline.

    Users should not subclass this. Treat it as: "a finger pointing at a URI,
    optionally holding edited content."
    """

    __slots__ = ("_uri", "_data", "_kind", "_dirty")

    def __init__(
        self,
        uri: PathLike,
        data: Any = None,
        kind: Optional[str] = None,
        dirty: bool = False,
    ) -> None:
        # Always normalize to a URI string so ops/resolve_path stay consistent.
        self._uri = resolve_path(uri).to_uri()
        self._data = data
        self._kind = kind  # "json" | "yaml" | "text" | "bytes" | None
        self._dirty = dirty

    # ------------------------------------------------------------------
    # Construction / identity
    # ------------------------------------------------------------------

    @property
    def uri(self) -> str:
        """Current location as URI string."""
        return self._uri

    def __repr__(self) -> str:
        payload = f", kind={self._kind!r}, dirty={self._dirty}" if self._kind else ""
        return f"Flow({self._uri!r}{payload})"

    def __str__(self) -> str:
        return self._uri

    def _clone(
        self,
        uri: Optional[PathLike] = None,
        data: Any = ...,
        kind: Any = ...,
        dirty: Any = ...,
    ) -> "Flow":
        return Flow(
            uri if uri is not None else self._uri,
            data=self._data if data is ... else data,
            kind=self._kind if kind is ... else kind,
            dirty=self._dirty if dirty is ... else dirty,
        )

    # ------------------------------------------------------------------
    # LOAD — pull content into the flow
    # ------------------------------------------------------------------

    def json(self) -> "Flow":
        """Load URI as JSON object into the flow payload."""
        from .json import loads
        from .ops import read

        text = read(self._uri, encoding="utf-8")
        assert isinstance(text, str)
        return self._clone(data=loads(text), kind="json", dirty=False)

    def yaml(self) -> "Flow":
        """Load URI as YAML object into the flow payload."""
        from .yaml import loads
        from .ops import read

        text = read(self._uri, encoding="utf-8")
        assert isinstance(text, str)
        return self._clone(data=loads(text), kind="yaml", dirty=False)

    def text(self) -> "Flow":
        """Load URI as text into the flow payload."""
        from .ops import read

        text = read(self._uri, encoding="utf-8")
        return self._clone(data=text, kind="text", dirty=False)

    def bytes(self) -> "Flow":  # noqa: A003 — intentional verb name
        """Load URI as bytes into the flow payload."""
        from .ops import read

        data = read(self._uri, binary=True)
        return self._clone(data=data, kind="bytes", dirty=False)

    @property
    def data(self) -> Any:
        """Current payload (after LOAD / EDIT). Raises if empty."""
        if self._kind is None:
            raise FlowError(
                "No payload loaded. Call .json() / .yaml() / .text() / .bytes() first."
            )
        return self._data

    # ------------------------------------------------------------------
    # EDIT — transform payload
    # ------------------------------------------------------------------

    def _require_payload(self, op: str) -> None:
        if self._kind is None:
            raise FlowError(f".{op}() needs a payload. Call .json()/.yaml()/.text() first.")

    def update(self, **kwargs: Any) -> "Flow":
        """Update mapping keys (JSON/YAML dict payload)."""
        self._require_payload("update")
        if not isinstance(self._data, dict):
            raise FlowError(".update() requires a dict payload (use .json()/.yaml()).")
        new_data = dict(self._data)
        new_data.update(kwargs)
        return self._clone(data=new_data, dirty=True)

    def merge(self, other: dict, deep: bool = True) -> "Flow":
        """Deep/shallow merge a dict into the payload."""
        self._require_payload("merge")
        if not isinstance(self._data, dict):
            raise FlowError(".merge() requires a dict payload.")
        from .json import merge as json_merge

        return self._clone(data=json_merge(self._data, other, deep=deep), dirty=True)

    def map(self, fn: Callable[[Any], Any]) -> "Flow":  # noqa: A003
        """Replace payload with ``fn(data)``."""
        self._require_payload("map")
        return self._clone(data=fn(self._data), dirty=True)

    # ------------------------------------------------------------------
    # SAVE — write payload
    # ------------------------------------------------------------------

    def save(self, dst: Optional[PathLike] = None) -> "Flow":
        """Write payload to ``dst`` (default: current uri). Returns Flow at write target."""
        self._require_payload("save")
        target = dst if dst is not None else self._uri
        self._write_payload(target)
        return Flow(target, data=self._data, kind=self._kind, dirty=False)

    def _write_payload(self, target: PathLike) -> None:
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
        """If payload was edited and not saved, write back before SEND."""
        if self._dirty and self._kind is not None:
            self._write_payload(self._uri)
            self._dirty = False

    # ------------------------------------------------------------------
    # SEND — place-level transfer
    # ------------------------------------------------------------------

    def to(self, dst: PathLike, **copy_kw: Any) -> "Flow":
        """Copy current place (or flush dirty payload first) to ``dst``.

        Returns a Flow pointing at ``dst``.
        """
        from .ops import copy

        self._flush_if_dirty()
        # If we have a clean payload and dst looks like a file write of content,
        # still use copy of the uri for directory/file fidelity.
        copy(self._uri, dst, **copy_kw)
        return Flow(dst)

    def fanout(self, *dsts: PathLike, **copy_kw: Any) -> "Flow":
        """Copy current place to many destinations. Returns self (source Flow).

        Cognitive rule: fanout keeps your finger on the *source*; destinations
        are side effects. Use ``same_hash(*dsts)`` to verify.
        """
        if not dsts:
            raise FlowError(".fanout() requires at least one destination")
        from .ops import copy

        self._flush_if_dirty()
        for dst in dsts:
            copy(self._uri, dst, **copy_kw)
        return self._clone(dirty=False)

    def move_to(self, dst: PathLike, **move_kw: Any) -> "Flow":
        """Move current place to ``dst``. Returns Flow at destination."""
        from .ops import move

        self._flush_if_dirty()
        move(self._uri, dst, **move_kw)
        return Flow(dst)

    def write(self, content: Union[str, bytes], encoding: str = "utf-8") -> "Flow":
        """Write raw content to the current URI (no LOAD required)."""
        from .ops import write

        write(self._uri, content, encoding=encoding)
        kind = "bytes" if isinstance(content, bytes) else "text"
        return self._clone(data=content, kind=kind, dirty=False)

    def remove(self, **remove_kw: Any) -> "Flow":
        """Remove the current URI. Returns self (uri unchanged; may no longer exist)."""
        from .ops import remove

        remove(self._uri, **remove_kw)
        return self._clone(data=None, kind=None, dirty=False)

    # ------------------------------------------------------------------
    # INSPECT — query without shifting the mental "finger"
    # ------------------------------------------------------------------

    def exists(self) -> bool:
        from .ops import exists
        return exists(self._uri)

    def hash(self, algorithm: str = "sha256") -> str:  # noqa: A003
        from .hash import hash_file
        return hash_file(self._uri, algorithm=algorithm)  # type: ignore[arg-type]

    def size(self) -> int:
        from .ops import file_size
        return file_size(self._uri)

    def tree(self, **kw: Any) -> str:
        from .ops import tree
        return tree(self._uri, **kw)

    def search(self, *patterns: str, mode: str = "include", recursive: bool = True) -> List[str]:
        from .ops import search
        pats = list(patterns) if patterns else None
        return search(self._uri, mode=mode if pats else "all", patterns=pats, recursive=recursive)

    def listdir(self, **kw: Any) -> list:
        from .ops import listdir
        return listdir(self._uri, **kw)

    def read(self, encoding: str = "utf-8", binary: bool = False) -> Union[str, bytes]:
        """One-shot read (does not store payload). Prefer .text()/.json() for chaining."""
        from .ops import read
        return read(self._uri, encoding=encoding, binary=binary)

    def ensure(self) -> "Flow":
        """Ensure current URI exists as a directory."""
        from .ops import ensure
        ensure(self._uri)
        return self

    # ------------------------------------------------------------------
    # CHECK — direct names (no assert_ prefix)
    # ------------------------------------------------------------------

    def same_hash(self, *others: PathLike, algorithm: str = "sha256") -> "Flow":
        """Fail if any ``other`` URI differs in hash from this flow. Returns self.

        Direct CHECK verb — pair with ``exists()`` (bool) for presence.
        """
        if not others:
            raise FlowError(".same_hash() requires at least one other URI")
        base = self.hash(algorithm=algorithm)
        from .hash import hash_file

        for other in others:
            h = hash_file(other, algorithm=algorithm)  # type: ignore[arg-type]
            if h != base:
                raise FlowError(
                    f"Hash mismatch: {self._uri} ({base[:12]}…) "
                    f"!= {other} ({h[:12]}…)"
                )
        return self


def at(uri: PathLike) -> Flow:
    """Start a flow at ``uri`` (bare path or any supported URI scheme).

    This is the only entry point you need to remember.
    """
    return Flow(uri)


__all__ = [
    "Flow",
    "FlowError",
    "at",
]
