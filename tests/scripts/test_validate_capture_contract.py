"""Capture manifest validation tests."""

from __future__ import annotations

from pathlib import Path

import scripts.validate_capture_contract as capture_contract


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_validate_capture_manifest_passes_with_allowlisted_legacy_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
        """# Capture Manifest

## Include Globs

- `AGENTS.md`
- `docs/references/**`
- `dev_tracker/ui/scripts/**`

## Exclude Globs

- `dev_tracker/ui/public/generated/**`

## Allowed Legacy Reference Files

- `docs/references/portability_copy_contract.md`
- `dev_tracker/ui/scripts/sync-docs.mjs`
""",
    )
    _write(tmp_path / "AGENTS.md", "# agents\n")
    _write(tmp_path / "docs/references/portability_copy_contract.md", "legacy docs/99_generated reference\n")
    _write(tmp_path / "dev_tracker/ui/scripts/sync-docs.mjs", "legacy docs/capability_pipeline fallback\n")
    _write(tmp_path / "dev_tracker/ui/public/generated/tracker_snapshot_v1.json", '{"legacy":"docs/99_generated"}')

    issues, included = capture_contract.validate_capture_manifest(
        repo_root=tmp_path,
        manifest_path=tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
    )

    assert issues == []
    assert "AGENTS.md" in included
    assert "dev_tracker/ui/public/generated/tracker_snapshot_v1.json" not in included


def test_validate_capture_manifest_fails_on_unallowlisted_legacy_reference(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
        """# Capture Manifest

## Include Globs

- `docs/exec_plans/**`

## Exclude Globs

- `dev_tracker/ui/public/generated/**`

## Allowed Legacy Reference Files

- `docs/references/portability_copy_contract.md`
""",
    )
    _write(tmp_path / "docs/exec_plans/index.md", "legacy path docs/99_generated should fail\n")

    issues, _included = capture_contract.validate_capture_manifest(
        repo_root=tmp_path,
        manifest_path=tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
    )

    assert issues
    assert any("legacy path marker" in issue.message for issue in issues)


def test_validate_capture_manifest_scans_svg_assets(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
        """# Capture Manifest

## Include Globs

- `docs/assets/**`

## Exclude Globs

- `dev_tracker/ui/public/generated/**`

## Allowed Legacy Reference Files

- `docs/references/portability_copy_contract.md`
""",
    )
    _write(
        tmp_path / "docs/assets/readme/leak.svg",
        "<svg><text>legacy docs/99_generated reference</text></svg>\n",
    )

    issues, included = capture_contract.validate_capture_manifest(
        repo_root=tmp_path,
        manifest_path=tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
    )

    assert "docs/assets/readme/leak.svg" in included
    assert issues
    assert any("legacy path marker" in issue.message for issue in issues)


def test_validate_capture_manifest_excludes_release_evidence_from_legacy_scan(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
        """# Capture Manifest

## Include Globs

- `Harness/artifacts/**`

## Exclude Globs

- `public_audit/release_evidence_excluded/**`

## Allowed Legacy Reference Files

- `docs/references/portability_copy_contract.md`
""",
    )
    _write(
        tmp_path / "Harness/artifacts/control/current_guidance.md",
        "# Current Guidance\n",
    )
    _write(
        tmp_path / "public_audit/release_evidence_excluded/latest/sidecar/docs/references/portability_copy_contract.md",
        "legacy docs/99_generated reference\n",
    )

    issues, included = capture_contract.validate_capture_manifest(
        repo_root=tmp_path,
        manifest_path=tmp_path / "docs/references/generic_harness_capture_manifest_v1.md",
    )

    assert issues == []
    assert "Harness/artifacts/control/current_guidance.md" in included
    assert (
        "public_audit/release_evidence_excluded/latest/sidecar/docs/references/portability_copy_contract.md"
        not in included
    )
