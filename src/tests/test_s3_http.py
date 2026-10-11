"""Tests for S3/HTTP/GCS/Azure URI parsing and backends."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock

from pyeff.uri import (
    S3Path,
    GCSPath,
    AzurePath,
    HTTPPath,
    s3,
    gs,
    az,
    http_url,
    parse_uri,
)
from pyeff.remote.http import HTTPRemote, http, http_download
from pyeff.remote.base import RemoteError, RemoteFileNotFoundError


class TestS3URI:
    def test_parse_s3_standard(self):
        p = parse_uri("s3://my-bucket/logs/app.log")
        assert isinstance(p, S3Path)
        assert p.bucket == "my-bucket"
        assert p.path == "logs/app.log"
    
    def test_parse_s3_colon_style(self):
        p = parse_uri("s3:my-bucket:/logs/app.log")
        assert isinstance(p, S3Path)
        assert p.bucket == "my-bucket"
        assert p.path == "logs/app.log"
    
    def test_parse_s3_bucket_only(self):
        p = parse_uri("s3://my-bucket/")
        assert p.bucket == "my-bucket"
        assert p.path == ""
    
    def test_s3_builder(self):
        p = s3("bucket", "key/file.txt", endpoint_url="http://localhost:9000")
        assert p.bucket == "bucket"
        assert p.path == "key/file.txt"
        assert p.endpoint_url == "http://localhost:9000"
        assert p.to_uri() == "s3://bucket/key/file.txt"
    
    def test_s3_connection_params(self):
        p = s3("b", "k", access_key="AK", secret_key="SK", region="us-east-1")
        params = p.get_connection_params()
        assert params["bucket"] == "b"
        assert params["access_key"] == "AK"
        assert params["secret_key"] == "SK"
        assert params["region"] == "us-east-1"


class TestGCSURI:
    def test_parse_gs(self):
        p = parse_uri("gs://my-bucket/path/file.csv")
        assert isinstance(p, GCSPath)
        assert p.bucket == "my-bucket"
        assert p.path == "path/file.csv"
    
    def test_parse_gcs_alias(self):
        p = parse_uri("gcs:my-bucket:/path/file.csv")
        assert isinstance(p, GCSPath)
        assert p.bucket == "my-bucket"
    
    def test_gs_builder(self):
        p = gs("bucket", "data/", project="my-proj")
        assert p.to_uri() == "gs://bucket/data/"
        assert p.project == "my-proj"


class TestAzureURI:
    def test_parse_az(self):
        p = parse_uri("az://my-container/blobs/file.txt")
        assert isinstance(p, AzurePath)
        assert p.container == "my-container"
        assert p.path == "blobs/file.txt"
    
    def test_parse_azure_alias(self):
        p = parse_uri("azure:my-container:/blobs/file.txt")
        assert isinstance(p, AzurePath)
        assert p.container == "my-container"
    
    def test_az_builder(self):
        p = az("ctr", "path/f.txt", connection_string="DefaultEndpoints...")
        assert p.to_uri() == "az://ctr/path/f.txt"
        assert "connection_string" in p.get_connection_params()


class TestHTTPURI:
    def test_parse_https(self):
        p = parse_uri("https://example.com/file.zip")
        assert isinstance(p, HTTPPath)
        assert p.url == "https://example.com/file.zip"
        assert p.scheme == "https"
    
    def test_parse_http(self):
        p = parse_uri("http://example.com/a/b")
        assert isinstance(p, HTTPPath)
        assert p.scheme == "http"
    
    def test_http_url_builder(self):
        p = http_url("https://cdn.example.com/x.tar.gz", timeout=30)
        assert p.timeout == 30
        assert p.get_url_path() == "/x.tar.gz"
    
    def test_http_connection_params(self):
        p = http_url("https://example.com/path/file?q=1")
        params = p.get_connection_params()
        assert params["base_url"] == "https://example.com"
        assert p.get_url_path() == "/path/file?q=1"
    
    def test_invalid_http(self):
        with pytest.raises(ValueError, match="Invalid http URI"):
            parse_uri("http:not-a-url")


class TestHTTPRemote:
    def test_http_factory(self):
        h = http("https://example.com")
        assert isinstance(h, HTTPRemote)
        assert h.base_url == "https://example.com"
    
    def test_url_join(self):
        h = HTTPRemote("https://example.com")
        assert h._url("/file.zip") == "https://example.com/file.zip"
        assert h._url("https://other.com/x") == "https://other.com/x"
    
    def test_copy_from_mocked(self, tmp_path):
        h = HTTPRemote("https://example.com")
        
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "5"}
        mock_resp.read = Mock(side_effect=[b"hello", b""])
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        
        with patch.object(h, "_request", return_value=mock_resp):
            dest = tmp_path / "out.txt"
            count = h.copy_from("/file.txt", dest)
        
        assert count == 1
        assert dest.read_bytes() == b"hello"
    
    def test_read_text_mocked(self):
        h = HTTPRemote("https://example.com")
        mock_resp = MagicMock()
        mock_resp.read = Mock(return_value=b'{"a": 1}')
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        
        with patch.object(h, "_request", return_value=mock_resp):
            content = h.read_text("/data.json")
        
        assert content == '{"a": 1}'
    
    def test_exists_mocked(self):
        h = HTTPRemote("https://example.com")
        mock_resp = MagicMock()
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        
        with patch.object(h, "_request", return_value=mock_resp):
            assert h.exists("/file.txt") is True
        
        with patch.object(h, "_request", side_effect=RemoteFileNotFoundError("x")):
            assert h.exists("/missing") is False
    
    def test_listdir_raises(self):
        h = HTTPRemote("https://example.com")
        with pytest.raises(RemoteError, match="listdir is not supported"):
            h.listdir("/")


class TestS3RemoteMocked:
    def test_s3_module_importable(self):
        """S3 module loads even without boto3."""
        from pyeff.remote.s3 import S3Remote, s3, BOTO3_AVAILABLE
        assert S3Remote is not None
        assert callable(s3)
    
    def test_s3_requires_boto3(self):
        from pyeff.remote.s3 import s3 as s3_factory, BOTO3_AVAILABLE
        
        if BOTO3_AVAILABLE:
            client = s3_factory("nonexistent-bucket-pyeff-test-xyz")
            assert client.bucket == "nonexistent-bucket-pyeff-test-xyz"
        else:
            with pytest.raises(ImportError, match="boto3"):
                s3_factory("any-bucket")
    
    def test_s3_remote_normalize_key(self):
        from pyeff.remote.s3 import S3Remote, BOTO3_AVAILABLE
        
        if not BOTO3_AVAILABLE:
            pytest.skip("boto3 not installed")
        
        with patch.object(S3Remote, "connect"):
            r = S3Remote("bucket")
            r._client = Mock()
            assert r._normalize_key("/a/b") == "a/b"
            assert r._normalize_key("a/b") == "a/b"


class TestUnifiedOpsDispatch:
    def test_copy_handler_s3_local(self):
        from pyeff.ops import _get_copy_handler
        from pyeff.uri import S3Path, LocalPath
        
        handler = _get_copy_handler(
            S3Path("b", "k"), LocalPath("./out")
        )
        assert handler.__name__ == "_copy_s3_to_local"
    
    def test_copy_handler_local_s3(self):
        from pyeff.ops import _get_copy_handler
        from pyeff.uri import S3Path, LocalPath
        
        handler = _get_copy_handler(
            LocalPath("./src"), S3Path("b", "k")
        )
        assert handler.__name__ == "_copy_local_to_s3"
    
    def test_copy_handler_https_local(self):
        from pyeff.ops import _get_copy_handler
        from pyeff.uri import HTTPPath, LocalPath
        
        handler = _get_copy_handler(
            HTTPPath("https://example.com/f"), LocalPath("./out")
        )
        assert handler.__name__ == "_copy_http_to_local"
    
    def test_copy_https_to_local_mocked(self, tmp_path):
        from pyeff import copy
        
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "4"}
        mock_resp.read = Mock(side_effect=[b"data", b""])
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        
        with patch("pyeff.remote.http.HTTPRemote._request", return_value=mock_resp):
            dest = tmp_path / "downloaded.bin"
            count = copy("https://example.com/file.bin", f"local:{dest}")
        
        assert count == 1
        assert dest.read_bytes() == b"data"
