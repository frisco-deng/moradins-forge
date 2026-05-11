"""Coverage for the agent-first Moradin Forge helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.moradin_forge import (
    AGENTS_MARKER_BEGIN,
    ForgeApplyOptions,
    ForgeError,
    PRIVATE_CODE_ROOT_TOKEN,
    SHARED_TEMPLATES_TOKEN,
    apply_integration,
    build_integration_plan,
    copy_payload_to_sidecar,
    detect_target_tooling,
    main,
    normalize_payload_relative_path,
    verify_integration,
    write_install_request_artifacts,
)


def write(path: Path, content: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_forge_root(tmp_path: Path) -> Path:
    forge_root = tmp_path / "forge"
    write(
        forge_root / "Harness/moradin_payload/manifest.yaml",
        "\n".join(
            [
                "manifest_version: 1",
                "name: moradin_harness_payload",
                "kind: moradin_payload",
                "payload_id: moradin_harness_payload",
                "payload_version: 0.2.0-alpha",
                "source_root: .",
                "sidecar_default_dir: .moradins-harness",
                "include_paths:",
                "  - AGENTS.md",
                "  - FORGE.md",
                "  - README.md",
                "  - Harness/entrypoints",
                "  - Harness/artifacts",
                "  - docs/design_docs",
                "  - docs/product_specs",
                "  - docs/references",
                "  - scripts/moradin_forge.py",
                "exclude_paths:",
                "  - public_audit/release_reports_excluded",
                "  - .git",
                "",
            ]
        ),
    )
    write(forge_root / "AGENTS.md", "Load Harness/entrypoints/agent.md\n")
    write(forge_root / "README.md", f"{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}\n")
    write(forge_root / "FORGE.md", "# Forge\n")
    write(forge_root / "Harness/entrypoints/forge.md", "# Forge Entrypoint\n")
    write(forge_root / "Harness/artifacts/control/current_guidance.md", "# Guidance\n")
    write(
        forge_root
        / "public_audit/release_evidence_excluded/latest/sidecar/secret.md",
        "# Manager evidence\n",
    )
    write(forge_root / "docs/references/moradin_forge_agent_integration_contract_v1.md", "# Contract\n")
    write(
        forge_root / "docs/design_docs/discovery_disc_20260101_000000_abc123_architecture.md",
        "generated discovery history\n",
    )
    write(
        forge_root / "docs/product_specs/discovery_disc_20260101_000000_abc123_project_spec.md",
        "generated discovery history\n",
    )
    write(forge_root / "scripts/moradin_forge.py", "# copied helper\n")
    return forge_root


def make_target(tmp_path: Path) -> Path:
    target = tmp_path / "target"
    write(target / "AGENTS.md", "# Existing Agents\n")
    write(target / "Makefile", "verify:\n\ttrue\n")
    write(target / "package.json", '{"scripts":{"test":"node --test"}}\n')
    write(target / "pyproject.toml", "[project]\nname = \"target\"\n")
    return target


def make_blank_target(tmp_path: Path) -> Path:
    target = tmp_path / "blank-target"
    target.mkdir(parents=True)
    return target


def add_full_tooling(target: Path) -> None:
    write(target / "Cargo.toml", "[package]\nname = \"target\"\nversion = \"0.0.0\"\n")
    write(target / "go.mod", "module example.com/target\n\ngo 1.23\n")
    write(target / "Dockerfile", "FROM scratch\n")
    write(target / "compose.yaml", "services: {}\n")
    write(target / ".github/workflows/ci.yml", "name: ci\non: [push]\njobs: {}\n")


def test_plan_does_not_write_target_repo(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)

    plan = build_integration_plan(forge_root, target)

    assert plan["version"] == "MoradinForgePlanV1"
    assert not (target / ".moradins-harness").exists()
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == "# Existing Agents\n"


def test_apply_requires_explicit_approval(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)

    with pytest.raises(ForgeError, match="requires --approve"):
        apply_integration(forge_root, target, ForgeApplyOptions())


def test_apply_copies_payload_excludes_release_evidence_and_preserves_root_files(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    original_makefile = (target / "Makefile").read_text(encoding="utf-8")
    original_agents = (target / "AGENTS.md").read_text(encoding="utf-8")

    result = apply_integration(forge_root, target, ForgeApplyOptions(approve=True))

    sidecar = target / ".moradins-harness"
    assert result["sidecar_path"] == sidecar.as_posix()
    assert (sidecar / "FORGE.md").is_file()
    assert (sidecar / "Harness/entrypoints/forge.md").is_file()
    assert not (sidecar / "public_audit/release_evidence_excluded/latest/sidecar/secret.md").exists()
    assert not (
        sidecar / "docs/design_docs/discovery_disc_20260101_000000_abc123_architecture.md"
    ).exists()
    assert not (
        sidecar / "docs/product_specs/discovery_disc_20260101_000000_abc123_project_spec.md"
    ).exists()
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == original_agents
    assert (target / "Makefile").read_text(encoding="utf-8") == original_makefile
    assert "shared-tooling-source" in (sidecar / "README.md").read_text(encoding="utf-8")
    assert (sidecar / "adapters/Makefile.snippet").is_file()
    assert (sidecar / "adapters/package.json.scripts.snippet.json").is_file()
    assert (sidecar / "adapters/python.commands.md").is_file()
    assert (sidecar / "Harness/artifacts/control/forge_integration/integration.json").is_file()

    verification = verify_integration(target)
    assert verification["status"] == "pass"


def test_apply_can_patch_agents_after_explicit_option(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)

    apply_integration(forge_root, target, ForgeApplyOptions(approve=True, patch_agents=True))

    assert AGENTS_MARKER_BEGIN in (target / "AGENTS.md").read_text(encoding="utf-8")


def test_detect_target_tooling_drives_adaptive_snippets(tmp_path: Path) -> None:
    target = make_target(tmp_path)

    tooling = detect_target_tooling(target)

    assert tooling["makefile_present"]
    assert tooling["package_json_present"]
    assert tooling["pyproject_toml_present"]
    assert tooling["package_scripts"] == ["test"]


def test_windows_style_payload_paths_normalize_for_planning() -> None:
    assert normalize_payload_relative_path(r"docs\references\index.md") == "docs/references/index.md"


def test_apply_to_blank_repo_creates_sidecar_without_root_adapters(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_blank_target(tmp_path)

    result = apply_integration(forge_root, target, ForgeApplyOptions(approve=True))

    sidecar = target / ".moradins-harness"
    assert result["adapter_status"] == "disabled"
    assert sidecar.is_dir()
    assert not (target / "AGENTS.md").exists()
    assert not (target / "Makefile").exists()
    assert (sidecar / "adapters/AGENTS.snippet.md").is_file()
    assert verify_integration(target)["status"] == "pass"


def test_apply_generates_adaptive_snippets_for_common_tooling(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    add_full_tooling(target)

    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))

    sidecar = target / ".moradins-harness"
    assert (sidecar / "adapters/package.json.scripts.snippet.json").is_file()
    assert (sidecar / "adapters/python.commands.md").is_file()
    assert (sidecar / "adapters/rust.commands.md").is_file()
    assert (sidecar / "adapters/go.commands.md").is_file()
    assert (sidecar / "adapters/docker.commands.md").is_file()
    assert (sidecar / "adapters/ci.commands.md").is_file()


def test_verify_fails_on_forbidden_reference_or_manager_artifact(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))
    sidecar = target / ".moradins-harness"
    write(sidecar / "docs/leak.md", f"{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}\n")
    write(sidecar / "public_audit/release_reports_excluded/leak.md", "manager evidence\n")

    result = verify_integration(target)

    assert result["status"] == "fail"
    codes = {issue["code"] for issue in result["issues"]}
    assert "internal_home_path" in codes
    assert "manager_artifact_copied" in codes


def test_existing_sidecar_blocks_without_overwrite(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    write(target / ".moradins-harness/old.txt", "old\n")

    with pytest.raises(ForgeError, match="sidecar already exists"):
        apply_integration(forge_root, target, ForgeApplyOptions(approve=True))


def test_payload_copy_rejects_symlinks(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    symlink = forge_root / "docs/references/symlink.md"
    symlink.symlink_to(forge_root / "FORGE.md")

    with pytest.raises(ForgeError, match="symlink"):
        copy_payload_to_sidecar(forge_root, tmp_path / "sidecar")


def test_install_request_is_request_only(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    readiness = {
        "checks": [
            {
                "id": "git",
                "label": "Git",
                "status": "missing",
                "human_run_commands": ["sudo apt-get install -y git"],
            }
        ]
    }

    artifacts = write_install_request_artifacts(forge_root, readiness, target_root=target)

    markdown = Path(artifacts["markdown"]).read_text(encoding="utf-8")
    assert "Moradin did not execute these commands" in markdown
    assert "sudo apt-get install -y git" in markdown


def test_cli_accepts_json_after_subcommand(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)

    code = main(
        [
            "--forge-root",
            forge_root.as_posix(),
            "plan",
            "--target",
            target.as_posix(),
            "--json",
        ]
    )

    output = capsys.readouterr().out
    assert code in {0, 1}
    assert '"version": "MoradinForgePlanV1"' in output


def test_cli_verify_reports_sidecar_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))

    code = main(
        [
            "--forge-root",
            forge_root.as_posix(),
            "verify",
            "--target",
            target.as_posix(),
            "--json",
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert '"version": "MoradinForgeVerifyResultV1"' in output
    assert '"status": "pass"' in output
