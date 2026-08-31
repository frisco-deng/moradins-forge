from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dependency_readiness import DependencyReadinessError, inspect_locks


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def fixtures(tmp_path: Path, nanoid: str) -> tuple[Path, Path, Path]:
    package = tmp_path / "package.json"
    lock = tmp_path / "package-lock.json"
    uv_lock = tmp_path / "uv.lock"
    write_json(package, {"overrides": {"nanoid": "3.3.18"}})
    write_json(
        lock,
        {
            "lockfileVersion": 3,
            "packages": {"node_modules/nanoid": {"version": nanoid}},
        },
    )
    uv_lock.write_text("version = 1\n", encoding="utf-8")
    return package, lock, uv_lock


def test_dependency_readiness_accepts_reviewed_nanoid_floor(tmp_path: Path) -> None:
    package, lock, uv_lock = fixtures(tmp_path, "3.3.18")

    result = inspect_locks(
        package_path=package,
        lock_path=lock,
        uv_lock_path=uv_lock,
    )

    assert result["status"] == "pass"
    assert result["nanoid"] == {"minimum": "3.3.18", "resolved": ["3.3.18"]}


def test_dependency_readiness_rejects_vulnerable_nanoid(tmp_path: Path) -> None:
    package, lock, uv_lock = fixtures(tmp_path, "3.3.16")

    with pytest.raises(DependencyReadinessError, match="3.3.18 or newer"):
        inspect_locks(
            package_path=package,
            lock_path=lock,
            uv_lock_path=uv_lock,
        )


def test_repository_lock_keeps_nanoid_above_security_floor() -> None:
    result = inspect_locks()

    assert all(
        tuple(int(part) for part in version.split(".")) >= (3, 3, 18)
        for version in result["nanoid"]["resolved"]
    )


def test_dependency_workflows_keep_pr_readiness_separate_from_submission() -> None:
    readiness = Path(
        ".github/workflows/tooling-dependency-readiness.yml"
    ).read_text(encoding="utf-8")
    submission = Path(
        ".github/workflows/tooling-dependency-submission.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request:" in readiness
    assert "contents: read" in readiness
    assert "make dependency-readiness" in readiness
    assert "pull_request:" not in submission
    assert (
        "advanced-security/component-detection-dependency-submission-action@"
        "31f25a8de68ae5ce2ca274bc28546a78683c15ce"
    ) in submission
    assert "detectorArgs: UvLock=EnableIfDefaultOff" in submission
    assert "continue-on-error" not in submission
    assert "soft-skip" not in submission
