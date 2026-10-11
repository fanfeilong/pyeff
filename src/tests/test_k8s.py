"""Tests for pyeff.remote.k8s module."""

import pytest
from unittest.mock import Mock, patch

from pyeff.remote.base import RemoteError, RemoteConnectionError
from pyeff.remote.k8s import (
    K8sRemote,
    k8s,
    k8s_copy,
    _parse_pod_spec,
    _split_pod_path,
)
from pyeff.uri import (
    K8sPath,
    k8s as k8s_uri,
    parse_uri,
)


class TestParsePodSpec:
    def test_pod_only(self):
        ns, pod, ctr = _parse_pod_spec("my-pod")
        assert ns == "default"
        assert pod == "my-pod"
        assert ctr is None
    
    def test_namespace_pod(self):
        ns, pod, ctr = _parse_pod_spec("prod/my-pod")
        assert ns == "prod"
        assert pod == "my-pod"
        assert ctr is None
    
    def test_namespace_pod_container(self):
        ns, pod, ctr = _parse_pod_spec("prod/my-pod/app")
        assert ns == "prod"
        assert pod == "my-pod"
        assert ctr == "app"
    
    def test_override_namespace(self):
        ns, pod, ctr = _parse_pod_spec("my-pod", namespace="staging")
        assert ns == "staging"
        assert pod == "my-pod"
    
    def test_override_container(self):
        ns, pod, ctr = _parse_pod_spec("prod/my-pod", container="sidecar")
        assert ns == "prod"
        assert pod == "my-pod"
        assert ctr == "sidecar"


class TestSplitPodPath:
    def test_pod_path(self):
        pod, path = _split_pod_path("my-pod:/app/data")
        assert pod == "my-pod"
        assert path == "/app/data"
    
    def test_ns_pod_path(self):
        pod, path = _split_pod_path("prod/my-pod:/app/data")
        assert pod == "prod/my-pod"
        assert path == "/app/data"
    
    def test_local_absolute(self):
        pod, path = _split_pod_path("/local/path")
        assert pod is None
        assert path == "/local/path"
    
    def test_local_relative(self):
        pod, path = _split_pod_path("./local/path")
        assert pod is None


class TestK8sFactory:
    def test_k8s_factory_returns_k8s_remote(self):
        k = k8s("my-pod")
        assert isinstance(k, K8sRemote)
        assert k.pod == "my-pod"
        assert k.namespace == "default"
    
    def test_k8s_factory_with_namespace(self):
        k = k8s("my-pod", namespace="prod")
        assert k.namespace == "prod"
        assert k.pod == "my-pod"
    
    def test_k8s_factory_compact_spec(self):
        k = k8s("prod/my-pod/app")
        assert k.namespace == "prod"
        assert k.pod == "my-pod"
        assert k.container == "app"
    
    def test_k8s_remote_has_unified_api(self):
        k = k8s("my-pod")
        assert hasattr(k, "copy")
        assert hasattr(k, "copy_from")
        assert hasattr(k, "copy_to")
        assert hasattr(k, "remove")
        assert hasattr(k, "search")
        assert hasattr(k, "exists")
        assert hasattr(k, "read_text")
        assert hasattr(k, "write_text")


class TestK8sRemoteMocked:
    @pytest.fixture
    def mock_k8s(self):
        """Create a mocked K8sRemote."""
        with patch("pyeff.remote.k8s._run_kubectl") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Running", stderr="")
            k = K8sRemote("my-pod", namespace="default")
            k._verified = True
            yield k, mock_run
    
    def test_exists_true(self, mock_k8s):
        k, mock_run = mock_k8s
        with patch.object(k, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=0)
            assert k.exists("/app/data") is True
    
    def test_exists_false(self, mock_k8s):
        k, mock_run = mock_k8s
        with patch.object(k, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=1)
            assert k.exists("/nonexistent") is False
    
    def test_is_file(self, mock_k8s):
        k, mock_run = mock_k8s
        with patch.object(k, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=0)
            assert k.is_file("/app/file.txt") is True
    
    def test_is_dir(self, mock_k8s):
        k, mock_run = mock_k8s
        with patch.object(k, "_exec") as mock_exec:
            mock_exec.return_value = Mock(returncode=0)
            assert k.is_dir("/app/data") is True
    
    def test_copy_detects_remote_to_local(self, mock_k8s):
        k, mock_run = mock_k8s
        with patch.object(k, "copy_from") as mock_copy_from:
            mock_copy_from.return_value = 5
            k.copy("/app/logs", "./logs")
            mock_copy_from.assert_called_once()
            assert mock_copy_from.call_args[0][0] == "/app/logs"
    
    def test_copy_detects_local_to_remote(self, mock_k8s):
        k, mock_run = mock_k8s
        with patch.object(k, "copy_to") as mock_copy_to:
            mock_copy_to.return_value = 3
            k.copy("./config", "/app/config")
            mock_copy_to.assert_called_once()
            assert mock_copy_to.call_args[0][0] == "./config"
    
    def test_copy_both_remote_raises(self, mock_k8s):
        k, mock_run = mock_k8s
        with pytest.raises(RemoteError, match="Both paths appear to be pod"):
            k.copy("/app/src", "/app/dst")
    
    def test_copy_both_local_raises(self, mock_k8s):
        k, mock_run = mock_k8s
        with pytest.raises(RemoteError, match="Both paths appear to be local"):
            k.copy("./src", "./dst")
    
    def test_pod_not_found(self):
        with patch("pyeff.remote.k8s._run_kubectl") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error from server")
            with pytest.raises(RemoteConnectionError):
                with K8sRemote("nonexistent-pod") as k:
                    pass


class TestK8sCopyFunction:
    def test_k8s_copy_both_local_raises(self):
        with pytest.raises(RemoteError, match="pod path"):
            k8s_copy("/local/a", "/local/b")
    
    def test_k8s_copy_pod_to_pod_raises(self):
        with pytest.raises(RemoteError, match="Pod-to-pod"):
            k8s_copy("pod1:/path", "pod2:/path")


class TestK8sURI:
    def test_k8s_path_basic(self):
        p = K8sPath("my-pod", "/app/data")
        assert p.scheme == "k8s"
        assert p.to_uri() == "k8s:my-pod:/app/data"
    
    def test_k8s_path_with_namespace(self):
        p = K8sPath("my-pod", "/app/data", namespace="prod")
        assert p.to_uri() == "k8s:prod/my-pod:/app/data"
    
    def test_k8s_path_with_container(self):
        p = K8sPath("my-pod", "/app/data", namespace="prod", container="app")
        assert p.to_uri() == "k8s:prod/my-pod/app:/app/data"
    
    def test_k8s_uri_builder(self):
        p = k8s_uri("my-pod", "/app/data", namespace="prod")
        assert isinstance(p, K8sPath)
        assert p.pod == "my-pod"
        assert p.namespace == "prod"
        assert p.path == "/app/data"
    
    def test_k8s_uri_builder_compact(self):
        p = k8s_uri("prod/my-pod/app", "/data")
        assert p.namespace == "prod"
        assert p.pod == "my-pod"
        assert p.container == "app"
    
    def test_parse_uri_k8s_pod(self):
        p = parse_uri("k8s:my-pod:/app/data")
        assert isinstance(p, K8sPath)
        assert p.pod == "my-pod"
        assert p.path == "/app/data"
    
    def test_parse_uri_k8s_ns_pod(self):
        p = parse_uri("k8s:prod/my-pod:/app/data")
        assert isinstance(p, K8sPath)
        assert p.namespace == "prod"
        assert p.pod == "my-pod"
        assert p.path == "/app/data"
    
    def test_parse_uri_k8s_ns_pod_container(self):
        p = parse_uri("k8s:prod/my-pod/app:/var/log")
        assert isinstance(p, K8sPath)
        assert p.namespace == "prod"
        assert p.pod == "my-pod"
        assert p.container == "app"
        assert p.path == "/var/log"
    
    def test_get_connection_params(self):
        p = K8sPath("my-pod", "/data", namespace="prod", container="app", context="minikube")
        params = p.get_connection_params()
        assert params["pod"] == "my-pod"
        assert params["namespace"] == "prod"
        assert params["container"] == "app"
        assert params["context"] == "minikube"
