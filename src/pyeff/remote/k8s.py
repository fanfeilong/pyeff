"""Kubernetes pod file operations.

This module provides file operations for Kubernetes pods via kubectl,
with the same API as local fs / Docker / SSH operations.

Requires: kubectl in PATH and a valid kubeconfig.

URI Format:
    k8s:pod:/path
    k8s:namespace/pod:/path
    k8s:namespace/pod/container:/path

Example:
    >>> from pyeff.remote.k8s import K8sRemote, k8s
    >>> 
    >>> with k8s("my-pod", namespace="default") as pod:
    ...     pod.copy_from("/app/logs", "./logs")
    ...     pod.copy_to("./config", "/app/config")
    ...     files = pod.search("/data", patterns=["*.csv"])
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple, Union

from .base import (
    Mode,
    PathLike,
    PatternFilter,
    ProgressCallback,
    RemoteBackend,
    RemoteConnectionError,
    RemoteError,
    RemoteFileInfo,
    RemoteFileNotFoundError,
)


def _run_kubectl(
    args: List[str],
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run a kubectl command."""
    cmd = ["kubectl"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if "not found" in stderr.lower():
            if "pods" in stderr.lower() or "Pod" in stderr:
                raise RemoteConnectionError(f"Pod not found: {stderr.strip()}")
            raise RemoteFileNotFoundError(stderr.strip())
        raise RemoteError(f"kubectl command failed: {stderr.strip()}")
    except FileNotFoundError:
        raise RemoteError(
            "kubectl not found. Please install kubectl and ensure it's in PATH."
        )


def _parse_pod_spec(
    pod: str,
    namespace: Optional[str] = None,
    container: Optional[str] = None,
) -> Tuple[str, str, Optional[str]]:
    """Parse pod specification.
    
    Accepts:
        - "pod-name"
        - "namespace/pod-name"
        - "namespace/pod-name/container"
    
    Returns:
        Tuple of (namespace, pod_name, container).
    """
    parts = pod.split("/")
    
    if len(parts) == 1:
        return namespace or "default", parts[0], container
    elif len(parts) == 2:
        return parts[0], parts[1], container
    elif len(parts) == 3:
        return parts[0], parts[1], container or parts[2]
    else:
        raise ValueError(
            f"Invalid pod spec: {pod!r}. "
            f"Expected 'pod', 'namespace/pod', or 'namespace/pod/container'"
        )


class K8sRemote(RemoteBackend):
    """Kubernetes pod file operations via kubectl.
    
    Provides file operations for K8s pods with the same API
    as local fs / Docker / SSH operations.
    
    Args:
        pod: Pod name, or "namespace/pod", or "namespace/pod/container".
        namespace: Kubernetes namespace (default: "default", or from pod spec).
        container: Container name within the pod (optional).
        context: kubectl context (optional).
        
    Example:
        >>> with K8sRemote("my-pod", namespace="prod") as k:
        ...     k.copy_from("/app/logs", "./logs")
        ...     k.remove("/tmp/cache")
        >>> 
        >>> with K8sRemote("prod/my-pod/app") as k:
        ...     content = k.read_text("/app/config.json")
    """
    
    def __init__(
        self,
        pod: str,
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        context: Optional[str] = None,
    ):
        ns, pod_name, ctr = _parse_pod_spec(pod, namespace, container)
        self.namespace = ns
        self.pod = pod_name
        self.container = ctr
        self.context = context
        self._verified = False
    
    def __enter__(self) -> "K8sRemote":
        self._verify_pod()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
    
    def _kubectl_base_args(self) -> List[str]:
        """Build common kubectl arguments (namespace, context, container)."""
        args: List[str] = []
        if self.context:
            args.extend(["--context", self.context])
        args.extend(["-n", self.namespace])
        return args
    
    def _container_args(self) -> List[str]:
        """Container flag for exec/cp."""
        if self.container:
            return ["-c", self.container]
        return []
    
    def _pod_ref(self) -> str:
        """Pod reference for kubectl cp: namespace/pod."""
        return f"{self.namespace}/{self.pod}"
    
    def _verify_pod(self) -> None:
        """Verify pod exists and is running."""
        if self._verified:
            return
        
        result = _run_kubectl(
            self._kubectl_base_args() + [
                "get", "pod", self.pod,
                "-o", "jsonpath={.status.phase}",
            ],
            check=False,
        )
        
        if result.returncode != 0:
            raise RemoteConnectionError(
                f"Pod not found: {self.namespace}/{self.pod}"
            )
        
        phase = result.stdout.strip()
        if phase != "Running":
            raise RemoteConnectionError(
                f"Pod not running: {self.namespace}/{self.pod} (phase={phase})"
            )
        
        self._verified = True
    
    def _exec(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute command in pod."""
        self._verify_pod()
        args = (
            self._kubectl_base_args()
            + ["exec", self.pod]
            + self._container_args()
            + ["--"]
            + cmd
        )
        return _run_kubectl(args, check=check)
    
    def _cp(self, src: str, dst: str) -> None:
        """Run kubectl cp."""
        self._verify_pod()
        args = self._kubectl_base_args() + ["cp"] + self._container_args() + [src, dst]
        _run_kubectl(args)
    
    def exists(self, remote_path: str) -> bool:
        """Check if path exists in pod."""
        result = self._exec(["test", "-e", remote_path], check=False)
        return result.returncode == 0
    
    def is_file(self, remote_path: str) -> bool:
        """Check if path is a file in pod."""
        result = self._exec(["test", "-f", remote_path], check=False)
        return result.returncode == 0
    
    def is_dir(self, remote_path: str) -> bool:
        """Check if path is a directory in pod."""
        result = self._exec(["test", "-d", remote_path], check=False)
        return result.returncode == 0
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        """List files in pod directory."""
        if not self.is_dir(remote_path):
            raise RemoteFileNotFoundError(f"Directory not found: {remote_path}")
        
        result = self._exec(["ls", "-la", remote_path])
        lines = result.stdout.strip().split("\n")
        
        filter_obj = PatternFilter(mode, patterns)
        files: List[RemoteFileInfo] = []
        
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            
            mode_str = parts[0]
            size = int(parts[4]) if parts[4].isdigit() else 0
            name = " ".join(parts[8:])
            
            if name in (".", ".."):
                continue
            
            if not filter_obj.match(name):
                continue
            
            is_dir = mode_str.startswith("d")
            full_path = f"{remote_path.rstrip('/')}/{name}"
            
            files.append(RemoteFileInfo(
                name=name,
                path=full_path,
                size=size,
                is_dir=is_dir,
                is_file=not is_dir,
                mode=mode_str,
            ))
        
        return files
    
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        """Search for files in pod."""
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        find_args = ["find", remote_path]
        if not recursive:
            find_args.extend(["-maxdepth", "1"])
        find_args.extend(["-type", "f"])
        
        result = self._exec(find_args, check=False)
        if result.returncode != 0:
            return []
        
        all_files = [f for f in result.stdout.strip().split("\n") if f]
        filter_obj = PatternFilter(mode, patterns)
        return [f for f in all_files if filter_obj.match(f)]
    
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files from pod to local."""
        local = Path(local_path)
        
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        if mode == "all" and not patterns:
            local.parent.mkdir(parents=True, exist_ok=True)
            self._cp(f"{self._pod_ref()}:{remote_path}", str(local))
            if progress:
                progress(remote_path, 1, 1)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        total = len(files)
        count = 0
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, remote_file in enumerate(files):
                rel_path = os.path.relpath(remote_file, remote_path)
                local_file = local / rel_path
                local_file.parent.mkdir(parents=True, exist_ok=True)
                
                tmp_file = Path(tmpdir) / f"file_{i}"
                self._cp(f"{self._pod_ref()}:{remote_file}", str(tmp_file))
                shutil.move(str(tmp_file), str(local_file))
                
                count += 1
                if progress:
                    progress(remote_file, count, total)
        
        return count
    
    def copy_to(
        self,
        local_path: PathLike,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files from local to pod."""
        local = Path(local_path)
        
        if not local.exists():
            raise FileNotFoundError(f"Local path not found: {local_path}")
        
        if mode == "all" and not patterns:
            self._cp(str(local), f"{self._pod_ref()}:{remote_path}")
            if progress:
                progress(str(local), 1, 1)
            return 1
        
        filter_obj = PatternFilter(mode, patterns)
        
        if local.is_file():
            if filter_obj.match(local.name):
                self._cp(str(local), f"{self._pod_ref()}:{remote_path}")
                if progress:
                    progress(str(local), 1, 1)
                return 1
            return 0
        
        files_to_copy: List[Tuple[Path, str]] = []
        for root, dirs, files in os.walk(local):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                rel_path = file_path.relative_to(local)
                if filter_obj.match(str(rel_path)):
                    remote_file = f"{remote_path.rstrip('/')}/{rel_path}"
                    files_to_copy.append((file_path, remote_file))
        
        total = len(files_to_copy)
        count = 0
        
        for local_file, remote_file in files_to_copy:
            remote_dir = str(PurePosixPath(remote_file).parent)
            self._exec(["mkdir", "-p", remote_dir], check=False)
            self._cp(str(local_file), f"{self._pod_ref()}:{remote_file}")
            
            count += 1
            if progress:
                progress(str(local_file), count, total)
        
        return count
    
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        """Remove files in pod."""
        if not self.exists(remote_path):
            return 0
        
        if mode == "all" and not patterns:
            rm_args = ["rm"]
            if recursive:
                rm_args.append("-rf")
            rm_args.append(remote_path)
            self._exec(rm_args)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        count = 0
        
        for remote_file in files:
            self._exec(["rm", "-f", remote_file], check=False)
            count += 1
        
        return count
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        """Read text file from pod."""
        if not self.is_file(remote_path):
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        
        result = self._exec(["cat", remote_path])
        return result.stdout
    
    def read_bytes(self, remote_path: str) -> bytes:
        """Read binary file from pod."""
        if not self.is_file(remote_path):
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            self._cp(f"{self._pod_ref()}:{remote_path}", tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            os.unlink(tmp_path)
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """Write text file to pod."""
        with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            remote_dir = str(PurePosixPath(remote_path).parent)
            self._exec(["mkdir", "-p", remote_dir], check=False)
            self._cp(tmp_path, f"{self._pod_ref()}:{remote_path}")
        finally:
            os.unlink(tmp_path)
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        """Write binary file to pod."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            remote_dir = str(PurePosixPath(remote_path).parent)
            self._exec(["mkdir", "-p", remote_dir], check=False)
            self._cp(tmp_path, f"{self._pod_ref()}:{remote_path}")
        finally:
            os.unlink(tmp_path)
    
    def copy(
        self,
        src: str,
        dst: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files between pod and local filesystem.
        
        Direction is auto-detected based on path format:
        - Absolute path (starts with /) = pod path
        - Relative path = local path
        
        Example:
            >>> with k8s("my-pod") as k:
            ...     k.copy("/app/logs", "./logs")      # pod → local
            ...     k.copy("./config", "/app/config")  # local → pod
        """
        src_is_remote = src.startswith("/")
        dst_is_remote = dst.startswith("/")
        
        if src_is_remote and dst_is_remote:
            raise RemoteError(
                "Both paths appear to be pod paths. "
                "Use relative path (./...) for local path."
            )
        
        if not src_is_remote and not dst_is_remote:
            raise RemoteError(
                "Both paths appear to be local paths. "
                "Use absolute path (/...) for pod path."
            )
        
        if src_is_remote:
            return self.copy_from(src, dst, mode, patterns, progress)
        else:
            return self.copy_to(src, dst, mode, patterns, progress)


def k8s(
    pod: str,
    namespace: Optional[str] = None,
    container: Optional[str] = None,
    context: Optional[str] = None,
) -> K8sRemote:
    """Create a Kubernetes remote interface.
    
    Factory function for creating K8sRemote instances.
    
    Args:
        pod: Pod name, or "namespace/pod", or "namespace/pod/container".
        namespace: Kubernetes namespace (default: "default").
        container: Container name within the pod.
        context: kubectl context.
        
    Returns:
        K8sRemote instance (use as context manager).
        
    Example:
        >>> from pyeff.remote import k8s
        >>> 
        >>> with k8s("my-pod", namespace="prod") as k:
        ...     k.copy("/app/logs", "./logs")
        ...     k.copy("./config", "/app/config")
        >>> 
        >>> with k8s("prod/my-pod/app") as k:
        ...     files = k.search("/data", patterns=["*.csv"])
    """
    return K8sRemote(
        pod=pod,
        namespace=namespace,
        container=container,
        context=context,
    )


def k8s_copy(
    src: str,
    dst: str,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    namespace: Optional[str] = None,
    container: Optional[str] = None,
    context: Optional[str] = None,
) -> int:
    """Copy files between K8s pod and local filesystem.
    
    Paths use "pod:/path" or "namespace/pod:/path" format for pod paths.
    
    Example:
        >>> k8s_copy("my-pod:/app/logs", "./logs")
        >>> k8s_copy("./config", "prod/my-pod:/app/config")
    """
    src_pod, src_path = _split_pod_path(src)
    dst_pod, dst_path = _split_pod_path(dst)
    
    if src_pod and dst_pod:
        raise RemoteError("Pod-to-pod copy not supported. Copy via local.")
    
    if not src_pod and not dst_pod:
        raise RemoteError("At least one path must be a pod path (pod:/path)")
    
    if src_pod:
        with K8sRemote(src_pod, namespace=namespace, container=container, context=context) as k:
            return k.copy_from(src_path, dst, mode=mode, patterns=patterns)
    else:
        with K8sRemote(dst_pod, namespace=namespace, container=container, context=context) as k:
            return k.copy_to(src, dst_path, mode=mode, patterns=patterns)


def _split_pod_path(path: str) -> Tuple[Optional[str], str]:
    """Split 'pod:/path' or 'ns/pod:/path' into (pod_spec, path)."""
    if ":" not in path:
        return None, path
    
    # Don't treat Windows drives or relative paths as pod paths
    if path.startswith("/") or path.startswith("."):
        return None, path
    
    # Find the last colon that separates pod from path
    # Formats: pod:/path, ns/pod:/path, ns/pod/ctr:/path
    idx = path.find(":")
    if idx <= 0:
        return None, path
    
    pod_spec = path[:idx]
    remote_path = path[idx + 1:]
    
    # Validate pod_spec looks like a pod reference
    if "/" in remote_path or remote_path.startswith("/"):
        # Single letter + colon is Windows drive
        if len(pod_spec) == 1 and pod_spec.isalpha():
            return None, path
        return pod_spec, remote_path
    
    return None, path
