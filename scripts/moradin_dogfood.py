#!/usr/bin/env python3
"""Run Moradin Forge's bounded transactional dogfood and release proof."""

from __future__ import annotations

import argparse
import gzip
import json
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.moradin_forge import (
    ForgeApplyOptions,
    ForgeError,
    apply_integration,
    build_integration_plan,
    rollback_integration,
    sha256_file,
    target_root_digest,
    verify_integration,
)
from scripts.public_export import export_public_tree


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "dogfood"
OWNERSHIP_MARKER = ".moradin-dogfood-output.json"
RELEASE_VERSION = "v0.2.0-beta.1"
ROLLBACK_ANCHOR = "v0.1.0-public-alpha"


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def run(command: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def git_identity(repo_root: Path) -> dict[str, Any]:
    sha = run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    branch = run(["git", "branch", "--show-current"], cwd=repo_root)
    status = run(["git", "status", "--porcelain=v1", "--untracked-files=normal"], cwd=repo_root)
    return {
        "head_sha": sha,
        "branch": branch,
        "clean": not bool(status),
        "dirty_paths": status.splitlines(),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare_owned_output(output_root: Path) -> None:
    if output_root.exists():
        marker = output_root / OWNERSHIP_MARKER
        if not marker.is_file():
            raise ForgeError(f"refusing to replace unowned dogfood output: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    write_json(
        output_root / OWNERSHIP_MARKER,
        {"version": 1, "owner": "moradin-dogfood", "created_at": utc_now()},
    )


def write_disposable_target(target_root: Path) -> None:
    target_root.mkdir(parents=True)
    files = {
        "AGENTS.md": "# Disposable Target\n\nKeep existing workflows.\n",
        "Makefile": ".PHONY: validate\nvalidate:\n\t@test -f app.py\n",
        "README.md": "# Disposable Forge Target\n",
        "app.py": "def ready() -> bool:\n    return True\n",
        "pyproject.toml": (
            "[project]\nname = \"moradin-disposable-target\"\nversion = \"0.0.0\"\n"
        ),
    }
    for relative, content in files.items():
        path = target_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    run(["git", "init", "-b", "main"], cwd=target_root)
    run(["git", "add", "."], cwd=target_root)
    run(
        [
            "git",
            "-c",
            "user.name=Moradin Dogfood",
            "-c",
            "user.email=moradin-dogfood@example.invalid",
            "commit",
            "-m",
            "Create disposable target",
        ],
        cwd=target_root,
    )


def run_golden_path(repo_root: Path, target_root: Path) -> dict[str, Any]:
    write_disposable_target(target_root)
    target_sha = run(["git", "rev-parse", "HEAD"], cwd=target_root)
    root_hash_before = target_root_digest(target_root, ".moradins-harness")
    status_before = run(["git", "status", "--porcelain=v1"], cwd=target_root)
    plan = build_integration_plan(repo_root, target_root)
    root_hash_after_plan = target_root_digest(target_root, ".moradins-harness")
    status_after_plan = run(["git", "status", "--porcelain=v1"], cwd=target_root)
    if root_hash_after_plan != root_hash_before or status_after_plan != status_before:
        raise ForgeError("plan mutated the disposable target")

    apply_result = apply_integration(
        repo_root,
        target_root,
        ForgeApplyOptions(approve=True),
    )
    verification = verify_integration(target_root)
    if verification["status"] != "pass":
        raise ForgeError("adopted sidecar failed verification")
    root_hash_after_apply = target_root_digest(target_root, ".moradins-harness")
    if root_hash_after_apply != root_hash_before:
        raise ForgeError("default apply modified target content outside the owned sidecar")

    confirmation_refused = False
    try:
        rollback_integration(target_root, approve=False)
    except ForgeError as error:
        confirmation_refused = "requires --approve" in str(error)
    if not confirmation_refused:
        raise ForgeError("rollback did not refuse missing confirmation")

    rollback = rollback_integration(target_root, approve=True)
    root_hash_after_rollback = target_root_digest(target_root, ".moradins-harness")
    target_status_after = run(["git", "status", "--porcelain=v1"], cwd=target_root)
    target_sha_after = run(["git", "rev-parse", "HEAD"], cwd=target_root)
    passed = all(
        [
            plan["consent_required"] is True,
            apply_result["target_root_hash_before"] == root_hash_before,
            verification["status"] == "pass",
            confirmation_refused,
            rollback["status"] == "pass",
            rollback["target_root_hash_restored"] is True,
            root_hash_after_rollback == root_hash_before,
            target_sha_after == target_sha,
            not target_status_after,
            not (target_root / ".moradins-harness").exists(),
        ]
    )
    return {
        "status": "pass" if passed else "fail",
        "target_git_sha": target_sha,
        "plan_read_only": root_hash_after_plan == root_hash_before and status_after_plan == status_before,
        "apply": {
            "status": "pass",
            "managed_tree_sha256": apply_result["managed_tree_sha256"],
            "target_root_unchanged": root_hash_after_apply == root_hash_before,
        },
        "verify": {"status": verification["status"], "issue_count": verification["issue_count"]},
        "rollback_confirmation_refused": confirmation_refused,
        "rollback": rollback,
        "target_root_hash_before": root_hash_before,
        "target_root_hash_after_plan": root_hash_after_plan,
        "target_root_hash_after_apply": root_hash_after_apply,
        "target_root_hash_after_rollback": root_hash_after_rollback,
        "target_git_clean_after": not bool(target_status_after),
    }


def normalized_spdx_id(value: str) -> str:
    return "SPDXRef-" + re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-")


def dependency_packages(repo_root: Path) -> list[tuple[str, str, str]]:
    packages: set[tuple[str, str, str]] = set()
    uv_lock = repo_root / "uv.lock"
    if uv_lock.is_file():
        payload = tomllib.loads(uv_lock.read_text(encoding="utf-8"))
        for package in payload.get("package", []):
            if isinstance(package, dict) and package.get("name") and package.get("version"):
                packages.add((str(package["name"]), str(package["version"]), "pypi"))
    npm_lock = repo_root / "dev_tracker/ui/package-lock.json"
    if npm_lock.is_file():
        payload = json.loads(npm_lock.read_text(encoding="utf-8"))
        for path, package in payload.get("packages", {}).items():
            if not path or not isinstance(package, dict):
                continue
            name = package.get("name") or path.rsplit("node_modules/", 1)[-1]
            version = package.get("version")
            if name and version:
                packages.add((str(name), str(version), "npm"))
    return sorted(packages)


def write_spdx_sbom(repo_root: Path, output_path: Path, source_sha: str) -> dict[str, Any]:
    root_id = "SPDXRef-Package-moradins-forge"
    packages: list[dict[str, Any]] = [
        {
            "SPDXID": root_id,
            "name": "moradins-forge",
            "versionInfo": RELEASE_VERSION.removeprefix("v"),
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "supplier": "NOASSERTION",
        }
    ]
    relationships: list[dict[str, str]] = []
    used_ids = {root_id}
    for index, (name, version, ecosystem) in enumerate(dependency_packages(repo_root), start=1):
        package_id = normalized_spdx_id(f"Package-{ecosystem}-{name}-{version}")
        if package_id in used_ids:
            package_id = f"{package_id}-{index}"
        used_ids.add(package_id)
        packages.append(
            {
                "SPDXID": package_id,
                "name": name,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "supplier": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:{ecosystem}/{name}@{version}",
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": root_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": package_id,
            }
        )
    payload: dict[str, Any] = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"moradins-forge-{RELEASE_VERSION}",
        "documentNamespace": f"https://github.com/frisco-deng/moradins-forge/sbom/{source_sha}",
        "creationInfo": {"created": utc_now(), "creators": ["Tool: moradin-dogfood"]},
        "documentDescribes": [root_id],
        "packages": packages,
        "relationships": relationships,
    }
    write_json(output_path, payload)
    return {"path": output_path.name, "sha256": sha256_file(output_path), "package_count": len(packages)}


def create_deterministic_archive(source_root: Path, archive_path: Path) -> str:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"moradins-forge-{RELEASE_VERSION.removeprefix('v')}"

    def normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = 0
        info.gid = 0
        info.uname = "root"
        info.gname = "root"
        info.mtime = 0
        return info

    with archive_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(source_root.rglob("*"), key=lambda item: item.relative_to(source_root).as_posix()):
                    relative = path.relative_to(source_root)
                    archive.add(path, arcname=(Path(prefix) / relative).as_posix(), recursive=False, filter=normalize)
    return sha256_file(archive_path)


def write_release_artifacts(repo_root: Path, release_root: Path, source_sha: str) -> dict[str, Any]:
    release_root.mkdir(parents=True, exist_ok=True)
    archive_path = release_root / f"moradins-forge-{RELEASE_VERSION.removeprefix('v')}.tar.gz"
    sbom_path = release_root / f"moradins-forge-{RELEASE_VERSION.removeprefix('v')}.spdx.json"
    with tempfile.TemporaryDirectory(prefix="moradin-public-export-") as temporary:
        export_root = Path(temporary) / "public-tree"
        export = export_public_tree(repo_root, export_root, force=False, init_git=False)
        if export["status"] != "pass":
            raise ForgeError("public export portability scan failed")
        archive_sha = create_deterministic_archive(export_root, archive_path)
        copied_file_count = export["copied_file_count"]
    sbom = write_spdx_sbom(repo_root, sbom_path, source_sha)
    manifest_path = release_root / "release-manifest.json"
    manifest = {
        "schema_version": 1,
        "release": RELEASE_VERSION,
        "source_sha": source_sha,
        "previous_release": ROLLBACK_ANCHOR,
        "archive": {"path": archive_path.name, "sha256": archive_sha},
        "sbom": sbom,
        "public_export_file_count": copied_file_count,
        "data_schema_compatibility": "sidecar ownership record added; existing sidecars are preserved and require fresh adoption",
        "rollback_command": "git switch --detach v0.1.0-public-alpha",
        "evidence": "../operator-result.json",
    }
    write_json(manifest_path, manifest)
    checksums_path = release_root / "SHA256SUMS"
    checksums_path.write_text(
        "".join(
            f"{sha256_file(path)}  {path.name}\n"
            for path in (archive_path, sbom_path, manifest_path)
        ),
        encoding="utf-8",
    )
    return {
        "archive": manifest["archive"],
        "sbom": sbom,
        "manifest": {"path": manifest_path.name, "sha256": sha256_file(manifest_path)},
        "checksums": {"path": checksums_path.name, "sha256": sha256_file(checksums_path)},
    }


def run_dogfood(
    repo_root: Path = REPO_ROOT,
    output_root: Path = DEFAULT_OUTPUT,
    *,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_root = output_root.resolve()
    git = git_identity(repo_root)
    if not git["clean"] and not allow_dirty:
        raise ForgeError("dogfood evidence requires a clean worktree")
    prepare_owned_output(output_root)
    work_root = output_root / "work"
    golden_path = run_golden_path(repo_root, work_root / "target")
    if golden_path["status"] != "pass":
        raise ForgeError("transactional golden path failed")
    release = write_release_artifacts(repo_root, output_root / "release", git["head_sha"])
    shutil.rmtree(work_root)
    cleanup_passed = not work_root.exists()
    completed_at = utc_now()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "repository": "moradins-forge",
        "head_sha": git["head_sha"],
        "branch": git["branch"],
        "clean": git["clean"],
        "profile": "disposable-git-core",
        "proof_class": "core-real",
        "status": "pass" if cleanup_passed else "fail",
        "completed_at": completed_at,
        "golden_path_result": golden_path,
        "dependency_identities": {
            "python": platform.python_version(),
            "uv_lock_sha256": sha256_file(repo_root / "uv.lock"),
            "ui_package_lock_sha256": sha256_file(repo_root / "dev_tracker/ui/package-lock.json"),
            "git": run(["git", "--version"], cwd=repo_root),
        },
        "internal_boundaries": [
            "real plan/apply/verify/rollback command implementation",
            "staged atomic sidecar cutover",
            "managed-file and AGENTS.md ownership hashes",
            "sanitized public export and deterministic release archive",
        ],
        "external_boundaries": [
            "tracked disposable Git target replaces a user repository",
            "no host installation, provider call, publication, or network operation",
            "Linux/WSL is the real lane; macOS and Windows remain dry/syntax lanes",
        ],
        "user_visible_outcome": (
            "A disposable Git repository was planned without mutation, adopted, validated, "
            "verified, and restored byte-for-byte by the explicit rollback command."
        ),
        "restart_persistence": {
            "status": "pass",
            "mode": "one-shot",
            "detail": "verification reloaded the ownership record in a separate command boundary",
        },
        "cleanup_result": {
            "status": "pass" if cleanup_passed else "fail",
            "owned_work_root_removed": cleanup_passed,
            "target_git_clean_before_cleanup": golden_path["target_git_clean_after"],
        },
        "rollback_reference": {
            "previous_release": ROLLBACK_ANCHOR,
            "command": "git switch --detach v0.1.0-public-alpha",
            "adoption_command": ".moradins-harness/scripts/moradin_forge.sh rollback --target . --approve",
        },
        "release_artifacts": release,
        "fallback_used": False,
    }
    write_json(output_root / "operator-result.json", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-dirty", action="store_true", help="Write diagnostic, non-promotable evidence.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = run_dogfood(args.repo_root, args.output, allow_dirty=args.allow_dirty)
    except (ForgeError, OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"moradin-dogfood: {error}")
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"dogfood: {payload['status']}")
        print(f"sha: {payload['head_sha']}")
        print(f"evidence: {(args.output / 'operator-result.json').resolve()}")
        print(f"release_manifest: {(args.output / 'release/release-manifest.json').resolve()}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
