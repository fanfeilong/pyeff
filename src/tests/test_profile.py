"""Tests for composable Profile / @name credential binding."""

import json
import os
from pathlib import Path

import pytest

from pyeff.profile import (
    Profile,
    ProfileError,
    DictSource,
    EnvSource,
    FileSource,
    CliSource,
    SystemSource,
    NacosSource,
    load_profile,
)
from pyeff.uri import K8sPath, S3Path, SSHPath
from pyeff.flow import at
from pyeff import copy, load_json


class TestNamedBinding:
    def test_two_k8s_entries_are_distinct(self):
        auth = load_profile(
            staging_k8s={"scheme": "k8s", "context": "staging", "namespace": "app"},
            prod_k8s={"scheme": "k8s", "context": "prod", "namespace": "app"},
        )
        a = auth.resolve("@staging_k8s:my-pod:/etc/x")
        b = auth.resolve("@prod_k8s:my-pod:/etc/x")
        assert isinstance(a, K8sPath) and isinstance(b, K8sPath)
        assert a.context == "staging"
        assert b.context == "prod"
        assert a.namespace == "app"
        assert a.pod == "my-pod"
        assert a.path == "/etc/x"
        # Same scheme, different who — no ambiguity
        assert a.context != b.context

    def test_ref_api_equivalent_to_at_syntax(self):
        auth = load_profile(
            staging_k8s={"scheme": "k8s", "context": "staging"},
        )
        p1 = auth.ref("staging_k8s", "pod:/data")
        p2 = auth.resolve("@staging_k8s:pod:/data")
        assert p1.context == p2.context == "staging"
        assert p1.pod == p2.pod == "pod"

    def test_s3_entry_merges_keys(self):
        auth = load_profile(
            minio={"scheme": "s3", "endpoint_url": "http://localhost:9000",
                   "access_key": "ak", "secret_key": "sk"},
        )
        p = auth.resolve("@minio:my-bucket/path/obj.txt")
        assert isinstance(p, S3Path)
        assert p.bucket == "my-bucket"
        assert p.access_key == "ak"
        assert p.endpoint_url == "http://localhost:9000"

    def test_ssh_host_from_profile(self):
        auth = load_profile(
            bastion={"scheme": "ssh", "host": "bastion.example",
                     "username": "deploy", "key": "~/.ssh/id_rsa"},
        )
        p = auth.ref("bastion", "/var/log")
        assert isinstance(p, SSHPath)
        assert p.key == "~/.ssh/id_rsa"
        assert "bastion" in p.host or p.host.endswith("example")


class TestSources:
    def test_file_yaml(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text(
            "staging_k8s:\n  scheme: k8s\n  context: staging\n"
            "prod_k8s:\n  scheme: k8s\n  context: prod\n"
        )
        auth = Profile().load(FileSource(f))
        assert auth.get("staging_k8s").params["context"] == "staging"
        assert "prod_k8s" in auth

    def test_file_json_profiles_wrapper(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps({
            "profiles": {
                "a": {"scheme": "s3", "access_key": "x"},
            }
        }))
        auth = Profile().load(FileSource(f))
        assert auth.get("a").scheme == "s3"

    def test_env_json_and_flat(self):
        env = {
            "PYEFF_PROFILES": json.dumps({
                "staging_k8s": {"scheme": "k8s", "context": "from-json"},
            }),
            "PYEFF_PROFILE_STAGING_K8S__NAMESPACE": "app",
            "PYEFF_PROFILE_PROD_S3__SCHEME": "s3",
            "PYEFF_PROFILE_PROD_S3__ACCESS_KEY": "ak",
        }
        auth = Profile().load(EnvSource(environ=env))
        assert auth.get("staging_k8s").params["context"] == "from-json"
        assert auth.get("staging_k8s").params["namespace"] == "app"
        assert auth.get("prod_s3").params["access_key"] == "ak"

    def test_cli_source(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text("base:\n  scheme: k8s\n  context: file\n")
        argv = [
            "prog",
            f"--pyeff-profile-file={f}",
            "--pyeff-profile", "base.namespace=cli-ns",
            "--pyeff-profile", "extra.scheme=s3",
            "--pyeff-profile", "extra.access_key=from-cli",
        ]
        auth = Profile().load(CliSource(argv))
        assert auth.get("base").params["context"] == "file"
        assert auth.get("base").params["namespace"] == "cli-ns"
        assert auth.get("extra").params["access_key"] == "from-cli"

    def test_system_source_defaults(self):
        auth = Profile().load(SystemSource())
        assert "default_k8s" in auth
        assert auth.get("default_s3").scheme == "s3"

    def test_compose_override_order(self):
        auth = (
            Profile()
            .load(DictSource({"x": {"scheme": "k8s", "context": "a"}}))
            .load(DictSource({"x": {"scheme": "k8s", "context": "b", "namespace": "n"}}))
        )
        e = auth.get("x")
        assert e.params["context"] == "b"
        assert e.params["namespace"] == "n"

    def test_nacos_with_fetcher_no_hardcode(self):
        def fetcher(data_id, group, conn):
            assert data_id == "pyeff-profiles"
            assert conn["server_addr"] == "nacos:8848"
            return json.dumps({
                "staging_k8s": {"scheme": "k8s", "context": "staging"},
            })

        # conn from "env" — not literals in production app; here simulating loaded conn
        conn = {"server_addr": "nacos:8848", "data_id": "pyeff-profiles"}
        auth = Profile().load(NacosSource(conn=conn, fetcher=fetcher))
        assert auth.get("staging_k8s").params["context"] == "staging"

    def test_nacos_requires_data_id_from_conn(self):
        with pytest.raises(ProfileError, match="data_id"):
            NacosSource(conn={"server_addr": "x"}).load()


class TestActivateAndFlow:
    def test_activate_resolves_at_ref(self):
        auth = load_profile(
            staging_k8s={"scheme": "k8s", "context": "staging"},
        )
        with auth.activate():
            from pyeff.uri import resolve_path
            p = resolve_path("@staging_k8s:pod:/x")
            assert isinstance(p, K8sPath)
            assert p.context == "staging"

    def test_missing_profile_raises(self):
        from pyeff.uri import resolve_path
        with pytest.raises(ProfileError, match="requires a Profile"):
            resolve_path("@nope:pod:/x")

    def test_flow_fanout_uses_auth_refs(self, tmp_path):
        src = tmp_path / "cfg.json"
        src.write_text('{"v": 1}')
        d1 = tmp_path / "a.json"
        d2 = tmp_path / "b.json"
        # Use local scheme named entries to exercise binding without remotes
        auth = load_profile(
            dest_a={"scheme": "local", "path": str(d1)},
            dest_b={"scheme": "local", "path": str(d2)},
        )
        at(str(src), auth=auth).fanout(
            auth.ref("dest_a", str(d1)),
            auth.ref("dest_b", str(d2)),
        )
        assert load_json(d1) == {"v": 1}
        assert load_json(d2) == {"v": 1}

    def test_unknown_entry(self):
        auth = load_profile()
        with pytest.raises(ProfileError, match="Unknown profile entry"):
            auth.ref("missing", "pod:/x")
