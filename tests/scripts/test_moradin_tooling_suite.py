"""Security and transaction coverage for the interactive Linux tooling suite."""

from __future__ import annotations

import hashlib
import bz2
import io
import json
import os
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import moradin_tooling_suite as suite


APT_FACTS = {
    "system": "linux",
    "arch": "amd64",
    "os_id": "ubuntu",
    "os_version": "24.04",
    "package_manager": "apt",
    "host_fingerprint_sha256": "a" * 64,
}


def completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def ready_python_lock(tool_rows: object, **_kwargs: object) -> dict[str, object]:
    rows = list(tool_rows)  # type: ignore[arg-type]
    direct = sorted(
        row["install_action"]["package"]
        for row in rows
        if row["install_action"]["kind"] == "user-local"
    )
    assets = []
    requirement_lines = []
    for requirement in direct:
        package, version = requirement.split("==", 1)
        digest = hashlib.sha256(requirement.encode()).hexdigest()
        filename = f"{package.replace('-', '_')}-{version}-py3-none-any.whl"
        requirement_lines.append(f"{requirement} --hash=sha256:{digest}")
        assets.append(
            {
                "package": package,
                "version": version,
                "filename": filename,
                "url": f"https://files.pythonhosted.org/packages/{filename}",
                "sha256": digest,
                "size": len(requirement.encode()),
                "source": "pypi",
            }
        )
    requirements = "\n".join(requirement_lines) + ("\n" if requirement_lines else "")
    return {
        "status": "ready",
        "direct_requirements": direct,
        "requirements": requirements,
        "requirements_sha256": hashlib.sha256(requirements.encode()).hexdigest(),
        "assets": assets,
        "blockers": [],
    }


def fixed_resolver(spec: object, **_kwargs: object) -> dict[str, object]:
    tool_id = str(getattr(spec, "id"))
    python_package = str(getattr(spec, "python_package"))
    github_repo = str(getattr(spec, "github_repo"))
    command = str(getattr(spec, "command"))
    digest = hashlib.sha256(tool_id.encode()).hexdigest()
    if python_package:
        return {
            "version": "1.2.3",
            "source": "pypi",
            "source_url": f"https://pypi.org/pypi/{python_package}/json",
            "asset_url": "",
            "sha256": digest,
            "artifact_sha256s": [digest],
            "trust": "pypi-hash-verified",
            "checked_at": "2026-07-31T00:00:00+00:00",
            "cache": "fresh",
        }
    return {
        "version": "v1.2.3",
        "source": "github-release",
        "source_url": f"https://github.com/{github_repo}/releases/tag/v1.2.3",
        "asset_url": f"https://github.com/{github_repo}/releases/download/v1.2.3/{command}",
        "asset_filename": command,
        "asset_size": len(tool_id.encode()),
        "sha256": digest,
        "artifact_sha256s": [digest],
        "trust": "official-release-digest",
        "checked_at": "2026-07-31T00:00:00+00:00",
        "cache": "fresh",
    }


@pytest.fixture
def isolated_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        suite,
        "_command_version",
        lambda spec, **_kwargs: "3.12.8" if spec.id == "python" else "",
    )
    monkeypatch.setattr(
        suite, "_command_is_forge_owned", lambda *_args, **_kwargs: False
    )
    monkeypatch.setattr(
        suite,
        "_package_versions",
        lambda package, _manager, **_kwargs: ("", "1.0.0") if package else ("", ""),
    )
    monkeypatch.setattr(suite, "_package_sizes", lambda *_args, **_kwargs: (1024, 2048))
    monkeypatch.setattr(suite, "build_python_tool_lock", ready_python_lock)


def test_catalog_is_external_complete_and_profiled() -> None:
    tool_ids = {spec.id for spec in suite.TOOL_CATALOG}
    assert {
        "git",
        "uv",
        "semgrep",
        "syft",
        "podman",
        "kubectl",
        "node",
        "cad",
    }.issubset(tool_ids)
    assert len(tool_ids) == len(suite.TOOL_CATALOG)
    assert all(spec.category and spec.reason for spec in suite.TOOL_CATALOG)
    assert (
        next(spec for spec in suite.TOOL_CATALOG if spec.id == "cad").manual_only
        is True
    )
    verification = {
        spec.id: suite._suite_verification_argv(spec) for spec in suite.TOOL_CATALOG
    }
    assert verification["unzip"] == ["unzip", "-v"]
    assert verification["rootless_uidmap"] == [
        "/usr/bin/test",
        "-x",
        "/usr/bin/newuidmap",
    ]
    assert verification["xvfb"] == ["Xvfb", "-help"]
    assert verification["expect"] == ["expect", "-v"]
    python = next(spec for spec in suite.TOOL_CATALOG if spec.id == "python")
    assert suite._suite_verification_options(python) == [
        ["python3.14", "--version"],
        ["python3.13", "--version"],
        ["python3.12", "--version"],
        ["python3", "--version"],
    ]


def test_catalog_owned_path_probe_does_not_claim_a_missing_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = next(item for item in suite.TOOL_CATALOG if item.id == "rootless_uidmap")
    monkeypatch.setattr(
        suite, "_trusted_detected_command", lambda _command: Path("/usr/bin/test")
    )
    monkeypatch.setattr(suite.shutil, "which", lambda _command: "/usr/bin/test")

    assert (
        suite._command_version(spec, runner=lambda *_args, **_kwargs: completed(1))
        == ""
    )


def test_practical_plan_is_digest_host_and_installer_bound(
    tmp_path: Path,
    isolated_planner: None,
) -> None:
    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="practical",
        facts=APT_FACTS,
        resolver=fixed_resolver,
    )

    assert plan["status"] == "ready"
    assert plan["plan_sha256"] == suite.plan_digest(plan)
    assert plan["platform"]["host_fingerprint_sha256"] == "a" * 64
    assert plan["catalog_sha256"] == suite.sha256_file(suite.CATALOG_PATH)
    assert plan["installer_files"] == suite.installer_file_records(suite.REPO_ROOT)
    assert {"git", "uv", "semgrep", "trivy", "syft"}.issubset(plan["selected_tools"])
    assert "podman" not in plan["selected_tools"]
    plan["profile"] = "tampered"
    assert plan["plan_sha256"] != suite.plan_digest(plan)


def test_plan_stages_the_exact_installer_runner(
    tmp_path: Path,
    isolated_planner: None,
) -> None:
    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="custom",
        include_tools=["git"],
        facts=APT_FACTS,
        resolver=fixed_resolver,
    )
    stage = tmp_path / "stage"
    manifest = suite.stage_suite_assets(plan, output=stage)

    runner_entries = [
        item for item in manifest["included"] if item["kind"] == "root-runner"
    ]
    assert len(runner_entries) == len(suite.INSTALLER_FILES)
    assert {item["path"].removeprefix("root-runner/") for item in runner_entries} == {
        path.as_posix() for path in suite.INSTALLER_FILES
    }
    suite.validate_staged_assets(stage, plan)


def test_untrusted_uv_is_not_executed_or_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "uv"
    executable.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    executable.chmod(0o755)
    spec = next(item for item in suite.TOOL_CATALOG if item.id == "uv")
    monkeypatch.setattr(suite.shutil, "which", lambda command: str(executable))
    monkeypatch.setattr(suite, "_command_is_forge_owned", lambda _spec: False)

    def forbidden_runner(_argv: list[str], **_kwargs: object) -> SimpleNamespace:
        raise AssertionError("an untrusted detected executable must not run")

    row = suite._tool_row(
        spec,
        facts=APT_FACTS,
        cache_path=tmp_path / "cache.json",
        refresh_versions=False,
        runner=forbidden_runner,
        resolver=fixed_resolver,
        epel_available=True,
    )

    assert row["installed_version"] == "present-unverified"
    assert row["status"] == "upgrade"
    assert row["install_action"]["kind"] == "forge-user"


def test_bootstrap_uv_path_is_exact_and_integrity_checked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    data = home / "data"
    uv = data / "moradins-forge/bootstrap/uv" / suite.BOOTSTRAP_UV_VERSION / "uv"
    uv.parent.mkdir(parents=True)
    uv.write_bytes(b"trusted uv")
    uv.chmod(0o700)
    digest = hashlib.sha256(uv.read_bytes()).hexdigest()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("MORADIN_FORGE_BOOTSTRAP_UV", str(uv))
    monkeypatch.setattr(suite, "normalized_arch", lambda: "amd64")
    monkeypatch.setitem(suite.BOOTSTRAP_UV_BINARY_SHA256, "amd64", digest)

    assert suite._trusted_bootstrap_uv_path(required=True) == uv.resolve()
    uv.write_bytes(b"tampered")
    with pytest.raises(suite.ToolingSuiteError, match="integrity"):
        suite._trusted_bootstrap_uv_path(required=True)


def test_rehashed_plan_cannot_change_catalog_owned_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_planner: None,
) -> None:
    monkeypatch.setattr(suite, "host_facts", lambda: APT_FACTS)
    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="custom",
        include_tools=["git"],
        facts=APT_FACTS,
        resolver=fixed_resolver,
    )
    row = plan["tools"][0]
    row["install_action"]["package"] = "curl"
    row["resolved"]["package"] = "curl"
    plan["root_actions"] = [row["install_action"]]
    plan["plan_sha256"] = suite.plan_digest(plan)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(suite.ToolingSuiteError, match="catalog-owned"):
        suite.load_suite_plan(
            path,
            approved_sha256=plan["plan_sha256"],
            forge_root=suite.REPO_ROOT,
        )


def test_rehashed_plan_cannot_redirect_catalog_owned_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_planner: None,
) -> None:
    monkeypatch.setattr(suite, "host_facts", lambda: APT_FACTS)
    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="custom",
        include_tools=["uv"],
        facts=APT_FACTS,
        resolver=fixed_resolver,
    )
    plan["tools"][0]["resolved"]["asset_url"] = (
        "https://github.com/attacker/tool/releases/download/v1.2.3/uv"
    )
    plan["plan_sha256"] = suite.plan_digest(plan)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(suite.ToolingSuiteError, match="catalog-owned"):
        suite.load_suite_plan(
            path,
            approved_sha256=plan["plan_sha256"],
            forge_root=suite.REPO_ROOT,
        )


def test_arm64_plan_uses_arm64_resolution(
    isolated_planner: None,
) -> None:
    observed: list[str] = []

    def resolver(spec: object, **kwargs: object) -> dict[str, object]:
        observed.append(str(kwargs["arch"]))
        return fixed_resolver(spec, **kwargs)

    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="custom",
        include_tools=["uv"],
        facts={**APT_FACTS, "arch": "arm64"},
        resolver=resolver,
    )
    assert plan["platform"]["arch"] == "arm64"
    assert observed == ["arm64"]


def test_extended_requires_engine_choice_and_preserves_existing_engine(
    monkeypatch: pytest.MonkeyPatch,
    isolated_planner: None,
) -> None:
    monkeypatch.setattr(suite, "command_present", lambda _command: False)
    with pytest.raises(suite.ToolingSuiteError, match="container-engine"):
        suite.build_suite_plan(
            forge_root=suite.REPO_ROOT,
            profile="extended",
            facts=APT_FACTS,
            resolver=fixed_resolver,
        )

    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="extended",
        container_engine="podman",
        facts=APT_FACTS,
        resolver=fixed_resolver,
    )
    assert "podman" in plan["selected_tools"]
    assert "docker" not in plan["selected_tools"]
    assert {
        "rootless_uidmap",
        "rootless_network",
        "rootless_storage",
    }.issubset(plan["selected_tools"])

    monkeypatch.setattr(suite, "command_present", lambda command: command == "docker")
    monkeypatch.setattr(
        suite,
        "_command_version",
        lambda spec, **_kwargs: "26.0.0" if spec.id == "docker" else "",
    )
    preserved = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="extended",
        facts=APT_FACTS,
        resolver=fixed_resolver,
    )
    docker = next(row for row in preserved["tools"] if row["id"] == "docker")
    assert docker["status"] == "preserved"
    assert docker["install_action"]["kind"] == "protected-existing"
    assert "rootless_uidmap" not in preserved["selected_tools"]


def test_epel_requires_separate_approval_then_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    isolated_planner: None,
) -> None:
    facts = {**APT_FACTS, "os_id": "rocky", "package_manager": "dnf"}
    monkeypatch.setattr(suite, "_epel_enabled", lambda **_kwargs: False)

    unapproved = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="practical",
        facts=facts,
        resolver=fixed_resolver,
    )
    assert unapproved["status"] == "needs-repository-approval"
    assert unapproved["repository_bootstrap"] is None

    approved = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="practical",
        approved_repositories=["epel"],
        facts=facts,
        resolver=fixed_resolver,
    )
    assert approved["status"] == "repository-bootstrap"
    assert approved["repository_bootstrap"]["package"] == "epel-release"
    assert approved["repository_bootstrap"]["requires_replan"] is True


def test_epel_installed_but_disabled_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    isolated_planner: None,
) -> None:
    facts = {**APT_FACTS, "os_id": "rocky", "package_manager": "dnf"}
    monkeypatch.setattr(suite, "_epel_enabled", lambda **_kwargs: False)
    original = suite._package_versions

    def versions(package: str, manager: str, **kwargs: object) -> tuple[str, str]:
        if package == "epel-release":
            return "9.6", "9.6"
        return original(package, manager, **kwargs)

    monkeypatch.setattr(suite, "_package_versions", versions)
    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="practical",
        approved_repositories=["epel"],
        facts=facts,
        resolver=fixed_resolver,
    )

    assert plan["status"] == "blocked"
    assert plan["repository_bootstrap"] is None
    assert any("installed but EPEL is not enabled" in item for item in plan["blockers"])


def test_arch_refuses_partial_package_transaction(isolated_planner: None) -> None:
    facts = {**APT_FACTS, "os_id": "arch", "package_manager": "pacman"}
    blocked = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="custom",
        include_tools=["git"],
        facts=facts,
        resolver=fixed_resolver,
    )
    assert blocked["status"] == "needs-arch-upgrade-approval"

    approved = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="custom",
        include_tools=["git"],
        approve_arch_system_upgrade=True,
        facts=facts,
        resolver=fixed_resolver,
    )
    assert approved["status"] == "ready"
    action = approved["root_actions"][0]
    assert suite._package_install_argv(
        "pacman", action["package"], action["version"], arch_sync=True
    )[:2] == ["pacman", "-Syu"]


@pytest.mark.parametrize(
    ("manager", "responses", "expected"),
    [
        (
            "apt",
            {
                "dpkg-query": completed(stdout="ii \t1.0"),
                "apt-cache": completed(stdout="Candidate: 1.1\n"),
            },
            ("1.0", "1.1"),
        ),
        (
            "dnf",
            {"rpm": completed(stdout="1.0"), "dnf": completed(stdout="1.1\n")},
            ("1.0", "1.1"),
        ),
        (
            "pacman",
            {
                "pacman-Q": completed(stdout="git 1.0\n"),
                "pacman-Si": completed(stdout="Version : 1.1\n"),
            },
            ("1.0", "1.1"),
        ),
    ],
)
def test_package_version_adapters(
    manager: str,
    responses: dict[str, SimpleNamespace],
    expected: tuple[str, str],
) -> None:
    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        key = argv[0]
        if argv[0] == "pacman":
            key = "pacman-Q" if argv[1] == "-Q" else "pacman-Si"
        return responses[key]

    assert suite._package_versions("git", manager, runner=runner) == expected


def minimal_asset_plan(
    payload: bytes, *, kind: str = "forge-user"
) -> dict[str, object]:
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "plan_sha256": "b" * 64,
        "tools": [
            {
                "id": "uv",
                "resolved": {
                    "asset_url": "https://github.com/example/tool/releases/download/v1/uv",
                    "asset_filename": "uv",
                    "sha256": digest,
                    "asset_size": len(payload),
                },
                "install_action": {"kind": kind},
            }
        ],
        "python_tool_lock": {"status": "not-required", "assets": []},
    }


def test_asset_stage_is_hash_bound_and_rejects_tampering(tmp_path: Path) -> None:
    payload = b"#!/bin/sh\nexit 0\n"
    plan = minimal_asset_plan(payload)

    def downloader(_url: str, destination: Path) -> None:
        destination.write_bytes(payload)

    stage = tmp_path / "stage"
    suite.stage_suite_assets(plan, output=stage, downloader=downloader)
    paths = suite.validate_staged_assets(stage, plan)
    assert paths["uv"].read_bytes() == payload

    paths["uv"].write_bytes(b"tampered")
    with pytest.raises(suite.ToolingSuiteError, match="integrity"):
        suite.validate_staged_assets(stage, plan)


def test_rehashed_stage_manifest_cannot_replace_approved_asset(tmp_path: Path) -> None:
    payload = b"#!/bin/sh\nexit 0\n"
    plan = minimal_asset_plan(payload)

    def downloader(_url: str, destination: Path) -> None:
        destination.write_bytes(payload)

    stage = tmp_path / "stage"
    suite.stage_suite_assets(plan, output=stage, downloader=downloader)
    manifest_path = stage / "stage-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset = stage / manifest["included"][0]["path"]
    replacement = b"#!/bin/sh\nexit 9\n"
    asset.write_bytes(replacement)
    manifest["included"][0]["sha256"] = hashlib.sha256(replacement).hexdigest()
    manifest["included"][0]["size"] = len(replacement)
    manifest["manifest_sha256"] = suite._record_digest(manifest, "manifest_sha256")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(suite.ToolingSuiteError, match="approved plan"):
        suite.validate_staged_assets(stage, plan)


def test_archive_extraction_rejects_links_and_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as handle:
        member = tarfile.TarInfo("../uv")
        content = b"unsafe"
        member.size = len(content)
        handle.addfile(member, io.BytesIO(content))

    with pytest.raises(suite.ToolingSuiteError, match="unsafe path"):
        suite.materialize_verified_binary(archive, "uv", tmp_path / "bin/uv")


def test_debian_asset_extracts_only_the_expected_executable(tmp_path: Path) -> None:
    data_buffer = io.BytesIO()
    with tarfile.open(fileobj=data_buffer, mode="w:gz") as archive:
        member = tarfile.TarInfo("usr/bin/tool")
        content = b"#!/bin/sh\nexit 0\n"
        member.size = len(content)
        member.mode = 0o755
        archive.addfile(member, io.BytesIO(content))

    def ar_member(name: str, payload: bytes) -> bytes:
        header = (
            f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(payload):<10}`\n"
        ).encode("ascii")
        assert len(header) == 60
        return header + payload + (b"\n" if len(payload) % 2 else b"")

    package = tmp_path / "tool.deb"
    package.write_bytes(
        b"!<arch>\n"
        + ar_member("debian-binary", b"2.0\n")
        + ar_member("data.tar.gz", data_buffer.getvalue())
    )
    destination = tmp_path / "bin/tool"
    suite.materialize_verified_binary(package, "tool", destination)
    assert destination.read_bytes() == content
    assert destination.stat().st_mode & 0o777 == 0o755


def test_single_file_compressed_release_asset_is_materialized(tmp_path: Path) -> None:
    content = b"#!/bin/sh\nexit 0\n"
    asset = tmp_path / "tool_linux_amd64.bz2"
    asset.write_bytes(bz2.compress(content))
    destination = tmp_path / "bin/tool"

    suite.materialize_verified_binary(asset, "tool", destination)

    assert destination.read_bytes() == content


def test_user_asset_switch_and_rollback_are_atomic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local/state"))
    payload = b"#!/bin/sh\nexit 0\n"
    plan = minimal_asset_plan(payload)

    def downloader(_url: str, destination: Path) -> None:
        destination.write_bytes(payload)

    stage = tmp_path / "stage"
    suite.stage_suite_assets(plan, output=stage, downloader=downloader)
    operations, _generation = suite._apply_user_actions(plan, stage)
    shim = home / ".local/bin/uv"
    assert shim.is_symlink()
    assert Path(os.readlink(shim)).read_bytes() == payload
    with pytest.raises(suite.ToolingSuiteError, match="already has state"):
        suite._apply_user_actions(plan, stage)

    result = suite._rollback_user_operations(
        operations,
        owned_root=home / ".local/share/moradins-forge/tools",
    )
    assert result == [{"tool_id": "uv", "status": "removed"}]
    assert not shim.exists()


def test_python_tool_install_uses_the_frozen_managed_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data/moradins-forge"
    state_root = tmp_path / "state/moradins-forge"
    bin_root = tmp_path / "bin"
    stage_root = tmp_path / "stage"
    (stage_root / "wheels").mkdir(parents=True)
    (stage_root / "constraints.txt").write_text("semgrep==1.2.3\n", encoding="utf-8")
    observed: dict[str, object] = {}
    monkeypatch.setattr(suite, "_user_roots", lambda: (data_root, state_root, bin_root))
    monkeypatch.setattr(suite, "validate_staged_assets", lambda *_args: {})
    monkeypatch.setattr(suite, "_trusted_user_uv", lambda *_args: Path("/trusted/uv"))

    def runner(argv: list[str], **kwargs: object) -> SimpleNamespace:
        observed["argv"] = argv
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        observed["env"] = environment
        tool_bin = Path(str(environment["UV_TOOL_BIN_DIR"]))
        tool_bin.mkdir(parents=True, exist_ok=True)
        (tool_bin / "semgrep").write_text("#!/bin/sh\n", encoding="utf-8")
        return completed()

    plan = {
        "plan_sha256": "a" * 64,
        "python_tool_lock": {"status": "ready"},
        "tools": [
            {
                "id": "semgrep",
                "install_action": {
                    "kind": "user-local",
                    "package": "semgrep==1.2.3",
                },
            }
        ],
    }
    suite._apply_user_actions(plan, stage_root, runner=runner)

    argv = observed["argv"]
    assert isinstance(argv, list)
    assert argv[argv.index("--python") + 1] == "3.12"
    assert "--managed-python" in argv
    assert "--no-python-downloads" in argv
    environment = observed["env"]
    assert isinstance(environment, dict)
    assert environment["UV_PYTHON_INSTALL_DIR"] == str(data_root / "bootstrap/python")


def test_root_global_install_receipt_and_rollback(tmp_path: Path) -> None:
    payload = b"#!/bin/sh\nexit 0\n"
    plan = minimal_asset_plan(payload, kind="forge-global")
    plan.update(
        {
            "status": "ready",
            "platform": {"package_manager": "apt"},
            "root_actions": [
                {
                    "kind": "forge-global",
                    "tool_id": "uv",
                    "version": "v1",
                }
            ],
        }
    )

    def downloader(_url: str, destination: Path) -> None:
        destination.write_bytes(payload)

    stage = tmp_path / "stage"
    suite.stage_suite_assets(plan, output=stage, downloader=downloader)

    def runner(_argv: list[str], **_kwargs: object) -> SimpleNamespace:
        return completed()

    receipt = suite.apply_root_transaction(
        plan,
        stage_root=stage,
        root_prefix=tmp_path / "root",
        runner=runner,
        require_root=False,
    )
    shim = tmp_path / "root/usr/local/bin/uv"
    assert shim.is_symlink()
    assert (tmp_path / "root/opt/moradins-forge").stat().st_mode & 0o777 == 0o755
    assert (tmp_path / "root/usr/local/bin").stat().st_mode & 0o777 == 0o755
    assert Path(os.readlink(shim)).parent.stat().st_mode & 0o777 == 0o755
    assert receipt["receipt_sha256"] == suite._record_digest(receipt, "receipt_sha256")
    assert receipt["installer_manifest_sha256"] == suite.installer_manifest_sha256()

    rollback = suite.rollback_root_receipt(
        Path(receipt["receipt"]),
        approved_sha256=receipt["receipt_sha256"],
        runner=runner,
        require_root=False,
        root_prefix=tmp_path / "root",
    )
    assert rollback["status"] == "pass"
    assert not shim.exists()


def test_rehashed_root_receipt_cannot_target_arbitrary_path(tmp_path: Path) -> None:
    payload = b"#!/bin/sh\nexit 0\n"
    plan = minimal_asset_plan(payload, kind="forge-global")
    plan.update(
        {
            "status": "ready",
            "platform": {"package_manager": "apt"},
            "root_actions": [
                {"kind": "forge-global", "tool_id": "uv", "version": "v1"}
            ],
        }
    )
    stage = tmp_path / "stage"
    suite.stage_suite_assets(
        plan,
        output=stage,
        downloader=lambda _url, destination: destination.write_bytes(payload),
    )
    receipt = suite.apply_root_transaction(
        plan,
        stage_root=stage,
        root_prefix=tmp_path / "root",
        runner=lambda _argv, **_kwargs: completed(),
        require_root=False,
    )
    receipt_path = Path(receipt["receipt"])
    stored = json.loads(receipt_path.read_text(encoding="utf-8"))
    stored["operations"][0]["shim"] = (tmp_path / "root/etc/unsafe").as_posix()
    stored["receipt_sha256"] = suite._record_digest(stored, "receipt_sha256")
    receipt_path.write_text(json.dumps(stored), encoding="utf-8")

    with pytest.raises(suite.ToolingSuiteError, match="unsafe global path"):
        suite.rollback_root_receipt(
            receipt_path,
            approved_sha256=stored["receipt_sha256"],
            require_root=False,
            root_prefix=tmp_path / "root",
        )


def test_os_upgrade_is_skipped_without_rollback_closure(tmp_path: Path) -> None:
    plan = {
        "plan_sha256": "c" * 64,
        "status": "ready",
        "platform": {"package_manager": "apt"},
        "tools": [
            {
                "id": "git",
                "verification_command": ["git", "--version"],
                "install_action": {
                    "kind": "system-package",
                    "tool_id": "git",
                    "package": "git",
                    "version": "2.0",
                    "previous_version": "1.0",
                },
            }
        ],
        "root_actions": [
            {
                "kind": "system-package",
                "tool_id": "git",
                "package": "git",
                "version": "2.0",
                "previous_version": "1.0",
            }
        ],
        "repository_bootstrap": None,
        "approve_arch_system_upgrade": False,
        "python_tool_lock": {"status": "not-required", "assets": []},
    }
    stage = tmp_path / "stage"
    suite.stage_suite_assets(plan, output=stage, downloader=lambda _url, _path: None)
    calls: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        if argv[0] == "dpkg-query":
            return completed(stdout="ii \t1.0")
        if argv[:2] == ["apt-cache", "policy"]:
            return completed(stdout="Candidate: 2.0\n")
        if argv[:2] == ["apt", "download"]:
            return completed(returncode=1)
        return completed()

    receipt = suite.apply_root_transaction(
        plan,
        stage_root=stage,
        root_prefix=tmp_path / "root",
        runner=runner,
        require_root=False,
    )
    assert receipt["operations"] == []
    assert receipt["skipped"] == [
        {
            "tool_id": "git",
            "reason": "existing package retained because rollback closure is unavailable",
        }
    ]
    assert not any(argv[:2] == ["apt-get", "install"] for argv in calls)


def test_new_signed_package_is_verified_receipted_and_removed_on_rollback(
    tmp_path: Path,
) -> None:
    plan = {
        "plan_sha256": "e" * 64,
        "status": "ready",
        "platform": {"package_manager": "apt"},
        "tools": [
            {
                "id": "git",
                "verification_command": ["git", "--version"],
                "install_action": {
                    "kind": "system-package",
                    "tool_id": "git",
                    "package": "git",
                    "version": "2.0",
                    "previous_version": "",
                },
            }
        ],
        "root_actions": [
            {
                "kind": "system-package",
                "tool_id": "git",
                "package": "git",
                "version": "2.0",
                "previous_version": "",
            }
        ],
        "repository_bootstrap": None,
        "approve_arch_system_upgrade": False,
        "python_tool_lock": {"status": "not-required", "assets": []},
    }
    stage = tmp_path / "stage"
    suite.stage_suite_assets(plan, output=stage, downloader=lambda _url, _path: None)
    state = {"installed": False}
    calls: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        if argv[0] == "dpkg-query":
            return (
                completed(stdout="ii \t2.0")
                if state["installed"]
                else completed(returncode=1)
            )
        if argv[:2] == ["apt-cache", "policy"]:
            return completed(stdout="Candidate: 2.0\n")
        if argv[:2] == ["apt-get", "install"]:
            state["installed"] = True
        elif argv[:2] == ["dpkg", "--remove"]:
            state["installed"] = False
        return completed()

    receipt = suite.apply_root_transaction(
        plan,
        stage_root=stage,
        root_prefix=tmp_path / "root",
        runner=runner,
        require_root=False,
    )
    assert state["installed"] is True
    assert receipt["operations"][0]["package"] == "git"
    result = suite.rollback_root_receipt(
        Path(receipt["receipt"]),
        approved_sha256=receipt["receipt_sha256"],
        runner=runner,
        require_root=False,
        root_prefix=tmp_path / "root",
    )
    assert result["status"] == "pass"
    assert result["root"][0]["status"] == (
        "removed-direct-package-dependencies-retained"
    )
    assert state["installed"] is False


@pytest.mark.parametrize(
    ("manager", "expected"),
    [
        ("apt", ["dpkg", "--remove", "--", "git"]),
        ("dnf", ["rpm", "-e", "git"]),
        ("pacman", ["pacman", "-R", "--noconfirm", "--", "git"]),
    ],
)
def test_new_package_rollback_never_requests_dependency_autoremove(
    manager: str,
    expected: list[str],
) -> None:
    assert (
        suite._rollback_package_argv(
            {
                "manager": manager,
                "package": "git",
                "previous_version": "",
                "rollback_asset": "",
            }
        )
        == expected
    )


def test_new_podman_is_verified_as_the_target_user_rootless() -> None:
    plan = {
        "platform": {"package_manager": "apt"},
        "tools": [
            {
                "id": "podman",
                "verification_command": ["podman", "--version"],
                "install_action": {"kind": "system-package", "package": "podman"},
            }
        ],
    }

    def passing_runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        return completed(stdout="true\n" if argv[:2] == ["podman", "info"] else "")

    suite._verify_root_actions_as_user(plan, runner=passing_runner)

    with pytest.raises(suite.ToolingSuiteError, match="podman"):
        suite._verify_root_actions_as_user(
            plan,
            runner=lambda _argv, **_kwargs: completed(stdout="false\n"),
        )


def test_portable_plan_removes_machine_and_workspace_values() -> None:
    plan = {
        "plan_sha256": "d" * 64,
        "approved_workspaces": ["/home/example/project"],
        "repositories": [{"path": "/home/example/project/repo"}],
        "platform": {"host_fingerprint_sha256": "e" * 64},
        "target_uid": 1000,
    }
    portable = suite._portable_suite_plan(plan)
    rendered = json.dumps(portable)
    assert "/home/example" not in rendered
    assert "e" * 64 not in rendered
    assert portable["source_plan_sha256"] == "d" * 64


def test_noop_apply_receipt_is_sanitized_verifiable_and_rollbackable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_planner: None,
) -> None:
    home = tmp_path / "home-private"
    workspace = tmp_path / "workspace-private"
    workspace.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / "cache"))
    monkeypatch.setattr(suite, "host_facts", lambda: APT_FACTS)
    monkeypatch.setattr(
        suite,
        "_package_versions",
        lambda package, _manager, **_kwargs: (
            ("1.0.0", "1.0.0") if package == "git" else ("", "")
        ),
    )
    plan = suite.build_suite_plan(
        forge_root=suite.REPO_ROOT,
        profile="custom",
        include_tools=["git"],
        workspaces=[workspace],
        facts=APT_FACTS,
        resolver=fixed_resolver,
    )
    plan_path = tmp_path / "plan.json"
    suite.write_suite_plan(plan, plan_path)

    receipt = suite.apply_suite_plan(
        plan_path,
        approved_sha256=plan["plan_sha256"],
        forge_root=suite.REPO_ROOT,
    )
    receipt_path = Path(receipt["receipt"])
    receipt_id = receipt_path.parent.name
    stored_text = receipt_path.read_text(encoding="utf-8")
    portable_text = (receipt_path.parent / "approved-plan.json").read_text(
        encoding="utf-8"
    )
    assert home.as_posix() not in stored_text + portable_text
    assert workspace.as_posix() not in stored_text + portable_text
    assert APT_FACTS["host_fingerprint_sha256"] not in portable_text
    assert suite.verify_suite_receipt(receipt_id)["status"] == "pass"
    assert (
        suite.rollback_suite_receipt(
            receipt_id,
            approved_sha256=receipt["receipt_sha256"],
            forge_root=suite.REPO_ROOT,
        )["status"]
        == "pass"
    )


def test_interactive_refuses_missing_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(suite.sys.stdin, "isatty", lambda: False)
    with pytest.raises(suite.ToolingSuiteError, match="requires a TTY"):
        suite.interactive(forge_root=suite.REPO_ROOT)


def test_interactive_eof_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError())
    )
    with pytest.raises(suite.ToolingSuiteError, match="ended before approval"):
        suite._prompt("choice: ")


def test_python_312_bootstrap_is_separate_user_owned_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uv = tmp_path / "uv"
    calls: list[list[str]] = []
    monkeypatch.setattr(suite, "_trusted_bootstrap_uv_path", lambda **_kwargs: uv)
    monkeypatch.setattr(suite, "_confirm", lambda _prompt: True)
    monkeypatch.setattr(suite, "_command_version", lambda _spec, **_kwargs: "3.12.12")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        return completed()

    suite._bootstrap_python_312(runner=runner)

    assert calls == [
        [
            str(uv),
            "python",
            "install",
            "--upgrade",
            "--managed-python",
            "--no-config",
            "--install-dir",
            str(tmp_path / "data/moradins-forge/bootstrap/python"),
            "3.12",
        ]
    ]


def test_sudo_phase_launches_only_a_sealed_root_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []
    digest = "a" * 64
    monkeypatch.setattr(suite, "_trusted_root_python", lambda: Path("/usr/bin/python3"))
    monkeypatch.setattr(suite, "_trusted_sudo", lambda: Path("/usr/bin/sudo"))

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        observed.extend(argv)
        return completed(stdout=json.dumps({"version": suite.ROOT_RECEIPT_VERSION}))

    monkeypatch.setattr(suite, "_run", runner)
    suite._invoke_root_apply(
        tmp_path / "plan.json",
        tmp_path / "stage",
        approved_sha256="b" * 64,
        installer_manifest_digest=digest,
    )

    python_index = observed.index("/usr/bin/python3")
    assert observed[python_index + 1 : python_index + 3] == ["-I", "-c"]
    assert suite.ROOT_RUNNER_BOOTSTRAP in observed
    assert (tmp_path / "stage/root-runner").resolve().as_posix() in observed
    assert (
        suite.REPO_ROOT / "scripts/moradin_tooling_suite.py"
    ).as_posix() not in observed
    assert f"/var/lib/moradins-forge/runners/{digest}" in observed


def test_interactive_install_all_and_custom_category_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["bad", "1", "1"])
    monkeypatch.setattr(suite, "_prompt", lambda _message: next(answers))
    assert suite._interactive_profile() == ("practical", [])

    answers = iter(["1", "2"])
    monkeypatch.setattr(suite, "_prompt", lambda _message: next(answers))
    assert suite._interactive_profile() == ("extended", [])

    categories = sorted({spec.category for spec in suite.TOOL_CATALOG})
    bootstrap_index = categories.index("bootstrap-core") + 1
    answers = iter(["2", str(bootstrap_index), "git"])
    monkeypatch.setattr(suite, "_prompt", lambda _message: next(answers))
    assert suite._interactive_profile() == ("custom", ["git"])

    answers = iter(["2", "all", "all"])
    monkeypatch.setattr(suite, "_prompt", lambda _message: next(answers))
    profile, selected = suite._interactive_profile()
    assert profile == "custom"
    assert set(selected) == {spec.id for spec in suite.TOOL_CATALOG}


def test_interactive_verify_cancelled_rollback_and_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["3", "latest", "4", "latest", "n", "5"])
    monkeypatch.setattr(suite, "_prompt", lambda _message: next(answers))
    monkeypatch.setattr(
        suite,
        "verify_suite_receipt",
        lambda _receipt: {"version": "verify", "status": "pass", "checks": []},
    )
    monkeypatch.setattr(
        suite,
        "_load_user_receipt",
        lambda _receipt: (Path("receipt.json"), {"receipt_sha256": "a" * 64}),
    )
    with pytest.raises(SystemExit) as exit_info:
        suite._interactive_profile()
    assert exit_info.value.code == 0


def test_interactive_approved_rollback_uses_the_exact_receipt_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["4", "latest", "y", "5"])
    observed: dict[str, str] = {}
    monkeypatch.setattr(suite, "_prompt", lambda _message: next(answers))
    monkeypatch.setattr(
        suite,
        "_load_user_receipt",
        lambda _receipt: (Path("receipt.json"), {"receipt_sha256": "a" * 64}),
    )

    def rollback(
        receipt: str,
        *,
        approved_sha256: str,
        forge_root: Path,
    ) -> dict[str, object]:
        observed.update(
            {
                "receipt": receipt,
                "approved_sha256": approved_sha256,
                "forge_root": forge_root.as_posix(),
            }
        )
        return {"version": "rollback", "status": "pass"}

    monkeypatch.setattr(suite, "rollback_suite_receipt", rollback)
    with pytest.raises(SystemExit) as exit_info:
        suite._interactive_profile()

    assert exit_info.value.code == 0
    assert observed == {
        "receipt": "latest",
        "approved_sha256": "a" * 64,
        "forge_root": suite.REPO_ROOT.as_posix(),
    }
