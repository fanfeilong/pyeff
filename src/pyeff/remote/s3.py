"""S3 / MinIO object storage file operations.

Requires: boto3 (pip install pyeff[s3])

URI Format:
    s3://bucket/key
    s3:bucket:/key

Example:
    >>> from pyeff.remote.s3 import S3Remote, s3
    >>> 
    >>> with s3("my-bucket") as client:
    ...     client.copy_from("logs/", "./logs")
    ...     client.copy_to("./data.csv", "uploads/data.csv")
    >>> 
    >>> # MinIO / custom endpoint
    >>> with s3("bucket", endpoint_url="http://localhost:9000",
    ...         access_key="minioadmin", secret_key="minioadmin") as client:
    ...     client.exists("path/to/file")
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

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

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception


def _check_boto3() -> None:
    if not BOTO3_AVAILABLE:
        raise ImportError(
            "S3 support requires 'boto3' package. "
            "Install with: pip install pyeff[s3] or pip install boto3"
        )


class S3Remote(RemoteBackend):
    """S3 / MinIO object storage operations.
    
    Args:
        bucket: S3 bucket name.
        endpoint_url: Custom endpoint (for MinIO / S3-compatible).
        access_key: AWS access key ID (or env AWS_ACCESS_KEY_ID).
        secret_key: AWS secret access key (or env AWS_SECRET_ACCESS_KEY).
        region: AWS region name.
        session_token: Optional session token.
        
    Example:
        >>> with S3Remote("my-bucket") as s3:
        ...     s3.copy_from("data/", "./data")
        ...     s3.write_text("config.json", '{"a": 1}')
    """
    
    def __init__(
        self,
        bucket: str,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        session_token: Optional[str] = None,
    ):
        _check_boto3()
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.session_token = session_token
        self._client = None
    
    def __enter__(self) -> "S3Remote":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def connect(self) -> None:
        """Create boto3 S3 client."""
        if self._client is not None:
            return
        
        kwargs: Dict[str, Any] = {}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if self.region:
            kwargs["region_name"] = self.region
        if self.access_key and self.secret_key:
            kwargs["aws_access_key_id"] = self.access_key
            kwargs["aws_secret_access_key"] = self.secret_key
            if self.session_token:
                kwargs["aws_session_token"] = self.session_token
        
        try:
            self._client = boto3.client("s3", **kwargs)
            # Verify bucket access
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            raise RemoteConnectionError(f"S3 connection failed: {e}")
        except Exception as e:
            raise RemoteConnectionError(f"S3 connection failed: {e}")
    
    def close(self) -> None:
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            self.connect()
        return self._client
    
    def _normalize_key(self, key: str) -> str:
        """Normalize S3 key (strip leading slashes)."""
        return key.lstrip("/")
    
    def exists(self, remote_path: str) -> bool:
        """Check if object or prefix exists."""
        key = self._normalize_key(remote_path)
        if not key:
            return True  # bucket root
        
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            pass
        
        # Check as prefix (directory)
        prefix = key if key.endswith("/") else key + "/"
        resp = self.client.list_objects_v2(
            Bucket=self.bucket, Prefix=prefix, MaxKeys=1
        )
        return resp.get("KeyCount", 0) > 0
    
    def is_file(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key or key.endswith("/"):
            return False
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False
    
    def is_dir(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key:
            return True
        if self.is_file(remote_path):
            return False
        prefix = key if key.endswith("/") else key + "/"
        resp = self.client.list_objects_v2(
            Bucket=self.bucket, Prefix=prefix, MaxKeys=1
        )
        return resp.get("KeyCount", 0) > 0
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        """List objects under a prefix (non-recursive, delimiter=/)."""
        prefix = self._normalize_key(remote_path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        
        filter_obj = PatternFilter(mode, patterns)
        results: List[RemoteFileInfo] = []
        
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=prefix, Delimiter="/"
        ):
            for cp in page.get("CommonPrefixes", []):
                name = cp["Prefix"][len(prefix):].rstrip("/")
                if name and filter_obj.match(name):
                    results.append(RemoteFileInfo(
                        name=name,
                        path=cp["Prefix"].rstrip("/"),
                        size=0,
                        is_dir=True,
                        is_file=False,
                    ))
            
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key == prefix:
                    continue
                name = key[len(prefix):]
                if "/" in name:
                    continue
                if name and filter_obj.match(name):
                    results.append(RemoteFileInfo(
                        name=name,
                        path=key,
                        size=obj.get("Size", 0),
                        is_dir=False,
                        is_file=True,
                    ))
        
        return results
    
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        """Search objects under a prefix."""
        prefix = self._normalize_key(remote_path)
        if prefix and not prefix.endswith("/") and self.is_dir(remote_path):
            prefix += "/"
        
        filter_obj = PatternFilter(mode, patterns)
        results: List[str] = []
        
        # Single file
        if prefix and not prefix.endswith("/") and self.is_file(remote_path):
            if filter_obj.match(PurePosixPath(prefix).name):
                return [prefix]
            return []
        
        paginator = self.client.get_paginator("list_objects_v2")
        kwargs: Dict[str, Any] = {"Bucket": self.bucket, "Prefix": prefix}
        if not recursive:
            kwargs["Delimiter"] = "/"
        
        for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                if filter_obj.match(PurePosixPath(key).name):
                    results.append(key)
        
        return results
    
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Download from S3 to local."""
        local = Path(local_path)
        key = self._normalize_key(remote_path)
        
        if self.is_file(remote_path):
            local.parent.mkdir(parents=True, exist_ok=True)
            if local.is_dir():
                local = local / PurePosixPath(key).name
            self.client.download_file(self.bucket, key, str(local))
            if progress:
                progress(key, 1, 1)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        if not files:
            if not self.exists(remote_path):
                raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
            return 0
        
        total = len(files)
        count = 0
        base = key.rstrip("/")
        
        for remote_key in files:
            if base and remote_key.startswith(base + "/"):
                rel = remote_key[len(base) + 1:]
            elif base and remote_key == base:
                rel = PurePosixPath(remote_key).name
            else:
                rel = remote_key
            
            local_file = local / rel
            local_file.parent.mkdir(parents=True, exist_ok=True)
            self.client.download_file(self.bucket, remote_key, str(local_file))
            count += 1
            if progress:
                progress(remote_key, count, total)
        
        return count
    
    def copy_to(
        self,
        local_path: PathLike,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Upload from local to S3."""
        local = Path(local_path)
        if not local.exists():
            raise FileNotFoundError(f"Local path not found: {local_path}")
        
        dest = self._normalize_key(remote_path)
        
        if local.is_file():
            key = dest
            if dest.endswith("/") or (dest and self.is_dir(remote_path)):
                key = f"{dest.rstrip('/')}/{local.name}"
            self.client.upload_file(str(local), self.bucket, key)
            if progress:
                progress(str(local), 1, 1)
            return 1
        
        filter_obj = PatternFilter(mode, patterns)
        files_to_upload: List[Tuple[Path, str]] = []
        
        for root, dirs, files in os.walk(local):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                rel = file_path.relative_to(local)
                if filter_obj.match(str(rel)):
                    key = f"{dest.rstrip('/')}/{rel}" if dest else str(rel)
                    key = key.replace("\\", "/")
                    files_to_upload.append((file_path, key))
        
        total = len(files_to_upload)
        count = 0
        
        for local_file, key in files_to_upload:
            self.client.upload_file(str(local_file), self.bucket, key)
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
        """Delete objects from S3."""
        key = self._normalize_key(remote_path)
        
        if self.is_file(remote_path):
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        if not files:
            return 0
        
        # Batch delete (max 1000)
        count = 0
        for i in range(0, len(files), 1000):
            batch = files[i:i + 1000]
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": k} for k in batch]},
            )
            count += len(batch)
        
        return count
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(remote_path).decode(encoding)
    
    def read_bytes(self, remote_path: str) -> bytes:
        key = self._normalize_key(remote_path)
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            raise RemoteFileNotFoundError(f"File not found: {remote_path}") from e
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        self.write_bytes(remote_path, content.encode(encoding))
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        key = self._normalize_key(remote_path)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)


def s3(
    bucket: str,
    endpoint_url: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
    session_token: Optional[str] = None,
) -> S3Remote:
    """Create an S3 / MinIO remote interface.
    
    Example:
        >>> with s3("my-bucket") as client:
        ...     client.copy_from("logs/", "./logs")
        >>> 
        >>> with s3("bucket", endpoint_url="http://localhost:9000",
        ...         access_key="minio", secret_key="minio123") as client:
        ...     client.exists("file.txt")
    """
    return S3Remote(
        bucket=bucket,
        endpoint_url=endpoint_url,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        session_token=session_token,
    )
