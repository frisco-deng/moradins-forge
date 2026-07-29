"""Coverage for the transactional dogfood and release artifact helpers."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from scripts import moradin_dogfood as dogfood
from scripts.moradin_dogfood import (
    RELEASE_OWNERSHIP_MARKER,
    RELEASE_VERSION,
    build_parser,
    create_deterministic_archive,
    prepare_owned_output,
    resolve_release_output,
    run_golden_path,
    write_release_artifacts,
    write_spdx_sbom,
)
from scripts.moradin_forge import ForgeError
from tests.scripts.test_moradin_forge import make_forge_root


def test_golden_path_restores_disposable_git_target(tmp_path: Path) -> None:
    forge_root = make_forge_root(tmp_path)
    target = tmp_path / "dogfood-target"

    result = run_golden_path(forge_root, target)

    assert result["status"] == "pass"
    assert result["plan_read_only"] is True
    assert result["rollback_confirmation_refused"] is True
    assert result["rollback"]["target_root_hash_restored"] is True
    assert result["target_root_hash_before"] == result["target_root_hash_after_rollback"]
    assert result["target_git_clean_after"] is True
    assert not (target / ".moradins-harness").exists()


def test_archive_is_deterministic_and_has_portable_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    second_source = tmp_path / "second-source"
    for root in (source, second_source):
        root.mkdir()
        (root / "README.md").write_text("portable\n", encoding="utf-8")
        nested = root / "docs"
        nested.mkdir()
        (nested / "guide.md").write_text("guide\n", encoding="utf-8")
    (source / "README.md").chmod(0o664)
    (source / "docs").chmod(0o775)
    (source / "docs/guide.md").chmod(0o664)
    (second_source / "README.md").chmod(0o644)
    (second_source / "docs").chmod(0o755)
    (second_source / "docs/guide.md").chmod(0o644)
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"

    first_sha = create_deterministic_archive(source, first)
    second_sha = create_deterministic_archive(second_source, second)

    assert first_sha == second_sha
    with tarfile.open(first, "r:gz") as archive:
        names = archive.getnames()
        prefix = f"moradins-forge-{RELEASE_VERSION.removeprefix('v')}"
        readme = archive.getmember(f"{prefix}/README.md")
        docs = archive.getmember(f"{prefix}/docs")
    assert f"{prefix}/README.md" in names
    assert f"{prefix}/docs/guide.md" in names
    assert readme.mode == 0o644
    assert docs.mode == 0o755


def test_spdx_sbom_uses_exact_lockfile_versions(tmp_path: Path) -> None:
    (tmp_path / "dev_tracker/ui").mkdir(parents=True)
    (tmp_path / "uv.lock").write_text(
        "version = 1\n\n[[package]]\nname = \"alpha\"\nversion = \"1.2.3\"\n",
        encoding="utf-8",
    )
    (tmp_path / "dev_tracker/ui/package-lock.json").write_text(
        json.dumps(
            {
                "packages": {
                    "": {"name": "ui", "version": "0.0.0"},
                    "node_modules/beta": {"name": "beta", "version": "4.5.6"},
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "release.spdx.json"

    result = write_spdx_sbom(tmp_path, output, "a" * 40)

    payload = json.loads(output.read_text(encoding="utf-8"))
    identities = {(package["name"], package["versionInfo"]) for package in payload["packages"]}
    assert payload["spdxVersion"] == "SPDX-2.3"
    assert ("alpha", "1.2.3") in identities
    assert ("beta", "4.5.6") in identities
    assert result["package_count"] == 3


def test_release_output_argument_selects_non_overlapping_stable_root(
    tmp_path: Path,
) -> None:
    dogfood_output = tmp_path / "artifacts" / "dogfood"
    release_output = tmp_path / "artifacts" / "release"

    args = build_parser().parse_args(["--release-output", str(release_output)])
    resolved, separate = resolve_release_output(dogfood_output.resolve(), args.release_output)

    assert resolved == release_output.resolve()
    assert separate is True
    with pytest.raises(ForgeError, match="must not overlap"):
        resolve_release_output(dogfood_output.resolve(), dogfood_output / "nested")


def test_release_output_replacement_requires_valid_ownership_marker(
    tmp_path: Path,
) -> None:
    release_output = tmp_path / "release"
    release_output.mkdir()
    preserved = release_output / "operator-owned.txt"
    preserved.write_text("keep\n", encoding="utf-8")

    with pytest.raises(ForgeError, match="unowned release output"):
        prepare_owned_output(
            release_output,
            marker_name=RELEASE_OWNERSHIP_MARKER,
            owner="moradin-release",
            label="release",
        )

    assert preserved.read_text(encoding="utf-8") == "keep\n"
    preserved.unlink()
    release_output.rmdir()
    prepare_owned_output(
        release_output,
        marker_name=RELEASE_OWNERSHIP_MARKER,
        owner="moradin-release",
        label="release",
    )
    stale = release_output / "stale.txt"
    stale.write_text("stale\n", encoding="utf-8")
    prepare_owned_output(
        release_output,
        marker_name=RELEASE_OWNERSHIP_MARKER,
        owner="moradin-release",
        label="release",
    )

    marker = json.loads(
        (release_output / RELEASE_OWNERSHIP_MARKER).read_text(encoding="utf-8")
    )
    assert marker["owner"] == "moradin-release"
    assert not stale.exists()


def test_stable_release_artifacts_are_reproducible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "forge"
    (repo_root / "dev_tracker/ui").mkdir(parents=True)
    (repo_root / "uv.lock").write_text(
        "version = 1\n\n[[package]]\nname = \"alpha\"\nversion = \"1.2.3\"\n",
        encoding="utf-8",
    )
    (repo_root / "dev_tracker/ui/package-lock.json").write_text(
        json.dumps(
            {
                "packages": {
                    "": {"name": "ui", "version": "0.0.0"},
                    "node_modules/beta": {"name": "beta", "version": "4.5.6"},
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_public_export(
        _repo_root: Path,
        output_root: Path,
        *,
        force: bool,
        init_git: bool,
    ) -> dict[str, object]:
        assert force is False
        assert init_git is False
        output_root.mkdir(parents=True)
        (output_root / "README.md").write_text("portable\n", encoding="utf-8")
        (output_root / "public_audit").mkdir()
        (output_root / "public_audit/portability_report.json").write_text(
            '{"generated_at":"non-deterministic"}\n',
            encoding="utf-8",
        )
        return {"status": "pass", "copied_file_count": 1}

    monkeypatch.setattr(dogfood, "export_public_tree", fake_public_export)
    source_sha = "a" * 40
    created_at = "2026-07-28T18:00:00Z"
    first = tmp_path / "first"
    second = tmp_path / "second"

    write_release_artifacts(
        repo_root,
        first,
        source_sha,
        created_at=created_at,
        evidence_path="../dogfood/operator-result.json",
    )
    write_release_artifacts(
        repo_root,
        second,
        source_sha,
        created_at=created_at,
        evidence_path="../dogfood/operator-result.json",
    )

    release_basename = f"moradins-forge-{RELEASE_VERSION.removeprefix('v')}"
    expected_names = {
        f"{release_basename}.tar.gz",
        f"{release_basename}.spdx.json",
        "release-manifest.json",
        "SHA256SUMS",
    }
    assert {path.name for path in first.iterdir()} == expected_names
    for name in expected_names:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    manifest = json.loads((first / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_sha"] == source_sha
    assert manifest["evidence"] == "../dogfood/operator-result.json"
    with tarfile.open(first / f"{release_basename}.tar.gz", "r:gz") as archive:
        assert not any("/public_audit/" in name for name in archive.getnames())
