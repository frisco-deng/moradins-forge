"""Coverage for public Moradin Forge export hardening."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.public_export import (
    BRANCH_WAIVER_TOKEN,
    PRIVATE_CODE_ROOT_TOKEN,
    PR_HARDENING_TOKEN,
    SHARED_TEMPLATES_TOKEN,
    TEMPLATE_REPO_ALIAS_TOKEN,
    check_public_export,
    export_public_tree,
    scan_public_root,
    scan_tree,
    sidecar_smoke,
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


def make_source_repo(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    write(source / ".gitignore", "artifacts/\n")
    write(source / "README.md", f"{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}\n")
    write(source / "FORGE.md", "# Forge\n")
    write(source / "AGENTS.md", f"{TEMPLATE_REPO_ALIAS_TOKEN}\n")
    write(source / "Makefile", "forge-explain:\n\tpython scripts/moradin_forge.py explain\n")
    write(source / "scripts/moradin_forge.py", "# helper\n")
    write(source / "scripts/forge_bootstrap.py", "# bootstrap helper\n")
    write(source / "install/bootstrap-linux.sh", "#!/usr/bin/env sh\n")
    write(source / "install/bootstrap-macos.sh", "#!/usr/bin/env sh\n")
    write(source / "install/bootstrap-windows.ps1", "#!/usr/bin/env pwsh\n")
    write(
        source / "docs/assets/readme/overview.svg",
        f"<svg><text>{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}</text></svg>\n",
    )
    write(source / "Harness/entrypoints/forge.md", "# Forge Entrypoint\n")
    write(
        source / "Harness/moradin_payload/manifest.yaml",
        "\n".join(
            [
                "manifest_version: 1",
                "name: moradin_harness_payload",
                "kind: moradin_payload",
                "payload_id: moradin_harness_payload",
                "payload_version: 0.2.0-beta.1",
                "source_root: .",
                "sidecar_default_dir: .moradins-harness",
                "include_paths:",
                "  - AGENTS.md",
                "  - FORGE.md",
                "  - README.md",
                "  - Harness/entrypoints",
                "  - Harness/artifacts/control/current_guidance.md",
                "  - scripts/moradin_forge.py",
                "  - scripts/forge_bootstrap.py",
                "  - install",
                "exclude_paths:",
                "  - public_audit/release_reports_excluded",
                "",
            ]
        ),
    )
    write(source / "Harness/artifacts/control/current_guidance.md", "# Current Guidance\n")
    write(source / f"Harness/artifacts/control/{BRANCH_WAIVER_TOKEN}.json", "{}\n")
    write(source / f"Harness/artifacts/control/{PR_HARDENING_TOKEN}/summary.json", "{}\n")
    write(source / "public_audit/release_evidence_excluded/latest/excluded.md", "secret\n")
    write(
        source / "docs/design_docs/discovery_disc_20260101_000000_abc123_architecture.md",
        "excluded discovery history\n",
    )
    write(
        source / "docs/product_specs/discovery_disc_20260101_000000_abc123_project_spec.md",
        "excluded discovery history\n",
    )
    write(source / ".git/config", "hidden history\n")
    write(source / ".codex_pr_body_mh004.md", "old pr body\n")
    write(source / "main.py", "print('placeholder')\n")
    write(source / "ui_audit/current_routes.md", "old ui audit\n")
    return source


def test_scan_tree_reports_forbidden_references(tmp_path: Path) -> None:
    root = tmp_path / "root"
    write(
        root / "docs/assets/readme/leak.svg",
        "\n".join(
            [
                "<svg>",
                *forbidden_reference_samples(),
                BRANCH_WAIVER_TOKEN,
                PR_HARDENING_TOKEN,
                "</svg>",
                "",
            ]
        ),
    )

    hits = scan_tree(root)

    assert {hit.pattern for hit in hits} >= {
        "internal_home_path",
        "mac_home_path",
        "windows_user_path",
        "wsl_unc_path",
        "ssh_clone_url",
        "codex_home_or_session_path",
        "shared_templates_ref",
        "branch_waiver_token",
        "review_hardening_token",
    }


def test_export_public_tree_excludes_history_and_sanitizes_text(tmp_path: Path) -> None:
    source = make_source_repo(tmp_path)
    export = tmp_path / "public"

    payload = export_public_tree(source, export, force=True)

    assert payload["status"] == "pass"
    assert not (export / ".git/config").exists()
    assert not (export / f"Harness/artifacts/control/{BRANCH_WAIVER_TOKEN}.json").exists()
    assert not (export / "Harness/artifacts/control/branch_hygiene_exception.json").exists()
    assert not (export / f"Harness/artifacts/control/{PR_HARDENING_TOKEN}/summary.json").exists()
    assert not (export / "Harness/artifacts/control/review_hardening/summary.json").exists()
    assert not (export / "public_audit/release_evidence_excluded/latest/excluded.md").exists()
    assert not (
        export / "docs/design_docs/discovery_disc_20260101_000000_abc123_architecture.md"
    ).exists()
    assert not (
        export / "docs/product_specs/discovery_disc_20260101_000000_abc123_project_spec.md"
    ).exists()
    assert not (export / ".codex_pr_body_mh004.md").exists()
    assert not (export / "main.py").exists()
    assert not (export / "ui_audit/current_routes.md").exists()
    assert (export / "install/bootstrap-linux.sh").is_file()
    assert (export / "install/bootstrap-macos.sh").is_file()
    assert (export / "install/bootstrap-windows.ps1").is_file()
    assert (export / "scripts/forge_bootstrap.py").is_file()
    svg_text = (export / "docs/assets/readme/overview.svg").read_text(encoding="utf-8")
    assert "shared-tooling-source" in svg_text
    assert PRIVATE_CODE_ROOT_TOKEN not in svg_text
    assert "shared-tooling-source" in (export / "README.md").read_text(encoding="utf-8")
    assert "cd <forge-root>" in (export / "AGENTS.md").read_text(encoding="utf-8")
    assert "/artifacts/" in (export / ".gitignore").read_text(encoding="utf-8")
    guidance = (export / "Harness/artifacts/control/current_guidance.md").read_text(
        encoding="utf-8"
    )
    assert BRANCH_WAIVER_TOKEN not in guidance
    assert PR_HARDENING_TOKEN not in guidance
    assert "moradin_tmp_runs" not in guidance
    assert "FORGE-001" in guidance
    assert (export / "public_audit/export_manifest.json").is_file()
    assert scan_public_root(export)["status"] == "pass"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_export_can_initialize_fresh_single_commit_repo(tmp_path: Path) -> None:
    source = make_source_repo(tmp_path)
    export = tmp_path / "public"

    payload = export_public_tree(source, export, force=True, init_git=True)

    commit_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=export,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    tracked_payload_file = subprocess.run(
        ["git", "ls-files", "--", "Harness/artifacts/control/current_guidance.md"],
        cwd=export,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    assert payload["fresh_git"]["initialized"]
    assert commit_count == "1"
    assert tracked_payload_file == "Harness/artifacts/control/current_guidance.md"


def test_sidecar_smoke_preserves_root_files_and_scans_sidecar(tmp_path: Path) -> None:
    source = tmp_path / "forge"
    write(
        source / "Harness/moradin_payload/manifest.yaml",
        "\n".join(
            [
                "manifest_version: 1",
                "name: moradin_harness_payload",
                "kind: moradin_payload",
                "payload_id: moradin_harness_payload",
                "payload_version: 0.2.0-beta.1",
                "source_root: .",
                "sidecar_default_dir: .moradins-harness",
                "include_paths:",
                "  - AGENTS.md",
                "  - FORGE.md",
                "  - README.md",
                "  - Harness/entrypoints",
                "  - scripts/moradin_forge.py",
                "  - scripts/forge_bootstrap.py",
                "  - install",
                "exclude_paths:",
                "  - public_audit/release_reports_excluded",
                "",
            ]
        ),
    )
    write(source / "AGENTS.md", f"use {PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}\n")
    write(source / "FORGE.md", "# Forge\n")
    write(source / "README.md", "# Readme\n")
    write(source / "Harness/entrypoints/forge.md", "# Forge Entrypoint\n")
    write(source / "scripts/moradin_forge.py", "# helper\n")
    write(source / "scripts/forge_bootstrap.py", "# bootstrap helper\n")
    write(source / "install/bootstrap-linux.sh", "#!/usr/bin/env sh\n")
    write(source / "install/bootstrap-macos.sh", "#!/usr/bin/env sh\n")
    write(source / "install/bootstrap-windows.ps1", "#!/usr/bin/env pwsh\n")

    payload = sidecar_smoke(source, tmp_path / "smoke", force=True)

    assert payload["status"] == "pass"
    assert payload["root_mutations"] == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_check_public_export_writes_combined_manifest_and_clean_git(tmp_path: Path) -> None:
    source = make_source_repo(tmp_path)
    export = tmp_path / "public"

    payload = check_public_export(
        source,
        export,
        tmp_path / "sidecar-smoke",
        force=True,
        init_git=True,
    )

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=export,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    assert payload["status"] == "pass"
    assert payload["sidecar_smoke"]["status"] == "pass"
    assert payload["fresh_git"]["commit_count"] == 1
    assert status == ""
    assert (export / "public_audit/export_manifest.json").is_file()
    audit_text = (export / "public_audit/portability_report.md").read_text(encoding="utf-8")
    manifest_text = (export / "public_audit/export_manifest.json").read_text(encoding="utf-8")
    assert "/tmp/" not in audit_text
    assert str(tmp_path) not in audit_text
    assert "/tmp/" not in manifest_text
    assert str(tmp_path) not in manifest_text
