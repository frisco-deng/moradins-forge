"""Air-gap request, sealing, extraction, and recovery contracts."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import gzip
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import moradin_airgap as airgap
from scripts import moradin_airgap_request as request_compat


UBUNTU_FACTS = {
    "system": "linux",
    "arch": "amd64",
    "os_id": "ubuntu",
    "os_version": "24.04",
    "package_manager": "apt",
    "host_fingerprint_sha256": "f" * 64,
}
APT_PACKAGE_STATE = [
    {
        "package": "ca-certificates",
        "version": "20240203",
        "architecture": "all",
        "essential": "no",
        "multi_arch": "foreign",
        "provides": "",
        "depends": "openssl (>= 1.1.1)",
        "pre_depends": "",
        "conflicts": "",
        "breaks": "",
        "replaces": "",
    },
    {
        "package": "git",
        "version": "1:2.43.0",
        "architecture": "amd64",
        "essential": "no",
        "multi_arch": "foreign",
        "provides": "",
        "depends": "libc6 (>= 2.38)",
        "pre_depends": "",
        "conflicts": "",
        "breaks": "",
        "replaces": "",
    },
]


def apt_package_state_output() -> str:
    return "".join(
        "\t".join(row[field] for field in airgap.APT_PACKAGE_STATE_FIELDS) + "\n"
        for row in APT_PACKAGE_STATE
    )


def completed(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_target_normalization_uses_suite_os_version_and_fails_closed() -> None:
    assert airgap._normalized_target_facts(UBUNTU_FACTS) == {
        "system": "linux",
        "os_id": "ubuntu",
        "version_id": "24.04",
        "package_manager": "apt",
        "arch": "amd64",
    }
    with pytest.raises(airgap.AirgapError, match="support"):
        airgap._normalized_target_facts(
            {**UBUNTU_FACTS, "os_version": "22.04"}
        )
    with pytest.raises(airgap.AirgapError, match="x86-64-only"):
        airgap._normalized_target_facts(
            {
                **UBUNTU_FACTS,
                "os_id": "arch",
                "os_version": "rolling",
                "package_manager": "pacman",
                "arch": "arm64",
            }
        )


def test_request_is_digest_bound_and_excludes_machine_identity(
    tmp_path: Path,
) -> None:
    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        if argv[:2] == ["dpkg-query", "-W"] and any(
            "${Package}" in item for item in argv
        ):
            return completed(stdout=apt_package_state_output())
        if argv[:2] == ["dpkg-query", "-W"] and any(
            "binary:Package" in item for item in argv
        ):
            return completed(stdout="ca-certificates\t20240203\ngit\t1:2.43.0\n")
        return completed(returncode=1)

    output = tmp_path / "REQUEST.json"
    request = airgap.build_airgap_request(
        forge_root=airgap.REPO_ROOT,
        profile="practical",
        output=output,
        facts=UBUNTU_FACTS,
        runner=runner,
    )

    assert request["request_sha256"] == airgap._record_digest(
        request, "request_sha256"
    )
    encoded = json.dumps(request)
    assert "host_fingerprint" not in encoded
    assert '"hostname":' not in encoded
    assert str(tmp_path) not in encoded
    assert '"workspace"' not in encoded.lower()
    assert airgap.load_airgap_request(output) == request


def test_python39_request_generator_matches_practical_engine_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        request_compat.shutil,
        "which",
        lambda command: f"/usr/bin/{command}" if command == "podman" else None,
    )
    catalog = request_compat.load_catalog(airgap.CATALOG_PATH)
    selected, engine, existing = request_compat.selected_tools(
        catalog, "practical", [], ""
    )

    assert selected
    assert engine == ""
    assert existing == ""

    monkeypatch.setattr(request_compat, "target_facts", lambda: {
        "system": "linux",
        "os_id": "ubuntu",
        "version_id": "24.04",
        "package_manager": "apt",
        "arch": "amd64",
    })
    monkeypatch.setattr(request_compat, "installed_version", lambda *_args: "")
    monkeypatch.setattr(request_compat, "installed_inventory", lambda _manager: [])
    monkeypatch.setattr(
        request_compat,
        "installed_apt_package_state",
        lambda: APT_PACKAGE_STATE,
    )
    output = tmp_path / "REQUEST.json"
    args = SimpleNamespace(
        forge_root=airgap.REPO_ROOT,
        profile="practical",
        output=output,
        exclude=[],
        container_engine="",
        approve_repository=[],
        arch_snapshot="",
        approve_arch_package_inventory=False,
    )
    request_compat.build_request(args)

    assert airgap.load_airgap_request(output)["existing_container_engine"] == ""


def test_request_rejects_recomputed_schema_and_package_tampering(
    tmp_path: Path,
) -> None:
    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        if argv[:2] == ["dpkg-query", "-W"] and any(
            "${Package}" in item for item in argv
        ):
            return completed(stdout=apt_package_state_output())
        if argv[:2] == ["dpkg-query", "-W"] and any(
            "binary:Package" in item for item in argv
        ):
            return completed(stdout="ca-certificates\t20240203\ngit\t1:2.43.0\n")
        return completed(returncode=1)

    source = tmp_path / "request.json"
    original = airgap.build_airgap_request(
        forge_root=airgap.REPO_ROOT,
        profile="practical",
        output=source,
        facts=UBUNTU_FACTS,
        runner=runner,
    )

    mutations = [
        ({**original, "unexpected": True}, "fields"),
        ({**original, "selected_tools": original["selected_tools"][:-1]}, "profile"),
        (
            {
                **original,
                "apt_package_state": [
                    {
                        **original["apt_package_state"][0],
                        "depends": "libc6\nConffiles: /unsafe/path",
                    },
                    *original["apt_package_state"][1:],
                ],
            },
            "unsafe package metadata",
        ),
        (
            {
                **original,
                "installed_package_inventory": [
                    *original["installed_package_inventory"],
                    {"package": "unsafe", "version": "1.0\nINJECT"},
                ],
            },
            "unsafe package metadata",
        ),
        ({**original, "installer_manifest_sha256": "0" * 64}, "installer"),
    ]
    for index, (payload, message) in enumerate(mutations):
        payload["request_sha256"] = airgap._record_digest(
            payload, "request_sha256"
        )
        path = tmp_path / f"tampered-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(airgap.AirgapError, match=message):
            airgap.load_airgap_request(path)


def test_apt_index_decompression_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "Packages.gz"
    with gzip.open(source, "wb") as stream:
        stream.write(b"x" * 1024)
    destination = tmp_path / "Packages"
    monkeypatch.setattr(airgap, "AIRGAP_MAX_FILE_BYTES", 32)

    with pytest.raises(airgap.AirgapError, match="safety limit"):
        airgap._copy_decompressed_apt_index(source, destination)
    assert not destination.exists()


def test_debian_package_fields_query_values_without_labeled_output(
    tmp_path: Path,
) -> None:
    package = tmp_path / "fixture.deb"
    responses = {
        "Package": "make\n",
        "Version": "4.3-4.1build2\n",
        "Architecture": "amd64\n",
    }
    commands: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(argv)
        return completed(stdout=responses[argv[-1]])

    assert airgap._debian_package_fields(
        package,
        ["Package", "Version", "Architecture"],
        runner=runner,
    ) == ["make", "4.3-4.1build2", "amd64"]
    assert commands == [
        ["dpkg-deb", "-f", package.as_posix(), field]
        for field in ("Package", "Version", "Architecture")
    ]


def test_apt_transaction_closure_uses_sanitized_target_solver_state() -> None:
    commands: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(argv)
        if argv[0] == "dpkg-query":
            return completed(returncode=1)
        if argv[:2] == ["apt-cache", "policy"]:
            return completed(stdout="  Candidate: 4.3-4.1build2\n")
        if argv[:2] == ["apt-get", "-o"]:
            status_argument = next(
                item for item in argv if item.startswith("Dir::State::status=")
            )
            status = Path(status_argument.partition("=")[2]).read_text(
                encoding="utf-8"
            )
            assert "Package: git\n" in status
            assert "Description:" not in status
            assert "/home/" not in status
            return completed(
                stdout=(
                    "Inst make (4.3-4.1build2 Ubuntu:24.04/noble [amd64])\n"
                    "Conf make (4.3-4.1build2 Ubuntu:24.04/noble [amd64])\n"
                )
            )
        return completed(returncode=1)

    assert airgap._apt_transaction_closure(
        ["make"],
        APT_PACKAGE_STATE,
        runner=runner,
    ) == ["make=4.3-4.1build2"]
    assert not any("apt-rdepends" in command for command in commands)


def test_apt_transaction_closure_rejects_package_removal() -> None:
    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        if argv[0] == "dpkg-query":
            return completed(returncode=1)
        if argv[:2] == ["apt-cache", "policy"]:
            return completed(stdout="  Candidate: 4.3-4.1build2\n")
        if argv[:2] == ["apt-get", "-o"]:
            return completed(
                stdout=(
                    "Remv protected-package [1.0]\n"
                    "Inst make (4.3-4.1build2 Ubuntu:24.04/noble [amd64])\n"
                )
            )
        return completed(returncode=1)

    with pytest.raises(airgap.AirgapError, match="remove"):
        airgap._apt_transaction_closure(
            ["make"],
            APT_PACKAGE_STATE,
            runner=runner,
        )


def test_managed_python_links_are_materialized_only_within_runtime(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    executable = source / "cpython/bin/python3.12"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"runtime")
    executable.chmod(0o755)
    (source / "cpython/bin/python3").symlink_to("python3.12")
    (source / "cpython-family").symlink_to("cpython", target_is_directory=True)
    materialized = tmp_path / "materialized"

    airgap._materialize_managed_python(source, materialized)
    manifest = airgap._python_runtime_manifest(materialized)

    assert not (materialized / "cpython/bin/python3").is_symlink()
    assert not (materialized / "cpython-family").exists()
    assert manifest["executable"] == "cpython/bin/python3.12"
    assert [row["path"] for row in manifest["files"]] == sorted(
        row["path"] for row in manifest["files"]
    )
    airgap._validate_python_runtime_tree(materialized, manifest)

    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    (unsafe / "escape").symlink_to("/etc/passwd")
    with pytest.raises(airgap.AirgapError, match="escapes"):
        airgap._materialize_managed_python(unsafe, tmp_path / "rejected")


def test_arch_request_requires_snapshot_and_separate_inventory_consent(
    tmp_path: Path,
) -> None:
    facts = {
        **UBUNTU_FACTS,
        "os_id": "arch",
        "os_version": "rolling",
        "package_manager": "pacman",
    }
    with pytest.raises(airgap.AirgapError, match="snapshot"):
        airgap.build_airgap_request(
            forge_root=airgap.REPO_ROOT,
            profile="practical",
            output=tmp_path / "request.json",
            facts=facts,
            runner=lambda *_args, **_kwargs: completed(returncode=1),
        )
    with pytest.raises(airgap.AirgapError, match="separate"):
        airgap.build_airgap_request(
            forge_root=airgap.REPO_ROOT,
            profile="practical",
            output=tmp_path / "request.json",
            facts=facts,
            arch_snapshot="2026/07/31",
            runner=lambda *_args, **_kwargs: completed(returncode=1),
        )


def test_arch_apply_rejects_full_inventory_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = [{"package": "pacman", "version": "7.0.0"}]
    lock = {
        "target": {"package_manager": "pacman"},
        "arch_package_inventory": approved,
        "package_assets": [],
    }
    monkeypatch.setattr(
        airgap,
        "_installed_package_inventory",
        lambda _manager: approved,
    )
    airgap._current_package_state_matches(lock)

    monkeypatch.setattr(
        airgap,
        "_installed_package_inventory",
        lambda _manager: [{"package": "pacman", "version": "7.0.1"}],
    )
    with pytest.raises(airgap.AirgapError, match="inventory changed"):
        airgap._current_package_state_matches(lock)


@pytest.mark.parametrize("kind", ["traversal", "symlink"])
def test_safe_extract_rejects_malicious_archives(
    tmp_path: Path,
    kind: str,
) -> None:
    bundle = tmp_path / "unsafe.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        if kind == "traversal":
            member = tarfile.TarInfo("../escape")
            payload = b"unsafe"
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        else:
            member = tarfile.TarInfo("unsafe-link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            archive.addfile(member)
    with pytest.raises(airgap.AirgapError, match="traversal|links"):
        airgap.safe_extract_bundle(bundle, tmp_path / "extract")
    assert not (tmp_path / "extract").exists()


def _cache_record(
    cache: Path,
    relative: str,
    payload: bytes,
) -> dict[str, object]:
    digest = hashlib.sha256(payload).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    (cache / digest).write_bytes(payload)
    return {"path": relative, "sha256": digest, "size": len(payload)}


def _minimal_lock(cache: Path, *, created_at: str) -> dict[str, object]:
    git_bundle = _cache_record(
        cache,
        "forge/moradins-forge-public.bundle",
        b"test git bundle fixture",
    )
    source_snapshot = _cache_record(
        cache,
        "forge/moradins-forge-source.tar.gz",
        b"test source snapshot fixture",
    )
    payload = _cache_record(cache, "payload/fixture.txt", b"tool closure")
    trust = _cache_record(cache, "payload/trust/archive.gpg", b"trust fixture")
    release = _cache_record(
        cache,
        "payload/trust/inrelease",
        b"signed release fixture",
    )
    index_content = b"Package: fixture\nVersion: 1\nArchitecture: amd64\n"
    index = _cache_record(
        cache,
        "payload/trust/packages.txt.gz",
        gzip.compress(index_content, mtime=0),
    )
    uv = _cache_record(cache, "payload/bootstrap/uv", b"uv fixture")
    python = _cache_record(
        cache,
        "payload/bootstrap/python-3.12.8.tar.gz",
        b"python fixture",
    )
    python_manifest = _cache_record(
        cache,
        "payload/bootstrap/python-3.12.8.manifest.json",
        b"python manifest fixture",
    )
    lock: dict[str, object] = {
        "version": airgap.AIRGAP_LOCK_VERSION,
        "created_at": created_at,
        "status": "complete",
        "source_sha": "1" * 40,
        "request_sha256": "2" * 64,
        "target": airgap._normalized_target_facts(UBUNTU_FACTS),
        "profile": "practical",
        "selected_tools": ["git"],
        "explicitly_excluded_tools": [],
        "approved_repositories": [],
        "existing_container_engine": "",
        "arch_snapshot": "",
        "arch_package_inventory": [],
        "expected_package_state": [],
        "catalog_sha256": "3" * 64,
        "installer_manifest_sha256": "4" * 64,
        "source": {
            "sanitized_commit": "5" * 40,
            "git_bundle": {
                "path": Path(str(git_bundle["path"])).name,
                "sha256": git_bundle["sha256"],
                "size": git_bundle["size"],
            },
            "source_snapshot": {
                "path": Path(str(source_snapshot["path"])).name,
                "sha256": source_snapshot["sha256"],
                "size": source_snapshot["size"],
            },
            "copied_file_count": 1,
        },
        "suite_plan": {
            "portable": True,
            "platform": {"host_fingerprint_sha256": "<host-bound-at-apply>"},
            "target_uid": "<target-uid>",
        },
        "package_assets": [],
        "trust_assets": [
            {
                "path": "archive.gpg",
                "kind": "apt-keyring",
                "sha256": trust["sha256"],
                "size": trust["size"],
            },
            {
                "path": "inrelease",
                "kind": "apt-inrelease",
                "sha256": release["sha256"],
                "size": release["size"],
            },
            {
                "path": "packages.txt.gz",
                "kind": "apt-packages-index",
                "sha256": index["sha256"],
                "size": index["size"],
                "compression": "gzip",
                "repository_sha256": hashlib.sha256(index_content).hexdigest(),
                "uncompressed_size": len(index_content),
            },
        ],
        "bootstrap": {
            "uv": {
                "path": "bootstrap/uv",
                "version": "0.10.12",
                "sha256": uv["sha256"],
                "size": uv["size"],
            },
            "python": {
                "path": "bootstrap/python-3.12.8.tar.gz",
                "version": "3.12.8",
                "sha256": python["sha256"],
                "size": python["size"],
                "manifest_path": "bootstrap/python-3.12.8.manifest.json",
                "manifest_sha256": python_manifest["sha256"],
                "manifest_size": python_manifest["size"],
                "executable": "cpython-3.12.8/bin/python3.12",
                "trust": "uv-python-managed-verified-download",
            },
        },
        "payload_files": sorted(
            [
                git_bundle,
                source_snapshot,
                payload,
                trust,
                release,
                index,
                uv,
                python,
                python_manifest,
            ],
            key=lambda row: str(row["path"]),
        ),
        "stale_after_days": 30,
        "privacy": "sanitized fixture",
    }
    lock["lock_sha256"] = airgap._record_digest(lock, "lock_sha256")
    return lock


def test_frozen_lock_build_is_byte_identical_and_stale_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setattr(airgap, "_airgap_cache_root", lambda: cache)
    monkeypatch.setattr(airgap.shutil, "which", lambda _command: None)
    lock = _minimal_lock(cache, created_at="2020-01-01T00:00:00+00:00")

    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    one = airgap._assemble_airgap_kit(
        lock, output=first, forge_root=airgap.REPO_ROOT
    )
    two = airgap._assemble_airgap_kit(
        lock, output=second, forge_root=airgap.REPO_ROOT
    )

    assert first.read_bytes() == second.read_bytes()
    assert one["bundle_sha256"] == two["bundle_sha256"]
    verification = airgap.verify_airgap_bundle(
        first, expected_sha256=one["bundle_sha256"]
    )
    assert verification["status"] == "pass"
    assert verification["complete"] is True
    assert verification["stale"] is True
    with pytest.raises(airgap.AirgapError, match="out-of-band"):
        airgap.verify_airgap_bundle(first, expected_sha256="0" * 64)


def test_lock_rebuild_proves_current_sanitized_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setattr(airgap, "_airgap_cache_root", lambda: cache)
    monkeypatch.setattr(airgap.shutil, "which", lambda _command: None)
    lock = _minimal_lock(cache, created_at="2026-07-31T00:00:00+00:00")
    lock["catalog_sha256"] = airgap.sha256_file(airgap.CATALOG_PATH)
    lock["installer_manifest_sha256"] = airgap.installer_manifest_sha256(
        airgap.REPO_ROOT
    )
    lock["lock_sha256"] = airgap._record_digest(lock, "lock_sha256")
    lock_path = tmp_path / "AIRGAP-LOCK.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(
        airgap,
        "assert_clean_public_forge",
        lambda _root: str(lock["source_sha"]),
    )
    monkeypatch.setattr(
        airgap,
        "build_sanitized_source",
        lambda _root, _destination: lock["source"],
    )

    output = tmp_path / "kit.tar.gz"
    result = airgap.build_airgap_bundle_from_lock(
        lock_path,
        output=output,
        forge_root=airgap.REPO_ROOT,
    )
    assert result["status"] == "complete"

    second = tmp_path / "mismatch.tar.gz"
    monkeypatch.setattr(
        airgap,
        "build_sanitized_source",
        lambda _root, _destination: {**lock["source"], "copied_file_count": 2},
    )
    with pytest.raises(airgap.AirgapError, match="sanitized source"):
        airgap.build_airgap_bundle_from_lock(
            lock_path,
            output=second,
            forge_root=airgap.REPO_ROOT,
        )
    assert not second.exists()


def test_bootstrap_rollback_removes_only_owned_unchanged_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = tmp_path / "data"
    state = tmp_path / "state"
    bin_root = tmp_path / "bin"
    monkeypatch.setattr(airgap, "_user_roots", lambda: (data, state, bin_root))
    extracted = tmp_path / "kit"
    bootstrap = extracted / "payload/bootstrap"
    bootstrap.mkdir(parents=True)
    uv = bootstrap / "uv"
    uv.write_bytes(b"verified uv fixture")
    python_tree = tmp_path / "python-tree"
    executable = python_tree / "cpython-3.12.8/bin/python3.12"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"python fixture")
    executable.chmod(0o755)
    manifest = airgap._python_runtime_manifest(python_tree)
    python_archive = bootstrap / "python.tar.gz"
    airgap.write_deterministic_tar(python_tree, python_archive)
    python_manifest = bootstrap / "python.manifest.json"
    python_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lock = {
        "bootstrap": {
            "uv": {
                "version": "0.10.12",
                "path": "bootstrap/uv",
                "sha256": airgap.sha256_file(uv),
            },
            "python": {
                "path": "bootstrap/python.tar.gz",
                "sha256": airgap.sha256_file(python_archive),
                "manifest_path": "bootstrap/python.manifest.json",
                "manifest_sha256": airgap.sha256_file(python_manifest),
                "manifest_size": python_manifest.stat().st_size,
                "executable": manifest["executable"],
            },
        }
    }

    receipt = airgap._install_airgap_bootstrap(extracted, lock)
    portable = airgap._portable_bootstrap_receipt(receipt)
    assert "runtime_uv_path" not in portable
    assert str(tmp_path) not in json.dumps(portable)
    assert (bin_root / "uv").is_symlink()

    airgap._rollback_airgap_bootstrap(receipt)
    assert not (bin_root / "uv").exists()
    assert not (
        data
        / "bootstrap/python"
        / airgap.sha256_file(python_manifest)
    ).exists()
    assert not (data / receipt["uv_relative"]).exists()
