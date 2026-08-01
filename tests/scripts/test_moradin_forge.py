"""Coverage for the agent-first Moradin Forge helper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import moradin_forge
from scripts.moradin_forge import (
    AGENTS_MARKER_BEGIN,
    ForgeApplyOptions,
    ForgeError,
    PRIVATE_CODE_ROOT_TOKEN,
    RELEASE_EVIDENCE_TOKEN,
    RELEASE_REPORTS_TOKEN,
    SHARED_TEMPLATES_TOKEN,
    apply_integration,
    build_integration_plan,
    build_upgrade_plan,
    copy_payload_to_sidecar,
    detect_readiness,
    detect_target_tooling,
    install_directory_no_replace,
    main,
    normalize_payload_relative_path,
    rollback_integration,
    rollback_upgrade,
    upgrade_integration,
    verify_integration,
    write_upgrade_plan_artifacts,
    write_install_request_artifacts,
)


def write(path: Path, content: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def forbidden_reference_samples() -> list[str]:
    return [
        f"{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}",
        "/".join(["", "Users", "alice", "code", "private"]),
        "C:" + "\\".join(["", "Users", "Alice", "code", "private"]),
        "\\\\" + "\\".join(["wsl.localhost", "Ubuntu", "home", "alice", "code"]),
        "git" + "@github.com:" + "frisco-deng/moradins-forge.git",
        "/".join(["", "home", "alice", ".codex", "sessions", "2026", "06", "09", "session.jsonl"]),
    ]


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
                "payload_version: 0.2.0-beta.3",
                "source_root: .",
                "sidecar_default_dir: .moradins-harness",
                "include_paths:",
                "  - AGENTS.md",
                "  - FORGE.md",
                "  - README.md",
                "  - Harness/moradin_payload/manifest.yaml",
                "  - Harness/entrypoints",
                "  - Harness/artifacts",
                "  - docs/assets",
                "  - docs/design_docs",
                "  - docs/product_specs",
                "  - docs/references",
                "  - scripts/moradin_forge.py",
                "  - scripts/moradin_workstation.py",
                "exclude_paths:",
                f"  - {RELEASE_REPORTS_TOKEN}",
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
        forge_root / "docs/assets/readme/overview.svg",
        f"<svg><text>{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}</text></svg>\n",
    )
    write(
        forge_root / Path(*RELEASE_EVIDENCE_TOKEN.split("/")) / "latest/sidecar/secret.md",
        "# Manager evidence\n",
    )
    write(forge_root / "docs/references/moradin_forge_agent_integration_contract_v1.md", "# Contract\n")
    write(
        forge_root / "docs/design_docs/discovery_disc_20260101_000000_abc123_architecture.md",
        "excluded discovery history\n",
    )
    write(
        forge_root / "docs/product_specs/discovery_disc_20260101_000000_abc123_project_spec.md",
        "excluded discovery history\n",
    )
    write(forge_root / "scripts/moradin_forge.py", "# copied helper\n")
    write(forge_root / "scripts/moradin_workstation.py", "# copied workstation helper\n")
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
    svg_text = (sidecar / "docs/assets/readme/overview.svg").read_text(encoding="utf-8")
    assert "shared-tooling-source" in svg_text
    assert PRIVATE_CODE_ROOT_TOKEN not in svg_text
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


def test_readiness_is_evidence_adaptive_and_has_no_private_bridge_gaps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = make_blank_target(tmp_path)
    write(target / "pyproject.toml", "[project]\nname='target'\n")
    write(target / ".github/workflows/ci.yml", "name: ci\n")
    present = {"git", "python3", "uv", "rg", "fd", "jq", "yq"}
    monkeypatch.setattr(
        moradin_forge,
        "detect_tool",
        lambda command: command in present,
    )

    readiness = detect_readiness(target)
    ids = {check["id"] for check in readiness["checks"]}

    assert {"git", "python", "uv", "pip_audit", "actionlint", "zizmor"}.issubset(ids)
    assert {"docker", "kubectl", "playwright", "cad"}.isdisjoint(ids)
    assert {"tpldeck", "uvbootstrap", "codex_run", "codex_docker", "codex_exec"}.isdisjoint(
        ids
    )


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
    write(
        sidecar / "docs/assets/readme/leak.svg",
        "\n".join(
            [
                "<svg>",
                *forbidden_reference_samples(),
                "</svg>",
                "",
            ]
        ),
    )
    write(sidecar / Path(*RELEASE_REPORTS_TOKEN.split("/")) / "leak.md", "local evidence\n")

    result = verify_integration(target)

    assert result["status"] == "fail"
    codes = {issue["code"] for issue in result["issues"]}
    assert "internal_home_path" in codes
    assert "mac_home_path" in codes
    assert "windows_user_path" in codes
    assert "wsl_unc_path" in codes
    assert "ssh_clone_url" in codes
    assert "codex_home_or_session_path" in codes
    assert "local_only_artifact_copied" in codes


def test_existing_sidecar_blocks_without_overwrite(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    write(target / ".moradins-harness/old.txt", "old\n")

    with pytest.raises(ForgeError, match="sidecar already exists"):
        apply_integration(forge_root, target, ForgeApplyOptions(approve=True))


def test_overwrite_flag_preserves_existing_sidecar(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    existing = target / ".moradins-harness/old.txt"
    write(existing, "preserve me\n")

    with pytest.raises(ForgeError, match="overwrite-sidecar is disabled"):
        apply_integration(
            forge_root,
            target,
            ForgeApplyOptions(approve=True, overwrite_sidecar=True),
        )

    assert existing.read_text(encoding="utf-8") == "preserve me\n"


def test_staged_install_never_replaces_destination(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    destination = tmp_path / "destination"
    write(staged / "new.txt", "new\n")
    write(destination / "foreign.txt", "foreign\n")

    with pytest.raises(ForgeError, match="appeared during staged apply"):
        install_directory_no_replace(staged, destination)

    assert (staged / "new.txt").is_file()
    assert (destination / "foreign.txt").read_text(encoding="utf-8") == "foreign\n"


def test_rollback_requires_confirmation_and_restores_target_hash(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    result = apply_integration(forge_root, target, ForgeApplyOptions(approve=True))

    with pytest.raises(ForgeError, match="rollback requires --approve"):
        rollback_integration(target, approve=False)

    rollback = rollback_integration(target, approve=True)

    assert rollback["status"] == "pass"
    assert rollback["target_root_hash_restored"] is True
    assert rollback["target_root_hash_after_rollback"] == result["target_root_hash_before"]
    assert not (target / ".moradins-harness").exists()


def test_rollback_refuses_modified_or_unowned_sidecar_content(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))
    sidecar = target / ".moradins-harness"
    managed = sidecar / "FORGE.md"
    managed.write_text("modified\n", encoding="utf-8")

    with pytest.raises(ForgeError, match="managed content changed"):
        rollback_integration(target, approve=True)

    assert sidecar.is_dir()
    managed.write_text("# Forge\n", encoding="utf-8")
    write(sidecar / "operator-note.txt", "unowned\n")
    with pytest.raises(ForgeError, match="managed content changed"):
        rollback_integration(target, approve=True)
    assert (sidecar / "operator-note.txt").is_file()


def test_rollback_restores_patched_agents_exactly(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    original = b"# Existing Agents\n\nkeep trailing whitespace  \n"
    (target / "AGENTS.md").write_bytes(original)
    apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(approve=True, patch_agents=True),
    )

    rollback = rollback_integration(target, approve=True)

    assert rollback["agents_restored"] is True
    assert (target / "AGENTS.md").read_bytes() == original


def test_rollback_preserves_unrelated_agent_guidance_changes(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(approve=True, patch_agents=True),
    )
    agents_path = target / "AGENTS.md"
    agents_path.write_text(agents_path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    rollback_integration(target, approve=True)

    assert not (target / ".moradins-harness").exists()
    assert agents_path.read_text(encoding="utf-8").endswith("changed\n")
    assert AGENTS_MARKER_BEGIN not in agents_path.read_text(encoding="utf-8")


def test_rollback_refuses_modified_owned_agent_marker(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(approve=True, patch_agents=True),
    )
    agents_path = target / "AGENTS.md"
    agents_path.write_text(
        agents_path.read_text(encoding="utf-8").replace(
            "## Moradin Forge",
            "## Modified Moradin Forge",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ForgeError, match="managed AGENTS.md marker was modified"):
        rollback_integration(target, approve=True)

    assert (target / ".moradins-harness").is_dir()


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


def test_apply_can_manage_agents_and_claude_independently(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    write(target / "CLAUDE.md", "# Existing Claude Guidance\n")
    original_agents = (target / "AGENTS.md").read_bytes()

    result = apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(
            approve=True,
            agent_files=("CLAUDE.md",),
        ),
    )

    assert result["agent_file_statuses"] == {"CLAUDE.md": "patched"}
    assert (target / "AGENTS.md").read_bytes() == original_agents
    assert AGENTS_MARKER_BEGIN in (target / "CLAUDE.md").read_text(encoding="utf-8")
    rollback = rollback_integration(target, approve=True)
    assert rollback["agent_files_restored"] == ["CLAUDE.md"]
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == "# Existing Claude Guidance\n"


@pytest.mark.parametrize(
    "agent_file",
    [
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        ".github/copilot-instructions.md",
        ".cursor/rules/moradin-forge.mdc",
    ],
)
def test_each_provider_file_requires_independent_create_and_rolls_back_cleanly(
    tmp_path: Path,
    agent_file: str,
) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_blank_target(tmp_path)

    result = apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(
            approve=True,
            agent_files=(agent_file,),
            create_agent_files=(agent_file,),
        ),
    )

    path = target / agent_file
    assert result["agent_file_statuses"] == {agent_file: "created"}
    text = path.read_text(encoding="utf-8")
    assert AGENTS_MARKER_BEGIN in text
    if agent_file.endswith(".mdc"):
        assert text.startswith("---\ndescription: Moradin Forge repository workflow")
    rollback = rollback_integration(target, approve=True)
    assert rollback["agent_files_restored"] == [agent_file]
    assert not path.exists()
    if agent_file == ".github/copilot-instructions.md":
        assert not (target / ".github").exists()
    if agent_file == ".cursor/rules/moradin-forge.mdc":
        assert not (target / ".cursor").exists()


def test_cursor_rule_refuses_to_replace_an_existing_unowned_file(
    tmp_path: Path,
) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    cursor = target / ".cursor/rules/moradin-forge.mdc"
    write(cursor, "---\ndescription: Existing project rule\n---\n")

    with pytest.raises(ForgeError, match="unowned"):
        apply_integration(
            forge_root,
            target,
            ForgeApplyOptions(
                approve=True,
                agent_files=(".cursor/rules/moradin-forge.mdc",),
            ),
        )

    assert cursor.read_text(encoding="utf-8").startswith("---\ndescription: Existing")
    assert not (target / ".moradins-harness").exists()


def test_provider_parent_symlink_is_rejected_before_any_write(
    tmp_path: Path,
) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / ".github").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ForgeError, match="unsafe parent"):
        apply_integration(
            forge_root,
            target,
            ForgeApplyOptions(
                approve=True,
                agent_files=(".github/copilot-instructions.md",),
                create_agent_files=(".github/copilot-instructions.md",),
            ),
        )

    assert not (outside / "copilot-instructions.md").exists()
    assert not (target / ".moradins-harness").exists()


def test_apply_requires_create_consent_for_missing_agent_file(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)

    result = apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(
            approve=True,
            agent_files=("CLAUDE.md",),
        ),
    )

    assert result["agent_file_statuses"] == {"CLAUDE.md": "snippet_only"}
    assert not (target / "CLAUDE.md").exists()


def test_apply_rejects_symlinked_agent_guidance_before_sidecar_write(
    tmp_path: Path,
) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    outside = tmp_path / "outside-claude.md"
    write(outside, "# outside\n")
    (target / "CLAUDE.md").symlink_to(outside)

    with pytest.raises(ForgeError, match="regular root file"):
        apply_integration(
            forge_root,
            target,
            ForgeApplyOptions(
                approve=True,
                agent_files=("CLAUDE.md",),
            ),
        )

    assert not (target / ".moradins-harness").exists()
    assert outside.read_text(encoding="utf-8") == "# outside\n"


def test_transactional_upgrade_and_immediate_rollback(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    write(target / "CLAUDE.md", "# Claude\n")
    apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(
            approve=True,
            agent_files=("AGENTS.md", "CLAUDE.md"),
        ),
    )
    previous_forge = (target / ".moradins-harness/FORGE.md").read_bytes()
    write(forge_root / "FORGE.md", "# Forge beta 3 updated\n")

    plan = build_upgrade_plan(forge_root, target)
    artifacts = write_upgrade_plan_artifacts(forge_root, plan)
    result = upgrade_integration(
        forge_root,
        target,
        plan_path=Path(artifacts["json"]),
        approved_sha256=plan["plan_sha256"],
    )

    assert result["status"] == "pass"
    assert (target / ".moradins-harness/FORGE.md").read_text(encoding="utf-8") == (
        "# Forge beta 3 updated\n"
    )
    assert verify_integration(target)["status"] == "pass"

    restored = rollback_upgrade(
        target,
        upgrade_id=result["upgrade_id"],
        approve=True,
    )

    assert restored["status"] == "pass"
    assert (target / ".moradins-harness/FORGE.md").read_bytes() == previous_forge
    assert verify_integration(target)["status"] == "pass"


def test_second_upgrade_retains_only_its_immediate_predecessor(
    tmp_path: Path,
) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))

    write(forge_root / "FORGE.md", "# first replacement\n")
    first_plan = build_upgrade_plan(forge_root, target)
    first_artifacts = write_upgrade_plan_artifacts(forge_root, first_plan)
    first = upgrade_integration(
        forge_root,
        target,
        plan_path=Path(first_artifacts["json"]),
        approved_sha256=first_plan["plan_sha256"],
    )

    write(forge_root / "FORGE.md", "# second replacement\n")
    second_plan = build_upgrade_plan(forge_root, target)
    second_artifacts = write_upgrade_plan_artifacts(forge_root, second_plan)
    second = upgrade_integration(
        forge_root,
        target,
        plan_path=Path(second_artifacts["json"]),
        approved_sha256=second_plan["plan_sha256"],
    )

    backup_root = (
        target
        / ".moradins-harness/Harness/artifacts/control/forge_integration/upgrade_backups"
    )
    assert sorted(path.name for path in backup_root.iterdir()) == [
        second["upgrade_id"]
    ]
    assert first["upgrade_id"] != second["upgrade_id"]

    rollback_upgrade(
        target,
        upgrade_id=second["upgrade_id"],
        approve=True,
    )

    assert (target / ".moradins-harness/FORGE.md").read_text(
        encoding="utf-8"
    ) == "# first replacement\n"
    assert verify_integration(target)["status"] == "pass"


def test_upgrade_accepts_legacy_v1_ownership_record(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))
    ownership_path = (
        target
        / ".moradins-harness/Harness/artifacts/control/forge_integration/ownership.json"
    )
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
    ownership["version"] = "MoradinForgeOwnershipV1"
    for key in (
        "agent_files",
        "compatibility",
        "payload_manifest_sha256",
        "payload_version",
        "upgrade_history",
    ):
        ownership.pop(key, None)
    ownership_path.write_text(
        json.dumps(ownership, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write(forge_root / "FORGE.md", "# Forge from legacy upgrade\n")

    plan = build_upgrade_plan(forge_root, target)
    artifacts = write_upgrade_plan_artifacts(forge_root, plan)
    result = upgrade_integration(
        forge_root,
        target,
        plan_path=Path(artifacts["json"]),
        approved_sha256=plan["plan_sha256"],
    )

    assert result["status"] == "pass"
    assert verify_integration(target)["status"] == "pass"


def test_upgrade_rejects_stale_or_mismatched_plan(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))
    write(forge_root / "FORGE.md", "# planned change\n")
    plan = build_upgrade_plan(forge_root, target)
    artifacts = write_upgrade_plan_artifacts(forge_root, plan)
    write(forge_root / "FORGE.md", "# changed after planning\n")

    with pytest.raises(ForgeError, match="source payload contents changed"):
        upgrade_integration(
            forge_root,
            target,
            plan_path=Path(artifacts["json"]),
            approved_sha256=plan["plan_sha256"],
        )

    with pytest.raises(ForgeError, match="approved plan digest"):
        upgrade_integration(
            forge_root,
            target,
            plan_path=Path(artifacts["json"]),
            approved_sha256="0" * 64,
        )


def test_interrupted_upgrade_swap_restores_sidecar_and_agent_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(
        forge_root,
        target,
        ForgeApplyOptions(approve=True, patch_agents=True),
    )
    sidecar = target / ".moradins-harness"
    before_sidecar = {
        path.relative_to(sidecar).as_posix(): path.read_bytes()
        for path in sidecar.rglob("*")
        if path.is_file()
    }
    before_agents = (target / "AGENTS.md").read_bytes()
    write(forge_root / "FORGE.md", "# interrupted candidate\n")
    plan = build_upgrade_plan(forge_root, target)
    artifacts = write_upgrade_plan_artifacts(forge_root, plan)
    original_replace = moradin_forge.os.replace

    def interrupt_candidate_swap(source: object, destination: object) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            destination_path == sidecar
            and source_path.name.startswith(".moradins-harness.upgrade-")
        ):
            raise OSError("simulated interruption before candidate switch")
        original_replace(source, destination)

    monkeypatch.setattr(moradin_forge.os, "replace", interrupt_candidate_swap)

    with pytest.raises(OSError, match="simulated interruption"):
        upgrade_integration(
            forge_root,
            target,
            plan_path=Path(artifacts["json"]),
            approved_sha256=plan["plan_sha256"],
        )

    after_sidecar = {
        path.relative_to(sidecar).as_posix(): path.read_bytes()
        for path in sidecar.rglob("*")
        if path.is_file()
    }
    assert after_sidecar == before_sidecar
    assert (target / "AGENTS.md").read_bytes() == before_agents
    assert not list(target.glob(".moradins-harness.upgrade-*"))
    assert not list(target.glob(".moradins-harness.previous-*"))


def test_upgrade_validates_staging_before_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge_root = make_forge_root(tmp_path)
    target = make_target(tmp_path)
    apply_integration(forge_root, target, ForgeApplyOptions(approve=True))
    sidecar = target / ".moradins-harness"
    before_forge = (sidecar / "FORGE.md").read_bytes()
    write(forge_root / "FORGE.md", "# approved candidate\n")
    plan = build_upgrade_plan(forge_root, target)
    artifacts = write_upgrade_plan_artifacts(forge_root, plan)
    original_write_adapters = moradin_forge.write_adapter_snippets
    calls = 0

    def corrupt_only_staging(
        sidecar_root: Path,
        sidecar_dir: str,
        target_root: Path,
    ) -> list[str]:
        nonlocal calls
        calls += 1
        written = original_write_adapters(
            sidecar_root,
            sidecar_dir,
            target_root,
        )
        if calls == 2:
            write(sidecar_root / "staging-corruption.txt", "unexpected\n")
        return written

    monkeypatch.setattr(
        moradin_forge,
        "write_adapter_snippets",
        corrupt_only_staging,
    )

    with pytest.raises(ForgeError, match="staged upgrade payload"):
        upgrade_integration(
            forge_root,
            target,
            plan_path=Path(artifacts["json"]),
            approved_sha256=plan["plan_sha256"],
        )

    assert (sidecar / "FORGE.md").read_bytes() == before_forge
    assert verify_integration(target)["status"] == "pass"
