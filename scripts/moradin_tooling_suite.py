#!/usr/bin/env python3
"""Interactive, digest-bound Linux workstation installer for Moradin Forge."""

from __future__ import annotations

import argparse
import bz2
import gzip
import hashlib
import io
import json
import lzma
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Sequence

try:
    from scripts.moradin_workstation import (
        CATALOG_PATH,
        TOOL_CATALOG,
        ToolSpec,
        WorkstationError,
        _assert_official_asset,
        _download_asset,
        build_python_tool_lock,
        canonical_json_bytes,
        command_present,
        discover_repositories,
        ensure_approved_workspace,
        inspect_repository_capabilities,
        normalized_arch,
        normalized_package_name,
        parse_hashed_requirements,
        plan_digest,
        resolve_latest_version,
        sha256_file,
        sha256_bytes,
        utc_now,
        write_json,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from moradin_workstation import (  # type: ignore[no-redef]
        CATALOG_PATH,
        TOOL_CATALOG,
        ToolSpec,
        WorkstationError,
        _assert_official_asset,
        _download_asset,
        build_python_tool_lock,
        canonical_json_bytes,
        command_present,
        discover_repositories,
        ensure_approved_workspace,
        inspect_repository_capabilities,
        normalized_arch,
        normalized_package_name,
        parse_hashed_requirements,
        plan_digest,
        resolve_latest_version,
        sha256_file,
        sha256_bytes,
        utc_now,
        write_json,
    )


CATALOG_VERSION = "MoradinForgeToolCatalogV2"
DOCTOR_VERSION = "MoradinForgeToolingDoctorV1"
SUITE_PLAN_VERSION = "MoradinForgeToolingSuitePlanV2"
CHECKPOINT_VERSION = "MoradinForgeToolingCheckpointV1"
SUITE_RECEIPT_VERSION = "MoradinForgeToolingSuiteReceiptV2"
ROOT_RECEIPT_VERSION = "MoradinForgeRootToolingReceiptV2"
SUITE_ROLLBACK_VERSION = "MoradinForgeToolingSuiteRollbackV2"
SUITE_BUNDLE_VERSION = "MoradinForgeToolingSuiteBundleV2"
LEGACY_SUITE_RECEIPT_VERSION = "MoradinForgeToolingSuiteReceiptV1"
LEGACY_ROOT_RECEIPT_VERSION = "MoradinForgeRootToolingReceiptV1"
PLAN_TTL = timedelta(hours=24)
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SUPPORTED_PROFILES = {"practical", "extended", "custom"}
SUPPORTED_ARCHES = {"amd64", "arm64"}
SUPPORTED_MANAGERS = {"apt", "dnf", "pacman"}
SYSTEM_COMMAND_PATHS = {
    "apt-cache": ("/usr/bin/apt-cache",),
    "apt-get": ("/usr/bin/apt-get",),
    "dpkg": ("/usr/bin/dpkg",),
    "dpkg-deb": ("/usr/bin/dpkg-deb",),
    "dpkg-query": ("/usr/bin/dpkg-query",),
    "dnf": ("/usr/bin/dnf", "/usr/bin/dnf5"),
    "rpm": ("/usr/bin/rpm",),
    "pacman": ("/usr/bin/pacman",),
    "pactree": ("/usr/bin/pactree",),
}
MAX_ASSET_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 2048
BOOTSTRAP_UV_VERSION = "0.10.12"
BOOTSTRAP_UV_BINARY_SHA256 = {
    "amd64": "56ad65c85aa2c92013807d89d2ff55579dfed03255363e6180c1cc8ca2c4ac59",
    "arm64": "7191fcbd3cbdea7b24e27d9941b22149bce70f925799c4ceb16a98490df5804d",
}
REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_FILES = (
    Path("install/tooling-suite.sh"),
    Path("install/tooling-suite-macos.sh"),
    Path("install/tooling-suite.ps1"),
    Path("install/airgap-container-build.sh"),
    Path("scripts/moradin_airgap_request.py"),
    Path("scripts/moradin_airgap_bootstrap.py"),
    Path("scripts/moradin_airgap.py"),
    Path("scripts/moradin_tooling_suite.py"),
    Path("scripts/moradin_tooling_suite_native.py"),
    Path("scripts/moradin_workstation.py"),
    Path("catalog/workstation-tools.toml"),
)
ROOT_RUNNER_BOOTSTRAP = r"""
import hashlib
import json
import os
import runpy
import shutil
import stat
import sys
import tempfile
from pathlib import Path

FILES = (
    "install/tooling-suite.sh",
    "install/tooling-suite-macos.sh",
    "install/tooling-suite.ps1",
    "install/airgap-container-build.sh",
    "scripts/moradin_airgap_request.py",
    "scripts/moradin_airgap_bootstrap.py",
    "scripts/moradin_airgap.py",
    "scripts/moradin_tooling_suite.py",
    "scripts/moradin_tooling_suite_native.py",
    "scripts/moradin_workstation.py",
    "catalog/workstation-tools.toml",
)
if len(sys.argv) < 7:
    raise SystemExit("root runner bootstrap arguments are incomplete")
(
    source_arg,
    expected,
    runtime_source_arg,
    runtime_manifest_arg,
    runtime_expected,
    runtime_executable_arg,
    *runner_args,
) = sys.argv[1:]
if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
    raise SystemExit("invalid root runner manifest digest")
base = Path("/var/lib/moradins-forge/runners")
destination = base / expected
os.umask(0o077)

def read_tree(root, require_root):
    raw_root = Path(root)
    if raw_root.is_symlink():
        raise SystemExit("unsafe root runner directory")
    root = raw_root.resolve(strict=True)
    result = {}
    payloads = {}
    for relative in FILES:
        path = root / relative
        current = root
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                raise SystemExit("unsafe root runner path")
        resolved = path.resolve(strict=True)
        if path.is_symlink() or not resolved.is_relative_to(root):
            raise SystemExit("unsafe root runner path")
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 16 * 1024 * 1024:
                raise SystemExit("unsafe root runner file")
            if require_root and (metadata.st_uid != 0 or metadata.st_mode & 0o022):
                raise SystemExit("unsafe root runner ownership")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                payload = handle.read(16 * 1024 * 1024 + 1)
        finally:
            os.close(descriptor)
        if len(payload) != metadata.st_size:
            raise SystemExit("root runner file changed while sealing")
        result[relative] = hashlib.sha256(payload).hexdigest()
        payloads[relative] = payload
    digest = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != expected:
        raise SystemExit("root runner manifest digest mismatch")
    return payloads

def safe_relative(value):
    if not value or "\\" in value or "\x00" in value:
        raise SystemExit("unsafe managed runtime path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise SystemExit("unsafe managed runtime path")
    return relative

def read_runtime_manifest(path, expected_digest, require_root):
    raw_path = Path(path)
    if raw_path.is_symlink():
        raise SystemExit("unsafe managed runtime manifest")
    descriptor = os.open(
        raw_path.resolve(strict=True),
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 16 * 1024 * 1024:
            raise SystemExit("unsafe managed runtime manifest")
        if require_root and (metadata.st_uid != 0 or metadata.st_mode & 0o022):
            raise SystemExit("unsafe managed runtime manifest ownership")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read(16 * 1024 * 1024 + 1)
    finally:
        os.close(descriptor)
    if hashlib.sha256(payload).hexdigest() != expected_digest:
        raise SystemExit("managed runtime manifest digest mismatch")
    try:
        manifest = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SystemExit("managed runtime manifest is invalid")
    if not isinstance(manifest, dict) or set(manifest) != {
        "version", "python_version", "executable", "files", "manifest_sha256"
    }:
        raise SystemExit("managed runtime manifest fields are malformed")
    canonical = dict(manifest)
    recorded = canonical.pop("manifest_sha256", "")
    internal_digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if (
        manifest.get("version") != "MoradinForgePythonRuntimeManifestV1"
        or manifest.get("python_version") != "3.12.8"
        or recorded != internal_digest
    ):
        raise SystemExit("managed runtime manifest binding is invalid")
    executable = safe_relative(str(manifest.get("executable", "")))
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise SystemExit("managed runtime manifest is empty")
    seen = []
    executable_bound = False
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size", "mode"}:
            raise SystemExit("managed runtime file record is malformed")
        relative = safe_relative(str(row.get("path", ""))).as_posix()
        digest = str(row.get("sha256", ""))
        size = row.get("size")
        mode = row.get("mode")
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(size, int)
            or size < 0
            or size > 512 * 1024 * 1024
            or mode not in {0o644, 0o755}
            or relative in seen
        ):
            raise SystemExit("managed runtime file metadata is unsafe")
        seen.append(relative)
        if relative == executable.as_posix() and mode == 0o755:
            executable_bound = True
    if seen != sorted(seen) or not executable_bound:
        raise SystemExit("managed runtime executable or ordering is invalid")
    return payload, manifest, executable

def runtime_file_set(root):
    raw_root = Path(root)
    if raw_root.is_symlink():
        raise SystemExit("unsafe managed runtime root")
    root = raw_root.resolve(strict=True)
    result = set()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise SystemExit("managed runtime contains a symbolic link")
        if path.is_file():
            result.add(relative)
        elif not path.is_dir():
            raise SystemExit("managed runtime contains a special file")
    return root, result

def verify_runtime(root, manifest, require_root):
    root, observed = runtime_file_set(root)
    expected_files = {str(row["path"]) for row in manifest["files"]}
    if observed - {".manifest.json"} != expected_files:
        raise SystemExit("managed runtime tree differs from its manifest")
    for row in manifest["files"]:
        path = root / safe_relative(str(row["path"]))
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        )
        digest = hashlib.sha256()
        size = 0
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise SystemExit("managed runtime file is unsafe")
            if require_root and (metadata.st_uid != 0 or metadata.st_mode & 0o022):
                raise SystemExit("managed runtime ownership is unsafe")
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        finally:
            os.close(descriptor)
        mode = 0o755 if metadata.st_mode & stat.S_IXUSR else 0o644
        if (
            size != int(row["size"])
            or digest.hexdigest() != row["sha256"]
            or mode != int(row["mode"])
        ):
            raise SystemExit("managed runtime file digest or mode mismatch")
    return root

def seal_runtime(source, manifest_path, expected_digest, executable_arg):
    if (
        len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise SystemExit("managed runtime manifest digest is invalid")
    runtime_base = Path("/var/lib/moradins-forge/python")
    runtime_destination = runtime_base / expected_digest
    current = Path("/")
    for part in runtime_base.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise SystemExit("unsafe managed runtime store path")
        if current.exists():
            metadata = current.stat()
            if metadata.st_uid != 0 or metadata.st_mode & 0o022:
                raise SystemExit("unsafe managed runtime store ownership")
    stored_manifest = runtime_destination / ".manifest.json"
    if runtime_destination.exists():
        payload, manifest, executable = read_runtime_manifest(
            stored_manifest, expected_digest, True
        )
        if executable.as_posix() != executable_arg:
            raise SystemExit("managed runtime executable approval changed")
        verify_runtime(runtime_destination, manifest, True)
        return runtime_destination / executable
    if source == "-" or manifest_path == "-":
        raise SystemExit("approved managed runtime is unavailable")
    payload, manifest, executable = read_runtime_manifest(
        manifest_path, expected_digest, False
    )
    if executable.as_posix() != executable_arg:
        raise SystemExit("managed runtime executable approval changed")
    source_root, observed = runtime_file_set(source)
    expected_files = {str(row["path"]) for row in manifest["files"]}
    if observed != expected_files:
        raise SystemExit("managed runtime source differs from its manifest")
    runtime_base.mkdir(parents=True, exist_ok=True, mode=0o700)
    if runtime_base.is_symlink() or runtime_base.stat().st_uid != 0:
        raise SystemExit("unsafe managed runtime store")
    temporary = Path(tempfile.mkdtemp(prefix=".python-", dir=runtime_base))
    try:
        for row in manifest["files"]:
            relative = safe_relative(str(row["path"]))
            source_path = source_root / relative
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            source_descriptor = os.open(
                source_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            )
            target_descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                int(row["mode"]),
            )
            digest = hashlib.sha256()
            size = 0
            try:
                source_metadata = os.fstat(source_descriptor)
                if not stat.S_ISREG(source_metadata.st_mode):
                    raise SystemExit("managed runtime source file is unsafe")
                while True:
                    chunk = os.read(source_descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
                    pending = memoryview(chunk)
                    while pending:
                        written = os.write(target_descriptor, pending)
                        if written <= 0:
                            raise SystemExit("managed runtime copy was interrupted")
                        pending = pending[written:]
                os.fsync(target_descriptor)
            finally:
                os.close(source_descriptor)
                os.close(target_descriptor)
            if size != int(row["size"]) or digest.hexdigest() != row["sha256"]:
                raise SystemExit("managed runtime changed while sealing")
            os.chmod(target, int(row["mode"]))
        manifest_descriptor = os.open(
            temporary / ".manifest.json",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o400,
        )
        with os.fdopen(manifest_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        verify_runtime(temporary, manifest, True)
        os.rename(temporary, runtime_destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    payload, manifest, executable = read_runtime_manifest(
        stored_manifest, expected_digest, True
    )
    verify_runtime(runtime_destination, manifest, True)
    return runtime_destination / executable

current = Path("/")
for part in base.parts[1:]:
    current = current / part
    if current.is_symlink():
        raise SystemExit("unsafe root runner store path")
    if current.exists():
        metadata = current.stat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise SystemExit("unsafe root runner store ownership")
if source_arg != "-":
    source_payloads = read_tree(Path(source_arg), False)
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    if base.is_symlink() or base.stat().st_uid != 0 or base.stat().st_mode & 0o077:
        raise SystemExit("unsafe root runner store")
    if not destination.exists():
        temporary = Path(tempfile.mkdtemp(prefix=".runner-", dir=base))
        try:
            for relative, payload in source_payloads.items():
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o500 if target.suffix in {".py", ".sh"} else 0o400,
                )
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            os.rename(temporary, destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
elif not destination.is_dir():
    raise SystemExit("approved root runner is unavailable")

read_tree(destination, True)
script = destination / "scripts/moradin_tooling_suite.py"
if sys.version_info < (3, 11):
    sealed_python = seal_runtime(
        runtime_source_arg,
        runtime_manifest_arg,
        runtime_expected,
        runtime_executable_arg,
    )
    environment = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": "/root",
        "MORADIN_FORGE_SEALED_PYTHON_DIGEST": runtime_expected,
        "MORADIN_FORGE_SEALED_PYTHON_EXECUTABLE": runtime_executable_arg,
    }
    os.execve(
        sealed_python,
        [sealed_python.as_posix(), "-B", script.as_posix(), *runner_args],
        environment,
    )
sys.path.insert(0, (destination / "scripts").as_posix())
sys.argv = [script.as_posix(), *runner_args]
runpy.run_path(script.as_posix(), run_name="__main__")
"""


class ToolingSuiteError(WorkstationError):
    """Raised when the Linux tooling suite cannot proceed safely."""


def _run(
    argv: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout: int = 30,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    arguments = list(argv)
    if runner is subprocess.run and arguments and arguments[0] in SYSTEM_COMMAND_PATHS:
        arguments[0] = _trusted_system_command(arguments[0]).as_posix()
    selected_environment = (
        env
        if env is not None
        else {
            "PATH": SAFE_PATH,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "HOME": Path.home().as_posix(),
        }
    )
    try:
        return runner(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=selected_environment,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as error:
        raise ToolingSuiteError(
            f"command timed out without completing: {argv[0]}"
        ) from error
    except OSError as error:
        raise ToolingSuiteError(
            f"command could not be executed safely: {argv[0]}"
        ) from error


def _trusted_system_command(command: str) -> Path:
    """Resolve a package command to a root-owned, immutable absolute path."""
    candidates = SYSTEM_COMMAND_PATHS.get(command, ())
    for raw in candidates:
        path = Path(raw)
        try:
            resolved = path.resolve(strict=True)
            metadata = resolved.stat()
        except OSError:
            continue
        if (
            resolved.is_file()
            and metadata.st_uid == 0
            and not metadata.st_mode & 0o022
            and os.access(resolved, os.X_OK)
        ):
            return resolved
    raise ToolingSuiteError(f"verified absolute command is unavailable: {command}")


def _known_system_command_paths(command: str) -> set[str]:
    paths = set(SYSTEM_COMMAND_PATHS.get(command, ()))
    for raw in SYSTEM_COMMAND_PATHS.get(command, ()):
        try:
            paths.add(Path(raw).resolve(strict=True).as_posix())
        except OSError:
            continue
    return paths


def _rpm_signature_verified(result: subprocess.CompletedProcess[str]) -> bool:
    signature_lines = [
        line.strip()
        for line in f"{result.stdout}\n{result.stderr}".splitlines()
        if re.search(r"\bsignatures?\b", line, flags=re.IGNORECASE)
    ]
    return result.returncode == 0 and bool(signature_lines) and all(
        re.search(r":\s*ok\s*$", line, flags=re.IGNORECASE) is not None
        for line in signature_lines
    )


def _read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _manager_for_release(release: dict[str, str]) -> str:
    os_id = release.get("ID", "").lower()
    id_like = set(release.get("ID_LIKE", "").lower().split())
    if os_id in {"ubuntu", "debian"} or id_like.intersection({"ubuntu", "debian"}):
        return "apt"
    if os_id in {"fedora", "rhel", "rocky", "almalinux"} or id_like.intersection(
        {"fedora", "rhel"}
    ):
        return "dnf"
    if os_id == "arch" or "arch" in id_like:
        return "pacman"
    return ""


def host_facts(
    *,
    os_release_path: Path = Path("/etc/os-release"),
    machine_id_path: Path = Path("/etc/machine-id"),
) -> dict[str, Any]:
    if platform.system().lower() != "linux":
        raise ToolingSuiteError(
            "the interactive tooling suite supports Linux and WSL only"
        )
    arch = normalized_arch()
    if arch not in SUPPORTED_ARCHES:
        raise ToolingSuiteError(f"unsupported Linux architecture: {arch}")
    release = _read_os_release(os_release_path)
    manager = _manager_for_release(release)
    if manager not in SUPPORTED_MANAGERS:
        raise ToolingSuiteError(
            "unsupported Linux distribution; expected apt, dnf, or pacman family"
        )
    try:
        machine_id = machine_id_path.read_text(encoding="utf-8").strip()
    except OSError:
        machine_id = "unavailable"
    fingerprint = hashlib.sha256(
        "\0".join(
            [
                machine_id,
                release.get("ID", "unknown"),
                release.get("VERSION_ID", "unknown"),
                arch,
            ]
        ).encode("utf-8")
    ).hexdigest()
    manager_command = {"apt": "apt-get", "dnf": "dnf", "pacman": "pacman"}[manager]
    manager_path = _trusted_system_command(manager_command).as_posix()
    return {
        "system": "linux",
        "arch": arch,
        "os_id": release.get("ID", "unknown").lower(),
        "os_version": release.get("VERSION_ID", "unknown"),
        "package_manager": manager,
        "package_manager_path": manager_path,
        "host_fingerprint_sha256": fingerprint,
    }


def build_doctor_report(
    *,
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate network-free installer blockers without mutating the host."""
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    try:
        detected = dict(facts or host_facts())
    except ToolingSuiteError as error:
        detected = {
            "system": platform.system().lower(),
            "arch": normalized_arch(),
            "os_id": "unsupported",
            "os_version": "unsupported",
            "package_manager": "",
            "package_manager_path": "",
            "host_fingerprint_sha256": "",
        }
        blockers.append({"id": "platform", "reason": str(error)})

    manager = str(detected.get("package_manager", ""))
    manager_path = str(detected.get("package_manager_path", ""))
    if manager in SUPPORTED_MANAGERS and not manager_path:
        manager_command = {"apt": "apt-get", "dnf": "dnf", "pacman": "pacman"}[manager]
        try:
            manager_path = _trusted_system_command(manager_command).as_posix()
            detected["package_manager_path"] = manager_path
        except ToolingSuiteError as error:
            blockers.append({"id": "package-manager", "reason": str(error)})
    if os.geteuid() == 0:
        blockers.append(
            {"id": "target-user", "reason": "run the suite as the target user, not root"}
        )
    home = Path.home()
    home_writable = (
        os.access(home, os.W_OK)
        if home.exists()
        else home.parent.is_dir() and os.access(home.parent, os.W_OK)
    )
    if not home_writable:
        blockers.append(
            {"id": "user-home", "reason": "the target user home is not writable"}
        )
    if any(command_present(item) for item in ("docker", "podman")):
        warnings.append(
            {
                "id": "container-state",
                "reason": "an existing container engine will be preserved",
            }
        )
    runtime = {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "implementation": platform.python_implementation(),
        "minimum": "3.11",
    }
    if sys.version_info < (3, 11):
        blockers.append({"id": "runtime", "reason": "Python 3.11 or newer is required"})
    payload: dict[str, Any] = {
        "version": DOCTOR_VERSION,
        "status": "blocked" if blockers else "ready",
        "platform": detected,
        "runtime": runtime,
        "target_uid": os.getuid(),
        "blockers": blockers,
        "warnings": warnings,
        "network_accessed": False,
        "privacy": "No workspace contents, hostnames, user paths, credentials, or telemetry are recorded.",
    }
    payload["doctor_sha256"] = _record_digest(payload, "doctor_sha256")
    return payload


def _protected_state(facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "container_engines": sorted(
            name for name in ("docker", "podman") if command_present(name)
        ),
        "package_manager": str(facts["package_manager"]),
        "package_manager_path": str(facts["package_manager_path"]),
        "target_uid": os.getuid(),
        "path_sha256": sha256_bytes(os.environ.get("PATH", "").encode()),
        "kernel_sha256": sha256_bytes(platform.release().encode()),
    }


def installer_manifest(forge_root: Path = REPO_ROOT) -> dict[str, str]:
    if forge_root.resolve() != REPO_ROOT.resolve():
        raise ToolingSuiteError(
            "--forge-root must be the checkout that owns this installer"
        )
    manifest: dict[str, str] = {}
    for relative in INSTALLER_FILES:
        path = forge_root / relative
        if path.is_symlink() or not path.is_file():
            raise ToolingSuiteError(
                f"installer file must be regular: {relative.as_posix()}"
            )
        manifest[relative.as_posix()] = sha256_file(path)
    return manifest


def installer_manifest_sha256(forge_root: Path = REPO_ROOT) -> str:
    return hashlib.sha256(
        canonical_json_bytes(installer_manifest(forge_root))
    ).hexdigest()


def installer_file_records(forge_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    hashes = installer_manifest(forge_root)
    return [
        {
            "path": relative,
            "sha256": digest,
            "size": (forge_root / relative).stat().st_size,
        }
        for relative, digest in sorted(hashes.items())
    ]


def _safe_environment(*, home: Path | None = None) -> dict[str, str]:
    environment = {
        "PATH": SAFE_PATH,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if home is not None:
        environment["HOME"] = home.as_posix()
    return environment


def _trusted_bootstrap_uv_path(*, required: bool) -> Path | None:
    raw = os.environ.get("MORADIN_FORGE_BOOTSTRAP_UV", "")
    if not raw:
        if required:
            raise ToolingSuiteError(
                "the checksum-verified Forge bootstrap uv runtime is unavailable"
            )
        return None
    data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    expected = data_root / "moradins-forge/bootstrap/uv" / BOOTSTRAP_UV_VERSION / "uv"
    candidate = Path(raw)
    try:
        resolved = candidate.resolve(strict=True)
        expected_resolved = expected.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise ToolingSuiteError(
            "the Forge bootstrap uv runtime is unavailable"
        ) from error
    expected_digest = BOOTSTRAP_UV_BINARY_SHA256.get(normalized_arch(), "")
    if (
        candidate.is_symlink()
        or resolved != expected_resolved
        or not resolved.is_file()
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o022
        or not expected_digest
        or sha256_file(resolved) != expected_digest
    ):
        raise ToolingSuiteError(
            "the Forge bootstrap uv runtime failed ownership or integrity checks"
        )
    return resolved


def _trusted_system_python(minimum: tuple[int, int]) -> Path:
    for candidate in (
        Path("/usr/bin/python3.12"),
        Path("/usr/bin/python3.11"),
        Path("/usr/bin/python3.10"),
        Path("/usr/bin/python3.9"),
        Path("/usr/bin/python3"),
    ):
        if not candidate.exists() or candidate.is_dir():
            continue
        try:
            resolved = candidate.resolve(strict=True)
            metadata = resolved.stat()
        except OSError:
            continue
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            continue
        result = _run(
            [
                resolved.as_posix(),
                "-c",
                (
                    "import sys; raise SystemExit(sys.version_info < "
                    f"({minimum[0]}, {minimum[1]}))"
                ),
            ],
            env=_safe_environment(home=Path("/root")),
        )
        if result.returncode == 0:
            return resolved
    raise ToolingSuiteError(
        "root phase requires a root-owned, non-writable Python "
        f"{minimum[0]}.{minimum[1]}+ under /usr/bin"
    )


def _trusted_root_bootstrap_python() -> Path:
    return _trusted_system_python((3, 9))


def _trusted_root_python() -> Path:
    sealed_digest = os.environ.get("MORADIN_FORGE_SEALED_PYTHON_DIGEST", "")
    sealed_executable = os.environ.get(
        "MORADIN_FORGE_SEALED_PYTHON_EXECUTABLE", ""
    )
    if sealed_digest or sealed_executable:
        if (
            not re.fullmatch(r"[0-9a-f]{64}", sealed_digest)
            or not sealed_executable
        ):
            raise ToolingSuiteError("sealed root Python binding is malformed")
        relative = Path(sealed_executable)
        if relative.is_absolute() or ".." in relative.parts:
            raise ToolingSuiteError("sealed root Python path is unsafe")
        expected = Path("/var/lib/moradins-forge/python") / sealed_digest / relative
        try:
            resolved = expected.resolve(strict=True)
            metadata = resolved.stat()
        except OSError as error:
            raise ToolingSuiteError("sealed root Python is unavailable") from error
        current = Path("/")
        for part in resolved.parts[1:]:
            current = current / part
            if current.is_symlink():
                raise ToolingSuiteError("sealed root Python path contains a link")
            current_metadata = current.stat()
            if current_metadata.st_uid != 0 or current_metadata.st_mode & 0o022:
                raise ToolingSuiteError("sealed root Python ownership is unsafe")
        if not resolved.is_file() or metadata.st_mode & 0o111 == 0:
            raise ToolingSuiteError("sealed root Python is not executable")
        return resolved
    return _trusted_system_python((3, 11))


def _trusted_sudo() -> Path:
    for candidate in (Path("/usr/bin/sudo"), Path("/bin/sudo")):
        try:
            resolved = candidate.resolve(strict=True)
            metadata = resolved.stat()
        except OSError:
            continue
        if (
            resolved.is_file()
            and os.access(resolved, os.X_OK)
            and metadata.st_uid == 0
            and not metadata.st_mode & 0o022
        ):
            return resolved
    raise ToolingSuiteError("sudo must be a root-owned, non-writable system executable")


def _root_runtime_arguments(
    bootstrap_python: Path,
    *,
    sealed_digest: str = "",
    sealed_executable: str = "",
) -> list[str]:
    modern = _run(
        [
            bootstrap_python.as_posix(),
            "-c",
            "import sys; raise SystemExit(sys.version_info < (3, 11))",
        ],
        env=_safe_environment(home=Path("/root")),
    )
    if modern.returncode == 0:
        return ["-", "-", "-", "-"]
    if sealed_digest or sealed_executable:
        if not re.fullmatch(r"[0-9a-f]{64}", sealed_digest):
            raise ToolingSuiteError("sealed Python runtime digest is malformed")
        relative = Path(sealed_executable)
        if (
            not sealed_executable
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise ToolingSuiteError("sealed Python runtime executable is malformed")
        return ["-", "-", sealed_digest, relative.as_posix()]
    source = Path(os.environ.get("MORADIN_FORGE_ROOT_PYTHON_SOURCE", ""))
    manifest = Path(os.environ.get("MORADIN_FORGE_ROOT_PYTHON_MANIFEST", ""))
    digest = os.environ.get("MORADIN_FORGE_ROOT_PYTHON_MANIFEST_SHA256", "")
    executable = os.environ.get("MORADIN_FORGE_ROOT_PYTHON_EXECUTABLE", "")
    relative = Path(executable)
    if (
        not source.is_absolute()
        or source.is_symlink()
        or not source.is_dir()
        or not manifest.is_absolute()
        or manifest.is_symlink()
        or not manifest.is_file()
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or sha256_file(manifest) != digest
        or not executable
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise ToolingSuiteError(
            "Python 3.9/3.10 root bootstrap requires the kit-bound managed runtime"
        )
    return [source.as_posix(), manifest.as_posix(), digest, relative.as_posix()]


def _assert_trusted_root_python() -> None:
    expected = _trusted_root_python()
    try:
        running = Path(sys.executable).resolve(strict=True)
    except OSError as error:
        raise ToolingSuiteError("root Python interpreter cannot be verified") from error
    if running != expected:
        raise ToolingSuiteError(
            "root phase is not running under the trusted system Python"
        )


def _package_name(spec: ToolSpec, manager: str) -> str:
    return {
        "apt": spec.apt_package,
        "dnf": spec.dnf_package,
        "pacman": spec.pacman_package,
    }.get(manager, "")


def _package_versions(
    package: str,
    manager: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, str]:
    if not package or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.:@/-]*", package):
        return "", ""
    installed = ""
    candidate = ""
    if manager == "apt":
        installed_result = _run(
            ["dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${Version}", package],
            runner=runner,
        )
        if installed_result.returncode == 0 and installed_result.stdout.startswith(
            "ii "
        ):
            installed = installed_result.stdout.split("\t", 1)[-1].strip()
        policy = _run(["apt-cache", "policy", package], runner=runner)
        if policy.returncode == 0:
            for line in policy.stdout.splitlines():
                if line.strip().startswith("Candidate:"):
                    value = line.split(":", 1)[1].strip()
                    candidate = "" if value == "(none)" else value
                    break
    elif manager == "dnf":
        installed_result = _run(
            ["rpm", "-q", "--qf", "%{EVR}", package],
            runner=runner,
        )
        if installed_result.returncode == 0:
            installed = installed_result.stdout.strip()
        query = _run(
            [
                "dnf",
                "--cacheonly",
                "--quiet",
                "repoquery",
                "--latest-limit",
                "1",
                "--qf",
                "%{EVR}",
                package,
            ],
            runner=runner,
        )
        if query.returncode == 0:
            candidate = next(
                (line.strip() for line in query.stdout.splitlines() if line.strip()),
                "",
            )
    elif manager == "pacman":
        installed_result = _run(["pacman", "-Q", package], runner=runner)
        if installed_result.returncode == 0:
            fields = installed_result.stdout.strip().split()
            installed = fields[-1] if len(fields) >= 2 else ""
        query = _run(["pacman", "-Si", package], runner=runner)
        if query.returncode == 0:
            for line in query.stdout.splitlines():
                if line.startswith("Version") and ":" in line:
                    candidate = line.split(":", 1)[1].strip()
                    break
    return installed, candidate


def _human_size_bytes(value: str) -> int:
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?i?B)$", value.strip(), re.I)
    if not match:
        return 0
    multipliers = {
        "B": 1,
        "KB": 1000,
        "KIB": 1024,
        "MB": 1000**2,
        "MIB": 1024**2,
        "GB": 1000**3,
        "GIB": 1024**3,
        "TB": 1000**4,
        "TIB": 1024**4,
    }
    return int(float(match.group(1)) * multipliers[match.group(2).upper()])


def _package_sizes(
    package: str,
    version: str,
    manager: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[int, int]:
    download = 0
    installed = 0
    if manager == "apt":
        result = _run(
            ["apt-cache", "show", "--no-all-versions", f"{package}={version}"],
            runner=runner,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("Size:"):
                    download = int(line.split(":", 1)[1].strip() or 0)
                elif line.startswith("Installed-Size:"):
                    installed = int(line.split(":", 1)[1].strip() or 0) * 1024
    elif manager == "dnf":
        result = _run(
            [
                "dnf",
                "--cacheonly",
                "--quiet",
                "repoquery",
                "--latest-limit",
                "1",
                "--qf",
                "%{downloadsize}|%{installsize}",
                package,
            ],
            runner=runner,
        )
        if result.returncode == 0:
            fields = next(
                (line.split("|") for line in result.stdout.splitlines() if "|" in line),
                [],
            )
            if len(fields) == 2 and all(field.strip().isdigit() for field in fields):
                download, installed = (int(field.strip()) for field in fields)
    elif manager == "pacman":
        result = _run(["pacman", "-Si", package], runner=runner)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("Download Size") and ":" in line:
                    download = _human_size_bytes(line.split(":", 1)[1])
                elif line.startswith("Installed Size") and ":" in line:
                    installed = _human_size_bytes(line.split(":", 1)[1])
    return download, installed


def _epel_enabled(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    result = _run(
        ["dnf", "--cacheonly", "--quiet", "repolist", "--enabled", "epel"],
        runner=runner,
    )
    return result.returncode == 0 and any(
        line.split(maxsplit=1)[0] == "epel"
        for line in result.stdout.splitlines()
        if line.strip()
    )


def _normalized_version_output(text: str) -> str:
    match = re.search(
        r"(?<![A-Za-z0-9])v?(\d+(?:\.\d+){1,3}(?:[-+._][A-Za-z0-9.-]+)?)", text
    )
    return match.group(1) if match else "present"


def _trusted_detected_command(command: str) -> Path | None:
    found = shutil.which(command)
    if not found:
        return None
    candidate = Path(found)
    try:
        resolved = candidate.resolve(strict=True)
        metadata = resolved.stat()
    except OSError:
        return None
    if not resolved.is_file() or metadata.st_mode & 0o022:
        return None
    system_roots = tuple(
        Path(path).resolve()
        for path in (
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        )
    )
    data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    user_roots = (
        (data_root / "moradins-forge/tools").resolve(),
        (data_root / "moradins-forge/bootstrap").resolve(),
    )
    if any(resolved.is_relative_to(root) for root in system_roots):
        return resolved if metadata.st_uid == 0 else None
    if any(resolved.is_relative_to(root) for root in user_roots):
        return resolved if metadata.st_uid == os.getuid() else None
    return None


def _command_version(
    spec: ToolSpec,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    selected: tuple[list[str], Path] | None = None
    untrusted_present = False
    for argv in _suite_verification_options(spec):
        if shutil.which(argv[0]) is None:
            continue
        trusted = _trusted_detected_command(argv[0])
        if trusted is not None:
            selected = (argv, trusted)
            break
        untrusted_present = True
    if selected is None:
        return "present-unverified" if untrusted_present else ""
    argv, trusted = selected
    argv = [trusted.as_posix(), *argv[1:]]
    environment = _safe_environment(home=Path.home())
    environment["PATH"] = (
        (Path.home() / ".local/bin").as_posix() + os.pathsep + SAFE_PATH
    )
    result = _run(argv, runner=runner, env=environment, timeout=20)
    if result.returncode != 0:
        if Path(argv[0]).name == "test":
            return ""
        return "present"
    return _normalized_version_output((result.stdout + "\n" + result.stderr)[:4096])


def _suite_verification_options(spec: ToolSpec) -> list[list[str]]:
    if spec.verification_argv:
        return [list(spec.verification_argv)]
    commands = dict.fromkeys((*spec.command_candidates, spec.command))
    return [[command, "--version"] for command in commands if command]


def _suite_verification_argv(spec: ToolSpec) -> list[str]:
    options = _suite_verification_options(spec)
    return next(
        (argv for argv in options if shutil.which(argv[0]) is not None),
        options[0] if options else [],
    )


def _suite_verification_is_catalog_owned(spec: ToolSpec, argv: object) -> bool:
    options = _suite_verification_options(spec)
    return argv in options if options else argv == []


def _version_matches(installed: str, resolved: str) -> bool:
    return bool(
        installed and resolved and installed.lstrip("v") == resolved.lstrip("v")
    )


def _command_is_forge_owned(spec: ToolSpec) -> bool:
    if not spec.command:
        return False
    found = shutil.which(spec.command)
    if not found:
        return False
    resolved = Path(found).resolve()
    data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    owned_roots = [
        (data_root / "moradins-forge/tools").resolve(),
        (data_root / "moradins-forge/bootstrap").resolve(),
        Path("/opt/moradins-forge/tools").resolve(),
    ]
    return any(resolved.is_relative_to(root) for root in owned_roots)


def _selected_specs(
    profile: str,
    *,
    include_tools: Sequence[str],
    exclude_tools: Sequence[str],
    container_engine: str,
) -> list[ToolSpec]:
    if profile not in SUPPORTED_PROFILES:
        raise ToolingSuiteError(f"unsupported tooling-suite profile: {profile}")
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    unknown = sorted((set(include_tools) | set(exclude_tools)) - set(catalog))
    if unknown:
        raise ToolingSuiteError("unknown tooling ids: " + ", ".join(unknown))
    if profile == "custom" and not include_tools:
        raise ToolingSuiteError("custom planning requires at least one --select tool")
    if profile == "practical":
        selected = {spec.id for spec in TOOL_CATALOG if "practical" in spec.profiles}
    elif profile == "extended":
        selected = {
            spec.id
            for spec in TOOL_CATALOG
            if set(spec.profiles).intersection({"practical", "extended"})
        }
        selected.discard("docker")
        selected.discard("podman")
        podman_present = command_present("podman")
        existing_engines = [
            tool for tool in ("podman", "docker") if command_present(tool)
        ]
        if existing_engines:
            selected.update(existing_engines)
        elif container_engine in {"podman", "docker"}:
            selected.add(container_engine)
        else:
            raise ToolingSuiteError(
                "extended planning requires --container-engine podman or docker "
                "when no container engine is installed"
            )
        if "podman" in selected and not podman_present:
            selected.update({"rootless_uidmap", "rootless_network", "rootless_storage"})
    else:
        selected = set()
    selected.update(include_tools)
    selected.difference_update(exclude_tools)
    return sorted(
        (catalog[tool_id] for tool_id in selected),
        key=lambda item: (item.category, item.id),
    )


def _workspace_evidence(
    workspaces: Sequence[Path],
) -> tuple[list[Path], list[dict[str, Any]], set[str]]:
    if not workspaces:
        return [], [], set()
    approved = sorted({ensure_approved_workspace(path) for path in workspaces})
    repositories = discover_repositories(approved)
    rows: list[dict[str, Any]] = []
    capabilities: set[str] = set()
    for repository in repositories:
        inspection = inspect_repository_capabilities(repository)
        capabilities.update(inspection["capabilities"])
        rows.append(
            {
                "path": repository.as_posix(),
                "capabilities": inspection["capabilities"],
                "markers": inspection["markers"],
            }
        )
    return approved, rows, capabilities


def _manual_action(spec: ToolSpec, reason: str) -> dict[str, Any]:
    return {
        "kind": "manual",
        "tool_id": spec.id,
        "package": "",
        "version": "",
        "manager": "",
        "repository": "",
        "requires_elevation": False,
        "auto_execute": False,
        "reason": reason,
    }


def _preserved_action(spec: ToolSpec, reason: str) -> dict[str, Any]:
    action = _manual_action(spec, reason)
    action["kind"] = "protected-existing"
    return action


def _resolved_package(package: str, manager: str, version: str) -> dict[str, Any]:
    return {
        "version": version,
        "source": manager,
        "source_url": "",
        "asset_url": "",
        "asset_filename": "",
        "sha256": "",
        "artifact_sha256s": [],
        "trust": "signed-package-manager",
        "checked_at": utc_now(),
        "cache": "fresh",
        "package": package,
    }


def _automatic_asset(resolved: dict[str, Any]) -> bool:
    return bool(
        resolved.get("cache") in {"fresh", "refreshed"}
        and resolved.get("asset_url")
        and re.fullmatch(r"[0-9a-f]{64}", str(resolved.get("sha256", "")))
        and 0 < int(resolved.get("asset_size", 0) or 0) <= MAX_ASSET_BYTES
        and resolved.get("trust") in {"official-release-digest", "pypi-hash-verified"}
    )


def _github_source_is_catalog_owned(spec: ToolSpec, resolved: dict[str, Any]) -> bool:
    if not spec.github_repo:
        return False
    repository = spec.github_repo.lower()
    asset = urllib.parse.urlsplit(str(resolved.get("asset_url", "")))
    source = urllib.parse.urlsplit(str(resolved.get("source_url", "")))
    expected_asset_prefix = f"/{repository}/releases/download/"
    github_source = source.hostname == "github.com" and source.path.lower().startswith(
        f"/{repository}/releases/tag/"
    )
    api_source = (
        source.hostname == "api.github.com"
        and source.path.lower() == f"/repos/{repository}/releases/latest"
    )
    return bool(
        asset.hostname == "github.com"
        and asset.path.lower().startswith(expected_asset_prefix)
        and (github_source or api_source)
        and Path(asset.path).name == str(resolved.get("asset_filename", ""))
    )


def _tool_row(
    spec: ToolSpec,
    *,
    facts: dict[str, Any],
    cache_path: Path,
    refresh_versions: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    resolver: Callable[..., dict[str, Any]],
    epel_available: bool,
) -> dict[str, Any]:
    manager = str(facts["package_manager"])
    command_version = _command_version(spec, runner=runner)
    package = _package_name(spec, manager)
    package_installed, package_candidate = _package_versions(
        package,
        manager,
        runner=runner,
    )
    present = bool(command_version or package_installed)
    action = _manual_action(spec, "no verified automatic installer is available")
    resolved: dict[str, Any] = {
        "version": command_version or package_installed or "unknown",
        "source": "installed" if present else "unresolved",
        "trust": "local-detection" if present else "manual-review",
        "cache": "fresh",
    }
    status = "current" if present else "manual"

    if spec.protected_existing and present:
        action = _preserved_action(
            spec,
            "existing container engine and configuration are preserved",
        )
        status = "preserved"
    elif spec.manual_only:
        action = _manual_action(
            spec, "capability requires environment-specific human review"
        )
        status = "manual"
    elif spec.install_strategy == "uv-python":
        version_match = re.match(r"^(\d+)\.(\d+)", command_version)
        command_is_312 = bool(
            version_match
            and (int(version_match.group(1)), int(version_match.group(2))) >= (3, 12)
        )
        if command_is_312:
            resolved = {
                "version": command_version,
                "source": "installed",
                "trust": "local-detection",
                "cache": "fresh",
            }
            action = _manual_action(spec, "Python 3.12+ is already available")
            action["kind"] = "none"
            status = "current"
        else:
            resolved = {
                "version": "3.12.8",
                "source": "manual-runtime-prerequisite",
                "trust": "manual-review",
                "cache": "fresh",
            }
            action = _manual_action(
                spec,
                "Python 3.12 must be bootstrapped explicitly before a full-profile plan",
            )
            status = "manual"
    elif spec.python_package:
        resolved = resolver(
            spec,
            cache_path=cache_path,
            refresh=refresh_versions,
            system="linux",
            arch=str(facts["arch"]),
            prefer_python=True,
        )
        version = str(resolved.get("version", ""))
        if _version_matches(command_version, version):
            status = "current"
            action = _manual_action(
                spec, "Forge tool is already at the planned version"
            )
            action["kind"] = "none"
        elif present and not _command_is_forge_owned(spec):
            status = "preserved"
            action = _preserved_action(
                spec,
                "an unmanaged existing executable will not be overwritten",
            )
        elif (
            resolved.get("cache") in {"fresh", "refreshed"}
            and resolved.get("source") == "pypi"
            and resolved.get("trust") == "pypi-hash-verified"
            and (resolved.get("artifact_sha256s") or resolved.get("sha256"))
            and version not in {"", "latest-stable"}
        ):
            action = {
                **_manual_action(spec, "isolated Forge-owned uv tool environment"),
                "kind": "user-local",
                "version": version,
                "package": f"{spec.python_package}=={version}",
                "auto_execute": True,
            }
            status = "upgrade" if present else "install"
    elif (
        package
        and package_candidate
        and not (
            manager == "dnf"
            and spec.dnf_repository == "epel"
            and facts["os_id"] != "fedora"
            and not epel_available
        )
    ):
        resolved = _resolved_package(package, manager, package_candidate)
        download_size, installed_size = _package_sizes(
            package,
            package_candidate,
            manager,
            runner=runner,
        )
        resolved.update(
            {
                "download_size": download_size,
                "installed_size": installed_size,
            }
        )
        if package_installed == package_candidate:
            status = "current"
            action = _manual_action(
                spec, "signed package is already at the planned version"
            )
            action["kind"] = "none"
        elif present and not package_installed:
            status = "preserved"
            action = _preserved_action(
                spec,
                "an unmanaged existing executable will not be overwritten",
            )
        else:
            action = {
                **_manual_action(spec, "exact signed operating-system package"),
                "kind": "system-package",
                "package": package,
                "version": package_candidate,
                "manager": manager,
                "repository": spec.dnf_repository,
                "requires_elevation": True,
                "auto_execute": True,
                "previous_version": package_installed,
                "rollback_closure": (
                    "required-at-apply" if package_installed else "remove-owned-package"
                ),
            }
            status = "upgrade" if package_installed else "install"
    else:
        resolved = resolver(
            spec,
            cache_path=cache_path,
            refresh=refresh_versions,
            system="linux",
            arch=str(facts["arch"]),
            prefer_python=False,
        )
        if _automatic_asset(resolved):
            if _version_matches(command_version, str(resolved.get("version", ""))):
                status = "current"
                action = _manual_action(
                    spec, "Forge tool is already at the planned version"
                )
                action["kind"] = "none"
            elif present and not _command_is_forge_owned(spec) and spec.id != "uv":
                status = "preserved"
                action = _preserved_action(
                    spec,
                    "an unmanaged existing executable will not be overwritten",
                )
            else:
                action = {
                    **_manual_action(spec, "checksum-verified official release asset"),
                    "kind": "forge-user" if spec.id == "uv" else "forge-global",
                    "version": str(resolved["version"]),
                    "requires_elevation": spec.id != "uv",
                    "auto_execute": True,
                    "rollback_closure": "atomic-version-switch",
                }
                status = "upgrade" if present else "install"
        elif present:
            status = "preserved"
            action = _preserved_action(
                spec,
                "the existing executable is preserved because verified release assets are unavailable",
            )
        else:
            status = "manual"
            action = _manual_action(
                spec, "no verified automatic installer is available"
            )

    return {
        "id": spec.id,
        "label": spec.label,
        "command": spec.command,
        "category": spec.category,
        "reason": spec.reason,
        "profiles": list(spec.profiles),
        "required": spec.required,
        "present": present,
        "installed_version": command_version or package_installed,
        "status": status,
        "resolved": resolved,
        "install_action": action,
        "verification_command": _suite_verification_argv(spec),
    }


def build_suite_plan(
    *,
    forge_root: Path,
    profile: str,
    workspaces: Sequence[Path] = (),
    include_tools: Sequence[str] = (),
    exclude_tools: Sequence[str] = (),
    container_engine: str = "",
    approved_repositories: Sequence[str] = (),
    approve_arch_system_upgrade: bool = False,
    refresh_versions: bool = False,
    facts: dict[str, Any] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    resolver: Callable[..., dict[str, Any]] = resolve_latest_version,
) -> dict[str, Any]:
    injected_facts = facts is not None
    facts = dict(facts or host_facts())
    if facts.get("system") != "linux" or facts.get("arch") not in SUPPORTED_ARCHES:
        raise ToolingSuiteError(
            "tooling-suite plan requires supported Linux host facts"
        )
    manager = str(facts.get("package_manager", ""))
    if manager not in SUPPORTED_MANAGERS:
        raise ToolingSuiteError("tooling-suite plan has an unsupported package manager")
    if not facts.get("package_manager_path"):
        manager_command = {"apt": "apt-get", "dnf": "dnf", "pacman": "pacman"}[manager]
        if injected_facts:
            facts["package_manager_path"] = SYSTEM_COMMAND_PATHS[manager_command][0]
        else:
            facts["package_manager_path"] = _trusted_system_command(
                manager_command
            ).as_posix()
    doctor = build_doctor_report(facts=facts)
    approved, repositories, capabilities = _workspace_evidence(workspaces)
    specs = _selected_specs(
        profile,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        container_engine=container_engine,
    )
    evidence_recommendations = sorted(
        spec.id
        for spec in TOOL_CATALOG
        if spec.id not in {item.id for item in specs}
        and capabilities.intersection(spec.triggers)
    )
    epel_required = bool(
        manager == "dnf"
        and facts.get("os_id") != "fedora"
        and any(spec.dnf_repository == "epel" for spec in specs)
    )
    epel_available = not epel_required or _epel_enabled(runner=runner)
    repository_approval = "epel" in set(approved_repositories)
    cache_path = (
        forge_root / "Harness/artifacts/control/tooling_plans/version_cache.json"
    )
    rows = [
        _tool_row(
            spec,
            facts=facts,
            cache_path=cache_path,
            refresh_versions=refresh_versions,
            runner=runner,
            resolver=resolver,
            epel_available=epel_available,
        )
        for spec in specs
    ]
    repository_bootstrap: dict[str, Any] | None = None
    blockers: list[str] = []
    status = "ready"
    if epel_required and not epel_available:
        if not repository_approval:
            status = "needs-repository-approval"
            blockers.append(
                "EPEL is required by selected packages and needs separate approval"
            )
        else:
            installed, candidate = _package_versions(
                "epel-release", "dnf", runner=runner
            )
            if not candidate:
                status = "blocked"
                blockers.append(
                    "a signed epel-release candidate is unavailable from configured repositories"
                )
            elif installed == candidate:
                status = "blocked"
                blockers.append(
                    "epel-release is installed but EPEL is not enabled; review the "
                    "repository configuration before retrying"
                )
            else:
                status = "repository-bootstrap"
                repository_bootstrap = {
                    "id": "epel",
                    "package": "epel-release",
                    "version": candidate,
                    "previous_version": installed,
                    "trust": "signed-package-manager",
                    "requires_replan": True,
                }
    root_actions = [
        row["install_action"]
        for row in rows
        if row["install_action"]["kind"] in {"system-package", "forge-global"}
    ]
    if manager == "pacman" and root_actions and not approve_arch_system_upgrade:
        status = "needs-arch-upgrade-approval"
        blockers.append(
            "Arch package actions require a separately approved full synchronization"
        )
    manual = [row["id"] for row in rows if row["status"] == "manual"]
    required_manual = [
        row["id"]
        for row in rows
        if row["required"] and not row["present"] and row["status"] == "manual"
    ]
    if required_manual and status == "ready":
        status = "blocked"
        blockers.append(
            "required tools lack a verified automatic installation: "
            + ", ".join(required_manual)
        )
    if doctor["status"] != "ready":
        status = "blocked"
        blockers.extend(
            f"doctor/{item['id']}: {item['reason']}" for item in doctor["blockers"]
        )
    python_lock = build_python_tool_lock(
        [
            {
                **row,
                "present": row["install_action"]["kind"] != "user-local",
            }
            for row in rows
        ],
        system="linux",
        arch=str(facts["arch"]),
        python_version="3.12",
        uv_command=_trusted_bootstrap_uv_path(required=False),
        environment=_safe_environment(home=Path.home()),
        runner=runner,
    )
    if (
        any(row["install_action"]["kind"] == "user-local" for row in rows)
        and python_lock.get("status") != "ready"
    ):
        if status == "ready":
            status = "blocked"
        blockers.append(
            "selected Python tools lack a complete hash-frozen wheel closure"
        )
    now = datetime.now(tz=UTC).replace(microsecond=0)
    verified_download_bytes = sum(
        int(row["resolved"].get("asset_size", 0) or 0)
        for row in rows
        if row["install_action"]["kind"] in {"forge-user", "forge-global"}
    ) + sum(int(asset.get("size", 0) or 0) for asset in python_lock.get("assets", []))
    package_download_bytes = sum(
        int(row["resolved"].get("download_size", 0) or 0)
        for row in rows
        if row["install_action"]["kind"] == "system-package"
    )
    package_installed_bytes = sum(
        int(row["resolved"].get("installed_size", 0) or 0)
        for row in rows
        if row["install_action"]["kind"] == "system-package"
    )
    package_size_unknown = sum(
        1
        for row in rows
        if row["install_action"]["kind"] == "system-package"
        and not int(row["resolved"].get("installed_size", 0) or 0)
    )
    transitions = [
        {
            "tool_id": row["id"],
            "from": row["installed_version"] or "absent",
            "to": str(
                row["install_action"].get("version")
                or row["resolved"].get("version")
                or row["status"]
            ),
            "action": row["install_action"]["kind"],
            "rollback": row["install_action"].get("rollback_closure", "not-mutating"),
        }
        for row in rows
    ]
    package_simulation = [
        {
            "tool_id": row["id"],
            "manager": row["install_action"]["manager"],
            "package": row["install_action"]["package"],
            "version": row["install_action"]["version"],
            "operation": row["status"],
        }
        for row in rows
        if row["install_action"]["kind"] == "system-package"
    ]
    prepared_assets = sorted(
        [
            {
                "tool_id": row["id"],
                "sha256": row["resolved"]["sha256"],
                "size": int(row["resolved"].get("asset_size", 0) or 0),
            }
            for row in rows
            if row["install_action"]["kind"] in {"forge-user", "forge-global"}
        ]
        + [
            {
                "tool_id": f"python:{asset['package']}",
                "sha256": asset["sha256"],
                "size": int(asset.get("size", 0) or 0),
            }
            for asset in python_lock.get("assets", [])
        ],
        key=lambda item: item["tool_id"],
    )
    protected_state = _protected_state(facts)
    payload: dict[str, Any] = {
        "version": SUITE_PLAN_VERSION,
        "generated_at": now.isoformat(),
        "expires_at": (now + PLAN_TTL).isoformat(),
        "profile": profile,
        "selected_tools": [spec.id for spec in specs],
        "explicitly_included_tools": sorted(set(include_tools)),
        "explicitly_excluded_tools": sorted(set(exclude_tools)),
        "container_engine": container_engine,
        "platform": facts,
        "target_uid": os.getuid(),
        "doctor": doctor,
        "doctor_sha256": doctor["doctor_sha256"],
        "catalog_version": CATALOG_VERSION,
        "runtime": doctor["runtime"],
        "approved_workspaces": [path.as_posix() for path in approved],
        "repositories": repositories,
        "capabilities": sorted(capabilities),
        "evidence_recommendations": evidence_recommendations,
        "approved_repositories": sorted(set(approved_repositories)),
        "approve_arch_system_upgrade": approve_arch_system_upgrade,
        "repository_bootstrap": repository_bootstrap,
        "tools": rows,
        "python_tool_lock": python_lock,
        "root_actions": root_actions,
        "package_simulation": package_simulation,
        "transition_matrix": transitions,
        "prepared_assets": prepared_assets,
        "protected_state_sha256": sha256_bytes(
            canonical_json_bytes(protected_state)
        ),
        "rollback_closure": {
            "root_actions": [
                {
                    "tool_id": action["tool_id"],
                    "closure": action.get("rollback_closure", ""),
                }
                for action in root_actions
            ],
            "user_actions": [
                {
                    "tool_id": row["id"],
                    "closure": row["install_action"].get(
                        "rollback_closure", "atomic-version-switch"
                    ),
                }
                for row in rows
                if row["install_action"]["kind"] in {"forge-user", "user-local"}
            ],
        },
        "estimated_disk": {
            "verified_download_bytes": verified_download_bytes,
            "system_package_download_bytes": package_download_bytes,
            "system_package_installed_bytes": package_installed_bytes,
            "system_package_size_unknown": package_size_unknown,
            "scope": "selected packages only; signed dependency deltas are shown by the manager before commit",
        },
        "manual_tools": manual,
        "blockers": blockers,
        "status": status,
        "catalog_sha256": sha256_file(CATALOG_PATH),
        "installer_files": installer_file_records(forge_root),
        "installer_manifest_sha256": installer_manifest_sha256(forge_root),
        "privacy": (
            "Local-only plan; no project contents, credentials, prompts, logs, "
            "raw machine identifiers, or telemetry are collected or uploaded."
        ),
    }
    validate_suite_plan_contents(payload)
    payload["plan_sha256"] = plan_digest(payload)
    return payload


def suite_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Moradin Forge Linux Tooling Suite Plan",
        "",
        f"- profile: `{plan['profile']}`",
        f"- platform: `{plan['platform']['os_id']}/{plan['platform']['arch']}`",
        f"- package manager: `{plan['platform']['package_manager']}`",
        f"- status: `{plan['status']}`",
        f"- expires_at: `{plan['expires_at']}`",
        f"- plan_sha256: `{plan['plan_sha256']}`",
        f"- verified download bytes: `{plan['estimated_disk']['verified_download_bytes']}`",
        f"- OS package download bytes: `{plan['estimated_disk']['system_package_download_bytes']}`",
        f"- OS package installed bytes: `{plan['estimated_disk']['system_package_installed_bytes']}`",
        f"- OS package sizes unavailable: `{plan['estimated_disk']['system_package_size_unknown']}`",
        "",
        "## Exact Actions",
        "",
    ]
    for row in plan["tools"]:
        action = row["install_action"]
        version = str(
            action.get("version") or row["resolved"].get("version", "unknown")
        )
        detail = str(action.get("reason", ""))
        if action["kind"] == "system-package":
            detail = (
                f"{action['manager']} `{action['package']}={version}`; "
                f"previous `{action.get('previous_version') or 'absent'}`; "
                f"repository `{action.get('repository') or 'configured-default'}`"
            )
        elif action["kind"] in {"forge-user", "forge-global"}:
            detail = (
                f"`{row['resolved']['asset_filename']}`; "
                f"sha256 `{row['resolved']['sha256']}`"
            )
        elif action["kind"] == "user-local":
            detail = f"offline wheel closure for `{action['package']}`"
        lines.append(
            f"- `{row['id']}`: `{row['status']}` via `{action['kind']}` at `{version}` — {detail}"
        )
    if plan.get("repository_bootstrap"):
        repository = plan["repository_bootstrap"]
        lines.extend(
            [
                "",
                "## Repository Bootstrap",
                "",
                f"- `{repository['id']}` via signed `{repository['package']}={repository['version']}`",
                "- The suite must be replanned after this separately approved transaction.",
            ]
        )
    lines.extend(["", "## Rollback and Privacy", ""])
    lines.append(
        "- Existing OS packages upgrade only when rollback closure is available at apply time."
    )
    lines.append("- Forge-owned binaries switch atomically and retain one predecessor.")
    lines.append("- The installer performs no telemetry or project-content upload.")
    if plan["manual_tools"]:
        lines.extend(["", "## Manual or Specialized", ""])
        lines.append("- " + ", ".join(f"`{item}`" for item in plan["manual_tools"]))
    if plan["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in plan["blockers"])
    return "\n".join(lines) + "\n"


def write_suite_plan(plan: dict[str, Any], output: Path) -> dict[str, str]:
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise ToolingSuiteError(f"plan output must be a regular file: {output}")
    write_json(output, plan)
    markdown = output.with_suffix(".md")
    markdown.write_text(suite_plan_markdown(plan), encoding="utf-8")
    return {"json": output.as_posix(), "markdown": markdown.as_posix()}


def validate_suite_plan_contents(plan: dict[str, Any]) -> None:
    platform_row = plan.get("platform", {})
    if (
        not isinstance(platform_row, dict)
        or platform_row.get("system") != "linux"
        or platform_row.get("arch") not in SUPPORTED_ARCHES
        or platform_row.get("package_manager") not in SUPPORTED_MANAGERS
        or platform_row.get("package_manager_path")
        not in set().union(
            *(
                _known_system_command_paths(command)
                for command in ("apt-get", "dnf", "pacman")
            )
        )
    ):
        raise ToolingSuiteError("tooling-suite platform binding is unsupported")
    doctor = plan.get("doctor", {})
    if (
        plan.get("catalog_version") != CATALOG_VERSION
        or not isinstance(doctor, dict)
        or doctor.get("version") != DOCTOR_VERSION
        or doctor.get("doctor_sha256") != _record_digest(doctor, "doctor_sha256")
        or plan.get("doctor_sha256") != doctor.get("doctor_sha256")
        or plan.get("runtime") != doctor.get("runtime")
    ):
        raise ToolingSuiteError("tooling-suite doctor or catalog binding is malformed")
    for field in (
        "package_simulation",
        "transition_matrix",
        "prepared_assets",
    ):
        if not isinstance(plan.get(field), list):
            raise ToolingSuiteError(f"tooling-suite {field} binding is malformed")
    if (
        not re.fullmatch(
            r"[0-9a-f]{64}", str(plan.get("protected_state_sha256", ""))
        )
        or not isinstance(plan.get("rollback_closure"), dict)
    ):
        raise ToolingSuiteError("tooling-suite protected state binding is malformed")
    if plan.get("profile") not in SUPPORTED_PROFILES:
        raise ToolingSuiteError("tooling-suite profile is unsupported")
    if plan.get("status") not in {
        "ready",
        "blocked",
        "needs-repository-approval",
        "needs-arch-upgrade-approval",
        "repository-bootstrap",
    }:
        raise ToolingSuiteError("tooling-suite status is unsupported")
    if set(plan.get("approved_repositories", [])) - {"epel"}:
        raise ToolingSuiteError("tooling-suite plan contains an unsupported repository")
    installer_files = plan.get("installer_files", [])
    if not isinstance(
        installer_files, list
    ) or installer_files != installer_file_records(REPO_ROOT):
        raise ToolingSuiteError("tooling-suite installer file manifest is malformed")
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    rows = plan.get("tools", [])
    if not isinstance(rows, list):
        raise ToolingSuiteError("tooling-suite rows are malformed")
    selected = plan.get("selected_tools", [])
    if (
        not isinstance(selected, list)
        or len(selected) != len(set(selected))
        or selected != [row.get("id") for row in rows if isinstance(row, dict)]
    ):
        raise ToolingSuiteError("selected tool list does not match plan rows")
    expected_root_actions: list[dict[str, Any]] = []
    direct_python: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ToolingSuiteError("tooling-suite contains a malformed row")
        tool_id = str(row.get("id", ""))
        if tool_id not in catalog:
            raise ToolingSuiteError(f"plan contains an unknown tool: {tool_id}")
        spec = catalog[tool_id]
        if (
            row.get("label") != spec.label
            or row.get("command") != spec.command
            or row.get("category") != spec.category
            or row.get("reason") != spec.reason
            or row.get("profiles") != list(spec.profiles)
            or row.get("required") is not spec.required
            or not _suite_verification_is_catalog_owned(
                spec, row.get("verification_command")
            )
            or not isinstance(row.get("present"), bool)
        ):
            raise ToolingSuiteError(
                f"plan row no longer matches the catalog: {tool_id}"
            )
        resolved = row.get("resolved", {})
        action = row.get("install_action", {})
        if not isinstance(resolved, dict) or not isinstance(action, dict):
            raise ToolingSuiteError(f"plan action is malformed: {tool_id}")
        if action.get("tool_id") != tool_id:
            raise ToolingSuiteError(f"plan action id does not match: {tool_id}")
        kind = str(action.get("kind", ""))
        row_status = str(row.get("status", ""))
        version = str(resolved.get("version", ""))
        if kind in {"none", "manual", "protected-existing"}:
            if (
                action.get("auto_execute") is not False
                or action.get("requires_elevation") is not False
            ):
                raise ToolingSuiteError(
                    f"non-executable plan action is unsafe: {tool_id}"
                )
            expected_status = {
                "none": "current",
                "manual": "manual",
                "protected-existing": "preserved",
            }[kind]
            if row_status != expected_status:
                raise ToolingSuiteError(
                    f"non-executable plan status is inconsistent: {tool_id}"
                )
        elif kind == "system-package":
            manager = str(platform_row["package_manager"])
            if (
                action.get("manager") != manager
                or action.get("package") != _package_name(spec, manager)
                or action.get("version") != version
                or action.get("repository") != spec.dnf_repository
                or action.get("requires_elevation") is not True
                or action.get("auto_execute") is not True
                or resolved.get("source") != manager
                or resolved.get("trust") != "signed-package-manager"
                or resolved.get("package") != action.get("package")
            ):
                raise ToolingSuiteError(
                    f"system package action is not catalog-owned: {tool_id}"
                )
            expected_status = "upgrade" if action.get("previous_version") else "install"
            if row_status != expected_status:
                raise ToolingSuiteError(
                    f"system package plan status is inconsistent: {tool_id}"
                )
            expected_root_actions.append(action)
        elif kind in {"forge-global", "forge-user"}:
            expected_kind = "forge-user" if tool_id == "uv" else "forge-global"
            url = str(resolved.get("asset_url", ""))
            asset_size = int(resolved.get("asset_size", 0) or 0)
            if (
                kind != expected_kind
                or not spec.github_repo
                or not _github_source_is_catalog_owned(spec, resolved)
                or action.get("version") != version
                or action.get("auto_execute") is not True
                or action.get("requires_elevation") is not (kind == "forge-global")
                or resolved.get("source") != "github-release"
                or resolved.get("trust") != "official-release-digest"
                or not re.fullmatch(r"[0-9a-f]{64}", str(resolved.get("sha256", "")))
                or not 0 < asset_size <= MAX_ASSET_BYTES
            ):
                raise ToolingSuiteError(
                    f"release asset action is not catalog-owned: {tool_id}"
                )
            if row_status not in {"install", "upgrade"} or (
                row_status == "upgrade"
            ) is not bool(row.get("present")):
                raise ToolingSuiteError(
                    f"release asset plan status is inconsistent: {tool_id}"
                )
            _assert_official_asset(url)
            if kind == "forge-global":
                expected_root_actions.append(action)
        elif kind == "user-local":
            expected_package = f"{spec.python_package}=={version}"
            if (
                not spec.python_package
                or action.get("package") != expected_package
                or action.get("version") != version
                or action.get("auto_execute") is not True
                or action.get("requires_elevation") is not False
                or resolved.get("source") != "pypi"
                or resolved.get("trust") != "pypi-hash-verified"
                or not (resolved.get("artifact_sha256s") or resolved.get("sha256"))
            ):
                raise ToolingSuiteError(
                    f"Python action is not catalog-owned: {tool_id}"
                )
            if row_status not in {"install", "upgrade"} or (
                row_status == "upgrade"
            ) is not bool(row.get("present")):
                raise ToolingSuiteError(
                    f"Python plan status is inconsistent: {tool_id}"
                )
            direct_python.add(expected_package)
        else:
            raise ToolingSuiteError(f"plan action kind is unsupported: {tool_id}")
    if plan.get("root_actions") != expected_root_actions:
        raise ToolingSuiteError(
            "root action list does not match catalog-owned tool actions"
        )
    python_lock = plan.get("python_tool_lock", {})
    if not isinstance(python_lock, dict):
        raise ToolingSuiteError("Python closure is malformed")
    if sorted(python_lock.get("direct_requirements", [])) != sorted(direct_python):
        raise ToolingSuiteError("Python closure does not match selected tools")
    requirements = str(python_lock.get("requirements", ""))
    if requirements and sha256_bytes(requirements.encode("utf-8")) != python_lock.get(
        "requirements_sha256"
    ):
        raise ToolingSuiteError("Python closure digest does not match")
    if direct_python and python_lock.get("status") != "ready":
        raise ToolingSuiteError(
            "automatic Python tools require a complete wheel closure"
        )
    if direct_python and (not requirements or not python_lock.get("assets")):
        raise ToolingSuiteError("ready Python closure must include frozen wheel assets")
    try:
        pinned_python = {
            (normalized_package_name(package), version)
            for package, version in parse_hashed_requirements(requirements)
        }
    except WorkstationError as error:
        raise ToolingSuiteError("Python closure requirements are malformed") from error
    asset_python: set[tuple[str, str]] = set()
    for asset in python_lock.get("assets", []):
        if not isinstance(asset, dict):
            raise ToolingSuiteError("Python closure asset is malformed")
        filename = str(asset.get("filename", ""))
        digest = str(asset.get("sha256", ""))
        package = normalized_package_name(str(asset.get("package", "")))
        version = str(asset.get("version", ""))
        size = int(asset.get("size", 0) or 0)
        parsed_url = urllib.parse.urlsplit(str(asset.get("url", "")))
        if (
            not filename
            or Path(filename).name != filename
            or not filename.endswith(".whl")
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or digest not in requirements
            or (package, version) not in pinned_python
            or (package, version) in asset_python
            or parsed_url.hostname != "files.pythonhosted.org"
            or Path(parsed_url.path).name != filename
            or not 0 < size <= MAX_ASSET_BYTES
        ):
            raise ToolingSuiteError("Python closure asset integrity is malformed")
        _assert_official_asset(str(asset.get("url", "")))
        asset_python.add((package, version))
    if asset_python != pinned_python:
        raise ToolingSuiteError(
            "Python closure assets do not match frozen requirements"
        )
    repository = plan.get("repository_bootstrap")
    if repository is not None:
        if (
            plan.get("status") != "repository-bootstrap"
            or platform_row.get("package_manager") != "dnf"
            or repository.get("id") != "epel"
            or repository.get("package") != "epel-release"
            or repository.get("trust") != "signed-package-manager"
            or repository.get("requires_replan") is not True
        ):
            raise ToolingSuiteError("repository bootstrap action is malformed")
    offline = plan.get("offline")
    if offline is not None:
        if (
            not isinstance(offline, dict)
            or offline.get("version") != "MoradinForgeAirgapOfflinePlanV2"
            or offline.get("network") != "disabled"
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(offline.get("bundle_sha256", ""))
            )
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(offline.get("lock_sha256", ""))
            )
        ):
            raise ToolingSuiteError("offline plan binding is malformed")
        package_assets = offline.get("package_assets")
        if not isinstance(package_assets, list):
            raise ToolingSuiteError("offline package closure is malformed")
        trust_assets = offline.get("trust_assets")
        if not isinstance(trust_assets, list) or not trust_assets:
            raise ToolingSuiteError("offline repository trust closure is malformed")
        seen_trust: set[str] = set()
        for asset in trust_assets:
            if not isinstance(asset, dict):
                raise ToolingSuiteError("offline trust asset is malformed")
            filename = str(asset.get("path", ""))
            if (
                not filename
                or Path(filename).name != filename
                or filename in seen_trust
                or not str(asset.get("kind", ""))
                or not re.fullmatch(r"[0-9a-f]{64}", str(asset.get("sha256", "")))
                or not 0 < int(asset.get("size", -1)) <= MAX_ASSET_BYTES
            ):
                raise ToolingSuiteError("offline trust asset integrity is malformed")
            manager = str(platform_row.get("package_manager", ""))
            kind = str(asset.get("kind", ""))
            allowed_kind = (
                kind
                in {"apt-inrelease", "apt-keyring", "apt-packages-index"}
                if manager == "apt"
                else kind == f"{manager}-repository-trust"
            )
            if not allowed_kind:
                raise ToolingSuiteError(
                    "offline trust asset does not match the package manager"
                )
            if kind == "apt-packages-index" and (
                asset.get("compression") != "gzip"
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(asset.get("repository_sha256", "")),
                )
                or not 0
                < int(asset.get("uncompressed_size", -1))
                <= MAX_ASSET_BYTES
            ):
                raise ToolingSuiteError(
                    "offline APT index compression binding is malformed"
                )
            seen_trust.add(filename)
        seen_files: set[str] = set()
        seen_packages: set[tuple[str, str, str]] = set()
        for asset in package_assets:
            if not isinstance(asset, dict):
                raise ToolingSuiteError("offline package asset is malformed")
            package = str(asset.get("package", ""))
            version = str(asset.get("version", ""))
            architecture = str(asset.get("arch", ""))
            filename = str(asset.get("filename", ""))
            digest = str(asset.get("sha256", ""))
            size = int(asset.get("size", -1))
            package_key = (package, version, architecture)
            if (
                not re.fullmatch(r"[A-Za-z0-9@._+:-]+", package)
                or not version
                or not architecture
                or not filename
                or Path(filename).name != filename
                or filename in seen_files
                or package_key in seen_packages
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not 0 < size <= MAX_ASSET_BYTES
            ):
                raise ToolingSuiteError("offline package asset integrity is malformed")
            if platform_row.get("package_manager") == "apt" and (
                asset.get("signature") != "apt-signed-index"
                or asset.get("repository_sha256") != digest
            ):
                raise ToolingSuiteError(
                    "offline Debian package signed-index binding is malformed"
                )
            seen_files.add(filename)
            seen_packages.add(package_key)
            signature_filename = str(asset.get("signature_filename", ""))
            if signature_filename:
                if (
                    Path(signature_filename).name != signature_filename
                    or signature_filename in seen_files
                    or not re.fullmatch(
                        r"[0-9a-f]{64}",
                        str(asset.get("signature_sha256", "")),
                    )
                    or not 0 < int(asset.get("signature_size", -1)) <= MAX_ASSET_BYTES
                ):
                    raise ToolingSuiteError(
                        "offline package signature integrity is malformed"
                    )
                seen_files.add(signature_filename)
            previous = str(asset.get("previous_version", ""))
            rollback_filename = str(asset.get("rollback_filename", ""))
            if previous and previous != version:
                if (
                    not rollback_filename
                    or Path(rollback_filename).name != rollback_filename
                    or rollback_filename in seen_files
                    or not re.fullmatch(
                        r"[0-9a-f]{64}",
                        str(asset.get("rollback_sha256", "")),
                    )
                    or not 0
                    < int(asset.get("rollback_size", -1))
                    <= MAX_ASSET_BYTES
                ):
                    raise ToolingSuiteError(
                        "offline package rollback closure is malformed"
                    )
                seen_files.add(rollback_filename)
                if platform_row.get("package_manager") == "apt" and (
                    asset.get("rollback_repository_sha256")
                    != asset.get("rollback_sha256")
                    or not str(asset.get("rollback_arch", ""))
                ):
                    raise ToolingSuiteError(
                        "offline Debian rollback signed-index binding is malformed"
                    )
                rollback_signature = str(
                    asset.get("rollback_signature_filename", "")
                )
                if rollback_signature:
                    if (
                        Path(rollback_signature).name != rollback_signature
                        or rollback_signature in seen_files
                        or not re.fullmatch(
                            r"[0-9a-f]{64}",
                            str(asset.get("rollback_signature_sha256", "")),
                        )
                        or not 0
                        < int(asset.get("rollback_signature_size", -1))
                        <= MAX_ASSET_BYTES
                    ):
                        raise ToolingSuiteError(
                            "offline rollback signature integrity is malformed"
                        )
                    seen_files.add(rollback_signature)
            elif rollback_filename:
                raise ToolingSuiteError(
                    "offline package has an unnecessary rollback asset"
                )


def load_suite_plan(
    path: Path,
    *,
    approved_sha256: str | None = None,
    forge_root: Path = REPO_ROOT,
    require_current_host: bool = True,
) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ToolingSuiteError(f"plan must be a regular file: {path}")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingSuiteError("tooling-suite plan is not valid JSON") from error
    if not isinstance(plan, dict) or plan.get("version") != SUITE_PLAN_VERSION:
        raise ToolingSuiteError(f"plan version must be {SUITE_PLAN_VERSION}")
    recorded = str(plan.get("plan_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", recorded) or recorded != plan_digest(plan):
        raise ToolingSuiteError("plan digest is missing or does not match its contents")
    if approved_sha256 is not None and approved_sha256 != recorded:
        raise ToolingSuiteError(
            "approved plan digest does not match the tooling-suite plan"
        )
    try:
        expires = datetime.fromisoformat(str(plan["expires_at"]))
    except (KeyError, TypeError, ValueError) as error:
        raise ToolingSuiteError("plan expiry is malformed") from error
    if expires.tzinfo is None or datetime.now(tz=UTC) > expires:
        raise ToolingSuiteError(
            "tooling-suite plan has expired; create and approve a fresh plan"
        )
    if plan.get("catalog_sha256") != sha256_file(CATALOG_PATH):
        raise ToolingSuiteError("tooling catalog changed after the plan was approved")
    if plan.get("installer_manifest_sha256") != installer_manifest_sha256(forge_root):
        raise ToolingSuiteError(
            "installer implementation changed after the plan was approved"
        )
    if require_current_host:
        current = dict(host_facts())
        expected = plan.get("platform", {})
        if not current.get("package_manager_path"):
            current_manager = str(current.get("package_manager", ""))
            manager_command = {
                "apt": "apt-get",
                "dnf": "dnf",
                "pacman": "pacman",
            }.get(current_manager, "")
            if manager_command:
                current["package_manager_path"] = _trusted_system_command(
                    manager_command
                ).as_posix()
        for key in (
            "system",
            "arch",
            "os_id",
            "package_manager",
            "package_manager_path",
            "host_fingerprint_sha256",
        ):
            if expected.get(key) != current.get(key):
                raise ToolingSuiteError(
                    f"tooling-suite plan does not match this host: {key}"
                )
        if int(plan.get("target_uid", -1)) != os.getuid():
            raise ToolingSuiteError(
                "tooling-suite plan does not match the invoking user"
            )
        protected = sha256_bytes(canonical_json_bytes(_protected_state(current)))
        if plan.get("protected_state_sha256") != protected:
            raise ToolingSuiteError(
                "tooling-suite protected container, provider, PATH, or kernel state changed"
            )
    validate_suite_plan_contents(plan)
    return plan


def _record_digest(payload: dict[str, Any], field: str) -> str:
    canonical = {
        key: value for key, value in payload.items() if key not in {field, "receipt"}
    }
    return hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()


def _safe_asset_filename(tool_id: str, resolved: dict[str, Any]) -> str:
    filename = str(resolved.get("asset_filename", ""))
    if not filename:
        filename = Path(str(resolved.get("asset_url", "")).split("?", 1)[0]).name
    if (
        not filename
        or Path(filename).name != filename
        or any(character in filename for character in ("\x00", "\\"))
    ):
        raise ToolingSuiteError(f"resolved asset filename is unsafe: {tool_id}")
    return f"{tool_id}-{filename}"


def _expected_stage_items(
    plan: dict[str, Any],
) -> dict[tuple[str, str, str], tuple[str, int]]:
    expected: dict[tuple[str, str, str], tuple[str, int]] = {}
    for row in plan["tools"]:
        action = row["install_action"]
        if action["kind"] not in {"forge-user", "forge-global"}:
            continue
        resolved = row["resolved"]
        path = f"assets/{_safe_asset_filename(str(row['id']), resolved)}"
        expected[(str(row["id"]), str(action["kind"]), path)] = (
            str(resolved["sha256"]),
            int(resolved["asset_size"]),
        )
    for asset in plan.get("python_tool_lock", {}).get("assets", []):
        filename = str(asset["filename"])
        key = (f"python:{asset['package']}", "python-wheel", f"wheels/{filename}")
        if key in expected:
            raise ToolingSuiteError("Python closure contains a duplicate staged asset")
        expected[key] = (str(asset["sha256"]), int(asset["size"]))
    for item in plan.get("installer_files", []):
        relative = str(item["path"])
        key = (
            f"installer:{relative}",
            "root-runner",
            f"root-runner/{relative}",
        )
        expected[key] = (str(item["sha256"]), int(item["size"]))
    offline = plan.get("offline", {})
    if isinstance(offline, dict):
        for item in offline.get("trust_assets", []):
            filename = str(item["path"])
            trust_key = (
                f"offline-trust:{filename}",
                "repository-trust",
                f"trust/{filename}",
            )
            if trust_key in expected:
                raise ToolingSuiteError("offline trust closure contains a duplicate")
            expected[trust_key] = (str(item["sha256"]), int(item["size"]))
        for item in offline.get("package_assets", []):
            filename = str(item["filename"])
            key = (
                f"offline-package:{filename}",
                "os-package",
                f"os-packages/{filename}",
            )
            if key in expected:
                raise ToolingSuiteError("offline package closure contains a duplicate")
            expected[key] = (str(item["sha256"]), int(item["size"]))
            signature_filename = str(item.get("signature_filename", ""))
            if signature_filename:
                signature_key = (
                    f"offline-signature:{signature_filename}",
                    "os-package-signature",
                    f"os-packages/{signature_filename}",
                )
                expected[signature_key] = (
                    str(item["signature_sha256"]),
                    int(item["signature_size"]),
                )
            rollback_filename = str(item.get("rollback_filename", ""))
            if rollback_filename:
                rollback_key = (
                    f"offline-rollback:{rollback_filename}",
                    "os-package-rollback",
                    f"os-packages/{rollback_filename}",
                )
                expected[rollback_key] = (
                    str(item["rollback_sha256"]),
                    int(item["rollback_size"]),
                )
                rollback_signature = str(
                    item.get("rollback_signature_filename", "")
                )
                if rollback_signature:
                    rollback_signature_key = (
                        f"offline-rollback-signature:{rollback_signature}",
                        "os-package-rollback-signature",
                        f"os-packages/{rollback_signature}",
                    )
                    expected[rollback_signature_key] = (
                        str(item["rollback_signature_sha256"]),
                        int(item["rollback_signature_size"]),
                    )
    return expected


def _expected_constraints(plan: dict[str, Any]) -> str:
    assets = plan.get("python_tool_lock", {}).get("assets", [])
    constraints = sorted(
        {f"{asset['package']}=={asset['version']}" for asset in assets}
    )
    return "\n".join(constraints) + ("\n" if constraints else "")


def stage_suite_assets(
    plan: dict[str, Any],
    *,
    output: Path,
    forge_root: Path = REPO_ROOT,
    downloader: Callable[[str, Path], None] = _download_asset,
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise ToolingSuiteError(f"asset staging output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="moradin-suite-assets-", dir=output.parent
    ) as temporary:
        root = Path(temporary) / "stage"
        assets = root / "assets"
        wheels = root / "wheels"
        assets.mkdir(parents=True)
        wheels.mkdir(parents=True)
        included: list[dict[str, Any]] = []
        for row in plan["tools"]:
            action = row["install_action"]
            if action["kind"] not in {"forge-user", "forge-global"}:
                continue
            resolved = row["resolved"]
            url = str(resolved.get("asset_url", ""))
            expected = str(resolved.get("sha256", ""))
            if not url or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ToolingSuiteError(
                    f"verified asset metadata is missing: {row['id']}"
                )
            filename = _safe_asset_filename(str(row["id"]), resolved)
            destination = assets / filename
            downloader(url, destination)
            if destination.is_symlink() or not destination.is_file():
                raise ToolingSuiteError(
                    f"downloaded asset is not a regular file: {row['id']}"
                )
            if destination.stat().st_size > MAX_ASSET_BYTES:
                raise ToolingSuiteError(f"downloaded asset is too large: {row['id']}")
            if destination.stat().st_size != int(resolved["asset_size"]):
                raise ToolingSuiteError(f"downloaded asset size mismatch: {row['id']}")
            actual = sha256_file(destination)
            if actual != expected:
                raise ToolingSuiteError(
                    f"downloaded asset digest mismatch: {row['id']}"
                )
            included.append(
                {
                    "tool_id": row["id"],
                    "kind": action["kind"],
                    "path": destination.relative_to(root).as_posix(),
                    "sha256": actual,
                    "size": destination.stat().st_size,
                }
            )
        python_lock = plan.get("python_tool_lock", {})
        if isinstance(python_lock, dict):
            requirements = str(python_lock.get("requirements", ""))
            if requirements:
                (root / "requirements.lock").write_text(requirements, encoding="utf-8")
            (root / "constraints.txt").write_text(
                _expected_constraints(plan), encoding="utf-8"
            )
            for asset in python_lock.get("assets", []):
                filename = str(asset.get("filename", ""))
                url = str(asset.get("url", ""))
                expected = str(asset.get("sha256", ""))
                if (
                    not filename
                    or Path(filename).name != filename
                    or not re.fullmatch(r"[0-9a-f]{64}", expected)
                ):
                    raise ToolingSuiteError(
                        "Python closure contains unsafe asset metadata"
                    )
                destination = wheels / filename
                if destination.exists():
                    raise ToolingSuiteError(
                        f"Python wheel filename collision: {filename}"
                    )
                downloader(url, destination)
                if destination.is_symlink() or not destination.is_file():
                    raise ToolingSuiteError(
                        f"Python wheel is not a regular file: {filename}"
                    )
                if destination.stat().st_size != int(asset["size"]):
                    raise ToolingSuiteError(f"Python wheel size mismatch: {filename}")
                if sha256_file(destination) != expected:
                    raise ToolingSuiteError(f"Python wheel digest mismatch: {filename}")
                included.append(
                    {
                        "tool_id": f"python:{asset['package']}",
                        "kind": "python-wheel",
                        "path": destination.relative_to(root).as_posix(),
                        "sha256": expected,
                        "size": destination.stat().st_size,
                    }
                )
        for item in plan.get("installer_files", []):
            relative = Path(str(item["path"]))
            source = forge_root / relative
            destination = root / "root-runner" / relative
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or source.is_symlink()
                or not source.is_file()
                or sha256_file(source) != item["sha256"]
                or source.stat().st_size != int(item["size"])
            ):
                raise ToolingSuiteError(
                    f"installer runner changed before staging: {relative.as_posix()}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            included.append(
                {
                    "tool_id": f"installer:{relative.as_posix()}",
                    "kind": "root-runner",
                    "path": destination.relative_to(root).as_posix(),
                    "sha256": str(item["sha256"]),
                    "size": int(item["size"]),
                }
            )
        write_json(root / "plan.json", plan)
        manifest: dict[str, Any] = {
            "version": 1,
            "plan_sha256": plan["plan_sha256"],
            "included": included,
        }
        manifest["manifest_sha256"] = _record_digest(manifest, "manifest_sha256")
        write_json(root / "stage-manifest.json", manifest)
        os.replace(root, output)
    return {**manifest, "output": output.as_posix()}


def validate_staged_assets(stage_root: Path, plan: dict[str, Any]) -> dict[str, Path]:
    if stage_root.is_symlink() or not stage_root.is_dir():
        raise ToolingSuiteError("asset stage must be a regular directory")
    if next((path for path in stage_root.rglob("*") if path.is_symlink()), None):
        raise ToolingSuiteError("asset stage must not contain symbolic links")
    manifest_path = stage_root / "stage-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ToolingSuiteError("asset stage manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingSuiteError("asset stage manifest is invalid") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("plan_sha256") != plan["plan_sha256"]
        or manifest.get("manifest_sha256")
        != _record_digest(manifest, "manifest_sha256")
    ):
        raise ToolingSuiteError("asset stage manifest binding is invalid")
    included = manifest.get("included", [])
    if not isinstance(included, list):
        raise ToolingSuiteError("asset stage manifest entries are malformed")
    expected_items = _expected_stage_items(plan)
    observed_items: dict[tuple[str, str, str], tuple[str, int]] = {}
    for item in included:
        if not isinstance(item, dict):
            raise ToolingSuiteError("asset stage manifest entry is malformed")
        key = (
            str(item.get("tool_id", "")),
            str(item.get("kind", "")),
            str(item.get("path", "")),
        )
        if key in observed_items:
            raise ToolingSuiteError("asset stage manifest contains a duplicate entry")
        observed_items[key] = (str(item.get("sha256", "")), int(item.get("size", -1)))
    if observed_items != expected_items:
        raise ToolingSuiteError("asset stage does not exactly match the approved plan")
    plan_copy = stage_root / "plan.json"
    requirements_path = stage_root / "requirements.lock"
    constraints_path = stage_root / "constraints.txt"
    try:
        copied_plan = json.loads(plan_copy.read_text(encoding="utf-8"))
        requirements = (
            requirements_path.read_text(encoding="utf-8")
            if requirements_path.is_file()
            else ""
        )
        constraints = constraints_path.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingSuiteError("asset stage control files are invalid") from error
    if copied_plan != plan:
        raise ToolingSuiteError(
            "asset stage plan copy does not match the approved plan"
        )
    expected_requirements = str(
        plan.get("python_tool_lock", {}).get("requirements", "")
    )
    if requirements != expected_requirements or constraints != _expected_constraints(
        plan
    ):
        raise ToolingSuiteError(
            "asset stage Python closure does not match the approved plan"
        )
    paths: dict[str, Path] = {}
    root = stage_root.resolve()
    for item in included:
        relative = Path(str(item.get("path", "")))
        path = (root / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not path.is_relative_to(root)
            or path.is_symlink()
            or not path.is_file()
        ):
            raise ToolingSuiteError("asset stage contains an unsafe path")
        if path.stat().st_size != int(item.get("size", -1)) or sha256_file(
            path
        ) != item.get("sha256"):
            raise ToolingSuiteError(
                f"staged asset integrity failed: {item.get('tool_id')}"
            )
        key = str(item.get("tool_id", ""))
        if item.get("kind") not in {"python-wheel", "root-runner"}:
            if key in paths:
                raise ToolingSuiteError(f"asset stage contains duplicate tool: {key}")
            paths[key] = path
    return paths


def _archive_member_is_safe(name: str) -> bool:
    path = Path(name)
    return bool(
        name
        and not path.is_absolute()
        and ".." not in path.parts
        and "\x00" not in name
    )


def _read_tar_executable(archive: tarfile.TarFile, command: str) -> bytes:
    members = archive.getmembers()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ToolingSuiteError("verified archive contains too many members")
    if any(not _archive_member_is_safe(member.name) for member in members):
        raise ToolingSuiteError("verified archive contains an unsafe path")
    if any(member.issym() or member.islnk() or member.isdev() for member in members):
        raise ToolingSuiteError("verified archive contains links or device entries")
    candidates = [
        member
        for member in members
        if member.isfile() and Path(member.name).name == command and member.mode & 0o111
    ]
    if len(candidates) != 1 or candidates[0].size > MAX_ASSET_BYTES:
        raise ToolingSuiteError("verified archive has an unexpected executable layout")
    extracted = archive.extractfile(candidates[0])
    if extracted is None:
        raise ToolingSuiteError("verified archive executable could not be read")
    return extracted.read(MAX_ASSET_BYTES + 1)


def _read_debian_data_archive(asset: Path, command: str) -> bytes:
    archive_payload = asset.read_bytes()
    if not archive_payload.startswith(b"!<arch>\n"):
        raise ToolingSuiteError("verified Debian package has an invalid archive header")
    offset = 8
    data_members: list[bytes] = []
    member_count = 0
    while offset < len(archive_payload):
        if len(archive_payload) - offset < 60:
            raise ToolingSuiteError("verified Debian package has a truncated member")
        header = archive_payload[offset : offset + 60]
        if header[58:60] != b"`\n":
            raise ToolingSuiteError("verified Debian package member header is invalid")
        try:
            name = header[:16].decode("ascii").strip().rstrip("/")
            size = int(header[48:58].decode("ascii").strip())
        except (UnicodeDecodeError, ValueError) as error:
            raise ToolingSuiteError(
                "verified Debian package member metadata is invalid"
            ) from error
        if (
            not name
            or name.startswith(("#1/", "/"))
            or size < 0
            or size > MAX_ASSET_BYTES
        ):
            raise ToolingSuiteError("verified Debian package contains an unsafe member")
        start = offset + 60
        end = start + size
        if end > len(archive_payload):
            raise ToolingSuiteError("verified Debian package member is truncated")
        member_count += 1
        if member_count > MAX_ARCHIVE_MEMBERS:
            raise ToolingSuiteError("verified Debian package contains too many members")
        if name.startswith("data.tar"):
            data_members.append(archive_payload[start:end])
        offset = end + (size % 2)
    if len(data_members) != 1:
        raise ToolingSuiteError(
            "verified Debian package has an unexpected data archive"
        )
    try:
        with tarfile.open(fileobj=io.BytesIO(data_members[0]), mode="r:*") as archive:
            return _read_tar_executable(archive, command)
    except tarfile.TarError as error:
        raise ToolingSuiteError(
            "verified Debian package data archive is invalid"
        ) from error


def _read_single_file_compression(asset: Path, kind: str) -> bytes:
    openers: dict[str, Callable[..., Any]] = {
        "bz2": bz2.open,
        "gz": gzip.open,
        "xz": lzma.open,
    }
    try:
        with openers[kind](asset, "rb") as stream:
            return stream.read(MAX_ASSET_BYTES + 1)
    except (EOFError, OSError, lzma.LZMAError) as error:
        raise ToolingSuiteError("verified compressed executable is invalid") from error


def materialize_verified_binary(asset: Path, command: str, destination: Path) -> None:
    if asset.is_symlink() or not asset.is_file() or not command:
        raise ToolingSuiteError("verified binary input is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".new")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    payload: bytes
    with asset.open("rb") as stream:
        archive_header = stream.read(8)
    if archive_header == b"!<arch>\n":
        payload = _read_debian_data_archive(asset, command)
    elif tarfile.is_tarfile(asset):
        with tarfile.open(asset, mode="r:*") as archive:
            payload = _read_tar_executable(archive, command)
    elif zipfile.is_zipfile(asset):
        with zipfile.ZipFile(asset) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise ToolingSuiteError("verified zip contains too many members")
            if any(not _archive_member_is_safe(member.filename) for member in members):
                raise ToolingSuiteError("verified zip contains an unsafe path")
            if any(
                stat.S_ISLNK((member.external_attr >> 16) & 0xFFFF)
                for member in members
            ):
                raise ToolingSuiteError("verified zip contains symbolic links")
            candidates = [
                member
                for member in members
                if not member.is_dir() and Path(member.filename).name == command
            ]
            if len(candidates) != 1 or candidates[0].file_size > MAX_ASSET_BYTES:
                raise ToolingSuiteError(
                    "verified zip has an unexpected executable layout"
                )
            payload = archive.read(candidates[0])
    elif asset.name.endswith(".bz2"):
        payload = _read_single_file_compression(asset, "bz2")
    elif asset.name.endswith(".gz"):
        payload = _read_single_file_compression(asset, "gz")
    elif asset.name.endswith(".xz"):
        payload = _read_single_file_compression(asset, "xz")
    else:
        payload = asset.read_bytes()
    if not payload or len(payload) > MAX_ASSET_BYTES:
        raise ToolingSuiteError("verified executable payload has an unsafe size")
    temporary.write_bytes(payload)
    temporary.chmod(0o755)
    os.replace(temporary, destination)


def _owned_symlink_target(path: Path, owned_root: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return ""
    if not path.is_symlink():
        raise ToolingSuiteError(
            f"refusing to replace an unowned executable: {path.name}"
        )
    target = os.readlink(path)
    resolved = (
        (path.parent / target).resolve()
        if not Path(target).is_absolute()
        else Path(target).resolve()
    )
    if not resolved.is_relative_to(owned_root.resolve()):
        raise ToolingSuiteError(
            f"refusing to replace an unowned executable link: {path.name}"
        )
    return target


def _switch_owned_symlink(path: Path, target: Path, owned_root: Path) -> str:
    previous = _owned_symlink_target(path, owned_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.moradin-new")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(target)
    os.replace(temporary, path)
    return previous


def _relative_owned_target(target: str, shim: Path, owned_root: Path) -> str:
    if not target:
        return ""
    raw = Path(target)
    resolved = (shim.parent / raw).resolve() if not raw.is_absolute() else raw.resolve()
    root = owned_root.resolve()
    if not resolved.is_relative_to(root):
        raise ToolingSuiteError("owned executable target escaped its versioned prefix")
    return resolved.relative_to(root).as_posix()


def _user_roots() -> tuple[Path, Path, Path]:
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return data / "moradins-forge", state / "moradins-forge", Path.home() / ".local/bin"


def _checkpoint_root(plan_sha256: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", plan_sha256):
        raise ToolingSuiteError("checkpoint plan digest is malformed")
    return _user_roots()[1] / "checkpoints" / plan_sha256


def _write_checkpoint(
    plan: dict[str, Any],
    component: str,
    *,
    status: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", component):
        raise ToolingSuiteError("checkpoint component is malformed")
    if status not in {"pass", "fail"}:
        raise ToolingSuiteError("checkpoint status is malformed")
    payload: dict[str, Any] = {
        "version": CHECKPOINT_VERSION,
        "generated_at": utc_now(),
        "plan_sha256": plan["plan_sha256"],
        "component": component,
        "status": status,
        "catalog_sha256": plan["catalog_sha256"],
        "installer_manifest_sha256": plan["installer_manifest_sha256"],
        "protected_state_sha256": plan["protected_state_sha256"],
        "evidence": evidence or {},
    }
    payload["checkpoint_sha256"] = _record_digest(
        payload, "checkpoint_sha256"
    )
    root = _checkpoint_root(str(plan["plan_sha256"]))
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{component}.json"
    temporary = root / f".{component}.json.new"
    write_json(temporary, payload)
    os.replace(temporary, destination)
    return payload


def _load_checkpoint(
    plan: dict[str, Any], component: str
) -> dict[str, Any] | None:
    path = _checkpoint_root(str(plan["plan_sha256"])) / f"{component}.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ToolingSuiteError("checkpoint must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingSuiteError("checkpoint is invalid") from error
    if (
        not isinstance(payload, dict)
        or payload.get("version") != CHECKPOINT_VERSION
        or payload.get("plan_sha256") != plan["plan_sha256"]
        or payload.get("component") != component
        or payload.get("catalog_sha256") != plan["catalog_sha256"]
        or payload.get("installer_manifest_sha256")
        != plan["installer_manifest_sha256"]
        or payload.get("protected_state_sha256")
        != plan["protected_state_sha256"]
        or payload.get("checkpoint_sha256")
        != _record_digest(payload, "checkpoint_sha256")
    ):
        raise ToolingSuiteError("checkpoint binding is invalid")
    return payload


def _emit_progress(mode: str, event: str, **fields: object) -> None:
    selected = "plain" if mode == "auto" and sys.stderr.isatty() else mode
    if selected in {"off", "auto"}:
        return
    payload = {"version": "MoradinForgeToolingProgressV1", "event": event, **fields}
    if selected == "json":
        print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)
    else:
        detail = " ".join(f"{key}={value}" for key, value in fields.items())
        print(f"[moradin-forge] {event}{' ' + detail if detail else ''}", file=sys.stderr, flush=True)


def tooling_suite_status() -> dict[str, Any]:
    _data_root, state_root, _bin_root = _user_roots()
    checkpoints: list[dict[str, str]] = []
    checkpoint_base = state_root / "checkpoints"
    if checkpoint_base.is_dir() and not checkpoint_base.is_symlink():
        for path in sorted(checkpoint_base.glob("*/*.json"))[-200:]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("version") == CHECKPOINT_VERSION:
                checkpoints.append(
                    {
                        "plan_sha256": str(payload.get("plan_sha256", "")),
                        "component": str(payload.get("component", "")),
                        "status": str(payload.get("status", "")),
                    }
                )
    latest_receipt = ""
    receipt_status = "missing"
    try:
        receipt_path, receipt = _load_user_receipt("latest")
        latest_receipt = receipt_path.parent.name
        receipt_status = str(receipt.get("status", "unknown"))
    except ToolingSuiteError:
        pass
    return {
        "version": "MoradinForgeToolingStatusV1",
        "status": "ready" if receipt_status == "pass" else "attention",
        "latest_receipt": latest_receipt,
        "latest_receipt_status": receipt_status,
        "checkpoints": checkpoints,
        "privacy": "Status contains digests, component names, and outcomes only.",
    }


def _trusted_user_uv(bin_root: Path, owned_root: Path) -> Path:
    managed = bin_root / "uv"
    if managed.exists() or managed.is_symlink():
        _owned_symlink_target(managed, owned_root)
        resolved = managed.resolve(strict=True)
        metadata = resolved.stat()
        if (
            not resolved.is_file()
            or not resolved.is_relative_to(owned_root.resolve())
            or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o022
        ):
            raise ToolingSuiteError("the Forge-managed uv runtime is unsafe")
        return resolved
    bootstrap = _trusted_bootstrap_uv_path(required=True)
    if bootstrap is None:  # pragma: no cover - required=True always raises
        raise ToolingSuiteError("the Forge bootstrap uv runtime is unavailable")
    return bootstrap


def _apply_user_actions(
    plan: dict[str, Any],
    stage_root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[list[dict[str, Any]], Path]:
    assets = validate_staged_assets(stage_root, plan)
    data_root, _state_root, bin_root = _user_roots()
    generation = str(plan["plan_sha256"])[:16]
    generation_root = data_root / "tools" / generation
    owned_root = data_root / "tools"
    operations: list[dict[str, Any]] = []
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    if generation_root.exists() or generation_root.is_symlink():
        raise ToolingSuiteError(
            "this exact user transaction already has state; create and approve a fresh plan"
        )
    generation_root.mkdir(parents=True, exist_ok=True)
    bin_root.mkdir(parents=True, exist_ok=True)
    try:
        for row in plan["tools"]:
            action = row["install_action"]
            kind = action["kind"]
            if kind == "forge-user":
                spec = catalog[row["id"]]
                destination = generation_root / spec.id / spec.command
                materialize_verified_binary(assets[spec.id], spec.command, destination)
                previous = _switch_owned_symlink(
                    bin_root / spec.command, destination, owned_root
                )
                operations.append(
                    {
                        "kind": kind,
                        "tool_id": spec.id,
                        "shim_name": spec.command,
                        "installed_target": destination.relative_to(
                            owned_root
                        ).as_posix(),
                        "previous_target": _relative_owned_target(
                            previous,
                            bin_root / spec.command,
                            owned_root,
                        ),
                    }
                )
        uv_path = (
            _trusted_user_uv(bin_root, owned_root)
            if any(
                row["install_action"]["kind"] == "user-local" for row in plan["tools"]
            )
            else None
        )
        for row in plan["tools"]:
            action = row["install_action"]
            kind = action["kind"]
            if kind == "user-local":
                if uv_path is None:  # pragma: no cover - guarded above
                    raise ToolingSuiteError("uv is required for planned user tools")
                python_lock = plan.get("python_tool_lock", {})
                if (
                    not isinstance(python_lock, dict)
                    or python_lock.get("status") != "ready"
                ):
                    raise ToolingSuiteError("complete Python wheel closure is required")
                tool_bin = generation_root / "python-bin"
                tool_data = generation_root / "python-tools"
                tool_bin.mkdir(parents=True, exist_ok=True)
                environment = _safe_environment(home=Path.home())
                environment.update(
                    {
                        "UV_TOOL_BIN_DIR": tool_bin.as_posix(),
                        "UV_TOOL_DIR": tool_data.as_posix(),
                        "UV_PYTHON_INSTALL_DIR": (
                            data_root / "bootstrap/python"
                        ).as_posix(),
                    }
                )
                argv = [
                    uv_path.as_posix(),
                    "tool",
                    "install",
                    "--force",
                    "--offline",
                    "--no-index",
                    "--no-config",
                    "--python",
                    "3.12",
                    "--managed-python",
                    "--no-python-downloads",
                    "--find-links",
                    (stage_root / "wheels").as_posix(),
                    "--constraints",
                    (stage_root / "constraints.txt").as_posix(),
                    str(action["package"]),
                ]
                result = _run(argv, runner=runner, timeout=900, env=environment)
                if result.returncode != 0:
                    raise ToolingSuiteError(
                        f"user tool installation failed: {row['id']}"
                    )
                spec = catalog[row["id"]]
                generated = tool_bin / spec.command
                if not generated.is_file() and not generated.is_symlink():
                    raise ToolingSuiteError(
                        f"user tool did not create its command: {row['id']}"
                    )
                previous = _switch_owned_symlink(
                    bin_root / spec.command, generated, owned_root
                )
                operations.append(
                    {
                        "kind": kind,
                        "tool_id": spec.id,
                        "shim_name": spec.command,
                        "installed_target": generated.relative_to(
                            owned_root
                        ).as_posix(),
                        "previous_target": _relative_owned_target(
                            previous,
                            bin_root / spec.command,
                            owned_root,
                        ),
                    }
                )
        _prune_user_generations(owned_root, bin_root, generation_root, operations)
    except Exception:
        _rollback_user_operations(operations, owned_root=owned_root, bin_root=bin_root)
        _remove_user_generation(
            generation_root, owned_root=owned_root, bin_root=bin_root
        )
        raise
    return operations, generation_root


def _rollback_user_operations(
    operations: Sequence[dict[str, Any]],
    *,
    owned_root: Path,
    bin_root: Path | None = None,
) -> list[dict[str, str]]:
    bin_root = bin_root or _user_roots()[2]
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    results: list[dict[str, str]] = []
    for operation in reversed(operations):
        tool_id = str(operation.get("tool_id", ""))
        spec = catalog.get(tool_id)
        shim_name = str(operation.get("shim_name", ""))
        if (
            spec is None
            or shim_name != spec.command
            or Path(shim_name).name != shim_name
        ):
            raise ToolingSuiteError("user receipt contains an unsafe executable shim")
        installed_relative = Path(str(operation.get("installed_target", "")))
        if installed_relative.is_absolute() or ".." in installed_relative.parts:
            raise ToolingSuiteError("user receipt contains an unsafe installed target")
        installed = (owned_root / installed_relative).resolve()
        if not installed.is_relative_to(owned_root.resolve()):
            raise ToolingSuiteError("user receipt installed target escaped its prefix")
        shim = bin_root / shim_name
        if not shim_name:
            continue
        if not shim.is_symlink() or shim.resolve() != installed:
            results.append(
                {"tool_id": str(operation["tool_id"]), "status": "preserved-newer"}
            )
            continue
        previous_relative = Path(str(operation.get("previous_target", "")))
        if str(previous_relative) not in {"", "."}:
            if previous_relative.is_absolute() or ".." in previous_relative.parts:
                raise ToolingSuiteError(
                    "user receipt contains an unsafe previous target"
                )
            previous = (owned_root / previous_relative).resolve()
            if not previous.is_relative_to(owned_root.resolve()):
                raise ToolingSuiteError(
                    "user receipt previous target escaped its prefix"
                )
            temporary = shim.with_name(f".{shim.name}.moradin-rollback")
            if temporary.exists() or temporary.is_symlink():
                temporary.unlink()
            temporary.symlink_to(previous)
            os.replace(temporary, shim)
            results.append({"tool_id": str(operation["tool_id"]), "status": "restored"})
        else:
            shim.unlink()
            results.append({"tool_id": str(operation["tool_id"]), "status": "removed"})
    return results


def _remove_user_generation(
    generation_root: Path, *, owned_root: Path, bin_root: Path
) -> None:
    root = owned_root.resolve()
    if (
        generation_root.is_symlink()
        or not generation_root.is_dir()
        or generation_root.resolve().parent != root
    ):
        return
    for shim in bin_root.iterdir() if bin_root.is_dir() else []:
        if shim.is_symlink() and shim.resolve().is_relative_to(
            generation_root.resolve()
        ):
            return
    shutil.rmtree(generation_root)


def _verify_user_actions(
    plan: dict[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    _data_root, _state_root, bin_root = _user_roots()
    environment = _safe_environment(home=Path.home())
    environment["PATH"] = bin_root.as_posix() + os.pathsep + SAFE_PATH
    for row in plan["tools"]:
        if row["install_action"]["kind"] not in {"forge-user", "user-local"}:
            continue
        argv = row.get("verification_command", [])
        if not argv:
            raise ToolingSuiteError(
                f"user tool lacks a verification command: {row['id']}"
            )
        result = _run(argv, runner=runner, timeout=30, env=environment)
        if result.returncode != 0:
            raise ToolingSuiteError(f"user tool verification failed: {row['id']}")


def _verify_root_actions_as_user(
    plan: dict[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    _data_root, _state_root, bin_root = _user_roots()
    environment = _safe_environment(home=Path.home())
    environment["PATH"] = bin_root.as_posix() + os.pathsep + SAFE_PATH
    manager = str(plan["platform"]["package_manager"])
    for row in plan["tools"]:
        action = row["install_action"]
        if action["kind"] not in {"system-package", "forge-global"}:
            continue
        argv = row.get("verification_command", [])
        if not argv:
            installed, _candidate = _package_versions(
                str(action.get("package", "")), manager, runner=runner
            )
            if installed:
                continue
            raise ToolingSuiteError(
                f"target-user package verification failed: {row['id']}"
            )
        result = _run(argv, runner=runner, timeout=60, env=environment)
        passed = result.returncode == 0
        if row["id"] == "podman" and action["kind"] == "system-package":
            rootless = _run(
                ["podman", "info", "--format", "{{.Host.Security.Rootless}}"],
                runner=runner,
                timeout=60,
                env=environment,
            )
            passed = (
                passed
                and rootless.returncode == 0
                and rootless.stdout.strip() == "true"
            )
        if not passed:
            raise ToolingSuiteError(
                f"target-user root action verification failed: {row['id']}"
            )


def _prune_user_generations(
    owned_root: Path,
    bin_root: Path,
    generation_root: Path,
    operations: Sequence[dict[str, Any]],
) -> None:
    if owned_root.is_symlink() or not owned_root.is_dir():
        return
    keep: set[str] = {generation_root.name}
    for shim in bin_root.iterdir() if bin_root.is_dir() else []:
        if not shim.is_symlink():
            continue
        resolved = shim.resolve()
        if resolved.is_relative_to(owned_root.resolve()):
            relative = resolved.relative_to(owned_root.resolve())
            if relative.parts:
                keep.add(relative.parts[0])
    for operation in operations:
        previous = str(operation.get("previous_target", ""))
        if not previous:
            continue
        resolved = (owned_root / previous).resolve()
        if resolved.is_relative_to(owned_root.resolve()):
            relative = resolved.relative_to(owned_root.resolve())
            if relative.parts:
                keep.add(relative.parts[0])
    for candidate in owned_root.iterdir():
        if (
            candidate.name not in keep
            and candidate.is_dir()
            and not candidate.is_symlink()
            and candidate.resolve().parent == owned_root.resolve()
        ):
            shutil.rmtree(candidate)


def _root_path(root_prefix: Path, relative: str) -> Path:
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise ToolingSuiteError("internal root path is unsafe")
    return root_prefix / relative


def _reject_root_symlinks(
    root_prefix: Path,
    paths: Sequence[Path],
    *,
    enforce_root_owner: bool = False,
) -> None:
    boundary = root_prefix.resolve()
    for path in paths:
        try:
            relative = path.relative_to(root_prefix)
        except ValueError as error:
            raise ToolingSuiteError(
                "internal root target escaped its prefix"
            ) from error
        current = root_prefix
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ToolingSuiteError(
                    f"root target contains a symbolic link: {relative}"
                )
            if current.exists():
                metadata = current.stat()
                if enforce_root_owner and (
                    metadata.st_uid != 0 or metadata.st_mode & 0o022
                ):
                    raise ToolingSuiteError(
                        f"root target has unsafe ownership: {relative}"
                    )
        if path.exists() and not path.resolve().is_relative_to(boundary):
            raise ToolingSuiteError("root target escaped its prefix")


def _mkdir_public_executable(path: Path, *, enforce_root_owner: bool = False) -> None:
    previous_umask = os.umask(0o022)
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o755)
    finally:
        os.umask(previous_umask)
    metadata = path.stat()
    if (
        path.is_symlink()
        or not path.is_dir()
        or metadata.st_mode & 0o777 != 0o755
        or (enforce_root_owner and metadata.st_uid != 0)
    ):
        raise ToolingSuiteError(
            f"Forge executable directory permissions are unsafe: {path}"
        )


def _mkdir_private(path: Path, *, enforce_root_owner: bool = False) -> None:
    previous_umask = os.umask(0o077)
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    finally:
        os.umask(previous_umask)
    metadata = path.stat()
    if (
        path.is_symlink()
        or not path.is_dir()
        or metadata.st_mode & 0o777 != 0o700
        or (enforce_root_owner and metadata.st_uid != 0)
    ):
        raise ToolingSuiteError(
            f"Forge private directory permissions are unsafe: {path}"
        )


def _seal_root_assets(
    staged: dict[str, Path],
    plan: dict[str, Any],
    destination_root: Path,
    *,
    enforce_root_owner: bool,
) -> dict[str, Path]:
    _mkdir_private(destination_root, enforce_root_owner=enforce_root_owner)
    expected = {
        row["id"]: str(row["resolved"].get("sha256", ""))
        for row in plan["tools"]
        if row["install_action"]["kind"] == "forge-global"
    }
    sealed: dict[str, Path] = {}
    for tool_id, digest in expected.items():
        source = staged.get(tool_id)
        if source is None or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ToolingSuiteError(f"root asset binding is missing: {tool_id}")
        destination = destination_root / tool_id
        temporary = destination.with_suffix(".new")
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o600)
        if (
            temporary.stat().st_size > MAX_ASSET_BYTES
            or sha256_file(temporary) != digest
        ):
            temporary.unlink(missing_ok=True)
            raise ToolingSuiteError(f"root asset changed after staging: {tool_id}")
        os.replace(temporary, destination)
        sealed[tool_id] = destination
    offline = plan.get("offline", {})
    if isinstance(offline, dict):
        package_root = destination_root / "os-packages"
        trust_root = destination_root / "trust"
        package_assets = offline.get("package_assets", [])
        trust_assets = offline.get("trust_assets", [])
        if package_assets:
            _mkdir_private(package_root, enforce_root_owner=enforce_root_owner)
        if trust_assets:
            _mkdir_private(trust_root, enforce_root_owner=enforce_root_owner)
        for item in trust_assets:
            filename = str(item.get("path", ""))
            source = staged.get("offline-trust:" + filename)
            digest = str(item.get("sha256", ""))
            if source is None or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ToolingSuiteError(
                    f"offline trust asset binding is missing: {filename}"
                )
            destination = trust_root / filename
            temporary = destination.with_suffix(destination.suffix + ".new")
            shutil.copyfile(source, temporary)
            os.chmod(temporary, 0o600)
            if sha256_file(temporary) != digest:
                temporary.unlink(missing_ok=True)
                raise ToolingSuiteError(
                    f"offline trust asset changed after staging: {filename}"
                )
            os.replace(temporary, destination)
            sealed["offline-trust:" + filename] = destination
        for item in package_assets:
            for prefix, filename_key, digest_key in (
                ("offline-package:", "filename", "sha256"),
                (
                    "offline-signature:",
                    "signature_filename",
                    "signature_sha256",
                ),
                (
                    "offline-rollback:",
                    "rollback_filename",
                    "rollback_sha256",
                ),
                (
                    "offline-rollback-signature:",
                    "rollback_signature_filename",
                    "rollback_signature_sha256",
                ),
            ):
                filename = str(item.get(filename_key, ""))
                if not filename:
                    continue
                source = staged.get(prefix + filename)
                digest = str(item.get(digest_key, ""))
                if source is None or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ToolingSuiteError(
                        f"offline root asset binding is missing: {filename}"
                    )
                destination = package_root / filename
                temporary = destination.with_suffix(destination.suffix + ".new")
                shutil.copyfile(source, temporary)
                os.chmod(temporary, 0o600)
                if sha256_file(temporary) != digest:
                    temporary.unlink(missing_ok=True)
                    raise ToolingSuiteError(
                        f"offline root asset changed after staging: {filename}"
                    )
                os.replace(temporary, destination)
                sealed[prefix + filename] = destination
    return sealed


def _prune_global_versions(
    operations: Sequence[dict[str, Any]],
    tools_root: Path,
) -> None:
    root = tools_root.resolve()
    for operation in operations:
        if operation.get("kind") != "forge-global":
            continue
        tool_root = tools_root / str(operation["tool_id"])
        if (
            tool_root.is_symlink()
            or not tool_root.is_dir()
            or tool_root.resolve().parent != root
        ):
            continue
        keep: set[Path] = {Path(str(operation["installed_target"])).resolve().parent}
        previous = str(operation.get("previous_target", ""))
        if previous:
            previous_path = Path(previous)
            if not previous_path.is_absolute():
                previous_path = Path(str(operation["shim"])).parent / previous_path
            previous_parent = previous_path.resolve().parent
            if previous_parent.is_relative_to(tool_root.resolve()):
                keep.add(previous_parent)
        for candidate in tool_root.iterdir():
            if (
                candidate.resolve() not in keep
                and candidate.is_dir()
                and not candidate.is_symlink()
                and candidate.resolve().parent == tool_root.resolve()
            ):
                shutil.rmtree(candidate)


def _package_install_argv(
    manager: str, package: str, version: str, *, arch_sync: bool
) -> list[str]:
    if manager == "apt":
        return [
            "apt-get",
            "install",
            "-y",
            "--no-install-recommends",
            "--",
            f"{package}={version}",
        ]
    if manager == "dnf":
        return [
            "dnf",
            "install",
            "-y",
            "--setopt=install_weak_deps=False",
            f"{package}-{version}",
        ]
    if manager == "pacman" and arch_sync:
        return ["pacman", "-Syu", "--needed", "--noconfirm", "--", package]
    raise ToolingSuiteError(f"package-manager action is unsupported: {manager}")


def _installed_package_version_only(
    package: str,
    manager: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    if manager == "apt":
        result = _run(
            ["dpkg-query", "-W", "-f=${Status}\t${Version}", "--", package],
            runner=runner,
            timeout=30,
            env=_safe_environment(home=Path("/root")),
        )
        status, separator, version = result.stdout.strip().partition("\t")
        return (
            version
            if result.returncode == 0
            and separator
            and status == "install ok installed"
            else ""
        )
    if manager == "dnf":
        result = _run(
            ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", "--", package],
            runner=runner,
            timeout=30,
            env=_safe_environment(home=Path("/root")),
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    if manager == "pacman":
        result = _run(
            ["pacman", "-Q", "--", package],
            runner=runner,
            timeout=30,
            env=_safe_environment(home=Path("/root")),
        )
        name, separator, version = result.stdout.strip().partition(" ")
        return version if result.returncode == 0 and separator and name == package else ""
    raise ToolingSuiteError(f"offline package manager is unsupported: {manager}")


def _offline_install_argv(manager: str, paths: Sequence[Path]) -> list[str]:
    rendered = [path.as_posix() for path in paths]
    if manager == "apt":
        return [
            "apt-get",
            "-o",
            "Dir::Etc::sourcelist=/dev/null",
            "-o",
            "Dir::Etc::sourceparts=-",
            "-o",
            "Acquire::http::Proxy=false",
            "-o",
            "Acquire::https::Proxy=false",
            "install",
            "-y",
            "--no-install-recommends",
            "--",
            *rendered,
        ]
    if manager == "dnf":
        return [
            "dnf",
            "--disablerepo=*",
            "install",
            "-y",
            "--setopt=install_weak_deps=False",
            "--setopt=keepcache=False",
            *rendered,
        ]
    if manager == "pacman":
        return ["pacman", "-U", "--needed", "--noconfirm", "--", *rendered]
    raise ToolingSuiteError(f"offline package manager is unsupported: {manager}")


def _apt_release_sha256s(text: str) -> set[str]:
    digests: set[str] = set()
    in_sha256 = False
    for line in text.splitlines():
        if line == "SHA256:":
            in_sha256 = True
            continue
        if in_sha256 and line.startswith(" "):
            fields = line.split()
            if len(fields) == 3 and re.fullmatch(r"[0-9a-f]{64}", fields[0]):
                digests.add(fields[0])
            continue
        if in_sha256:
            break
    return digests


def _apt_index_package_hashes(text: str) -> set[tuple[str, str, str, str]]:
    records: set[tuple[str, str, str, str]] = set()
    for stanza in text.split("\n\n"):
        fields: dict[str, str] = {}
        for line in stanza.splitlines():
            key, separator, value = line.partition(":")
            if separator and key in {"Package", "Version", "Architecture", "SHA256"}:
                fields[key] = value.strip()
        if set(fields) == {"Package", "Version", "Architecture", "SHA256"}:
            records.add(
                (
                    fields["Package"],
                    fields["Version"],
                    fields["Architecture"],
                    fields["SHA256"],
                )
            )
    return records


def _offline_debian_package_fields(
    package_path: Path,
    fields: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> list[str]:
    allowed = {"Architecture", "Package", "Version"}
    if not fields or set(fields) - allowed:
        raise ToolingSuiteError("unsupported offline Debian metadata field")
    values: list[str] = []
    for field in fields:
        result = _run(
            ["dpkg-deb", "-f", package_path.as_posix(), field],
            runner=runner,
            timeout=30,
            env=_safe_environment(home=Path("/root")),
        )
        value = result.stdout.strip()
        if result.returncode != 0 or not value or "\n" in value:
            raise ToolingSuiteError(
                "offline Debian package metadata is malformed"
            )
        values.append(value)
    return values


def _verify_offline_apt_trust(
    plan: dict[str, Any],
    sealed: dict[str, Path],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    offline = plan.get("offline", {})
    records = list(offline.get("trust_assets", []))
    keyrings = [
        sealed.get("offline-trust:" + str(item["path"]))
        for item in records
        if item.get("kind") == "apt-keyring"
    ]
    releases = [
        sealed.get("offline-trust:" + str(item["path"]))
        for item in records
        if item.get("kind") == "apt-inrelease"
    ]
    indexes = [
        sealed.get("offline-trust:" + str(item["path"]))
        for item in records
        if item.get("kind") == "apt-packages-index"
    ]
    if not keyrings or not releases or not indexes or any(
        path is None for path in [*keyrings, *releases, *indexes]
    ):
        raise ToolingSuiteError("sealed APT trust closure is incomplete")
    verified_digests: set[str] = set()
    for release in releases:
        assert release is not None
        argv = ["gpgv"]
        for keyring in keyrings:
            assert keyring is not None
            argv.extend(["--keyring", keyring.as_posix()])
        argv.append(release.as_posix())
        result = _run(
            argv,
            runner=runner,
            timeout=60,
            env=_safe_environment(home=Path("/root")),
        )
        if result.returncode != 0:
            raise ToolingSuiteError("sealed APT InRelease signature verification failed")
        verified_digests.update(
            _apt_release_sha256s(release.read_text(encoding="utf-8"))
        )
    records_by_path = {str(item["path"]): item for item in records}
    indexed_packages: set[tuple[str, str, str, str]] = set()
    for index in indexes:
        assert index is not None
        record = records_by_path[index.name]
        repository_digest = str(record.get("repository_sha256", ""))
        expected_size = int(record.get("uncompressed_size", -1))
        if (
            record.get("compression") != "gzip"
            or repository_digest not in verified_digests
            or not 0 < expected_size <= MAX_ASSET_BYTES
        ):
            raise ToolingSuiteError(
                "sealed APT Packages index is absent from signed release metadata"
            )
        try:
            with gzip.open(index, "rb") as stream:
                content = stream.read(expected_size + 1)
            text = content.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ToolingSuiteError(
                "sealed APT Packages index compression is invalid"
            ) from error
        if (
            len(content) != expected_size
            or hashlib.sha256(content).hexdigest() != repository_digest
        ):
            raise ToolingSuiteError(
                "sealed APT Packages index content binding is invalid"
            )
        indexed_packages.update(_apt_index_package_hashes(text))
    for asset in offline.get("package_assets", []):
        digest = str(asset.get("sha256", ""))
        if asset.get("repository_sha256") != digest or (
            str(asset["package"]),
            str(asset["version"]),
            str(asset["arch"]),
            digest,
        ) not in indexed_packages:
            raise ToolingSuiteError(
                f"offline Debian package lacks signed-index proof: {asset['package']}"
            )
        previous = str(asset.get("previous_version", ""))
        if previous and previous != asset.get("version"):
            rollback_digest = str(asset.get("rollback_sha256", ""))
            if asset.get("rollback_repository_sha256") != rollback_digest or (
                str(asset["package"]),
                previous,
                str(asset.get("rollback_arch", "")),
                rollback_digest,
            ) not in indexed_packages:
                raise ToolingSuiteError(
                    f"offline Debian rollback lacks signed-index proof: {asset['package']}"
                )


def _apply_offline_package_closure(
    plan: dict[str, Any],
    sealed: dict[str, Path],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> list[dict[str, Any]]:
    offline = plan.get("offline", {})
    manager = str(plan["platform"]["package_manager"])
    assets = list(offline.get("package_assets", []))
    direct = {
        str(action["package"]): str(action["tool_id"])
        for action in plan["root_actions"]
        if action["kind"] == "system-package"
    }
    changed: list[dict[str, Any]] = []
    install_paths: list[Path] = []
    if manager == "apt":
        _verify_offline_apt_trust(plan, sealed, runner=runner)
    for asset in assets:
        package = str(asset["package"])
        version = str(asset["version"])
        previous = str(asset.get("previous_version", ""))
        current = _installed_package_version_only(
            package,
            manager,
            runner=runner,
        )
        if current != previous:
            raise ToolingSuiteError(
                f"offline package state drifted after approval: {package}"
            )
        path = sealed.get("offline-package:" + str(asset["filename"]))
        if path is None:
            raise ToolingSuiteError(f"sealed offline package is missing: {package}")
        if manager == "dnf":
            signature = _run(
                ["rpmkeys", "--checksig", "--verbose", path.as_posix()],
                runner=runner,
                timeout=30,
                env=_safe_environment(home=Path("/root")),
            )
            if not _rpm_signature_verified(signature):
                raise ToolingSuiteError(
                    f"offline RPM signature verification failed: {package}"
                )
        elif manager == "pacman":
            signature_path = sealed.get(
                "offline-signature:" + str(asset.get("signature_filename", ""))
            )
            if signature_path is None:
                raise ToolingSuiteError(
                    f"offline Pacman signature is missing: {package}"
                )
            signature = _run(
                [
                    "pacman-key",
                    "--verify",
                    signature_path.as_posix(),
                    path.as_posix(),
                ],
                runner=runner,
                timeout=30,
                env=_safe_environment(home=Path("/root")),
            )
            if signature.returncode != 0:
                raise ToolingSuiteError(
                    f"offline Pacman signature verification failed: {package}"
                )
        elif manager == "apt":
            package_fields = _offline_debian_package_fields(
                path,
                ["Package", "Version", "Architecture"],
                runner=runner,
            )
            if package_fields != [
                package,
                version,
                str(asset["arch"]),
            ]:
                raise ToolingSuiteError(
                    f"offline Debian package verification failed: {package}"
                )
        if current == version:
            continue
        rollback_path: Path | None = None
        rollback_signature_path: Path | None = None
        rollback_filename = str(asset.get("rollback_filename", ""))
        if previous and previous != version:
            rollback_path = sealed.get("offline-rollback:" + rollback_filename)
            if rollback_path is None:
                raise ToolingSuiteError(
                    f"offline rollback closure is missing: {package}"
                )
            rollback_signature_filename = str(
                asset.get("rollback_signature_filename", "")
            )
            if rollback_signature_filename:
                rollback_signature_path = sealed.get(
                    "offline-rollback-signature:" + rollback_signature_filename
                )
                if rollback_signature_path is None:
                    raise ToolingSuiteError(
                        f"offline rollback signature is missing: {package}"
                    )
        install_paths.append(path)
        changed.append(
            {
                "kind": "system-package",
                "tool_id": direct.get(package, f"offline-dependency:{package}"),
                "manager": manager,
                "package": package,
                "version": version,
                "previous_version": previous,
                "rollback_asset": rollback_path.as_posix() if rollback_path else "",
                "rollback_signature": (
                    rollback_signature_path.as_posix()
                    if rollback_signature_path
                    else ""
                ),
                "offline": True,
            }
        )
    if install_paths:
        result = _run(
            _offline_install_argv(manager, install_paths),
            runner=runner,
            timeout=3600,
            env=_safe_environment(home=Path("/root")),
        )
        if result.returncode != 0:
            raise ToolingSuiteError("sealed offline package transaction failed")
    for operation in changed:
        installed = _installed_package_version_only(
            str(operation["package"]),
            manager,
            runner=runner,
        )
        if installed != operation["version"]:
            raise ToolingSuiteError(
                f"offline package verification failed: {operation['package']}"
            )
    dependencies = [
        operation
        for operation in changed
        if str(operation["tool_id"]).startswith("offline-dependency:")
    ]
    direct_operations = [
        operation
        for operation in changed
        if not str(operation["tool_id"]).startswith("offline-dependency:")
    ]
    return [*dependencies, *direct_operations]


def _prepare_package_rollback(
    manager: str,
    package: str,
    previous_version: str,
    backup_root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    root_prefix: Path,
) -> Path | None:
    if not previous_version:
        return None
    backup_root.mkdir(parents=True, exist_ok=True)
    if manager == "apt":
        result = _run(
            ["apt", "download", f"{package}={previous_version}"],
            runner=runner,
            timeout=900,
            env=_safe_environment(home=Path("/root")),
            cwd=backup_root,
        )
        candidates = sorted(backup_root.glob("*.deb")) if result.returncode == 0 else []
    elif manager == "dnf":
        result = _run(
            [
                "dnf",
                "download",
                "--destdir",
                backup_root.as_posix(),
                f"{package}-{previous_version}",
            ],
            runner=runner,
            timeout=900,
            env=_safe_environment(home=Path("/root")),
        )
        candidates = sorted(backup_root.glob("*.rpm")) if result.returncode == 0 else []
    elif manager == "pacman":
        cache = _root_path(root_prefix, "var/cache/pacman/pkg")
        candidates = sorted(cache.glob(f"{package}-{previous_version}-*.pkg.tar.*"))
    else:
        candidates = []
    regular = [path for path in candidates if path.is_file() and not path.is_symlink()]
    if len(regular) != 1:
        return None
    return regular[0]


def _rollback_package_argv(operation: dict[str, Any]) -> list[str]:
    manager = str(operation["manager"])
    package = str(operation["package"])
    previous = str(operation.get("previous_version", ""))
    artifact = str(operation.get("rollback_asset", ""))
    if previous and artifact:
        if operation.get("offline") is True:
            if manager == "apt":
                return ["dpkg", "--install", "--", artifact]
            if manager == "dnf":
                return ["rpm", "-U", "--oldpackage", "--replacepkgs", artifact]
            if manager == "pacman":
                return ["pacman", "-U", "--noconfirm", "--", artifact]
        if manager == "apt":
            return ["apt-get", "install", "-y", "--", artifact]
        if manager == "dnf":
            return ["dnf", "downgrade", "-y", artifact]
        if manager == "pacman":
            return ["pacman", "-U", "--noconfirm", "--", artifact]
    if not previous:
        if manager == "apt":
            return ["dpkg", "--remove", "--", package]
        if manager == "dnf":
            return ["rpm", "-e", package]
        if manager == "pacman":
            return ["pacman", "-R", "--noconfirm", "--", package]
    return []


def _rollback_root_operations(
    operations: Sequence[dict[str, Any]],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    owned_root: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for operation in reversed(operations):
        if operation["kind"] == "forge-global":
            shim = Path(operation["shim"])
            installed = str(operation["installed_target"])
            if not shim.is_symlink() or os.readlink(shim) != installed:
                results.append(
                    {"tool_id": operation["tool_id"], "status": "preserved-newer"}
                )
                continue
            previous = str(operation.get("previous_target", ""))
            if previous:
                temporary = shim.with_name(f".{shim.name}.moradin-rollback")
                if temporary.exists() or temporary.is_symlink():
                    temporary.unlink()
                temporary.symlink_to(previous)
                os.replace(temporary, shim)
                results.append({"tool_id": operation["tool_id"], "status": "restored"})
            else:
                shim.unlink()
                results.append({"tool_id": operation["tool_id"], "status": "removed"})
            version_root = Path(installed).parent
            tool_root = owned_root / str(operation["tool_id"])
            if (
                version_root.is_dir()
                and not version_root.is_symlink()
                and version_root.resolve().parent == tool_root.resolve()
                and not any(
                    candidate.is_symlink()
                    and candidate.resolve().is_relative_to(version_root.resolve())
                    for candidate in shim.parent.iterdir()
                )
            ):
                shutil.rmtree(version_root)
        elif operation["kind"] == "system-package":
            current = _installed_package_version_only(
                str(operation["package"]),
                str(operation["manager"]),
                runner=runner,
            )
            if current != str(operation.get("version", "")):
                results.append(
                    {"tool_id": operation["tool_id"], "status": "preserved-newer"}
                )
                continue
            rollback_asset = str(operation.get("rollback_asset", ""))
            rollback_signature = str(operation.get("rollback_signature", ""))
            if operation.get("offline") is True and rollback_asset:
                manager = str(operation["manager"])
                if manager == "dnf":
                    signature = _run(
                        ["rpmkeys", "--checksig", "--verbose", rollback_asset],
                        runner=runner,
                        timeout=30,
                        env=_safe_environment(home=Path("/root")),
                    )
                    if not _rpm_signature_verified(signature):
                        results.append(
                            {"tool_id": operation["tool_id"], "status": "failed"}
                        )
                        continue
                elif manager == "pacman":
                    if not rollback_signature:
                        results.append(
                            {"tool_id": operation["tool_id"], "status": "failed"}
                        )
                        continue
                    signature = _run(
                        ["pacman-key", "--verify", rollback_signature, rollback_asset],
                        runner=runner,
                        timeout=30,
                        env=_safe_environment(home=Path("/root")),
                    )
                    if signature.returncode != 0:
                        results.append(
                            {"tool_id": operation["tool_id"], "status": "failed"}
                        )
                        continue
            argv = _rollback_package_argv(operation)
            if not argv:
                results.append({"tool_id": operation["tool_id"], "status": "manual"})
                continue
            result = _run(
                argv,
                runner=runner,
                timeout=900,
                env=_safe_environment(home=Path("/root")),
            )
            restored_status = "restored" if result.returncode == 0 else "failed"
            if result.returncode == 0 and not operation.get("previous_version"):
                restored_status = "removed-direct-package-dependencies-retained"
            results.append(
                {
                    "tool_id": operation["tool_id"],
                    "status": restored_status,
                }
            )
    return results


def apply_root_transaction(
    plan: dict[str, Any],
    *,
    stage_root: Path,
    root_prefix: Path = Path("/"),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_root: bool = True,
) -> dict[str, Any]:
    if require_root and os.geteuid() != 0:
        raise ToolingSuiteError(
            "the root transaction must run through the reviewed sudo boundary"
        )
    if plan["status"] not in {"ready", "repository-bootstrap"}:
        raise ToolingSuiteError(
            f"root transaction refuses plan status: {plan['status']}"
        )
    staged_assets = validate_staged_assets(stage_root, plan)
    generation = str(plan["plan_sha256"])[:16]
    tools_root = _root_path(root_prefix, "opt/moradins-forge/tools")
    forge_opt_root = _root_path(root_prefix, "opt/moradins-forge")
    bin_root = _root_path(root_prefix, "usr/local/bin")
    receipt_root = _root_path(
        root_prefix, f"var/lib/moradins-forge/receipts/{generation}"
    )
    backup_root = _root_path(root_prefix, f"var/backups/moradins-forge/{generation}")
    _reject_root_symlinks(
        root_prefix,
        (forge_opt_root, tools_root, bin_root, receipt_root, backup_root),
        enforce_root_owner=require_root,
    )
    if (
        receipt_root.exists()
        or receipt_root.is_symlink()
        or backup_root.exists()
        or backup_root.is_symlink()
    ):
        raise ToolingSuiteError(
            "this exact root transaction already has state; create and approve a fresh plan"
        )
    _mkdir_public_executable(forge_opt_root, enforce_root_owner=require_root)
    _mkdir_public_executable(tools_root, enforce_root_owner=require_root)
    _mkdir_public_executable(bin_root, enforce_root_owner=require_root)
    _mkdir_private(receipt_root, enforce_root_owner=require_root)
    _mkdir_private(backup_root, enforce_root_owner=require_root)
    assets = _seal_root_assets(
        staged_assets,
        plan,
        backup_root / "staged-assets",
        enforce_root_owner=require_root,
    )
    manager = str(plan["platform"]["package_manager"])
    rows_by_id = {row["id"]: row for row in plan["tools"]}
    actions = list(plan["root_actions"])
    if plan.get("repository_bootstrap"):
        repository = plan["repository_bootstrap"]
        actions = [
            {
                "kind": "system-package",
                "tool_id": "repository:epel",
                "package": repository["package"],
                "version": repository["version"],
                "manager": "dnf",
                "previous_version": repository.get("previous_version", ""),
                "rollback_closure": (
                    "required-at-apply"
                    if repository.get("previous_version")
                    else "remove-owned-package"
                ),
            }
        ]
    operations: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    try:
        offline_enabled = isinstance(plan.get("offline"), dict)
        if offline_enabled:
            operations.extend(
                _apply_offline_package_closure(
                    plan,
                    assets,
                    runner=runner,
                )
            )
            actions = [
                action for action in actions if action["kind"] != "system-package"
            ]
        package_actions = [
            action for action in actions if action["kind"] == "system-package"
        ]
        if package_actions and manager == "apt":
            refresh = _run(
                ["apt-get", "update"],
                runner=runner,
                timeout=900,
                env=_safe_environment(home=Path("/root")),
            )
            if refresh.returncode != 0:
                raise ToolingSuiteError("signed apt metadata refresh failed")
        for action in actions:
            tool_id = str(action["tool_id"])
            if action["kind"] == "system-package":
                package = str(action["package"])
                previous, candidate = _package_versions(package, manager, runner=runner)
                if candidate != action["version"]:
                    raise ToolingSuiteError(
                        f"signed package candidate changed after approval: {tool_id}"
                    )
                rollback_asset: Path | None = None
                if previous and previous != candidate:
                    rollback_asset = _prepare_package_rollback(
                        manager,
                        package,
                        previous,
                        backup_root / tool_id.replace(":", "_"),
                        runner=runner,
                        root_prefix=root_prefix,
                    )
                    if rollback_asset is None:
                        skipped.append(
                            {
                                "tool_id": tool_id,
                                "reason": "existing package retained because rollback closure is unavailable",
                            }
                        )
                        continue
                if previous == candidate:
                    skipped.append({"tool_id": tool_id, "reason": "already current"})
                    continue
                argv = _package_install_argv(
                    manager,
                    package,
                    candidate,
                    arch_sync=bool(plan.get("approve_arch_system_upgrade")),
                )
                result = _run(
                    argv,
                    runner=runner,
                    timeout=1800,
                    env=_safe_environment(home=Path("/root")),
                )
                if result.returncode != 0:
                    raise ToolingSuiteError(
                        f"signed package transaction failed: {tool_id}"
                    )
                operation = {
                    "kind": "system-package",
                    "tool_id": tool_id,
                    "manager": manager,
                    "package": package,
                    "version": candidate,
                    "previous_version": previous,
                    "rollback_asset": rollback_asset.as_posix()
                    if rollback_asset
                    else "",
                }
                operations.append(operation)
            elif action["kind"] == "forge-global":
                row = rows_by_id[tool_id]
                spec = catalog[tool_id]
                version = re.sub(r"[^A-Za-z0-9._+-]", "_", str(action["version"]))
                tool_root = tools_root / tool_id
                version_root = tool_root / version
                _mkdir_public_executable(tool_root, enforce_root_owner=require_root)
                if version_root.exists() or version_root.is_symlink():
                    raise ToolingSuiteError(
                        f"planned Forge version directory already exists: {tool_id}"
                    )
                _mkdir_public_executable(version_root, enforce_root_owner=require_root)
                destination = version_root / spec.command
                shim = bin_root / spec.command
                try:
                    materialize_verified_binary(
                        assets[tool_id], spec.command, destination
                    )
                    previous = _switch_owned_symlink(shim, destination, tools_root)
                except Exception:
                    if (
                        version_root.is_dir()
                        and not version_root.is_symlink()
                        and version_root.resolve().parent == tool_root.resolve()
                    ):
                        shutil.rmtree(version_root)
                    raise
                operations.append(
                    {
                        "kind": "forge-global",
                        "tool_id": tool_id,
                        "version": row["resolved"].get("version", action["version"]),
                        "shim": shim.as_posix(),
                        "installed_target": destination.as_posix(),
                        "previous_target": previous,
                    }
                )
            else:
                raise ToolingSuiteError(f"unexpected root action: {tool_id}")
        for operation in operations:
            if operation["tool_id"] == "repository:epel":
                if not _epel_enabled(runner=runner):
                    raise ToolingSuiteError(
                        "EPEL package installation did not enable the approved repository"
                    )
                continue
            tool_id = str(operation["tool_id"])
            row = rows_by_id.get(tool_id)
            if operation["kind"] == "system-package":
                if operation.get("offline") is True:
                    installed = _installed_package_version_only(
                        str(operation["package"]),
                        manager,
                        runner=runner,
                    )
                else:
                    installed, _candidate = _package_versions(
                        str(operation["package"]),
                        manager,
                        runner=runner,
                    )
                if installed != operation["version"]:
                    raise ToolingSuiteError(
                        f"root package verification failed: {operation['tool_id']}"
                    )
            if row is None and tool_id.startswith("offline-dependency:"):
                continue
            if row is None:
                raise ToolingSuiteError(
                    f"root operation does not map to a catalog tool: {tool_id}"
                )
            argv = row.get(
                "verification_command",
                _suite_verification_argv(catalog[operation["tool_id"]]),
            )
            if not argv:
                continue
            result = _run(
                argv,
                runner=runner,
                timeout=30,
                env=_safe_environment(home=Path("/root")),
            )
            if result.returncode != 0:
                raise ToolingSuiteError(
                    f"root verification failed: {operation['tool_id']}"
                )
        _prune_global_versions(operations, tools_root)
    except Exception as error:
        rollback = _rollback_root_operations(
            operations, runner=runner, owned_root=tools_root
        )
        retained = [
            str(item["tool_id"])
            for item in rollback
            if item["status"] in {"failed", "manual"}
        ]
        if retained:
            raise ToolingSuiteError(
                "root transaction failed and safe rollback retained package drift: "
                + ", ".join(retained)
            ) from error
        dependency_drift = [
            str(item["tool_id"])
            for item in rollback
            if item["status"] == "removed-direct-package-dependencies-retained"
        ]
        if dependency_drift:
            raise ToolingSuiteError(
                "root transaction failed; direct packages were removed but signed "
                "dependency drift was retained by design: "
                + ", ".join(dependency_drift)
            ) from error
        for failed_root in (receipt_root, backup_root):
            if (
                failed_root.is_dir()
                and not failed_root.is_symlink()
                and failed_root.resolve().parent == failed_root.parent.resolve()
            ):
                shutil.rmtree(failed_root)
        raise
    receipt: dict[str, Any] = {
        "version": ROOT_RECEIPT_VERSION,
        "generated_at": utc_now(),
        "plan_sha256": plan["plan_sha256"],
        "installer_manifest_sha256": plan.get(
            "installer_manifest_sha256", installer_manifest_sha256(REPO_ROOT)
        ),
        "status": "pass",
        "operations": operations,
        "skipped": skipped,
        "runtime_manifest_sha256": os.environ.get(
            "MORADIN_FORGE_SEALED_PYTHON_DIGEST", ""
        ),
        "runtime_executable": os.environ.get(
            "MORADIN_FORGE_SEALED_PYTHON_EXECUTABLE", ""
        ),
        "privacy": "Local root receipt; contains no project content, prompts, credentials, or telemetry.",
    }
    receipt["receipt_sha256"] = _record_digest(receipt, "receipt_sha256")
    receipt_path = receipt_root / "receipt.json"
    write_json(receipt_path, receipt)
    os.chmod(receipt_path, 0o600)
    return {**receipt, "receipt": receipt_path.as_posix()}


def _validate_root_receipt(
    receipt: dict[str, Any],
    receipt_path: Path,
    *,
    root_prefix: Path,
    enforce_root_owner: bool,
) -> None:
    receipt_store = _root_path(root_prefix, "var/lib/moradins-forge/receipts")
    try:
        resolved_receipt = receipt_path.resolve(strict=True)
        resolved_store = receipt_store.resolve(strict=True)
    except OSError as error:
        raise ToolingSuiteError("root receipt store is unavailable") from error
    if not resolved_receipt.is_relative_to(resolved_store):
        raise ToolingSuiteError("root receipt is outside the Forge receipt store")
    relative = resolved_receipt.relative_to(resolved_store)
    current = receipt_store
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ToolingSuiteError("root receipt path contains a symbolic link")
    metadata = resolved_receipt.stat()
    if enforce_root_owner and (metadata.st_uid != 0 or metadata.st_mode & 0o077):
        raise ToolingSuiteError("root receipt ownership or permissions are unsafe")
    if receipt.get("status") != "pass" or not re.fullmatch(
        r"[0-9a-f]{64}", str(receipt.get("plan_sha256", ""))
    ):
        raise ToolingSuiteError("root receipt status or plan binding is malformed")
    if receipt.get("installer_manifest_sha256") != installer_manifest_sha256(REPO_ROOT):
        raise ToolingSuiteError("root receipt does not match its sealed runner")
    runtime_digest = str(receipt.get("runtime_manifest_sha256", ""))
    runtime_executable = str(receipt.get("runtime_executable", ""))
    runtime_relative = Path(runtime_executable)
    if bool(runtime_digest) != bool(runtime_executable) or (
        runtime_digest
        and (
            not re.fullmatch(r"[0-9a-f]{64}", runtime_digest)
            or runtime_relative.is_absolute()
            or ".." in runtime_relative.parts
        )
    ):
        raise ToolingSuiteError("root receipt sealed Python binding is malformed")
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    tools_root = _root_path(root_prefix, "opt/moradins-forge/tools").resolve()
    bin_root = _root_path(root_prefix, "usr/local/bin").resolve()
    backup_root = _root_path(root_prefix, "var/backups/moradins-forge").resolve()
    seen: set[str] = set()
    for operation in receipt.get("operations", []):
        if not isinstance(operation, dict):
            raise ToolingSuiteError("root receipt operation is malformed")
        tool_id = str(operation.get("tool_id", ""))
        if tool_id in seen:
            raise ToolingSuiteError("root receipt contains a duplicate operation")
        seen.add(tool_id)
        kind = str(operation.get("kind", ""))
        if kind == "forge-global":
            spec = catalog.get(tool_id)
            if spec is None or not spec.command:
                raise ToolingSuiteError("root receipt contains an unknown global tool")
            shim = Path(str(operation.get("shim", "")))
            installed = Path(str(operation.get("installed_target", "")))
            expected_shim = bin_root / spec.command
            expected_tool_root = tools_root / tool_id
            if (
                shim != expected_shim
                or not installed.is_absolute()
                or installed.name != spec.command
                or not installed.resolve().is_relative_to(expected_tool_root.resolve())
                or installed.resolve().parent.parent != expected_tool_root.resolve()
            ):
                raise ToolingSuiteError("root receipt contains an unsafe global path")
            previous = str(operation.get("previous_target", ""))
            if previous:
                previous_path = Path(previous)
                if not previous_path.is_absolute():
                    previous_path = shim.parent / previous_path
                if not previous_path.resolve().is_relative_to(
                    expected_tool_root.resolve()
                ):
                    raise ToolingSuiteError(
                        "root receipt contains an unsafe predecessor"
                    )
        elif kind == "system-package":
            manager = str(operation.get("manager", ""))
            package = str(operation.get("package", ""))
            if tool_id == "repository:epel":
                expected_package = "epel-release"
                expected_manager = "dnf"
            elif (
                operation.get("offline") is True
                and tool_id.startswith("offline-dependency:")
            ):
                expected_package = tool_id.removeprefix("offline-dependency:")
                expected_manager = manager
            else:
                spec = catalog.get(tool_id)
                if spec is None:
                    raise ToolingSuiteError(
                        "root receipt contains an unknown package tool"
                    )
                expected_manager = manager
                expected_package = _package_name(spec, manager)
            if (
                manager not in SUPPORTED_MANAGERS
                or manager != expected_manager
                or not expected_package
                or package != expected_package
            ):
                raise ToolingSuiteError(
                    "root receipt package action is not catalog-owned"
                )
            rollback_asset = str(operation.get("rollback_asset", ""))
            if rollback_asset:
                asset = Path(rollback_asset)
                if (
                    not asset.is_absolute()
                    or not asset.resolve().is_relative_to(backup_root)
                    or asset.is_symlink()
                    or not asset.is_file()
                ):
                    raise ToolingSuiteError("root receipt rollback asset is unsafe")
            rollback_signature = str(operation.get("rollback_signature", ""))
            if rollback_signature:
                signature = Path(rollback_signature)
                if (
                    operation.get("offline") is not True
                    or not rollback_asset
                    or not signature.is_absolute()
                    or not signature.resolve().is_relative_to(backup_root)
                    or signature.is_symlink()
                    or not signature.is_file()
                ):
                    raise ToolingSuiteError(
                        "root receipt rollback signature is unsafe"
                    )
        else:
            raise ToolingSuiteError("root receipt operation kind is unsupported")


def rollback_root_receipt(
    receipt_path: Path,
    *,
    approved_sha256: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_root: bool = True,
    root_prefix: Path = Path("/"),
) -> dict[str, Any]:
    if require_root and os.geteuid() != 0:
        raise ToolingSuiteError(
            "root rollback must run through the reviewed sudo boundary"
        )
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ToolingSuiteError("root receipt must be a regular file")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingSuiteError("root receipt is invalid") from error
    if not isinstance(receipt, dict) or receipt.get("version") not in {
        ROOT_RECEIPT_VERSION,
        LEGACY_ROOT_RECEIPT_VERSION,
    }:
        raise ToolingSuiteError("root receipt version is unsupported")
    recorded = str(receipt.get("receipt_sha256", ""))
    if recorded != approved_sha256 or recorded != _record_digest(
        receipt, "receipt_sha256"
    ):
        raise ToolingSuiteError("approved root receipt digest does not match")
    _validate_root_receipt(
        receipt,
        receipt_path,
        root_prefix=root_prefix,
        enforce_root_owner=require_root,
    )
    results = _rollback_root_operations(
        receipt.get("operations", []),
        runner=runner,
        owned_root=_root_path(root_prefix, "opt/moradins-forge/tools"),
    )
    return {
        "version": SUITE_ROLLBACK_VERSION,
        "status": "pass"
        if all(item["status"] not in {"failed", "manual"} for item in results)
        else "fail",
        "root": results,
    }


def _invoke_root_apply(
    plan_path: Path,
    stage_root: Path,
    *,
    approved_sha256: str,
    installer_manifest_digest: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", installer_manifest_digest):
        raise ToolingSuiteError("root runner manifest digest is malformed")
    root_python = _trusted_root_bootstrap_python()
    runtime_arguments = _root_runtime_arguments(root_python)
    sudo_path = _trusted_sudo()
    runner_root = Path("/var/lib/moradins-forge/runners") / installer_manifest_digest
    argv = [
        sudo_path.as_posix(),
        "--",
        "/usr/bin/env",
        "-i",
        f"PATH={SAFE_PATH}",
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        root_python.as_posix(),
        "-I",
        "-c",
        ROOT_RUNNER_BOOTSTRAP,
        (stage_root / "root-runner").resolve().as_posix(),
        installer_manifest_digest,
        *runtime_arguments,
        "--forge-root",
        runner_root.as_posix(),
        "_root-apply",
        "--plan",
        plan_path.resolve().as_posix(),
        "--stage-root",
        stage_root.resolve().as_posix(),
        "--approve-plan-sha256",
        approved_sha256,
        "--target-uid",
        str(os.getuid()),
    ]
    result = _run(argv, timeout=3600)
    if result.returncode != 0:
        message = (
            result.stderr.strip().splitlines()[-1]
            if result.stderr.strip()
            else "unknown error"
        )
        raise ToolingSuiteError(f"approved root transaction failed: {message}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ToolingSuiteError(
            "root transaction did not return a valid receipt"
        ) from error
    if not isinstance(payload, dict) or payload.get("version") != ROOT_RECEIPT_VERSION:
        raise ToolingSuiteError("root transaction returned an unsupported receipt")
    return payload


def _invoke_root_rollback(
    receipt_path: Path,
    *,
    approved_sha256: str,
    installer_manifest_digest: str,
    runtime_manifest_sha256: str = "",
    runtime_executable: str = "",
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", installer_manifest_digest):
        raise ToolingSuiteError("root runner manifest digest is malformed")
    root_python = _trusted_root_bootstrap_python()
    runtime_arguments = _root_runtime_arguments(
        root_python,
        sealed_digest=runtime_manifest_sha256,
        sealed_executable=runtime_executable,
    )
    sudo_path = _trusted_sudo()
    runner_root = Path("/var/lib/moradins-forge/runners") / installer_manifest_digest
    argv = [
        sudo_path.as_posix(),
        "--",
        "/usr/bin/env",
        "-i",
        f"PATH={SAFE_PATH}",
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        root_python.as_posix(),
        "-I",
        "-c",
        ROOT_RUNNER_BOOTSTRAP,
        "-",
        installer_manifest_digest,
        *runtime_arguments,
        "--forge-root",
        runner_root.as_posix(),
        "_root-rollback",
        "--receipt",
        receipt_path.as_posix(),
        "--approve-receipt-sha256",
        approved_sha256,
    ]
    result = _run(argv, timeout=3600)
    if result.returncode != 0:
        message = (
            result.stderr.strip().splitlines()[-1]
            if result.stderr.strip()
            else "unknown error"
        )
        raise ToolingSuiteError(f"approved root rollback failed: {message}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ToolingSuiteError("root rollback did not return valid JSON") from error
    if not isinstance(payload, dict):
        raise ToolingSuiteError("root rollback returned an invalid result")
    return payload


def _completed_receipt_for_plan(plan_sha256: str) -> tuple[Path, dict[str, Any]] | None:
    _data_root, state_root, _bin_root = _user_roots()
    for path in reversed(sorted((state_root / "receipts").glob("*/receipt.json"))):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(receipt, dict)
            and receipt.get("version") in {
                SUITE_RECEIPT_VERSION,
                LEGACY_SUITE_RECEIPT_VERSION,
            }
            and receipt.get("plan_sha256") == plan_sha256
            and receipt.get("status") == "pass"
            and receipt.get("receipt_sha256")
            == _record_digest(receipt, "receipt_sha256")
        ):
            return path, receipt
    return None


def apply_suite_plan(
    plan_path: Path,
    *,
    approved_sha256: str,
    forge_root: Path,
    downloader: Callable[[str, Path], None] = _download_asset,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    root_applier: Callable[[dict[str, Any], Path], dict[str, Any]] | None = None,
    progress: str = "off",
) -> dict[str, Any]:
    plan = load_suite_plan(
        plan_path,
        approved_sha256=approved_sha256,
        forge_root=forge_root,
    )
    if plan["status"] not in {"ready", "repository-bootstrap"}:
        raise ToolingSuiteError(
            f"tooling-suite plan is not applicable: {plan['status']}"
        )
    completed = _completed_receipt_for_plan(str(plan["plan_sha256"]))
    if completed is not None:
        receipt_path, receipt = completed
        verification = verify_suite_receipt(receipt_path.as_posix(), runner=runner)
        if verification["status"] != "pass":
            raise ToolingSuiteError(
                "completed plan receipt no longer verifies; use the receipt rollback path"
            )
        _emit_progress(progress, "verified-completed-plan", plan_sha256=plan["plan_sha256"])
        return {
            **receipt,
            "receipt": receipt_path.as_posix(),
            "idempotent_reapply": True,
            "verification": verification,
        }
    data_root, state_root, bin_root = _user_roots()
    generation = str(plan["plan_sha256"])[:16]
    cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    stage_root = cache_base / "moradins-forge" / "tooling-suite" / generation
    _emit_progress(progress, "staging", plan_sha256=plan["plan_sha256"])
    if stage_root.exists():
        validate_staged_assets(stage_root, plan)
    else:
        stage_suite_assets(
            plan,
            output=stage_root,
            forge_root=forge_root,
            downloader=downloader,
        )
    _write_checkpoint(
        plan,
        "assets-staged",
        status="pass",
        evidence={"stage_manifest_sha256": sha256_file(stage_root / "stage-manifest.json")},
    )
    _emit_progress(progress, "staged", plan_sha256=plan["plan_sha256"])
    user_operations: list[dict[str, Any]] = []
    generation_root = data_root / "tools" / generation
    root_receipt: dict[str, Any] | None = None
    resumed_components: list[str] = []
    phase = "user-actions"
    try:
        if plan["status"] == "ready":
            user_checkpoint = _load_checkpoint(plan, "user-actions")
            if user_checkpoint and user_checkpoint.get("status") == "pass":
                evidence = user_checkpoint.get("evidence", {})
                user_operations = list(evidence.get("operations", []))
                if not generation_root.is_dir() or generation_root.is_symlink():
                    raise ToolingSuiteError(
                        "user checkpoint exists but its versioned generation is unavailable"
                    )
                _verify_user_actions(plan, runner=runner)
                resumed_components.append("user-actions")
            else:
                _emit_progress(progress, "applying-user-actions")
                user_operations, generation_root = _apply_user_actions(
                    plan,
                    stage_root,
                    runner=runner,
                )
                _verify_user_actions(plan, runner=runner)
                _write_checkpoint(
                    plan,
                    "user-actions",
                    status="pass",
                    evidence={"operations": user_operations},
                )
        needs_root = bool(plan["root_actions"] or plan.get("repository_bootstrap"))
        if needs_root:
            phase = "root-actions"
            root_checkpoint = _load_checkpoint(plan, "root-actions")
            if root_checkpoint and root_checkpoint.get("status") == "pass":
                evidence = root_checkpoint.get("evidence", {})
                root_receipt = dict(evidence.get("receipt", {}))
                if plan["status"] == "ready":
                    _verify_root_actions_as_user(plan, runner=runner)
                resumed_components.append("root-actions")
            else:
                _emit_progress(progress, "awaiting-human-root-approval")
                root_receipt = (
                    root_applier(plan, stage_root)
                    if root_applier is not None
                    else _invoke_root_apply(
                        plan_path,
                        stage_root,
                        approved_sha256=approved_sha256,
                        installer_manifest_digest=str(plan["installer_manifest_sha256"]),
                    )
                )
                if plan["status"] == "ready":
                    _verify_root_actions_as_user(plan, runner=runner)
                _write_checkpoint(
                    plan,
                    "root-actions",
                    status="pass",
                    evidence={"receipt": root_receipt},
                )
        phase = "verification"
        if plan["status"] == "ready":
            _verify_user_actions(plan, runner=runner)
            if needs_root:
                _verify_root_actions_as_user(plan, runner=runner)
        _write_checkpoint(
            plan,
            "verification",
            status="pass",
            evidence={"resumed_components": resumed_components},
        )
        _emit_progress(progress, "verified", plan_sha256=plan["plan_sha256"])
    except Exception as apply_error:
        _write_checkpoint(
            plan,
            phase,
            status="fail",
            evidence={"error_type": type(apply_error).__name__},
        )
        root_rollback_error: Exception | None = None
        if phase == "root-actions" and (
            root_receipt
            and root_receipt.get("receipt")
            and root_receipt.get("receipt_sha256")
            and root_receipt.get("installer_manifest_sha256")
        ):
            try:
                _invoke_root_rollback(
                    Path(str(root_receipt["receipt"])),
                    approved_sha256=str(root_receipt["receipt_sha256"]),
                    installer_manifest_digest=str(
                        root_receipt["installer_manifest_sha256"]
                    ),
                    runtime_manifest_sha256=str(
                        root_receipt.get("runtime_manifest_sha256", "")
                    ),
                    runtime_executable=str(
                        root_receipt.get("runtime_executable", "")
                    ),
                )
            except Exception as error:  # preserve root recovery evidence
                root_rollback_error = error
        if root_rollback_error is not None:
            raise ToolingSuiteError(
                "post-apply verification failed and automatic root rollback also failed; "
                "retain the root receipt for reviewed recovery"
            ) from apply_error
        raise
    receipt_dir = (
        state_root
        / "receipts"
        / f"{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{generation}"
    )
    try:
        receipt_dir.mkdir(parents=True, exist_ok=False)
        write_json(receipt_dir / "approved-plan.json", _portable_suite_plan(plan))
        receipt: dict[str, Any] = {
            "version": SUITE_RECEIPT_VERSION,
            "generated_at": utc_now(),
            "status": "replan-required"
            if plan["status"] == "repository-bootstrap"
            else "pass",
            "plan_sha256": plan["plan_sha256"],
            "profile": plan["profile"],
            "generation": generation,
            "resumed_components": resumed_components,
            "checkpoints": [
                "assets-staged",
                "user-actions",
                *( ["root-actions"] if root_receipt else [] ),
                "verification",
            ],
            "user_operations": user_operations,
            "root_receipt": (
                {
                    "path": root_receipt.get("receipt", ""),
                    "sha256": root_receipt.get("receipt_sha256", ""),
                    "installer_manifest_sha256": root_receipt.get(
                        "installer_manifest_sha256", ""
                    ),
                    "operations": root_receipt.get("operations", []),
                    "skipped": root_receipt.get("skipped", []),
                    "runtime_manifest_sha256": root_receipt.get(
                        "runtime_manifest_sha256", ""
                    ),
                    "runtime_executable": root_receipt.get(
                        "runtime_executable", ""
                    ),
                }
                if root_receipt
                else None
            ),
            "privacy": (
                "No telemetry, project contents, prompts, credentials, raw commands, "
                "workspace paths, or machine identifiers are stored."
            ),
        }
        receipt["receipt_sha256"] = _record_digest(receipt, "receipt_sha256")
        receipt_path = receipt_dir / "receipt.json"
        write_json(receipt_path, receipt)
        _write_checkpoint(
            plan,
            "receipt",
            status="pass",
            evidence={"receipt_id": receipt_dir.name},
        )
    except Exception as receipt_error:
        root_rollback_error: Exception | None = None
        if (
            root_receipt
            and root_receipt.get("receipt")
            and root_receipt.get("receipt_sha256")
        ):
            try:
                _invoke_root_rollback(
                    Path(str(root_receipt["receipt"])),
                    approved_sha256=str(root_receipt["receipt_sha256"]),
                    installer_manifest_digest=str(
                        root_receipt["installer_manifest_sha256"]
                    ),
                    runtime_manifest_sha256=str(
                        root_receipt.get("runtime_manifest_sha256", "")
                    ),
                    runtime_executable=str(
                        root_receipt.get("runtime_executable", "")
                    ),
                )
            except Exception as error:  # preserve root recovery evidence
                root_rollback_error = error
        _rollback_user_operations(
            user_operations,
            owned_root=data_root / "tools",
            bin_root=bin_root,
        )
        _remove_user_generation(
            generation_root,
            owned_root=data_root / "tools",
            bin_root=bin_root,
        )
        if receipt_dir.is_dir() and not receipt_dir.is_symlink():
            shutil.rmtree(receipt_dir)
        if root_rollback_error is not None:
            raise ToolingSuiteError(
                "receipt persistence and automatic root rollback both failed; "
                "retain the root receipt for reviewed recovery"
            ) from receipt_error
        raise
    return {**receipt, "receipt": receipt_path.as_posix()}


def _latest_user_receipt() -> Path:
    _data_root, state_root, _bin_root = _user_roots()
    candidates = sorted((state_root / "receipts").glob("*/receipt.json"))
    if not candidates:
        raise ToolingSuiteError("no tooling-suite receipt is available")
    return candidates[-1]


def _load_user_receipt(path_or_latest: str) -> tuple[Path, dict[str, Any]]:
    if path_or_latest == "latest":
        path = _latest_user_receipt()
    elif re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", path_or_latest):
        _data_root, state_root, _bin_root = _user_roots()
        path = state_root / "receipts" / path_or_latest / "receipt.json"
    else:
        path = Path(path_or_latest)
    if path.is_symlink() or not path.is_file():
        raise ToolingSuiteError("tooling-suite receipt must be a regular file")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingSuiteError("tooling-suite receipt is invalid") from error
    if not isinstance(receipt, dict) or receipt.get("version") not in {
        SUITE_RECEIPT_VERSION,
        LEGACY_SUITE_RECEIPT_VERSION,
    }:
        raise ToolingSuiteError("tooling-suite receipt version is unsupported")
    if receipt.get("receipt_sha256") != _record_digest(receipt, "receipt_sha256"):
        raise ToolingSuiteError("tooling-suite receipt digest does not match")
    return path, receipt


def verify_suite_receipt(
    path_or_latest: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    receipt_path, receipt = _load_user_receipt(path_or_latest)
    plan_path = receipt_path.parent / "approved-plan.json"
    if plan_path.is_symlink() or not plan_path.is_file():
        raise ToolingSuiteError("approved plan copy is missing beside the receipt")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ToolingSuiteError("approved plan copy is invalid") from error
    if (
        plan.get("source_plan_sha256") != receipt.get("plan_sha256")
        or plan_digest(plan) != plan.get("plan_sha256")
        or plan.get("portable") is not True
    ):
        raise ToolingSuiteError("receipt and approved plan copy are not bound")
    _data_root, _state_root, bin_root = _user_roots()
    environment = _safe_environment(home=Path.home())
    environment["PATH"] = bin_root.as_posix() + os.pathsep + SAFE_PATH
    checks: list[dict[str, Any]] = []
    for row in plan["tools"]:
        action = row["install_action"]
        if action["kind"] in {"manual", "none", "protected-existing"}:
            continue
        argv = row["verification_command"]
        if not argv:
            package = str(action.get("package", ""))
            installed, _candidate = _package_versions(
                package,
                str(plan["platform"]["package_manager"]),
                runner=runner,
            )
            passed = bool(installed)
            exit_code = 0 if passed else 1
        else:
            result = _run(argv, runner=runner, timeout=30, env=environment)
            exit_code = result.returncode
            passed = exit_code == 0
        checks.append(
            {
                "tool_id": row["id"],
                "status": "pass" if passed else "fail",
                "exit_code": exit_code,
            }
        )
    return {
        "version": "MoradinForgeToolingSuiteVerifyV2",
        "status": "pass"
        if all(item["status"] == "pass" for item in checks)
        else "fail",
        "receipt_sha256": receipt["receipt_sha256"],
        "checks": checks,
        "onboard_handoff": (
            "scripts/moradin_forge.sh onboard --workspace <approved-workspace>"
            if all(item["status"] == "pass" for item in checks)
            else ""
        ),
    }


def latest_suite_receipt_status(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Return a sanitized readiness result for onboarding's latest receipt check."""

    try:
        payload = verify_suite_receipt("latest", runner=runner)
    except ToolingSuiteError as error:
        message = str(error)
        missing = message == "no tooling-suite receipt is available"
        return {
            "status": "missing" if missing else "fail",
            "verified": False,
            "message": message,
        }
    return {
        "status": str(payload["status"]),
        "verified": payload["status"] == "pass",
        "receipt_sha256": str(payload["receipt_sha256"]),
        "check_count": len(payload["checks"]),
        "message": "latest tooling-suite receipt verified",
    }


def rollback_suite_receipt(
    path_or_latest: str,
    *,
    approved_sha256: str,
    forge_root: Path,
    root_rollback: Callable[[Path, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _path, receipt = _load_user_receipt(path_or_latest)
    if approved_sha256 != receipt["receipt_sha256"]:
        raise ToolingSuiteError("approved receipt digest does not match")
    root_result: dict[str, Any] | None = None
    root = receipt.get("root_receipt")
    if isinstance(root, dict) and root.get("path"):
        root_result = (
            root_rollback(Path(str(root["path"])), str(root["sha256"]))
            if root_rollback is not None
            else _invoke_root_rollback(
                Path(str(root["path"])),
                approved_sha256=str(root["sha256"]),
                installer_manifest_digest=str(root["installer_manifest_sha256"]),
                runtime_manifest_sha256=str(
                    root.get("runtime_manifest_sha256", "")
                ),
                runtime_executable=str(root.get("runtime_executable", "")),
            )
        )
    data_root, _state_root, bin_root = _user_roots()
    user_result = _rollback_user_operations(
        receipt.get("user_operations", []),
        owned_root=data_root / "tools",
        bin_root=bin_root,
    )
    generation = str(receipt.get("generation", ""))
    if not re.fullmatch(r"[0-9a-f]{16}", generation):
        raise ToolingSuiteError("tooling-suite receipt generation is malformed")
    generation_root = data_root / "tools" / generation
    tools_root = (data_root / "tools").resolve()
    if (
        generation_root.is_dir()
        and not generation_root.is_symlink()
        and generation_root.resolve().is_relative_to(tools_root)
        and generation_root.resolve() != tools_root
    ):
        _remove_user_generation(
            generation_root,
            owned_root=data_root / "tools",
            bin_root=bin_root,
        )
    status = "pass"
    if root_result and root_result.get("status") != "pass":
        status = "fail"
    return {
        "version": SUITE_ROLLBACK_VERSION,
        "status": status,
        "user": user_result,
        "root": root_result,
    }


def _portable_suite_plan(plan: dict[str, Any]) -> dict[str, Any]:
    portable = json.loads(json.dumps(plan))
    source_sha = portable.pop("plan_sha256")
    portable["approved_workspaces"] = [
        f"<workspace-{index}>"
        for index, _path in enumerate(portable.get("approved_workspaces", []), start=1)
    ]
    for index, repository in enumerate(portable.get("repositories", []), start=1):
        repository["path"] = f"<repo-{index}>"
    platform_row = portable.get("platform", {})
    platform_row["host_fingerprint_sha256"] = "<host-bound-at-apply>"
    portable["target_uid"] = "<target-uid>"
    doctor = portable.get("doctor", {})
    if isinstance(doctor, dict):
        doctor_platform = doctor.get("platform", {})
        if isinstance(doctor_platform, dict):
            doctor_platform["host_fingerprint_sha256"] = "<host-bound-at-apply>"
        doctor["target_uid"] = "<target-uid>"
        doctor.pop("doctor_sha256", None)
        doctor["doctor_sha256"] = _record_digest(doctor, "doctor_sha256")
        portable["doctor_sha256"] = doctor["doctor_sha256"]
    portable["source_plan_sha256"] = source_sha
    portable["portable"] = True
    portable["plan_sha256"] = plan_digest(portable)
    return portable


def build_suite_bundle(
    plan_path: Path,
    *,
    output: Path,
    forge_root: Path,
    downloader: Callable[[str, Path], None] = _download_asset,
) -> dict[str, Any]:
    plan = load_suite_plan(plan_path, forge_root=forge_root)
    if output.exists() or output.is_symlink():
        raise ToolingSuiteError(f"bundle output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="moradin-suite-bundle-", dir=output.parent
    ) as temporary:
        root = Path(temporary) / "bundle"
        stage = Path(temporary) / "stage"
        stage_suite_assets(
            plan,
            output=stage,
            forge_root=forge_root,
            downloader=downloader,
        )
        root.mkdir()
        for name in ("assets", "wheels", "root-runner"):
            source = stage / name
            if source.is_dir():
                shutil.copytree(source, root / name)
        for name in ("constraints.txt", "requirements.lock", "stage-manifest.json"):
            source = stage / name
            if source.is_file():
                shutil.copyfile(source, root / name)
        for relative in INSTALLER_FILES:
            source = forge_root / relative
            destination = root / "forge" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        write_json(root / "tooling-suite-plan.json", _portable_suite_plan(plan))
        package_blockers = sorted(
            {
                row["id"]
                for row in plan["tools"]
                if row["install_action"]["kind"] == "system-package"
            }
        )
        manifest: dict[str, Any] = {
            "version": SUITE_BUNDLE_VERSION,
            "source_plan_sha256": plan["plan_sha256"],
            "status": "partial" if package_blockers else "pass",
            "package_manager_assets_not_bundled": package_blockers,
            "privacy": (
                "Bundle contains tool assets, portable metadata, and verification data only; "
                "it contains no projects, credentials, prompts, logs, usernames, hostnames, or paths."
            ),
        }
        write_json(root / "bundle-manifest.json", manifest)
        checksums = [
            f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
            for path in sorted(item for item in root.rglob("*") if item.is_file())
        ]
        (root / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
        os.replace(root, output)
    return {**manifest, "output": output.as_posix()}


def _prompt(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError as error:
        raise ToolingSuiteError("interactive input ended before approval") from error


def _confirm(prompt: str) -> bool:
    return _prompt(f"{prompt} [y/N] ").lower() in {"y", "yes"}


def _print_onboard_handoff(*, offline: bool = False, stream: Any = None) -> None:
    stream = sys.stdout if stream is None else stream
    offline_flag = " --offline" if offline else ""
    print("\nCopyable agent prompt:", file=stream)
    print("```text", file=stream)
    print("I have completed the Moradin Forge tooling installation.", file=stream)
    print("Ask which workspace roots I approve, then run:", file=stream)
    print(
        "scripts/moradin_forge.sh onboard --workspace "
        f"<approved-workspace>{offline_flag}",
        file=stream,
    )
    print(
        "Show discovered repositories and every proposed provider file change.",
        file=stream,
    )
    print(
        "Ask separately before creating or patching each guidance file.",
        file=stream,
    )
    print("```", file=stream)


def _plan_needs_python_312_bootstrap(plan: dict[str, Any]) -> bool:
    return any(
        row.get("id") == "python"
        and row.get("status") == "manual"
        and row.get("resolved", {}).get("source") == "manual-runtime-prerequisite"
        for row in plan.get("tools", [])
        if isinstance(row, dict)
    )


def _bootstrap_python_312(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    uv_path = _trusted_bootstrap_uv_path(required=True)
    if uv_path is None:  # pragma: no cover - required=True always raises
        raise ToolingSuiteError("the Forge bootstrap uv runtime is unavailable")
    data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    python_root = data_root / "moradins-forge/bootstrap/python"
    argv = [
        uv_path.as_posix(),
        "python",
        "install",
        "--upgrade",
        "--managed-python",
        "--no-config",
        "--install-dir",
        python_root.as_posix(),
        "3.12",
    ]
    print("\nSeparate user-level Python prerequisite")
    print("command: " + " ".join(argv))
    print("target: uv-managed user prefix with a versioned ~/.local/bin shim")
    print("trust: checksum-verified pinned uv and uv-verified Python distribution")
    if not _confirm("Install or update user-level Python 3.12 before replanning?"):
        raise ToolingSuiteError(
            "Python 3.12 bootstrap was declined; the selected profile remains blocked"
        )
    environment = _safe_environment(home=Path.home())
    environment["PATH"] = (
        (Path.home() / ".local/bin").as_posix() + os.pathsep + SAFE_PATH
    )
    result = _run(argv, runner=runner, timeout=1800, env=environment)
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise ToolingSuiteError(f"user-level Python 3.12 bootstrap failed{suffix}")
    python_spec = next(spec for spec in TOOL_CATALOG if spec.id == "python")
    version = _command_version(python_spec, runner=runner)
    match = re.match(r"^(\d+)\.(\d+)", version)
    if not match or (int(match.group(1)), int(match.group(2))) < (3, 12):
        raise ToolingSuiteError(
            "uv completed but Python 3.12 is not available on the user PATH"
        )


def _airgap_module() -> Any:
    try:
        from scripts import moradin_airgap
    except ModuleNotFoundError:  # pragma: no cover - direct execution
        import moradin_airgap  # type: ignore[no-redef]
    return moradin_airgap


def _interactive_airgap(*, forge_root: Path) -> None:
    airgap = _airgap_module()
    while True:
        print("\nAir-Gapped Setup")
        print("1. Generate a sanitized request on this disconnected target")
        print("2. Build a complete kit on this connected Forge machine")
        print("3. Verify a transferred kit")
        print("4. Apply a verified kit on this disconnected target")
        print("5. Back")
        choice = _prompt("Choose an air-gap action: ")
        try:
            if choice == "1":
                profile_choice = _prompt(
                    "Profile: 1 Practical All (recommended), 2 Extended All: "
                )
                if profile_choice not in {"1", "2"}:
                    print("Choose 1 or 2.")
                    continue
                profile = "practical" if profile_choice == "1" else "extended"
                output = Path(_prompt("Request output path: ")).expanduser().resolve()
                facts = host_facts()
                approved_repositories: list[str] = []
                if facts["os_id"] in {"rocky", "rhel", "almalinux"} and _confirm(
                    "Approve EPEL metadata for selected tools when required?"
                ):
                    approved_repositories.append("epel")
                arch_snapshot = ""
                arch_inventory = False
                if facts["package_manager"] == "pacman":
                    arch_snapshot = _prompt("Frozen Arch snapshot (YYYY/MM/DD): ")
                    arch_inventory = _confirm(
                        "Export the complete Arch package inventory into the sanitized request?"
                    )
                payload = airgap.build_airgap_request(
                    forge_root=forge_root,
                    profile=profile,
                    output=output,
                    approved_repositories=approved_repositories,
                    arch_snapshot=arch_snapshot,
                    approve_arch_package_inventory=arch_inventory,
                )
                print(json.dumps(payload, indent=2, sort_keys=True))
                continue
            if choice == "2":
                source_kind = _prompt("Build from 1 request or 2 frozen lock: ")
                if source_kind not in {"1", "2"}:
                    print("Choose 1 or 2.")
                    continue
                source = Path(_prompt("Request/lock path: ")).expanduser().resolve()
                output = Path(_prompt("Kit output path: ")).expanduser().resolve()
                if source_kind == "1":
                    payload = airgap.build_airgap_bundle_from_request(
                        source,
                        output=output,
                        forge_root=forge_root,
                    )
                else:
                    payload = airgap.build_airgap_bundle_from_lock(
                        source,
                        output=output,
                        forge_root=forge_root,
                    )
                print(json.dumps(payload, indent=2, sort_keys=True))
                print(
                    "Transport this bundle digest separately: "
                    + str(payload["bundle_sha256"])
                )
                continue
            if choice == "3":
                bundle = Path(_prompt("Kit path: ")).expanduser().resolve()
                digest = _prompt("Separately transported kit SHA-256: ")
                payload = airgap.verify_airgap_bundle(
                    bundle,
                    expected_sha256=digest,
                )
                print(json.dumps(payload, indent=2, sort_keys=True))
                continue
            if choice == "4":
                bundle = Path(_prompt("Kit path: ")).expanduser().resolve()
                digest = _prompt("Separately transported kit SHA-256: ")
                preview = airgap.preview_airgap_apply(
                    bundle,
                    expected_sha256=digest,
                    forge_root=forge_root,
                )
                print(suite_plan_markdown(preview["plan"]).rstrip())
                print(f"offline_package_additions: {preview['package_additions']}")
                print(f"offline_package_upgrades: {preview['package_upgrades']}")
                print(f"offline_package_bytes: {preview['disk_bytes']}")
                print(f"offline_plan_sha256: {preview['plan_sha256']}")
                stale_approval = ""
                if preview["bundle"]["stale"]:
                    stale_approval = _prompt(
                        "Kit is older than 30 days; type its exact SHA-256 again: "
                    )
                    if stale_approval != digest:
                        raise ToolingSuiteError(
                            "stale air-gap kit digest approval did not match"
                        )
                if not _confirm(
                    "Apply this exact offline plan through the sealed sudo phase?"
                ):
                    print("Air-gap apply cancelled without changes.")
                    continue
                payload = airgap.apply_airgap_bundle(
                    bundle,
                    approved_bundle_sha256=digest,
                    approved_plan_sha256=str(preview["plan_sha256"]),
                    approved_stale_bundle_sha256=stale_approval,
                    approved_plan=preview["plan"],
                    forge_root=forge_root,
                )
                print(json.dumps(payload, indent=2, sort_keys=True))
                _print_onboard_handoff(offline=True)
                continue
            if choice == "5":
                return
            print("Enter a number from 1 through 5.")
        except airgap.AirgapError as error:
            print(f"Air-gap action failed closed: {error}")


def _interactive_profile(*, forge_root: Path = REPO_ROOT) -> tuple[str, list[str]]:
    while True:
        print("\nMoradin Forge Linux Tooling Suite")
        print("1. Install All")
        print("2. Customize")
        print("3. Verify an installation")
        print("4. Roll back an installation")
        print("5. Air-Gapped Setup")
        print("6. Exit")
        choice = _prompt("Choose an action: ")
        if choice == "1":
            while True:
                print("\n1. Practical All (recommended)")
                print("2. Extended All")
                selected = _prompt("Choose an Install All profile: ")
                if selected == "1":
                    return "practical", []
                if selected == "2":
                    return "extended", []
                print("Enter 1 or 2.")
        if choice == "2":
            categories: dict[str, list[ToolSpec]] = {}
            for spec in TOOL_CATALOG:
                categories.setdefault(spec.category, []).append(spec)
            category_names = sorted(categories)
            print("\nTool categories")
            for index, category in enumerate(category_names, start=1):
                print(f"{index}. {category}")
            while True:
                raw_categories = _prompt(
                    "Select comma-separated category numbers, or 'all': "
                ).lower()
                if raw_categories == "all":
                    chosen_categories = category_names
                else:
                    try:
                        indexes = {
                            int(item.strip())
                            for item in raw_categories.split(",")
                            if item.strip()
                        }
                    except ValueError:
                        indexes = set()
                    if indexes and all(
                        1 <= index <= len(category_names) for index in indexes
                    ):
                        chosen_categories = [
                            category_names[index - 1] for index in sorted(indexes)
                        ]
                    else:
                        print("Choose valid category numbers or 'all'.")
                        continue
                available = sorted(
                    (
                        spec
                        for category in chosen_categories
                        for spec in categories[category]
                    ),
                    key=lambda item: (item.category, item.id),
                )
                print("\nTools in selected categories")
                for spec in available:
                    suffix = " [manual handoff]" if spec.manual_only else ""
                    print(f"  {spec.id:<20} {spec.label}{suffix}")
                while True:
                    raw_tools = _prompt(
                        "Enter comma-separated tool IDs, or 'all' for these categories: "
                    ).lower()
                    if raw_tools == "all":
                        return "custom", [spec.id for spec in available]
                    selected = sorted(
                        {item.strip() for item in raw_tools.split(",") if item.strip()}
                    )
                    known = {spec.id for spec in available}
                    unknown = sorted(set(selected) - known)
                    if selected and not unknown:
                        return "custom", selected
                    if unknown:
                        print("Unknown or unselected tool IDs: " + ", ".join(unknown))
                    else:
                        print("Select at least one tool.")
        if choice == "3":
            receipt = _prompt("Receipt ID/path, or 'latest': ") or "latest"
            payload = verify_suite_receipt(receipt)
            print(json.dumps(payload, indent=2, sort_keys=True))
            _print_onboard_handoff()
            continue
        if choice == "4":
            receipt = _prompt("Receipt ID/path, or 'latest': ") or "latest"
            _path, payload = _load_user_receipt(receipt)
            print(f"receipt_sha256: {payload['receipt_sha256']}")
            if not _confirm("Roll back only the receipt-owned changes?"):
                print("Rollback cancelled.")
                continue
            result = rollback_suite_receipt(
                receipt,
                approved_sha256=str(payload["receipt_sha256"]),
                forge_root=REPO_ROOT,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            continue
        if choice == "5":
            _interactive_airgap(forge_root=forge_root)
            continue
        if choice == "6":
            raise SystemExit(0)
        print("Enter a number from 1 through 6.")


def interactive(*, forge_root: Path) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ToolingSuiteError(
            "interactive mode requires a TTY; use plan/apply with an exact digest"
        )
    if os.geteuid() == 0:
        raise ToolingSuiteError(
            "interactive mode must run as the target user, not root"
        )
    profile, selected = _interactive_profile(forge_root=forge_root)
    workspaces: list[Path] = []
    if _confirm("Add approved workspace roots for evidence-based recommendations?"):
        while True:
            value = _prompt("Workspace path (blank when finished): ")
            if not value:
                break
            workspaces.append(Path(value))
        if not workspaces:
            print("No workspace roots selected; the installer will not scan projects.")
    container_engine = ""
    if profile == "extended" and not any(
        command_present(item) for item in ("podman", "docker")
    ):
        while container_engine not in {"podman", "docker"}:
            value = _prompt("Rootless container engine [podman/docker]: ").lower()
            if value in {"", "podman"}:
                container_engine = "podman"
            elif value == "docker":
                container_engine = "docker"
            else:
                print("Choose podman or docker.")
    approvals: list[str] = []
    arch_approved = False
    while True:
        plan = build_suite_plan(
            forge_root=forge_root,
            profile=profile,
            workspaces=workspaces,
            include_tools=selected,
            container_engine=container_engine,
            approved_repositories=approvals,
            approve_arch_system_upgrade=arch_approved,
        )
        if _plan_needs_python_312_bootstrap(plan):
            print("\n" + suite_plan_markdown(plan))
            _bootstrap_python_312()
            continue
        if plan["status"] == "needs-repository-approval":
            print("\n" + suite_plan_markdown(plan))
            print("\nSelected tools require the signed EPEL repository on this host.")
            if not _confirm("Approve adding EPEL as a separate root transaction?"):
                raise ToolingSuiteError(
                    "EPEL approval was declined; customize the selection and retry"
                )
            approvals.append("epel")
            continue
        if plan["status"] == "needs-arch-upgrade-approval":
            print("\n" + suite_plan_markdown(plan))
            print("\nArch does not support partial upgrades.")
            if not _confirm(
                "Approve the complete pacman synchronization shown in the plan?"
            ):
                raise ToolingSuiteError("Arch synchronization approval was declined")
            arch_approved = True
            continue
        state_root = _user_roots()[1]
        plan_path = (
            state_root
            / "plans"
            / f"{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{plan['plan_sha256'][:12]}.json"
        )
        write_suite_plan(plan, plan_path)
        print("\n" + suite_plan_markdown(plan))
        if plan["status"] not in {"ready", "repository-bootstrap"}:
            print(f"The plan cannot be applied: {plan['status']}")
            return 2
        if not _confirm("Apply this exact digest-bound plan?"):
            print(f"Plan saved without changes: {plan_path}")
            return 0
        receipt = apply_suite_plan(
            plan_path,
            approved_sha256=str(plan["plan_sha256"]),
            forge_root=forge_root,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        if receipt["status"] == "replan-required":
            print(
                "Repository trust was updated and receipted; rebuilding the exact tool plan."
            )
            continue
        _print_onboard_handoff()
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Moradin Forge interactive Linux tooling suite"
    )
    parser.add_argument("--forge-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("interactive", help="Open the Install All or Customize menu.")

    doctor = subparsers.add_parser(
        "doctor", help="Run aggregate network-free host readiness checks."
    )
    doctor.add_argument("--output", choices=("auto", "summary", "json"), default="auto")

    status = subparsers.add_parser(
        "status", help="Report receipt and resumable checkpoint state."
    )
    status.add_argument(
        "--progress", choices=("auto", "plain", "json", "off"), default="auto"
    )

    plan_parser = subparsers.add_parser(
        "plan", help="Build a deterministic tooling-suite plan."
    )
    profile_group = plan_parser.add_mutually_exclusive_group(required=True)
    profile_group.add_argument("--profile", choices=("practical", "extended"))
    profile_group.add_argument("--custom", action="store_true")
    plan_parser.add_argument("--workspace", type=Path, action="append", default=[])
    plan_parser.add_argument("--select", action="append", default=[])
    plan_parser.add_argument("--exclude", action="append", default=[])
    plan_parser.add_argument(
        "--container-engine", choices=("podman", "docker"), default=""
    )
    plan_parser.add_argument(
        "--approve-repository", choices=("epel",), action="append", default=[]
    )
    plan_parser.add_argument("--approve-arch-system-upgrade", action="store_true")
    plan_parser.add_argument("--refresh-versions", action="store_true")
    plan_parser.add_argument("--output", type=Path, required=True)

    apply_parser = subparsers.add_parser(
        "apply", help="Apply an exact digest-approved suite plan."
    )
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--approve-plan-sha256", required=True)
    apply_parser.add_argument(
        "--progress", choices=("auto", "plain", "json", "off"), default="auto"
    )

    bundle = subparsers.add_parser(
        "bundle",
        help=(
            "Build a compatibility asset bundle; it may be partial when OS "
            "packages are selected."
        ),
    )
    bundle.add_argument("--plan", type=Path, required=True)
    bundle.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser("verify", help="Verify a tooling-suite receipt.")
    verify_group = verify.add_mutually_exclusive_group(required=True)
    verify_group.add_argument("--receipt")
    verify_group.add_argument("--latest", action="store_true")

    rollback = subparsers.add_parser(
        "rollback", help="Roll back receipt-owned suite changes."
    )
    rollback.add_argument("--receipt", default="latest")
    rollback.add_argument("--approve-receipt-sha256", required=True)

    airgap_request = subparsers.add_parser(
        "airgap-request",
        help="Write a sanitized target request on a disconnected Linux host.",
    )
    airgap_request.add_argument(
        "--profile", choices=("practical", "extended"), required=True
    )
    airgap_request.add_argument("--output", type=Path, required=True)
    airgap_request.add_argument("--exclude", action="append", default=[])
    airgap_request.add_argument(
        "--container-engine", choices=("podman", "docker"), default=""
    )
    airgap_request.add_argument(
        "--approve-repository", choices=("epel",), action="append", default=[]
    )
    airgap_request.add_argument("--arch-snapshot", default="")
    airgap_request.add_argument(
        "--approve-arch-package-inventory", action="store_true"
    )

    airgap_build = subparsers.add_parser(
        "airgap-build",
        help="Build a complete target-specific kit with a rootless builder.",
    )
    build_source = airgap_build.add_mutually_exclusive_group(required=True)
    build_source.add_argument("--request", type=Path)
    build_source.add_argument("--lock", type=Path)
    airgap_build.add_argument("--output", type=Path, required=True)

    airgap_verify = subparsers.add_parser(
        "airgap-verify",
        help="Verify a sealed kit against its separately transported digest.",
    )
    airgap_verify.add_argument("--bundle", type=Path, required=True)
    airgap_verify.add_argument("--expected-sha256", required=True)

    airgap_apply = subparsers.add_parser(
        "airgap-apply",
        help="Rebind and apply a complete kit with all network sources disabled.",
    )
    airgap_apply.add_argument("--bundle", type=Path, required=True)
    airgap_apply.add_argument("--approve-bundle-sha256", required=True)
    airgap_apply.add_argument("--approve-offline-plan-sha256", default="")
    airgap_apply.add_argument("--approve-stale-bundle-sha256", default="")

    root_apply = subparsers.add_parser("_root-apply", help=argparse.SUPPRESS)
    root_apply.add_argument("--plan", type=Path, required=True)
    root_apply.add_argument("--stage-root", type=Path, required=True)
    root_apply.add_argument("--approve-plan-sha256", required=True)
    root_apply.add_argument("--target-uid", type=int, required=True)

    root_rollback = subparsers.add_parser("_root-rollback", help=argparse.SUPPRESS)
    root_rollback.add_argument("--receipt", type=Path, required=True)
    root_rollback.add_argument("--approve-receipt-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    args = build_parser().parse_args(argv)
    forge_root = args.forge_root.resolve()
    try:
        airgap = None
        if str(args.command).startswith("airgap-"):
            try:
                from scripts import moradin_airgap as airgap
            except ModuleNotFoundError:  # pragma: no cover - direct execution
                import moradin_airgap as airgap  # type: ignore[no-redef]
        if args.command == "interactive":
            return interactive(forge_root=forge_root)
        if args.command == "doctor":
            payload = build_doctor_report()
            selected = (
                "summary"
                if args.output == "auto" and sys.stderr.isatty()
                else "json"
                if args.output == "auto"
                else args.output
            )
            if selected == "summary":
                print(
                    f"Moradin Forge doctor: {payload['status']} "
                    f"({len(payload['blockers'])} blockers, {len(payload['warnings'])} warnings)",
                    file=sys.stderr,
                )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["status"] == "ready" else 2
        if args.command == "status":
            _emit_progress(args.progress, "reading-status")
            payload = tooling_suite_status()
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "plan":
            profile = "custom" if args.custom else str(args.profile)
            payload = build_suite_plan(
                forge_root=forge_root,
                profile=profile,
                workspaces=args.workspace,
                include_tools=args.select,
                exclude_tools=args.exclude,
                container_engine=args.container_engine,
                approved_repositories=args.approve_repository,
                approve_arch_system_upgrade=args.approve_arch_system_upgrade,
                refresh_versions=args.refresh_versions,
            )
            artifacts = write_suite_plan(payload, args.output.resolve())
            print(
                json.dumps(
                    {**payload, "artifacts": artifacts}, indent=2, sort_keys=True
                )
            )
            return 0 if payload["status"] in {"ready", "repository-bootstrap"} else 2
        if args.command == "apply":
            payload = apply_suite_plan(
                args.plan,
                approved_sha256=args.approve_plan_sha256,
                forge_root=forge_root,
                progress=args.progress,
            )
            payload["onboard_handoff"] = (
                "scripts/moradin_forge.sh onboard --workspace <approved-workspace>"
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "bundle":
            payload = build_suite_bundle(
                args.plan,
                output=args.output.resolve(),
                forge_root=forge_root,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["status"] == "pass" else 1
        if args.command == "verify":
            payload = verify_suite_receipt(
                "latest" if args.latest else str(args.receipt)
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["status"] == "pass" else 1
        if args.command == "rollback":
            payload = rollback_suite_receipt(
                args.receipt,
                approved_sha256=args.approve_receipt_sha256,
                forge_root=forge_root,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["status"] == "pass" else 1
        if args.command == "airgap-request":
            assert airgap is not None
            try:
                payload = airgap.build_airgap_request(
                    forge_root=forge_root,
                    profile=args.profile,
                    output=args.output.resolve(),
                    exclude_tools=args.exclude,
                    container_engine=args.container_engine,
                    approved_repositories=args.approve_repository,
                    arch_snapshot=args.arch_snapshot,
                    approve_arch_package_inventory=(
                        args.approve_arch_package_inventory
                    ),
                )
            except airgap.AirgapError as error:
                raise ToolingSuiteError(str(error)) from error
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "airgap-build":
            assert airgap is not None
            try:
                if args.request:
                    payload = airgap.build_airgap_bundle_from_request(
                        args.request.resolve(),
                        output=args.output.resolve(),
                        forge_root=forge_root,
                    )
                else:
                    payload = airgap.build_airgap_bundle_from_lock(
                        args.lock.resolve(),
                        output=args.output.resolve(),
                        forge_root=forge_root,
                    )
            except airgap.AirgapError as error:
                raise ToolingSuiteError(str(error)) from error
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "airgap-verify":
            assert airgap is not None
            try:
                payload = airgap.verify_airgap_bundle(
                    args.bundle.resolve(),
                    expected_sha256=args.expected_sha256,
                )
            except airgap.AirgapError as error:
                raise ToolingSuiteError(str(error)) from error
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "airgap-apply":
            assert airgap is not None
            try:
                preview = airgap.preview_airgap_apply(
                    args.bundle.resolve(),
                    expected_sha256=args.approve_bundle_sha256,
                    forge_root=forge_root,
                )
                print(suite_plan_markdown(preview["plan"]).rstrip(), file=sys.stderr)
                print(
                    f"offline_package_additions: {len(preview['package_additions'])}",
                    file=sys.stderr,
                )
                print(
                    f"offline_package_upgrades: {len(preview['package_upgrades'])}",
                    file=sys.stderr,
                )
                print(f"offline_package_bytes: {preview['disk_bytes']}", file=sys.stderr)
                print(f"repository_actions: {preview['repository_actions']}", file=sys.stderr)
                print(f"rollback: {preview['rollback']}", file=sys.stderr)
                print(f"offline_plan_sha256: {preview['plan_sha256']}", file=sys.stderr)
                stale_approval = args.approve_stale_bundle_sha256
                if preview["bundle"]["stale"] and not stale_approval:
                    if not sys.stdin.isatty():
                        raise ToolingSuiteError(
                            "stale air-gap kit requires an exact non-interactive approval"
                        )
                    typed = _prompt(
                        "Kit is older than 30 days. Type its exact SHA-256 to continue: "
                    )
                    if typed != args.approve_bundle_sha256:
                        raise ToolingSuiteError("stale kit digest approval did not match")
                    stale_approval = typed
                plan_approval = args.approve_offline_plan_sha256
                if not plan_approval:
                    if not sys.stdin.isatty() or not sys.stdout.isatty():
                        print(
                            json.dumps(
                                {
                                    "version": "MoradinForgeToolingResultV2",
                                    "status": "approval-required",
                                    "mutation": False,
                                    "bundle_sha256": args.approve_bundle_sha256,
                                    "plan_sha256": preview["plan_sha256"],
                                    "required_argument": (
                                        "--approve-offline-plan-sha256"
                                    ),
                                },
                                indent=2,
                                sort_keys=True,
                            )
                        )
                        return 2
                    if not _confirm(
                        "Apply this exact offline plan through the sealed sudo phase?"
                    ):
                        print(
                            json.dumps(
                                {
                                    "version": airgap.AIRGAP_APPLY_VERSION,
                                    "status": "cancelled",
                                    "mutation": False,
                                },
                                indent=2,
                                sort_keys=True,
                            )
                        )
                        return 0
                    plan_approval = str(preview["plan_sha256"])
                payload = airgap.apply_airgap_bundle(
                    args.bundle.resolve(),
                    approved_bundle_sha256=args.approve_bundle_sha256,
                    approved_plan_sha256=plan_approval,
                    approved_stale_bundle_sha256=stale_approval,
                    approved_plan=preview["plan"],
                    forge_root=forge_root,
                )
            except airgap.AirgapError as error:
                raise ToolingSuiteError(str(error)) from error
            print(json.dumps(payload, indent=2, sort_keys=True))
            if payload["status"] == "pass":
                _print_onboard_handoff(offline=True, stream=sys.stderr)
            return 0
        if args.command == "_root-apply":
            if os.geteuid() != 0:
                raise ToolingSuiteError("internal root apply requires effective UID 0")
            os.umask(0o077)
            _assert_trusted_root_python()
            plan = load_suite_plan(
                args.plan,
                approved_sha256=args.approve_plan_sha256,
                forge_root=forge_root,
                require_current_host=False,
            )
            current = host_facts()
            for key in (
                "system",
                "arch",
                "os_id",
                "package_manager",
                "host_fingerprint_sha256",
            ):
                if plan["platform"].get(key) != current.get(key):
                    raise ToolingSuiteError(f"root plan host binding failed: {key}")
            if (
                int(plan.get("target_uid", -1)) != args.target_uid
                or args.target_uid <= 0
            ):
                raise ToolingSuiteError("root plan target UID binding failed")
            payload = apply_root_transaction(plan, stage_root=args.stage_root)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "_root-rollback":
            if os.geteuid() != 0:
                raise ToolingSuiteError(
                    "internal root rollback requires effective UID 0"
                )
            os.umask(0o077)
            _assert_trusted_root_python()
            payload = rollback_root_receipt(
                args.receipt,
                approved_sha256=args.approve_receipt_sha256,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload["status"] == "pass" else 1
    except (ToolingSuiteError, WorkstationError) as error:
        print(f"moradin-tooling-suite: {error}", file=sys.stderr)
        if args.command != "interactive":
            print(
                json.dumps(
                    {
                        "version": "MoradinForgeToolingResultV2",
                        "status": "error",
                        "error": str(error),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
