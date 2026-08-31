from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from scripts import moradin_tooling_suite as linux_suite
from scripts import moradin_tooling_suite_native as native


def fixed_homebrew_resolution(spec: object, **_kwargs: object) -> dict[str, object]:
    tool_id = str(getattr(spec, "id"))
    return {
        "version": "1.2.3",
        "source": "homebrew",
        "source_url": "https://formulae.brew.sh/api/formula/git.json",
        "asset_url": "",
        "asset_filename": "",
        "asset_size": 0,
        "sha256": hashlib.sha256(tool_id.encode()).hexdigest(),
        "artifact_sha256s": [],
        "trust": "signed-package-manager",
        "checked_at": "2026-08-31T00:00:00+00:00",
        "cache": "fresh",
    }


def test_catalog_v2_contains_full_portable_extended_baseline() -> None:
    catalog = {spec.id: spec for spec in native.TOOL_CATALOG}

    assert {
        "openssl",
        "zip",
        "bzip2",
        "zstd",
        "ruff",
        "pyright",
        "opentofu",
        "tflint",
        "terraform_docs",
        "ansible",
        "argocd",
        "rclone",
        "velero",
        "skopeo",
        "crane",
        "clamav",
        "yara",
        "modelscan",
        "cargo_audit",
        "cargo_deny",
    }.issubset(catalog)
    assert all(
        "extended" in catalog[tool_id].profiles
        for tool_id in {
            "opentofu",
            "ansible",
            "rclone",
            "clamav",
            "cargo_audit",
        }
    )
    assert catalog["terraform"].manual_only is True
    assert catalog["packer"].manual_only is True


def test_native_doctor_reports_all_blockers_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "normalized_platform", lambda: "macos")
    monkeypatch.setattr(native, "normalized_arch", lambda: "amd64")
    monkeypatch.setattr(native, "_trusted_manager", lambda _system: None)
    monkeypatch.setattr(native, "command_present", lambda _command: False)

    report = native.build_doctor("macos")

    assert report["version"] == native.DOCTOR_VERSION
    assert report["status"] == "blocked"
    assert report["network_accessed"] is False
    assert {item["id"] for item in report["blockers"]} == {"package-manager"}
    assert report["doctor_sha256"] == native._digest(report, "doctor_sha256")


def test_native_cli_emits_one_json_result_on_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "version": native.DOCTOR_VERSION,
        "status": "ready",
        "platform": {},
        "runtime": {},
        "blockers": [],
        "warnings": [],
        "network_accessed": False,
    }
    monkeypatch.setattr(native, "build_doctor", lambda _system: payload)

    code = native.main(["--platform", "macos", "doctor", "--output", "json"])
    captured = capsys.readouterr()

    assert code == 0
    assert json.loads(captured.out) == payload
    assert captured.err == ""


def test_planner_uv_uses_only_the_prepared_digest_bound_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"verified uv fixture"
    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w:gz") as bundle:
        member = tarfile.TarInfo("uv-test/uv")
        member.mode = 0o755
        member.size = len(payload)
        bundle.addfile(member, io.BytesIO(payload))
    archive_sha256 = hashlib.sha256(archive_bytes.getvalue()).hexdigest()
    expected = {
        "status": "ready",
        "version": "1.2.3",
        "asset_filename": "uv-test.tar.gz",
        "archive_sha256": archive_sha256,
        "binary_sha256": hashlib.sha256(payload).hexdigest(),
        "source_url": "https://github.com/astral-sh/uv/releases/download/1.2.3/uv-test.tar.gz",
    }
    root = tmp_path / "planner-runtime" / archive_sha256
    root.mkdir(parents=True)
    (root / expected["asset_filename"]).write_bytes(archive_bytes.getvalue())
    monkeypatch.setattr(native, "_state_root", lambda _system: tmp_path)
    monkeypatch.setattr(
        native.subprocess,
        "run",
        lambda *_args, **_kwargs: type("Result", (), {"returncode": 0})(),
    )

    executable, record = native._stage_planner_uv(
        system="macos",
        arch="amd64",
        refresh=False,
        expected=expected,
        allow_download=False,
    )

    assert executable is not None
    assert executable.read_bytes() == payload
    assert record == expected


def test_native_plan_binds_doctor_catalog_runtime_and_transitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = tmp_path / "brew"
    manager.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    manager.chmod(0o755)
    facts = {
        "system": "macos",
        "arch": "amd64",
        "package_manager": "homebrew",
        "package_manager_path": manager.as_posix(),
        "target_user_sha256": "a" * 64,
    }
    doctor = {
        "version": native.DOCTOR_VERSION,
        "status": "ready",
        "platform": facts,
        "runtime": {"implementation": "CPython", "python": "3.12.8", "minimum": "3.11"},
        "blockers": [],
        "warnings": [],
        "network_accessed": False,
        "privacy": "fixture",
    }
    doctor["doctor_sha256"] = native._digest(doctor, "doctor_sha256")
    monkeypatch.setattr(native, "build_doctor", lambda _system: doctor)
    monkeypatch.setattr(native, "command_present", lambda _command: False)
    monkeypatch.setattr(
        native.shutil,
        "which",
        lambda command, **_kwargs: manager.as_posix() if command == "brew" else None,
    )
    monkeypatch.setattr(
        native,
        "build_python_tool_lock",
        lambda *_args, **_kwargs: {
            "status": "not-required",
            "direct_requirements": [],
            "requirements": "",
            "requirements_sha256": hashlib.sha256(b"").hexdigest(),
            "assets": [],
            "blockers": [],
        },
    )

    plan = native.build_plan(
        forge_root=native.REPO_ROOT,
        expected_system="macos",
        profile="custom",
        include=["git"],
        resolver=fixed_homebrew_resolution,
    )

    assert plan["version"] == native.PLAN_VERSION
    assert plan["catalog_version"] == native.CATALOG_VERSION
    assert plan["doctor_sha256"] == doctor["doctor_sha256"]
    assert plan["platform"] == facts
    assert plan["selected_tools"] == ["git"]
    assert plan["transition_matrix"][0]["action"] == "user-package-manager"
    assert plan["plan_sha256"] == native.plan_digest(plan)


def test_native_plan_preserves_older_component_without_rollback_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facts = {
        "system": "macos",
        "arch": "amd64",
        "package_manager": "homebrew",
        "package_manager_path": (tmp_path / "brew").as_posix(),
        "target_user_sha256": "a" * 64,
    }
    doctor = {
        "version": native.DOCTOR_VERSION,
        "status": "ready",
        "platform": facts,
        "runtime": {"implementation": "CPython", "python": "3.12.8", "minimum": "3.11"},
        "blockers": [],
        "warnings": [],
        "network_accessed": False,
        "privacy": "fixture",
    }
    doctor["doctor_sha256"] = native._digest(doctor, "doctor_sha256")
    monkeypatch.setattr(native, "build_doctor", lambda _system: doctor)
    monkeypatch.setattr(native, "command_present", lambda command: command == "git")
    monkeypatch.setattr(native, "_installed_manager_version", lambda *_args: "1.0.0")
    monkeypatch.setattr(
        native.shutil,
        "which",
        lambda command, **_kwargs: facts["package_manager_path"]
        if command == "brew"
        else None,
    )
    monkeypatch.setattr(native, "installer_manifest", lambda _root: {"installer": "d" * 64})
    monkeypatch.setattr(
        native,
        "build_python_tool_lock",
        lambda *_args, **_kwargs: {
            "status": "not-required",
            "direct_requirements": [],
            "requirements": "",
            "requirements_sha256": hashlib.sha256(b"").hexdigest(),
            "assets": [],
            "blockers": [],
        },
    )

    plan = native.build_plan(
        forge_root=native.REPO_ROOT,
        expected_system="macos",
        profile="custom",
        include=["git"],
        resolver=fixed_homebrew_resolution,
    )

    assert plan["tools"][0]["status"] == "preserved"
    assert plan["tools"][0]["install_action"]["kind"] == "manual"
    assert plan["preserved_tools"] == ["git"]
    assert plan["transition_matrix"][0]["from"] == "1.0.0"
    assert plan["transition_matrix"][0]["to"] == "1.2.3"


def test_native_wrappers_never_launch_hidden_elevation() -> None:
    macos = Path("install/tooling-suite-macos.sh").read_text(encoding="utf-8")
    windows = Path("install/tooling-suite.ps1").read_text(encoding="utf-8")

    assert "sudo" not in macos
    assert "Start-Process" not in windows
    assert "-Verb RunAs" not in windows
    assert "moradin_tooling_suite_native.py" in macos
    assert "moradin_tooling_suite_native.py" in windows


def test_linux_v1_receipt_remains_digest_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = {
        "version": linux_suite.LEGACY_SUITE_RECEIPT_VERSION,
        "status": "pass",
        "plan_sha256": "a" * 64,
        "generation": "a" * 16,
        "user_operations": [],
        "root_receipt": None,
    }
    receipt["receipt_sha256"] = linux_suite._record_digest(
        receipt, "receipt_sha256"
    )
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    loaded_path, loaded = linux_suite._load_user_receipt(path.as_posix())

    assert loaded_path == path
    assert loaded["version"] == linux_suite.LEGACY_SUITE_RECEIPT_VERSION
    data_root = tmp_path / "data"
    state_root = tmp_path / "state"
    bin_root = tmp_path / "bin"
    for root in (data_root, state_root, bin_root):
        root.mkdir()
    monkeypatch.setattr(
        linux_suite,
        "_user_roots",
        lambda: (data_root, state_root, bin_root),
    )

    rolled_back = linux_suite.rollback_suite_receipt(
        path.as_posix(),
        approved_sha256=receipt["receipt_sha256"],
        forge_root=linux_suite.REPO_ROOT,
    )

    assert rolled_back["status"] == "pass"
    assert rolled_back["root"] is None


def test_native_checkpoint_is_digest_bound_and_reusable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "_state_root", lambda _system: tmp_path)
    plan = {
        "platform": {"system": "macos"},
        "plan_sha256": "b" * 64,
        "protected_state_sha256": "c" * 64,
    }

    native._checkpoint(plan, "tool-git", "pass", {"tool_id": "git"})
    checkpoint = native._load_checkpoint(plan, "tool-git")

    assert checkpoint is not None
    assert checkpoint["evidence"] == {"tool_id": "git"}
    path = tmp_path / "checkpoints" / ("b" * 64) / "tool-git.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence"]["tool_id"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert native._load_checkpoint(plan, "tool-git") is None


def test_native_plan_rejects_protected_state_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facts = {
        "system": "macos",
        "arch": "amd64",
        "package_manager": "homebrew",
        "package_manager_path": "/opt/homebrew/bin/brew",
        "target_user_sha256": "a" * 64,
    }
    monkeypatch.setattr(native, "native_facts", lambda _system: facts)
    monkeypatch.setattr(native, "installer_manifest", lambda _root: {"installer": "d" * 64})
    monkeypatch.setattr(native, "command_present", lambda command: command == "docker")
    monkeypatch.setattr(native, "CATALOG_PATH", tmp_path / "catalog.toml")
    native.CATALOG_PATH.write_text("catalog", encoding="utf-8")
    manifest = {"installer": "d" * 64}
    plan = {
        "version": native.PLAN_VERSION,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "platform": facts,
        "catalog_sha256": native.sha256_file(native.CATALOG_PATH),
        "installer_manifest": manifest,
        "protected_state_sha256": hashlib.sha256(
            native.canonical_json_bytes(
                {
                    "container_engines": [],
                    "manager_path": facts["package_manager_path"],
                    "target_user_sha256": facts["target_user_sha256"],
                }
            )
        ).hexdigest(),
        "status": "ready",
    }
    plan["plan_sha256"] = native.plan_digest(plan)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(native.NativeSuiteError, match="protected"):
        native.load_plan(path, plan["plan_sha256"], "macos")


def test_windows_rollback_emits_human_run_elevated_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = tmp_path / "winget.exe"
    manager.write_bytes(b"fixture")
    receipt_root = tmp_path / "receipts" / "receipt-one"
    receipt_root.mkdir(parents=True)
    receipt = {
        "version": native.RECEIPT_VERSION,
        "generated_at": "2026-08-31T00:00:00+00:00",
        "status": "awaiting-human",
        "plan_sha256": "a" * 64,
        "profile": "custom",
        "platform": "windows",
        "generation": "b" * 16,
        "executed": [],
        "pending_elevated_tools": ["git"],
        "elevated_script": "install-approved-tools.ps1",
        "privacy": "fixture",
    }
    receipt["receipt_sha256"] = native._digest(receipt, "receipt_sha256")
    receipt_path = receipt_root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(native, "_data_root", lambda _system: tmp_path / "data")
    monkeypatch.setattr(native, "_trusted_manager", lambda _system: manager)
    monkeypatch.setattr(native, "command_present", lambda command: command == "git")

    result = native.rollback_receipt(
        "windows",
        receipt_path.as_posix(),
        receipt["receipt_sha256"],
    )

    script = receipt_root / "rollback-approved-tools.ps1"
    assert result["status"] == "awaiting-human"
    assert result["elevated_script"] == script.name
    assert "winget.exe" in script.read_text(encoding="utf-8")
    assert "Git.Git" in script.read_text(encoding="utf-8")


def test_checkpoint_digest_rejects_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "state"))
    plan = {
        "plan_sha256": "b" * 64,
        "catalog_sha256": "c" * 64,
        "installer_manifest_sha256": "d" * 64,
        "protected_state_sha256": "e" * 64,
    }
    linux_suite._write_checkpoint(
        plan,
        "component-one",
        status="pass",
        evidence={"outcome": "verified"},
    )
    path = linux_suite._checkpoint_root("b" * 64) / "component-one.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence"]["outcome"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(linux_suite.ToolingSuiteError, match="binding"):
        linux_suite._load_checkpoint(plan, "component-one")
