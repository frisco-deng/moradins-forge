"""Qualification preflight fails before container provisioning, with exact identity."""
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import moradin_airgap as airgap


def source(tmp_path, origin="https://github.com/frisco-deng/moradins-forge"):
    for cmd in [["git", "init", "-q", "-b", "main"], ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], ["git", "config", "remote.origin.url", origin]]:
        subprocess.run(cmd, cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def assess(root, *, image=None, platform="linux/amd64", local=0, engine="podman", calls=None):
    calls = calls if calls is not None else []
    def engine_check():
        calls.append("engine")
        return engine
    def run(argv):
        calls.append(argv)
        return SimpleNamespace(returncode=local)
    arch = next(v for k, v in airgap.TARGET_IMAGES.items() if k[0] == "arch")
    return airgap.qualification_preflight(root, image or arch, platform, images=airgap.TARGET_IMAGES,
        source_check=airgap.assert_clean_public_forge, engine_check=engine_check, run=run)


@pytest.mark.parametrize("local", [0, 1])
def test_canonical_image_is_returned_without_pulling_or_starting_containers(tmp_path, local):
    calls = []
    result = assess(source(tmp_path), local=local, calls=calls)
    assert result["status"] == "ready" and result["containers_started"] == 0
    assert result["qualification_accepted"] is False
    assert result["target_image"].startswith("docker.io/archlinux/archlinux@sha256:")
    assert result["image_pull_required"] == (local == 1)
    assert calls == ["engine", ["podman", "image", "exists", result["target_image"]]]


def test_alias_origin_rejected_before_engine_probe(tmp_path):
    calls=[]
    source(tmp_path, "git@example.invalid:forge/project")
    with pytest.raises(airgap.AirgapError, match="canonical public Forge HTTPS origin"):
        assess(tmp_path, calls=calls)
    assert calls == []


def test_dirty_source_and_parent_repository_identity_rejected(tmp_path):
    source(tmp_path)
    (tmp_path/"unpublished").write_text("work")
    with pytest.raises(airgap.AirgapError, match="clean public"):
        assess(tmp_path)
    (tmp_path/"unpublished").unlink()
    child=tmp_path/"child"
    child.mkdir()
    with pytest.raises(airgap.AirgapError, match="canonical repository root"):
        assess(child)


@pytest.mark.parametrize("change,expected", [({"image":"archlinux/archlinux:latest"},"exact registered digest"),
    ({"platform":"linux/arm64"},"amd64 only"),({"engine":"docker"},"rootless Podman"),({"local":125},"image-store inspection")])
def test_exact_runtime_and_platform_checks_are_preserved(tmp_path, change, expected):
    with pytest.raises(ValueError, match=expected):
        assess(source(tmp_path), **change)


def test_public_cli_source_failure_creates_no_payload(tmp_path):
    source(tmp_path, "https://example.invalid/project")
    output=tmp_path/"result.json"
    repo=Path(__file__).resolve().parents[2]
    result=subprocess.run(["uv","run","python",str(repo/"scripts/moradin_tooling_suite.py"),"--forge-root",str(tmp_path),
        "airgap-build","--preflight","--target-image","invalid","--target-platform","linux/amd64","--output",str(output)],
        cwd=repo,capture_output=True,text=True)
    assert result.returncode == 2 and "canonical public Forge HTTPS origin" in result.stderr
    assert not output.exists()
