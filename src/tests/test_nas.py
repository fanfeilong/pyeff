"""Tests for SMB and WebDAV (NAS) backends."""

import pytest
from unittest.mock import MagicMock, Mock, patch

from pyeff.uri import (
    SMBPath,
    WebDAVPath,
    smb_uri,
    webdav_uri,
    parse_uri,
)
from pyeff.remote.webdav import WebDAVRemote, webdav
from pyeff.remote.base import RemoteError, RemoteFileNotFoundError


class TestSMBURI:
    def test_parse_smb_standard(self):
        p = parse_uri("smb://nas.local/shared/docs/file.txt")
        assert isinstance(p, SMBPath)
        assert p.host == "nas.local"
        assert p.share == "shared"
        assert p.path == "docs/file.txt"
    
    def test_parse_smb_share_root(self):
        p = parse_uri("smb://nas.local/shared/")
        assert p.host == "nas.local"
        assert p.share == "shared"
        assert p.path == ""
    
    def test_parse_smb_colon_style(self):
        p = parse_uri("smb:nas.local/shared:/docs/file.txt")
        assert isinstance(p, SMBPath)
        assert p.host == "nas.local"
        assert p.share == "shared"
        assert p.path == "docs/file.txt"
    
    def test_smb_uri_builder(self):
        p = smb_uri(
            "nas.local", "shared", "docs/",
            username="user", password="pass",
        )
        assert p.to_uri() == "smb://nas.local/shared/docs/"
        params = p.get_connection_params()
        assert params["username"] == "user"
        assert params["password"] == "pass"
    
    def test_invalid_smb(self):
        with pytest.raises(ValueError, match="Invalid smb URI"):
            parse_uri("smb://nas.local")


class TestWebDAVURI:
    def test_parse_webdavs(self):
        p = parse_uri("webdavs://nas.local/webdav/docs/file.txt")
        assert isinstance(p, WebDAVPath)
        assert p.base_url == "https://nas.local"
        assert p.path == "webdav/docs/file.txt"
        assert p.scheme == "webdavs"
    
    def test_parse_webdav(self):
        p = parse_uri("webdav://nas.local/files/")
        assert p.base_url == "http://nas.local"
        assert p.path == "files/"
        assert p.scheme == "webdav"
    
    def test_parse_davs_alias(self):
        p = parse_uri("davs://cloud.local/remote.php/dav/files/user/Doc")
        assert isinstance(p, WebDAVPath)
        assert p.base_url == "https://cloud.local"
        assert "remote.php" in p.path
    
    def test_webdav_uri_builder(self):
        p = webdav_uri(
            "https://nas.local/remote.php/dav/files/user",
            "Documents/file.txt",
            username="user",
            password="secret",
        )
        assert p.base_url.startswith("https://")
        assert p.path == "Documents/file.txt"
        params = p.get_connection_params()
        assert params["username"] == "user"
        assert params["password"] == "secret"
    
    def test_webdav_uri_normalizes_scheme(self):
        p = webdav_uri("webdavs://nas.local/dav", "a.txt")
        assert p.base_url == "https://nas.local/dav"


class TestWebDAVRemote:
    def test_factory(self):
        w = webdav("https://nas.local/webdav", username="u", password="p")
        assert isinstance(w, WebDAVRemote)
        assert w.username == "u"
    
    def test_url_join(self):
        w = WebDAVRemote("https://nas.local/webdav")
        assert w._url("docs/file.txt").endswith("/docs/file.txt")
        assert "webdav" in w._url("docs/file.txt")
    
    def test_parse_propfind(self):
        w = WebDAVRemote("https://nas.local/webdav/")
        xml = b"""<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:">
          <d:response>
            <d:href>/webdav/docs/</d:href>
            <d:propstat>
              <d:prop>
                <d:displayname>docs</d:displayname>
                <d:resourcetype><d:collection/></d:resourcetype>
              </d:prop>
            </d:propstat>
          </d:response>
          <d:response>
            <d:href>/webdav/docs/file.txt</d:href>
            <d:propstat>
              <d:prop>
                <d:displayname>file.txt</d:displayname>
                <d:getcontentlength>12</d:getcontentlength>
                <d:resourcetype/>
              </d:prop>
            </d:propstat>
          </d:response>
        </d:multistatus>
        """
        items = w._parse_propfind(xml, "docs")
        assert len(items) == 2
        files = [i for i in items if not i["is_dir"]]
        assert files[0]["name"] == "file.txt"
        assert files[0]["size"] == 12
    
    def test_read_bytes_mocked(self):
        w = WebDAVRemote("https://nas.local/webdav")
        mock_resp = MagicMock()
        mock_resp.read = Mock(return_value=b"hello")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        
        with patch.object(w, "_request", return_value=mock_resp):
            assert w.read_bytes("file.txt") == b"hello"
    
    def test_copy_from_file_mocked(self, tmp_path):
        w = WebDAVRemote("https://nas.local/webdav")
        mock_resp = MagicMock()
        mock_resp.read = Mock(return_value=b"content")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        
        with patch.object(w, "is_file", return_value=True), \
             patch.object(w, "_request", return_value=mock_resp):
            dest = tmp_path / "out.txt"
            count = w.copy_from("file.txt", dest)
        
        assert count == 1
        assert dest.read_bytes() == b"content"


class TestSMBRemote:
    def test_smb_requires_package(self):
        from pyeff.remote.smb import smb, SMB_AVAILABLE
        
        if SMB_AVAILABLE:
            client = smb("host", "share", username="u", password="p")
            assert client.host == "host"
            assert client.share == "share"
        else:
            with pytest.raises(ImportError, match="smbprotocol"):
                smb("host", "share")
    
    def test_unc_path(self):
        from pyeff.remote.smb import SMBRemote, SMB_AVAILABLE
        
        if not SMB_AVAILABLE:
            pytest.skip("smbprotocol not installed")
        
        with patch.object(SMBRemote, "connect"):
            r = SMBRemote("nas", "shared")
            r._registered = True
            assert r._unc("docs/file.txt") == r"\\nas\shared\docs\file.txt"
            assert r._unc("") == r"\\nas\shared"


class TestOpsDispatch:
    def test_smb_to_local_handler(self):
        from pyeff.ops import _get_copy_handler
        from pyeff.uri import SMBPath, LocalPath
        
        h = _get_copy_handler(
            SMBPath("nas", "share", "docs/"), LocalPath("./out")
        )
        assert h.__name__ == "_copy_smb_to_local"
    
    def test_local_to_webdav_handler(self):
        from pyeff.ops import _get_copy_handler
        from pyeff.uri import WebDAVPath, LocalPath
        
        h = _get_copy_handler(
            LocalPath("./src"),
            WebDAVPath("https://nas/webdav", "docs/"),
        )
        assert h.__name__ == "_copy_local_to_webdav"
    
    def test_webdavs_to_local_handler(self):
        from pyeff.ops import _get_copy_handler
        
        src = parse_uri("webdavs://nas.local/files/a.txt")
        dst = parse_uri("local:./a.txt")
        h = _get_copy_handler(src, dst)
        assert h.__name__ == "_copy_webdav_to_local"
