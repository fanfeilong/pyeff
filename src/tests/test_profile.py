"""Tests: map declares API keys and binds source names."""

import json

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


class TestMapIsDeclaration:
    def test_map_required(self):
        with pytest.raises(TypeError):
            Profile().load(DictSource({"a": {"scheme": "k8s"}}))  # type: ignore[call-arg]

    def test_two_k8s_via_map(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text(
            "clusters:\n"
            "  staging:\n    scheme: k8s\n    context: staging\n"
            "  prod:\n    scheme: k8s\n    context: prod\n"
        )
        auth = Profile().load(
            FileSource(f),
            map={
                "staging_k8s": "clusters.staging",
                "prod_k8s": "clusters.prod",
            },
        )
        a = auth.resolve("@staging_k8s:my-pod:/etc/x")
        b = auth.resolve("@prod_k8s:my-pod:/etc/x")
        assert a.context == "staging" and b.context == "prod"
        assert a.pod == "my-pod"

    def test_identity_list_map(self):
        auth = Profile().load(
            DictSource({
                "staging_k8s": {"scheme": "k8s", "context": "staging"},
                "ignored": {"scheme": "s3"},
            }),
            map=["staging_k8s"],
        )
        assert auth.get("staging_k8s").params["context"] == "staging"
        assert "ignored" not in auth
        with pytest.raises(ProfileError, match="not declared"):
            auth.get("ignored")

    def test_env_map_different_source_name(self):
        env = {
            "PYEFF_PROFILE_MINIO__SCHEME": "s3",
            "PYEFF_PROFILE_MINIO__ACCESS_KEY": "ak",
            "PYEFF_PROFILE_MINIO__ENDPOINT_URL": "http://localhost:9000",
        }
        auth = Profile().load(
            EnvSource(environ=env), map={"prod_s3": "minio"}
        )
        p = auth.resolve("@prod_s3:my-bucket/obj.txt")
        assert isinstance(p, S3Path)
        assert p.access_key == "ak"

    def test_undeclared_at_ref_fails(self):
        auth = Profile().load(
            DictSource({"a": {"scheme": "k8s", "context": "x"}}),
            map=["a"],
        )
        with pytest.raises(ProfileError, match="not declared"):
            auth.resolve("@b:pod:/x")

    def test_mapped_but_missing_in_source(self):
        auth = Profile().load(
            DictSource({}),
            map={"staging_k8s": "clusters.staging"},
        )
        with pytest.raises(ProfileError, match="no data"):
            auth.get("staging_k8s")

    def test_second_load_adds_keys(self):
        auth = (
            Profile()
            .load(
                DictSource({"a": {"scheme": "k8s", "context": "1"}}),
                map=["a"],
            )
            .load(
                DictSource({"MINIO": {"scheme": "s3", "access_key": "ak"}}),
                map={"prod_s3": "MINIO"},
            )
        )
        assert set(auth.keys()) == {"a", "prod_s3"}
        assert auth.get("prod_s3").params["access_key"] == "ak"


class TestSources:
    def test_cli_mapped(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text("file_k8s:\n  scheme: k8s\n  context: file\n")
        argv = [
            "prog",
            f"--pyeff-profile-file={f}",
            "--pyeff-profile", "file_k8s.namespace=cli-ns",
        ]
        auth = Profile().load(
            CliSource(argv), map={"staging_k8s": "file_k8s"}
        )
        assert auth.get("staging_k8s").params["namespace"] == "cli-ns"

    def test_system_mapped(self):
        auth = Profile().load(
            SystemSource(), map={"edge_k8s": "default_k8s"}
        )
        # system default_k8s has scheme only
        assert auth.get("edge_k8s").scheme == "k8s"

    def test_nacos_with_map(self):
        def fetcher(data_id, group, conn):
            return json.dumps({
                "k8s": {"staging": {"scheme": "k8s", "context": "staging"}}
            })

        auth = Profile().load(
            NacosSource(
                conn={"server_addr": "nacos:8848", "data_id": "p"},
                fetcher=fetcher,
            ),
            map={"staging_k8s": "k8s.staging"},
        )
        assert auth.get("staging_k8s").params["context"] == "staging"

    def test_ssh_mapped(self):
        auth = Profile().load(
            DictSource({
                "jump": {
                    "scheme": "ssh",
                    "host": "bastion.example",
                    "username": "deploy",
                    "key": "~/.ssh/id_rsa",
                }
            }),
            map={"bastion": "jump"},
        )
        p = auth.ref("bastion", "/var/log")
        assert isinstance(p, SSHPath)
        assert p.key == "~/.ssh/id_rsa"


class TestLoadProfileSugar:
    def test_pairs(self, tmp_path):
        f = tmp_path / "p.yaml"
        f.write_text(
            "clusters:\n  staging:\n    scheme: k8s\n    context: st\n"
        )
        auth = load_profile(
            (FileSource(f), {"staging_k8s": "clusters.staging"}),
            (DictSource({"MINIO": {"scheme": "s3", "access_key": "ak"}}),
             {"prod_s3": "MINIO"}),
        )
        assert auth.get("staging_k8s").params["context"] == "st"
        assert auth.get("prod_s3").params["access_key"] == "ak"


class TestFlow:
    def test_fanout(self, tmp_path):
        src = tmp_path / "cfg.json"
        src.write_text('{"v": 1}')
        d1 = tmp_path / "a.json"
        d2 = tmp_path / "b.json"
        auth = Profile().load(
            DictSource({
                "dest_a": {"scheme": "local", "path": str(d1)},
                "dest_b": {"scheme": "local", "path": str(d2)},
            }),
            map=["dest_a", "dest_b"],
        )
        at(str(src), auth=auth).fanout(
            auth.ref("dest_a", str(d1)),
            auth.ref("dest_b", str(d2)),
        )
        assert load_json(d1) == {"v": 1}
        assert load_json(d2) == {"v": 1}
