"""Coverage for the transactional dogfood and release artifact helpers."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from scripts.moradin_dogfood import (
    create_deterministic_archive,
    run_golden_path,
    write_spdx_sbom,
)
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
    source.mkdir()
    (source / "README.md").write_text("portable\n", encoding="utf-8")
    nested = source / "docs"
    nested.mkdir()
    (nested / "guide.md").write_text("guide\n", encoding="utf-8")
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"

    first_sha = create_deterministic_archive(source, first)
    second_sha = create_deterministic_archive(source, second)

    assert first_sha == second_sha
    with tarfile.open(first, "r:gz") as archive:
        names = archive.getnames()
    assert "moradins-forge-0.2.0-beta.1/README.md" in names
    assert "moradins-forge-0.2.0-beta.1/docs/guide.md" in names


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
