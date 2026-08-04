"""Python 3.9-compatible disconnected runtime bootstrap contracts."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from scripts import moradin_airgap as airgap
from scripts import moradin_airgap_bootstrap as bootstrap


def build_bootstrap_kit(tmp_path: Path) -> tuple[Path, str, dict[str, object]]:
    python_tree = tmp_path / "python-tree"
    executable = python_tree / "cpython-3.12.8/bin/python3.12"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"portable Python fixture")
    executable.chmod(0o755)
    manifest = airgap._python_runtime_manifest(python_tree)

    kit_root = tmp_path / "kit"
    payload = kit_root / "payload/bootstrap"
    payload.mkdir(parents=True)
    runtime_archive = payload / "python-3.12.8.tar.gz"
    airgap.write_deterministic_tar(python_tree, runtime_archive)
    manifest_path = payload / "python-3.12.8.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lock: dict[str, object] = {
        "version": bootstrap.LOCK_VERSION,
        "bootstrap": {
            "python": {
                "version": "3.12.8",
                "path": "bootstrap/python-3.12.8.tar.gz",
                "sha256": airgap.sha256_file(runtime_archive),
                "size": runtime_archive.stat().st_size,
                "manifest_path": "bootstrap/python-3.12.8.manifest.json",
                "manifest_sha256": airgap.sha256_file(manifest_path),
                "manifest_size": manifest_path.stat().st_size,
                "executable": manifest["executable"],
                "trust": "uv-python-managed-verified-download",
            }
        },
    }
    lock["lock_sha256"] = airgap._record_digest(lock, "lock_sha256")
    (kit_root / "AIRGAP-LOCK.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    airgap.write_sha256sums(kit_root)
    kit = tmp_path / "KIT.tar.gz"
    digest = airgap.write_deterministic_tar(kit_root, kit)
    return kit, digest, manifest


def test_python39_bootstrap_extracts_only_digest_bound_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit, digest, manifest = build_bootstrap_kit(tmp_path)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    executable = bootstrap.runtime_for_bundle(kit, digest)

    assert executable.read_bytes() == b"portable Python fixture"
    assert executable.relative_to(tmp_path / "cache").as_posix().endswith(
        str(manifest["executable"])
    )
    assert bootstrap.runtime_for_bundle(kit, digest) == executable


def test_python39_bootstrap_keeps_digest_bound_runtime_immutable() -> None:
    runtime = Path("/cache/python3.12")
    main_script = Path("/forge/scripts/moradin_tooling_suite.py")

    assert bootstrap.runtime_argv(runtime, main_script, ["airgap-verify"]) == [
        runtime.as_posix(),
        "-B",
        main_script.as_posix(),
        "airgap-verify",
    ]


def test_python39_bootstrap_rejects_wrong_out_of_band_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit, _digest, _manifest = build_bootstrap_kit(tmp_path)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    with pytest.raises(bootstrap.BootstrapError, match="out-of-band"):
        bootstrap.runtime_for_bundle(kit, "0" * 64)


def test_python39_bootstrap_rejects_link_even_with_exact_outer_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_bootstrap_kit(tmp_path)
    kit_root = tmp_path / "kit"
    unsafe = tmp_path / "unsafe.tar.gz"
    with tarfile.open(unsafe, "w:gz") as archive:
        for path in sorted(kit_root.rglob("*")):
            archive.add(
                path,
                arcname=path.relative_to(kit_root).as_posix(),
                recursive=False,
            )
        link = tarfile.TarInfo("payload/escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive.addfile(link)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    with pytest.raises(bootstrap.BootstrapError, match="links or special"):
        bootstrap.runtime_for_bundle(unsafe, bootstrap.sha256_file(unsafe))
