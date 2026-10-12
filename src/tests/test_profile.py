"""Tests for declare → map → @key profile binding."""

import json
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
from pyeff import load_json


class TestDeclareThenMap:
    def test_must_declare_before_load(self):
        with pytest.raises(ProfileError, match="declare"):
            Profile().load(DictSource({"a": {"scheme": "k8s"}}))

    def test_two_k8s_via_map_from_nested_file(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text(
            "clusters:\n"
            "  staging:\n    scheme: k8s\n    context: staging\n"
            "  prod:\n    scheme: k8s\n    context: prod\n"
        )
        auth = (
            Profile()
            .declare("staging_k8s", "prod_k8s")
            .load(
                FileSource(f),
                map={
                    "staging_k8s": "clusters.staging",
                    "prod_k8s": "clusters.prod",
                },
            )
        )
        a = auth.resolve("@staging_k8s:my-pod:/etc/x")
        b = auth.resolve("@prod_k8s:my-pod:/etc/x")
        assert isinstance(a, K8sPath) and isinstance(b, K8sPath)
        assert a.context == "staging"
        assert b.context == "prod"
        assert a.pod == "my-pod"

    def test_identity_map_when_omitted(self):
        auth = (
            Profile()
            .declare("staging_k8s")
            .load(DictSource({
                "staging_k8s": {"scheme": "k8s", "context": "staging"},
                "ignored_other": {"scheme": "s3"},  # not declared → ignored
            }))
        )
        assert auth.get("staging_k8s").params["context"] == "staging"
        assert "ignored_other" not in auth
        with pytest.raises(ProfileError, match="not declared"):
            auth.get("ignored_other")

    def test_declare_scheme_default(self):
        auth = (
            Profile()
            .declare(staging_k8s={"scheme": "k8s"})
            .load(DictSource({"staging_k8s": {"context": "staging"}}))
        )
        assert auth.get("staging_k8s").scheme == "k8s"
        assert auth.get("staging_k8s").params["context"] == "staging"

    def test_env_map_different_source_name(self):
        env = {
            "PYEFF_PROFILE_MINIO__SCHEME": "s3",
            "PYEFF_PROFILE_MINIO__ACCESS_KEY": "ak",
            "PYEFF_PROFILE_MINIO__ENDPOINT_URL": "http://localhost:9000",
        }
        auth = (
            Profile()
            .declare("prod_s3")
            .load(EnvSource(environ=env), map={"prod_s3": "minio"})
        )
        p = auth.resolve("@prod_s3:my-bucket/obj.txt")
        assert isinstance(p, S3Path)
        assert p.access_key == "ak"
        assert p.bucket == "my-bucket"

    def test_ref_uses_declared_key_only(self):
        auth = (
            Profile()
            .declare("staging_k8s")
            .load(DictSource({
                "staging_k8s": {"scheme": "k8s", "context": "staging"},
            }))
        )
        p1 = auth.ref("staging_k8s", "pod:/data")
        p2 = auth.resolve("@staging_k8s:pod:/data")
        assert p1.context == p2.context == "staging"

    def test_undeclared_at_ref_fails(self):
        auth = Profile().declare("a").load(
            DictSource({"a": {"scheme": "k8s", "context": "x"}})
        )
        with pytest.raises(ProfileError, match="not declared"):
            auth.resolve("@b:pod:/x")

    def test_declared_but_unfilled_fails(self):
        auth = Profile().declare("staging_k8s")
        with pytest.raises(ProfileError, match="no data"):
            auth.get("staging_k8s")


class TestSourcesWithDeclare:
    def test_file_json_profiles_wrapper(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps({
            "profiles": {
                "a": {"scheme": "s3", "access_key": "x"},
            }
        }))
        auth = Profile().declare("a").load(FileSource(f))
        assert auth.get("a").scheme == "s3"

    def test_cli_mapped(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text("file_k8s:\n  scheme: k8s\n  context: file\n")
        argv = [
            "prog",
            f"--pyeff-profile-file={f}",
            "--pyeff-profile", "file_k8s.namespace=cli-ns",
        ]
        auth = (
            Profile()
            .declare("staging_k8s")
            .load(CliSource(argv), map={"staging_k8s": "file_k8s"})
        )
        assert auth.get("staging_k8s").params["context"] == "file"
        assert auth.get("staging_k8s").params["namespace"] == "cli-ns"

    def test_system_mapped_to_declared(self):
        auth = (
            Profile()
            .declare(edge_k8s={"scheme": "k8s"})
            .load(SystemSource(), map={"edge_k8s": "default_k8s"})
        )
        assert auth.get("edge_k8s").scheme == "k8s"

    def test_compose_override(self):
        auth = (
            Profile()
            .declare("x")
            .load(DictSource({"x": {"scheme": "k8s", "context": "a"}}))
            .load(DictSource({"x": {"scheme": "k8s", "context": "b", "namespace": "n"}}))
        )
        e = auth.get("x")
        assert e.params["context"] == "b"
        assert e.params["namespace"] == "n"

    def test_nacos_with_map(self):
        def fetcher(data_id, group, conn):
            return json.dumps({
                "k8s": {
                    "staging": {"scheme": "k8s", "context": "staging"},
                }
            })

        conn = {"server_addr": "nacos:8848", "data_id": "pyeff-profiles"}
        auth = (
            Profile()
            .declare("staging_k8s")
            .load(
                NacosSource(conn=conn, fetcher=fetcher),
                map={"staging_k8s": "k8s.staging"},
            )
        )
        assert auth.get("staging_k8s").params["context"] == "staging"

    def test_ssh_host_from_mapped_entry(self):
        auth = (
            Profile()
            .declare("bastion")
            .load(DictSource({
                "jump": {
                    "scheme": "ssh",
                    "host": "bastion.example",
                    "username": "deploy",
                    "key": "~/.ssh/id_rsa",
                }
            }), map={"bastion": "jump"})
        )
        p = auth.ref("bastion", "/var/log")
        assert isinstance(p, SSHPath)
        assert p.key == "~/.ssh/id_rsa"


class TestLoadProfileSugar:
    def test_load_profile_with_maps(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text(
            "clusters:\n  staging:\n    scheme: k8s\n    context: st\n"
        )
        auth = load_profile(
            ["staging_k8s", "prod_s3"],
            (FileSource(f), {"staging_k8s": "clusters.staging"}),
            (DictSource({"MINIO": {"scheme": "s3", "access_key": "ak"}}),
             {"prod_s3": "MINIO"}),
        )
        assert auth.get("staging_k8s").params["context"] == "st"
        assert auth.get("prod_s3").params["access_key"] == "ak"


class TestActivateAndFlow:
    def test_activate_resolves_declared_ref(self):
        auth = (
            Profile()
            .declare("staging_k8s")
            .load(DictSource({
                "staging_k8s": {"scheme": "k8s", "context": "staging"},
            }))
        )
        with auth.activate():
            from pyeff.uri import resolve_path
            p = resolve_path("@staging_k8s:pod:/x")
            assert isinstance(p, K8sPath)
            assert p.context == "staging"

    def test_flow_fanout_uses_declared_refs(self, tmp_path):
        src = tmp_path / "cfg.json"
        src.write_text('{"v": 1}')
        d1 = tmp_path / "a.json"
        d2 = tmp_path / "b.json"
        auth = (
            Profile()
            .declare("dest_a", "dest_b")
            .load(DictSource({
                "dest_a": {"scheme": "local", "path": str(d1)},
                "dest_b": {"scheme": "local", "path": str(d2)},
            }))
        )
        at(str(src), auth=auth).fanout(
            auth.ref("dest_a", str(d1)),
            auth.ref("dest_b", str(d2)),
        )
        assert load_json(d1) == {"v": 1}
        assert load_json(d2) == {"v": 1}
