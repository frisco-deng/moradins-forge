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


def make_source_repo(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    write(source / ".gitignore", "artifacts/\n")
    write(source / "README.md", f"{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}\n")
    write(source / "FORGE.md", "# Forge\n")
    write(source / "AGENTS.md", f"{TEMPLATE_REPO_ALIAS_TOKEN}\n")
    write(source / "Makefile", "forge-explain:\n\tpython scripts/moradin_forge.py explain\n")
    write(source / "scripts/moradin_forge.py", "# helper\n")
    write(source / "Harness/entrypoints/forge.md", "# Forge Entrypoint\n")
    write(
        source / "Harness/moradin_payload/manifest.yaml",
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
                "  - Harness/artifacts/control/current_guidance.md",
                "  - scripts/moradin_forge.py",
                "exclude_paths:",
                "  - public_audit/release_reports_excluded",
                "",
            ]
        ),
    )
    write(source / "Harness/artifacts/control/current_guidance.md", "# Current Guidance\n")
    write(source / f"Harness/artifacts/control/{BRANCH_WAIVER_TOKEN}.json", "{}\n")
    write(source / f"Harness/artifacts/control/{PR_HARDENING_TOKEN}/summary.json", "{}\n")
    write(source / "public_audit/release_evidence_excluded/latest/private.md", "secret\n")
    write(
        source / "docs/design_docs/discovery_disc_20260101_000000_abc123_architecture.md",
        "generated discovery history\n",
    )
    write(
        source / "docs/product_specs/discovery_disc_20260101_000000_abc123_project_spec.md",
        "generated discovery history\n",
    )
    write(source / ".git/config", "private history\n")
    write(source / ".codex_pr_body_mh004.md", "old pr body\n")
    write(source / "main.py", "print('placeholder')\n")
    write(source / "ui_audit/current_routes.md", "old ui audit\n")
    return source


def test_scan_tree_reports_forbidden_references(tmp_path: Path) -> None:
    root = tmp_path / "root"
    write(
        root / "README.md",
        "\n".join(
            [
                f"{PRIVATE_CODE_ROOT_TOKEN}/{SHARED_TEMPLATES_TOKEN}",
                BRANCH_WAIVER_TOKEN,
                PR_HARDENING_TOKEN,
                "",
            ]
        ),
    )

    hits = scan_tree(root)

    assert {hit.pattern for hit in hits} >= {
        "internal_home_path",
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
    assert not (export / "public_audit/release_evidence_excluded/latest/private.md").exists()
    assert not (
        export / "docs/design_docs/discovery_disc_20260101_000000_abc123_architecture.md"
    ).exists()
    assert not (
        export / "docs/product_specs/discovery_disc_20260101_000000_abc123_project_spec.md"
    ).exists()
    assert not (export / ".codex_pr_body_mh004.md").exists()
    assert not (export / "main.py").exists()
    assert not (export / "ui_audit/current_routes.md").exists()
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
                "payload_version: 0.2.0-alpha",
                "source_root: .",
                "sidecar_default_dir: .moradins-harness",
                "include_paths:",
                "  - AGENTS.md",
                "  - FORGE.md",
                "  - README.md",
                "  - Harness/entrypoints",
                "  - scripts/moradin_forge.py",
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
