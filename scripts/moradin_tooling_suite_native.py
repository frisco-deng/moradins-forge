#!/usr/bin/env python3
"""Digest-bound connected tooling suite for macOS and Windows."""

from __future__ import annotations

import argparse
from dataclasses import replace
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Sequence

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if SCRIPT_REPO_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, SCRIPT_REPO_ROOT.as_posix())

from scripts.moradin_workstation import (  # noqa: E402
    CATALOG_PATH,
    TOOL_CATALOG,
    WorkstationError,
    _assert_official_https_url,
    _download_asset,
    _install_action,
    build_python_tool_lock,
    canonical_json_bytes,
    command_present,
    normalized_arch,
    normalized_platform,
    plan_digest,
    render_privileged_powershell,
    resolve_latest_version,
    sha256_file,
    utc_now,
    verification_argv,
    write_json,
)


CATALOG_VERSION = "MoradinForgeToolCatalogV2"
DOCTOR_VERSION = "MoradinForgeToolingDoctorV1"
PLAN_VERSION = "MoradinForgeToolingSuitePlanV2"
CHECKPOINT_VERSION = "MoradinForgeToolingCheckpointV1"
RECEIPT_VERSION = "MoradinForgeToolingSuiteReceiptV2"
ROLLBACK_VERSION = "MoradinForgeToolingSuiteRollbackV2"
PLAN_TTL = timedelta(hours=24)
MAX_PLANNER_UV_BYTES = 128 * 1024 * 1024
SUPPORTED_SYSTEMS = {"macos", "windows"}
SUPPORTED_ARCHES = {"amd64", "arm64"}
REPO_ROOT = SCRIPT_REPO_ROOT
NATIVE_FILES = (
    Path("install/tooling-suite-macos.sh"),
    Path("install/tooling-suite.ps1"),
    Path("scripts/moradin_tooling_suite_native.py"),
    Path("scripts/moradin_workstation.py"),
    Path("catalog/workstation-tools.toml"),
)


class NativeSuiteError(WorkstationError):
    """A native connected installer operation failed closed."""


def _digest(payload: dict[str, Any], field: str) -> str:
    return hashlib.sha256(
        canonical_json_bytes({key: value for key, value in payload.items() if key != field})
    ).hexdigest()


def _identity_sha256(system: str) -> str:
    identity = str(os.getuid()) if system == "macos" else getpass.getuser()
    return hashlib.sha256(f"moradin-forge\0{system}\0{identity}".encode()).hexdigest()


def _state_root(system: str) -> Path:
    if system == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "moradins-forge" / "tooling-suite-v2"


def _data_root(system: str) -> Path:
    if system == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "moradins-forge" / "tools"


def _windows_authenticode_valid(path: Path) -> bool:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        return False
    environment = os.environ.copy()
    environment["MORADIN_FORGE_VERIFY_PATH"] = path.as_posix()
    command = (
        "$s = Get-AuthenticodeSignature -LiteralPath "
        "$env:MORADIN_FORGE_VERIFY_PATH; "
        "if ($s.Status -eq 'Valid' -and $s.SignerCertificate.Subject -match "
        "'Microsoft') { exit 0 }; exit 1"
    )
    try:
        result = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _trusted_manager(system: str) -> Path | None:
    command = "brew" if system == "macos" else "winget"
    found = shutil.which(command)
    if not found:
        return None
    try:
        resolved = Path(found).resolve(strict=True)
        metadata = resolved.stat()
    except OSError:
        return None
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        return None
    if system == "macos":
        if metadata.st_mode & 0o022 or metadata.st_uid not in {0, os.getuid()}:
            return None
    elif resolved.suffix.lower() != ".exe" or not _windows_authenticode_valid(resolved):
        return None
    return resolved


def native_facts(expected_system: str) -> dict[str, str]:
    actual = normalized_platform()
    arch = normalized_arch()
    if actual != expected_system:
        raise NativeSuiteError(f"entrypoint targets {expected_system}, not {actual}")
    if arch not in SUPPORTED_ARCHES:
        raise NativeSuiteError(f"unsupported {expected_system} architecture: {arch}")
    manager = _trusted_manager(expected_system)
    return {
        "system": expected_system,
        "arch": arch,
        "package_manager": "homebrew" if expected_system == "macos" else "winget",
        "package_manager_path": manager.as_posix() if manager else "",
        "target_user_sha256": _identity_sha256(expected_system),
    }


def build_doctor(expected_system: str) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    try:
        facts = native_facts(expected_system)
    except NativeSuiteError as error:
        facts = {
            "system": expected_system,
            "arch": normalized_arch(),
            "package_manager": "homebrew" if expected_system == "macos" else "winget",
            "package_manager_path": "",
            "target_user_sha256": "",
        }
        blockers.append({"id": "platform", "reason": str(error)})
    if not facts["package_manager_path"]:
        blockers.append(
            {
                "id": "package-manager",
                "reason": (
                    "Homebrew is required and must be installed from its reviewed official package"
                    if expected_system == "macos"
                    else "WinGet is required from the signed Windows App Installer package"
                ),
            }
        )
    if sys.version_info < (3, 11):
        blockers.append({"id": "runtime", "reason": "Python 3.11 or newer is required"})
    if expected_system == "macos" and hasattr(os, "geteuid") and os.geteuid() == 0:
        blockers.append({"id": "target-user", "reason": "run as the target user, not root"})
    if any(command_present(name) for name in ("docker", "podman")):
        warnings.append(
            {"id": "container-state", "reason": "existing container configuration is preserved"}
        )
    payload: dict[str, Any] = {
        "version": DOCTOR_VERSION,
        "status": "blocked" if blockers else "ready",
        "platform": facts,
        "runtime": {
            "implementation": platform.python_implementation(),
            "python": ".".join(str(item) for item in sys.version_info[:3]),
            "minimum": "3.11",
        },
        "blockers": blockers,
        "warnings": warnings,
        "network_accessed": False,
        "privacy": "No workspace contents, hostnames, user names, credentials, or telemetry are recorded.",
    }
    payload["doctor_sha256"] = _digest(payload, "doctor_sha256")
    return payload


def _protected_state(facts: dict[str, str]) -> dict[str, Any]:
    return {
        "container_engines": sorted(
            name for name in ("docker", "podman") if command_present(name)
        ),
        "manager_path": facts["package_manager_path"],
        "target_user_sha256": facts["target_user_sha256"],
        "path_sha256": hashlib.sha256(os.environ.get("PATH", "").encode()).hexdigest(),
        "kernel_sha256": hashlib.sha256(platform.release().encode()).hexdigest(),
    }


def installer_manifest(forge_root: Path) -> dict[str, str]:
    if forge_root.resolve() != REPO_ROOT.resolve():
        raise NativeSuiteError("--forge-root must identify this Forge checkout")
    result: dict[str, str] = {}
    for relative in NATIVE_FILES:
        path = forge_root / relative
        if path.is_symlink() or not path.is_file():
            raise NativeSuiteError(f"native installer file is missing: {relative}")
        result[relative.as_posix()] = sha256_file(path)
    return result


def _selected_specs(profile: str, include: Sequence[str], exclude: Sequence[str]) -> list[Any]:
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    unknown = sorted((set(include) | set(exclude)) - set(catalog))
    if unknown:
        raise NativeSuiteError("unknown tooling ids: " + ", ".join(unknown))
    if profile == "custom":
        if not include:
            raise NativeSuiteError("custom planning requires at least one --select")
        selected = set(include)
    elif profile == "practical":
        selected = {spec.id for spec in TOOL_CATALOG if "practical" in spec.profiles}
    elif profile == "extended":
        selected = {
            spec.id
            for spec in TOOL_CATALOG
            if set(spec.profiles).intersection({"practical", "extended"})
        }
    else:
        raise NativeSuiteError(f"unsupported profile: {profile}")
    selected.update(include)
    selected.difference_update(exclude)
    return sorted((catalog[item] for item in selected), key=lambda spec: (spec.category, spec.id))


def _version_key(value: str) -> tuple[int, ...]:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){1,3})(?!\d)", value)
    return tuple(int(item) for item in match.group(1).split(".")) if match else ()


def _preserved_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        **action,
        "kind": "manual",
        "auto_execute": False,
        "requires_elevation": False,
        "reason": (
            "installed version is retained because the native provider "
            "did not supply an exact reversible rollback closure"
        ),
    }


def _installed_manager_version(
    system: str,
    manager_path: str,
    spec: Any,
) -> str:
    if not manager_path:
        return ""
    if system == "macos" and spec.brew_formula:
        argv = [manager_path, "list", "--versions", spec.brew_formula]
    elif system == "windows" and spec.winget_id:
        argv = [
            manager_path,
            "list",
            "--id",
            spec.winget_id,
            "--exact",
            "--disable-interactivity",
            "--accept-source-agreements",
        ]
    else:
        return ""
    try:
        result = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    versions = re.findall(r"(?<!\d)\d+(?:\.\d+){1,3}(?!\d)", result.stdout)
    return versions[-1] if versions else ""


def _stage_planner_uv(
    *,
    system: str,
    arch: str,
    refresh: bool,
    expected: dict[str, Any] | None = None,
    allow_download: bool = True,
) -> tuple[Path | None, dict[str, Any]]:
    spec = next(item for item in TOOL_CATALOG if item.id == "uv")
    asset_spec = replace(
        spec,
        apt_package="",
        dnf_package="",
        pacman_package="",
        brew_formula="",
        winget_id="",
        python_package="",
    )
    resolved = (
        {
            "version": expected.get("version", ""),
            "asset_url": expected.get("source_url", ""),
            "sha256": expected.get("archive_sha256", ""),
            "asset_filename": expected.get("asset_filename", ""),
        }
        if expected is not None
        else resolve_latest_version(
            asset_spec,
            cache_path=_state_root(system) / "planner-uv-version-cache.json",
            refresh=refresh,
            system=system,
            arch=arch,
            prefer_python=False,
        )
    )
    url = str(resolved.get("asset_url", ""))
    archive_sha256 = str(resolved.get("sha256", ""))
    filename = str(resolved.get("asset_filename", ""))
    if (
        not url
        or not re.fullmatch(r"[0-9a-f]{64}", archive_sha256)
        or Path(filename).name != filename
    ):
        return None, {
            "status": "unavailable",
            "version": str(resolved.get("version", "")),
            "reason": "official uv archive and digest are unavailable",
        }
    root = _state_root(system) / "planner-runtime" / archive_sha256
    executable = root / ("uv.exe" if system == "windows" else "uv")
    root.mkdir(parents=True, exist_ok=True)
    archive = root / filename
    if archive.is_symlink() or (
        archive.exists()
        and (not archive.is_file() or sha256_file(archive) != archive_sha256)
    ):
        archive.unlink(missing_ok=True)
    if not archive.is_file():
        if not allow_download:
            raise NativeSuiteError("approved planner uv archive is no longer staged")
        temporary = root / f".{filename}.download"
        _download_asset(url, temporary)
        if sha256_file(temporary) != archive_sha256:
            temporary.unlink(missing_ok=True)
            raise NativeSuiteError("planner uv archive integrity failed")
        os.replace(temporary, archive)
    executable_bytes: bytes
    if filename.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            if len(members) > 32:
                raise NativeSuiteError("planner uv archive has too many members")
            candidates = []
            for member in members:
                relative = Path(member.filename)
                mode = member.external_attr >> 16
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or (mode and (mode & 0o170000) == 0o120000)
                ):
                    raise NativeSuiteError("planner uv archive member is unsafe")
                if (
                    not member.is_dir()
                    and relative.name == executable.name
                    and 0 < member.file_size <= MAX_PLANNER_UV_BYTES
                ):
                    candidates.append(member)
            if len(candidates) != 1:
                raise NativeSuiteError("planner uv archive executable is ambiguous")
            executable_bytes = bundle.read(candidates[0])
    elif filename.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive, mode="r:gz") as bundle:
            members = bundle.getmembers()
            if len(members) > 32:
                raise NativeSuiteError("planner uv archive has too many members")
            candidates = []
            for member in members:
                relative = Path(member.name)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or member.issym()
                    or member.islnk()
                    or member.isdev()
                ):
                    raise NativeSuiteError("planner uv archive member is unsafe")
                if (
                    member.isfile()
                    and relative.name == executable.name
                    and 0 < member.size <= MAX_PLANNER_UV_BYTES
                ):
                    candidates.append(member)
            if len(candidates) != 1:
                raise NativeSuiteError("planner uv archive executable is ambiguous")
            stream = bundle.extractfile(candidates[0])
            if stream is None:
                raise NativeSuiteError("planner uv archive executable is unreadable")
            executable_bytes = stream.read(MAX_PLANNER_UV_BYTES + 1)
    else:
        raise NativeSuiteError("planner uv archive format is unsupported")
    if not 0 < len(executable_bytes) <= MAX_PLANNER_UV_BYTES:
        raise NativeSuiteError("planner uv executable size is unsafe")
    executable_new = root / f".{executable.name}.new"
    executable_new.write_bytes(executable_bytes)
    executable_new.chmod(0o700)
    os.replace(executable_new, executable)
    result = subprocess.run(
        [executable.as_posix(), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        executable.unlink(missing_ok=True)
        raise NativeSuiteError("verified planner uv runtime did not execute")
    return executable, {
        "status": "ready",
        "version": str(resolved.get("version", "")),
        "asset_filename": filename,
        "archive_sha256": archive_sha256,
        "binary_sha256": sha256_file(executable),
        "source_url": url,
    }


def build_plan(
    *,
    forge_root: Path,
    expected_system: str,
    profile: str,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    refresh: bool = False,
    resolver: Callable[..., dict[str, Any]] = resolve_latest_version,
) -> dict[str, Any]:
    doctor = build_doctor(expected_system)
    facts = doctor["platform"]
    specs = _selected_specs(profile, include, exclude)
    cache = _state_root(expected_system) / "version-cache.json"
    uv_present = command_present("uv")
    uv_planned = uv_present or any(
        spec.id == "uv"
        and (
            (expected_system == "macos" and bool(spec.brew_formula))
            or (expected_system == "windows" and bool(spec.winget_id))
        )
        for spec in specs
    )
    rows: list[dict[str, Any]] = []
    for spec in specs:
        present = command_present(spec.command)
        resolved = resolver(
            spec,
            cache_path=cache,
            refresh=refresh,
            system=expected_system,
            arch=facts["arch"],
            prefer_python=uv_present,
        )
        action = _install_action(
            spec,
            system=expected_system,
            resolved=resolved,
            uv_present=uv_planned,
        )
        installed_version = (
            _installed_manager_version(
                expected_system,
                str(facts["package_manager_path"]),
                spec,
            )
            if present
            else ""
        )
        resolved_version = str(resolved.get("version", ""))
        drifted = bool(
            present
            and _version_key(installed_version)
            and _version_key(resolved_version)
            and _version_key(installed_version) < _version_key(resolved_version)
            and action["kind"] in {"user-package-manager", "user-local"}
        )
        if drifted:
            action = _preserved_action(action)
        rows.append(
            {
                "id": spec.id,
                "label": spec.label,
                "command": spec.command,
                "category": spec.category,
                "reason": spec.reason,
                "required": spec.required,
                "present": present,
                "installed_version": installed_version or ("present" if present else ""),
                "status": (
                    "preserved"
                    if drifted
                    else "current"
                    if present
                    else "manual"
                    if action["kind"] == "manual"
                    else "install"
                ),
                "resolved": resolved,
                "install_action": action,
                "verification_command": verification_argv(spec),
            }
        )
    needs_planner_uv = any(
        row["status"] == "install"
        and row["install_action"]["kind"] == "user-local"
        for row in rows
    )
    planner_uv: Path | None = None
    planner_runtime: dict[str, Any] = {"status": "not-required"}
    if needs_planner_uv:
        planner_uv, planner_runtime = _stage_planner_uv(
            system=expected_system,
            arch=str(facts["arch"]),
            refresh=refresh,
        )
    python_lock = build_python_tool_lock(
        [
            {**row, "present": row["install_action"]["kind"] != "user-local"}
            for row in rows
        ],
        system=expected_system,
        arch=facts["arch"],
        uv_command=planner_uv,
    )
    blockers = [dict(item) for item in doctor["blockers"]]
    for row in rows:
        if row["required"] and not row["present"] and row["install_action"]["kind"] == "manual":
            blockers.append({"id": row["id"], "reason": "required tool lacks a verified provider"})
    if any(row["install_action"]["kind"] == "user-local" for row in rows) and python_lock.get("status") != "ready":
        blockers.append({"id": "python-closure", "reason": "hash-frozen Python wheel closure is incomplete"})
    if needs_planner_uv and planner_runtime.get("status") != "ready":
        blockers.append(
            {
                "id": "planner-runtime",
                "reason": "a verified uv planner runtime could not be staged",
            }
        )
    now = datetime.now(tz=UTC).replace(microsecond=0)
    manifest = installer_manifest(forge_root)
    protected = _protected_state(facts)
    payload: dict[str, Any] = {
        "version": PLAN_VERSION,
        "generated_at": now.isoformat(),
        "expires_at": (now + PLAN_TTL).isoformat(),
        "profile": profile,
        "catalog_version": CATALOG_VERSION,
        "catalog_sha256": sha256_file(CATALOG_PATH),
        "installer_manifest": manifest,
        "installer_manifest_sha256": hashlib.sha256(canonical_json_bytes(manifest)).hexdigest(),
        "doctor": doctor,
        "doctor_sha256": doctor["doctor_sha256"],
        "runtime": doctor["runtime"],
        "platform": facts,
        "selected_tools": [row["id"] for row in rows],
        "explicitly_included_tools": sorted(set(include)),
        "explicitly_excluded_tools": sorted(set(exclude)),
        "tools": rows,
        "python_tool_lock": python_lock,
        "planner_runtime": planner_runtime,
        "package_simulation": [
            {
                "tool_id": row["id"],
                "provider": row["resolved"].get("source", "manual"),
                "version": row["resolved"].get("version", ""),
                "operation": row["status"],
            }
            for row in rows
        ],
        "transition_matrix": [
            {
                "tool_id": row["id"],
                "from": row["installed_version"] or "absent",
                "to": row["resolved"].get("version", row["status"]),
                "action": row["install_action"]["kind"],
            }
            for row in rows
        ],
        "prepared_assets": [
            {"package": asset["package"], "sha256": asset["sha256"], "size": asset.get("size", 0)}
            for asset in python_lock.get("assets", [])
        ]
        + (
            [
                {
                    "package": "uv-planner",
                    "sha256": planner_runtime["archive_sha256"],
                    "size": 0,
                }
            ]
            if planner_runtime.get("status") == "ready"
            else []
        ),
        "protected_state_sha256": hashlib.sha256(canonical_json_bytes(protected)).hexdigest(),
        "rollback_closure": {
            row["id"]: (
                "native-package-removal" if row["install_action"]["kind"] == "user-package-manager"
                else "isolated-user-generation" if row["install_action"]["kind"] == "user-local"
                else "human-elevated-script" if row["install_action"]["kind"] == "privileged-script"
                else "not-mutating"
            )
            for row in rows
        },
        "blockers": blockers,
        "manual_tools": [row["id"] for row in rows if row["install_action"]["kind"] == "manual"],
        "preserved_tools": [row["id"] for row in rows if row["status"] == "preserved"],
        "status": "blocked" if blockers else "ready",
        "privacy": "The plan stores only tool metadata, digests, transitions, and a hashed target identity.",
    }
    payload["plan_sha256"] = plan_digest(payload)
    return payload


def validate_plan_contents(plan: dict[str, Any], expected_system: str) -> None:
    if plan.get("catalog_version") != CATALOG_VERSION:
        raise NativeSuiteError("native plan catalog version is unsupported")
    doctor = plan.get("doctor", {})
    if (
        not isinstance(doctor, dict)
        or doctor.get("version") != DOCTOR_VERSION
        or doctor.get("doctor_sha256") != _digest(doctor, "doctor_sha256")
        or plan.get("doctor_sha256") != doctor.get("doctor_sha256")
        or plan.get("runtime") != doctor.get("runtime")
    ):
        raise NativeSuiteError("native plan doctor binding is invalid")
    rows = plan.get("tools")
    selected = plan.get("selected_tools")
    if (
        not isinstance(rows, list)
        or not isinstance(selected, list)
        or selected != [row.get("id") for row in rows if isinstance(row, dict)]
        or len(selected) != len(set(selected))
    ):
        raise NativeSuiteError("native plan selected tools are malformed")
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    uv_capable = any(
        isinstance(row, dict)
        and row.get("install_action", {}).get("kind") == "user-local"
        for row in rows
    )
    allowed_status = {"current", "install", "manual", "preserved"}
    for row in rows:
        if not isinstance(row, dict) or row.get("id") not in catalog:
            raise NativeSuiteError("native plan contains an unknown tool")
        spec = catalog[str(row["id"])]
        if row.get("command") != spec.command or row.get("category") != spec.category:
            raise NativeSuiteError(f"native plan catalog binding failed: {spec.id}")
        if row.get("verification_command") != verification_argv(spec):
            raise NativeSuiteError(f"native plan verification changed: {spec.id}")
        if row.get("status") not in allowed_status or not isinstance(
            row.get("present"), bool
        ):
            raise NativeSuiteError(f"native plan transition is malformed: {spec.id}")
        resolved = row.get("resolved")
        if not isinstance(resolved, dict):
            raise NativeSuiteError(f"native plan resolution is malformed: {spec.id}")
        for key in ("source_url", "asset_url"):
            url = str(resolved.get(key, ""))
            if url:
                _assert_official_https_url(url)
        expected_action = _install_action(
            spec,
            system=expected_system,
            resolved=resolved,
            uv_present=uv_capable,
        )
        if row.get("status") == "preserved":
            expected_action = _preserved_action(expected_action)
        if row.get("install_action") != expected_action:
            raise NativeSuiteError(f"native plan install action changed: {spec.id}")
    planner = plan.get("planner_runtime", {})
    if not isinstance(planner, dict) or planner.get("status") not in {
        "ready",
        "not-required",
    }:
        raise NativeSuiteError("native planner runtime binding is malformed")
    if planner.get("status") == "ready":
        if (
            Path(str(planner.get("asset_filename", ""))).name
            != str(planner.get("asset_filename", ""))
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(planner.get("archive_sha256", ""))
            )
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(planner.get("binary_sha256", ""))
            )
        ):
            raise NativeSuiteError("native planner runtime integrity is malformed")
        _assert_official_https_url(str(planner.get("source_url", "")))
    for field in ("package_simulation", "transition_matrix", "prepared_assets"):
        if not isinstance(plan.get(field), list):
            raise NativeSuiteError(f"native plan {field} is malformed")
    if (
        not re.fullmatch(
            r"[0-9a-f]{64}", str(plan.get("protected_state_sha256", ""))
        )
        or not isinstance(plan.get("rollback_closure"), dict)
        or plan.get("status") not in {"ready", "blocked"}
    ):
        raise NativeSuiteError("native plan safety binding is malformed")


def load_plan(path: Path, approved: str, expected_system: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise NativeSuiteError("plan must be a regular file")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NativeSuiteError("plan is not valid JSON") from error
    if not isinstance(plan, dict) or plan.get("version") != PLAN_VERSION:
        raise NativeSuiteError(f"plan version must be {PLAN_VERSION}")
    if plan.get("plan_sha256") != approved or approved != plan_digest(plan):
        raise NativeSuiteError("approved plan digest does not match")
    expires = datetime.fromisoformat(str(plan.get("expires_at", "")))
    if expires.tzinfo is None or datetime.now(tz=UTC) > expires:
        raise NativeSuiteError("plan expired; verified components remain detectable in a fresh plan")
    facts = native_facts(expected_system)
    if plan.get("platform") != facts:
        raise NativeSuiteError("plan does not match the current platform, provider, or target user")
    protected = hashlib.sha256(canonical_json_bytes(_protected_state(facts))).hexdigest()
    if plan.get("protected_state_sha256") != protected:
        raise NativeSuiteError("protected container, provider, or target-user state changed")
    manifest = installer_manifest(REPO_ROOT)
    if plan.get("catalog_sha256") != sha256_file(CATALOG_PATH) or plan.get("installer_manifest") != manifest:
        raise NativeSuiteError("catalog or installer changed after approval")
    validate_plan_contents(plan, expected_system)
    if plan.get("status") != "ready":
        raise NativeSuiteError("plan is blocked; resolve all doctor and required-tool blockers")
    return plan


def _checkpoint(plan: dict[str, Any], component: str, status: str, evidence: dict[str, Any]) -> None:
    payload: dict[str, Any] = {
        "version": CHECKPOINT_VERSION,
        "plan_sha256": plan["plan_sha256"],
        "component": component,
        "status": status,
        "protected_state_sha256": plan["protected_state_sha256"],
        "evidence": evidence,
    }
    payload["checkpoint_sha256"] = _digest(payload, "checkpoint_sha256")
    root = _state_root(plan["platform"]["system"]) / "checkpoints" / plan["plan_sha256"]
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / f".{component}.new"
    write_json(temporary, payload)
    os.replace(temporary, root / f"{component}.json")


def _load_checkpoint(plan: dict[str, Any], component: str) -> dict[str, Any] | None:
    path = (
        _state_root(plan["platform"]["system"])
        / "checkpoints"
        / plan["plan_sha256"]
        / f"{component}.json"
    )
    if path.is_symlink() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("version") != CHECKPOINT_VERSION
        or payload.get("plan_sha256") != plan["plan_sha256"]
        or payload.get("component") != component
        or payload.get("status") != "pass"
        or payload.get("protected_state_sha256") != plan["protected_state_sha256"]
        or payload.get("checkpoint_sha256") != _digest(payload, "checkpoint_sha256")
    ):
        return None
    return payload


def _progress(mode: str, event: str, **fields: object) -> None:
    selected = "plain" if mode == "auto" and sys.stderr.isatty() else "json" if mode == "auto" else mode
    if selected == "off":
        return
    payload = {"version": "MoradinForgeToolingProgressV1", "event": event, **fields}
    print(json.dumps(payload, sort_keys=True) if selected == "json" else f"[moradin-forge] {event}", file=sys.stderr, flush=True)


def _stage_python_assets(plan: dict[str, Any]) -> Path:
    system = plan["platform"]["system"]
    root = _state_root(system) / "assets" / plan["plan_sha256"]
    wheels = root / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    lock = plan.get("python_tool_lock", {})
    for asset in lock.get("assets", []):
        destination = wheels / str(asset["filename"])
        if destination.is_file() and sha256_file(destination) == asset["sha256"]:
            continue
        temporary = wheels / f".{asset['filename']}.download"
        _download_asset(str(asset["url"]), temporary)
        if sha256_file(temporary) != asset["sha256"]:
            temporary.unlink(missing_ok=True)
            raise NativeSuiteError(f"Python asset integrity failed for {asset['package']}")
        os.replace(temporary, destination)
    constraints = sorted(
        f"{asset['package']}=={asset['version']}" for asset in lock.get("assets", [])
    )
    (root / "constraints.txt").write_text("\n".join(constraints) + ("\n" if constraints else ""), encoding="utf-8")
    return root


def _run(argv: Sequence[str], *, env: dict[str, str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(list(argv), check=False, capture_output=True, text=True, env=env, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NativeSuiteError(f"approved operation could not execute: {argv[0]}") from error


def _rollback_incomplete_component(
    *,
    system: str,
    row: dict[str, Any],
    environment: dict[str, str],
) -> dict[str, Any]:
    action = row["install_action"]
    argv: list[str] = []
    if action["kind"] == "user-package-manager" and system == "macos":
        manager = _trusted_manager("macos")
        if manager:
            argv = [manager.as_posix(), "uninstall", str(action["package"])]
    elif action["kind"] == "user-local":
        uv = shutil.which("uv", path=environment["PATH"])
        if uv:
            argv = [str(Path(uv).resolve()), "tool", "uninstall", str(action["package"])]
    if not argv:
        return {"attempted": False, "status": "manual-review"}
    result = _run(argv, env=environment)
    return {
        "attempted": True,
        "status": "pass" if result.returncode == 0 else "fail",
        "argv_sha256": hashlib.sha256(canonical_json_bytes(argv)).hexdigest(),
    }


def _receipt_candidates(system: str) -> list[Path]:
    return sorted((_state_root(system) / "receipts").glob("*/receipt.json"))


def _load_receipt(system: str, value: str) -> tuple[Path, dict[str, Any]]:
    if value == "latest":
        candidates = _receipt_candidates(system)
        if not candidates:
            raise NativeSuiteError("no native tooling receipt exists")
        path = candidates[-1]
    elif re.fullmatch(r"[0-9A-Za-z._-]+", value):
        path = _state_root(system) / "receipts" / value / "receipt.json"
    else:
        path = Path(value)
    if path.is_symlink() or not path.is_file():
        raise NativeSuiteError("receipt must be a regular file")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or receipt.get("version") != RECEIPT_VERSION or receipt.get("receipt_sha256") != _digest(receipt, "receipt_sha256"):
        raise NativeSuiteError("receipt version or digest is invalid")
    return path, receipt


def apply_plan(path: Path, approved: str, expected_system: str, progress: str) -> dict[str, Any]:
    plan = load_plan(path, approved, expected_system)
    for receipt_path in reversed(_receipt_candidates(expected_system)):
        try:
            existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if existing.get("plan_sha256") == approved and existing.get("status") in {
            "pass",
            "awaiting-human",
        }:
            verified = verify_receipt(expected_system, receipt_path.as_posix())
            if verified["status"] == "pass":
                return {
                    **existing,
                    "receipt_id": receipt_path.parent.name,
                    "idempotent_reapply": True,
                    "onboard_handoff": verified["onboard_handoff"],
                }
    _progress(progress, "staging", plan_sha256=approved)
    stage = _stage_python_assets(plan)
    _checkpoint(plan, "assets-staged", "pass", {"asset_count": len(plan["prepared_assets"])})
    generation = approved[:16]
    install_root = _data_root(expected_system) / generation
    bin_root = install_root / "bin"
    bin_root.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "HOMEBREW_NO_AUTO_UPDATE": "1",
            "UV_TOOL_DIR": (install_root / "uv-tools").as_posix(),
            "UV_TOOL_BIN_DIR": bin_root.as_posix(),
            "PATH": bin_root.as_posix() + os.pathsep + os.environ.get("PATH", ""),
        }
    )
    executed: list[dict[str, Any]] = []
    privileged = [
        row
        for row in plan["tools"]
        if row["status"] in {"install", "upgrade"}
        and row["install_action"]["kind"] == "privileged-script"
    ]
    automatic = [
        row
        for row in plan["tools"]
        if row["status"] in {"install", "upgrade"}
        and row["install_action"]["kind"] in {"user-package-manager", "user-local"}
    ]
    automatic.sort(
        key=lambda row: (
            0 if row["id"] == "uv" else 1,
            str(row["category"]),
            str(row["id"]),
        )
    )
    planner_uv: Path | None = None
    if any(row["install_action"]["kind"] == "user-local" for row in automatic):
        expected_runtime = plan.get("planner_runtime", {})
        if not isinstance(expected_runtime, dict) or expected_runtime.get("status") != "ready":
            raise NativeSuiteError("approved plan lacks its verified planner runtime")
        planner_uv, current_runtime = _stage_planner_uv(
            system=expected_system,
            arch=str(plan["platform"]["arch"]),
            refresh=False,
            expected=expected_runtime,
            allow_download=False,
        )
        if planner_uv is None or current_runtime != expected_runtime:
            raise NativeSuiteError("approved planner runtime binding changed")
    for row in automatic:
        action = row["install_action"]
        component = f"tool-{row['id']}"
        saved = _load_checkpoint(plan, component)
        if saved is not None:
            verification = list(row["verification_command"])
            checked = (
                not verification
                or _run(verification, env=environment, timeout=60).returncode == 0
            )
            if checked:
                resumed = dict(saved.get("evidence", {}))
                resumed["resumed_from_checkpoint"] = True
                executed.append(resumed)
                _progress(progress, "resumed-component", tool_id=row["id"])
                continue
        _progress(progress, "applying-component", tool_id=row["id"])
        if action["kind"] == "user-package-manager":
            manager = Path(plan["platform"]["package_manager_path"])
            argv = [manager.as_posix(), *list(action["argv"])[1:]]
        else:
            if planner_uv is None:  # pragma: no cover - guarded above
                raise NativeSuiteError("verified planner uv is unavailable")
            argv = [
                planner_uv.as_posix(),
                "tool",
                "install",
                "--force",
                "--offline",
                "--no-index",
                "--no-config",
                "--no-python-downloads",
                "--find-links",
                (stage / "wheels").as_posix(),
                "--constraints",
                (stage / "constraints.txt").as_posix(),
                str(action["package"]),
            ]
        result = _run(argv, env=environment)
        record = {
            "tool_id": row["id"],
            "action_kind": action["kind"],
            "version": row["resolved"].get("version", ""),
            "argv_sha256": hashlib.sha256(canonical_json_bytes(argv)).hexdigest(),
            "exit_code": result.returncode,
        }
        if result.returncode != 0:
            record["incomplete_component_rollback"] = _rollback_incomplete_component(
                system=expected_system,
                row=row,
                environment=environment,
            )
            _checkpoint(plan, component, "fail", record)
            raise NativeSuiteError(f"component failed: {row['id']}")
        if action["kind"] == "user-package-manager":
            spec = next(item for item in TOOL_CATALOG if item.id == row["id"])
            installed = _installed_manager_version(
                expected_system,
                str(plan["platform"]["package_manager_path"]),
                spec,
            )
            record["installed_version"] = installed
            if (
                _version_key(str(row["resolved"].get("version", "")))
                and _version_key(installed)
                != _version_key(str(row["resolved"].get("version", "")))
            ):
                record["incomplete_component_rollback"] = (
                    _rollback_incomplete_component(
                        system=expected_system,
                        row=row,
                        environment=environment,
                    )
                )
                _checkpoint(plan, component, "fail", record)
                raise NativeSuiteError(
                    f"native provider installed an unapproved version: {row['id']}"
                )
        verify = list(row["verification_command"])
        if verify:
            verification = _run(verify, env=environment, timeout=60)
            record["verification_exit_code"] = verification.returncode
            if verification.returncode != 0:
                record["incomplete_component_rollback"] = _rollback_incomplete_component(
                    system=expected_system,
                    row=row,
                    environment=environment,
                )
                _checkpoint(plan, component, "fail", record)
                raise NativeSuiteError(f"component verification failed: {row['id']}")
        executed.append(record)
        _checkpoint(plan, component, "pass", record)
    receipt_id = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + generation
    receipt_root = _state_root(expected_system) / "receipts" / receipt_id
    receipt_root.mkdir(parents=True, exist_ok=False)
    elevated_script = ""
    elevated_script_sha256 = ""
    if privileged:
        elevated = receipt_root / "install-approved-tools.ps1"
        elevated.write_text(render_privileged_powershell(plan), encoding="utf-8")
        elevated_script = elevated.name
        elevated_script_sha256 = sha256_file(elevated)
    receipt: dict[str, Any] = {
        "version": RECEIPT_VERSION,
        "generated_at": utc_now(),
        "status": "awaiting-human" if privileged else "pass",
        "plan_sha256": approved,
        "profile": plan["profile"],
        "platform": expected_system,
        "generation": generation,
        "executed": executed,
        "pending_elevated_tools": [row["id"] for row in privileged],
        "elevated_script": elevated_script,
        "elevated_script_sha256": elevated_script_sha256,
        "privacy": "The receipt stores tool IDs, versions, digests, and outcomes only.",
    }
    receipt["receipt_sha256"] = _digest(receipt, "receipt_sha256")
    write_json(receipt_root / "receipt.json", receipt)
    _checkpoint(plan, "receipt", "pass", {"receipt_id": receipt_id})
    return {
        **receipt,
        "receipt_id": receipt_id,
        "onboard_handoff": (
            "scripts/moradin_forge.sh onboard --workspace <approved-workspace>"
        ),
    }


def verify_receipt(system: str, value: str) -> dict[str, Any]:
    path, receipt = _load_receipt(system, value)
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    generation_root = _data_root(system) / str(receipt.get("generation", ""))
    environment = os.environ.copy()
    environment["PATH"] = (
        (generation_root / "bin").as_posix()
        + os.pathsep
        + os.environ.get("PATH", "")
    )
    results = []
    for item in receipt.get("executed", []):
        spec = catalog.get(str(item.get("tool_id", "")))
        argv = list(verification_argv(spec)) if spec else []
        passed = bool(spec)
        if argv:
            passed = (
                subprocess.run(
                    argv,
                    check=False,
                    capture_output=True,
                    timeout=60,
                    env=environment,
                ).returncode
                == 0
            )
        results.append({"tool_id": item.get("tool_id", ""), "status": "pass" if passed else "fail"})
    pending = []
    for tool_id in receipt.get("pending_elevated_tools", []):
        spec = catalog.get(str(tool_id))
        if spec and command_present(spec.command):
            results.append({"tool_id": tool_id, "status": "pass"})
        else:
            pending.append(tool_id)
    script_name = str(receipt.get("elevated_script", ""))
    script_sha256 = str(receipt.get("elevated_script_sha256", ""))
    script_valid = True
    if pending and script_name:
        script = path.parent / script_name
        script_valid = (
            Path(script_name).name == script_name
            and script.is_file()
            and not script.is_symlink()
            and re.fullmatch(r"[0-9a-f]{64}", script_sha256) is not None
            and sha256_file(script) == script_sha256
        )
        if not script_valid:
            results.append({"tool_id": "elevated-script", "status": "fail"})
    status = "pass" if all(item["status"] == "pass" for item in results) and not pending else "attention"
    return {
        "version": "MoradinForgeToolingVerificationV2",
        "status": status,
        "receipt_id": path.parent.name,
        "results": results,
        "pending_elevated_tools": pending,
        "onboard_handoff": (
            "scripts/moradin_forge.sh onboard --workspace <approved-workspace>"
            if status == "pass"
            else ""
        ),
    }


def rollback_receipt(system: str, value: str, approved: str) -> dict[str, Any]:
    receipt_path, receipt = _load_receipt(system, value)
    if approved != receipt["receipt_sha256"]:
        raise NativeSuiteError("approved receipt digest does not match")
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    results = []
    generation = str(receipt.get("generation", ""))
    generation_root = _data_root(system) / generation
    env = os.environ.copy()
    env.update(
        {
            "UV_TOOL_DIR": (generation_root / "uv-tools").as_posix(),
            "UV_TOOL_BIN_DIR": (generation_root / "bin").as_posix(),
            "PATH": (generation_root / "bin").as_posix()
            + os.pathsep
            + os.environ.get("PATH", ""),
        }
    )
    for item in reversed(receipt.get("executed", [])):
        spec = catalog.get(str(item.get("tool_id", "")))
        if spec is None:
            continue
        if item.get("action_kind") == "user-local" and spec.python_package:
            uv = shutil.which("uv", path=env["PATH"])
            argv = (
                [str(Path(uv).resolve()), "tool", "uninstall", spec.python_package]
                if uv
                else []
            )
        elif item.get("action_kind") == "user-package-manager" and system == "macos" and spec.brew_formula:
            manager = _trusted_manager("macos")
            argv = [manager.as_posix(), "uninstall", spec.brew_formula] if manager else []
        else:
            argv = []
        if not argv:
            results.append({"tool_id": spec.id, "status": "manual"})
            continue
        result = _run(argv, env=env)
        results.append({"tool_id": spec.id, "status": "pass" if result.returncode == 0 else "fail"})
    pending_windows: list[Any] = []
    if system == "windows":
        for tool_id in receipt.get("pending_elevated_tools", []):
            spec = catalog.get(str(tool_id))
            if spec and spec.winget_id and command_present(spec.command):
                pending_windows.append(spec)
            elif spec:
                results.append({"tool_id": spec.id, "status": "pass"})
        if pending_windows:
            manager = _trusted_manager("windows")
            if manager is None:
                raise NativeSuiteError("trusted WinGet is required to prepare rollback")
            lines = [
                "$ErrorActionPreference = 'Stop'",
                "$manager = '" + manager.as_posix().replace("'", "''") + "'",
            ]
            for spec in pending_windows:
                if not re.fullmatch(r"[0-9A-Za-z._-]+", spec.winget_id):
                    raise NativeSuiteError("catalog WinGet identifier is unsafe")
                lines.append(
                    "& $manager uninstall --id '"
                    + spec.winget_id
                    + "' --exact --disable-interactivity"
                )
                lines.append("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }")
                results.append({"tool_id": spec.id, "status": "awaiting-human"})
            script = receipt_path.parent / "rollback-approved-tools.ps1"
            script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    data_root = _data_root(system)
    root = data_root / generation
    if (
        re.fullmatch(r"[0-9a-f]{16}", generation)
        and data_root.is_dir()
        and not data_root.is_symlink()
        and root.parent.resolve() == data_root.resolve()
        and root.is_dir()
        and not root.is_symlink()
    ):
        if not pending_windows:
            shutil.rmtree(root)
    failed = any(item["status"] == "fail" for item in results)
    awaiting = any(item["status"] == "awaiting-human" for item in results)
    return {
        "version": ROLLBACK_VERSION,
        "status": "fail" if failed else "awaiting-human" if awaiting else "pass",
        "receipt_sha256": approved,
        "results": results,
        "elevated_script": "rollback-approved-tools.ps1" if pending_windows else "",
        "elevated_script_sha256": (
            sha256_file(receipt_path.parent / "rollback-approved-tools.ps1")
            if pending_windows
            else ""
        ),
    }


def status(system: str) -> dict[str, Any]:
    candidates = _receipt_candidates(system)
    if not candidates:
        return {"version": "MoradinForgeToolingStatusV1", "status": "attention", "latest_receipt": "", "receipt_status": "missing"}
    path, receipt = _load_receipt(system, candidates[-1].as_posix())
    verification = verify_receipt(system, path.as_posix())
    return {
        "version": "MoradinForgeToolingStatusV1",
        "status": "ready" if verification["status"] == "pass" else "attention",
        "latest_receipt": path.parent.name,
        "receipt_status": receipt["status"],
        "verification_status": verification["status"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("macos", "windows"), required=True)
    parser.add_argument("--forge-root", type=Path, default=REPO_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--output", choices=("auto", "summary", "json"), default="auto")
    state = commands.add_parser("status")
    state.add_argument("--progress", choices=("auto", "plain", "json", "off"), default="auto")
    plan = commands.add_parser("plan")
    profiles = plan.add_mutually_exclusive_group(required=True)
    profiles.add_argument("--profile", choices=("practical", "extended"))
    profiles.add_argument("--custom", action="store_true")
    plan.add_argument("--select", action="append", default=[])
    plan.add_argument("--exclude", action="append", default=[])
    plan.add_argument("--refresh-versions", action="store_true")
    plan.add_argument("--output", type=Path, required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--approve-plan-sha256", required=True)
    apply.add_argument("--progress", choices=("auto", "plain", "json", "off"), default="auto")
    verify = commands.add_parser("verify")
    receipts = verify.add_mutually_exclusive_group(required=True)
    receipts.add_argument("--latest", action="store_true")
    receipts.add_argument("--receipt")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--receipt", default="latest")
    rollback.add_argument("--approve-receipt-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        forge_root = args.forge_root.resolve()
        if args.command == "doctor":
            payload = build_doctor(args.platform)
            if args.output in {"summary", "auto"} and sys.stderr.isatty():
                print(f"Moradin Forge doctor: {payload['status']}", file=sys.stderr)
            code = 0 if payload["status"] == "ready" else 2
        elif args.command == "status":
            _progress(args.progress, "reading-status")
            payload = status(args.platform)
            code = 0
        elif args.command == "plan":
            profile = "custom" if args.custom else args.profile
            payload = build_plan(
                forge_root=forge_root,
                expected_system=args.platform,
                profile=profile,
                include=args.select,
                exclude=args.exclude,
                refresh=args.refresh_versions,
            )
            write_json(args.output.resolve(), payload)
            payload = {**payload, "plan_artifact": args.output.name}
            code = 0 if payload["status"] == "ready" else 2
        elif args.command == "apply":
            payload = apply_plan(args.plan, args.approve_plan_sha256, args.platform, args.progress)
            code = 0
        elif args.command == "verify":
            payload = verify_receipt(args.platform, "latest" if args.latest else args.receipt)
            code = 0 if payload["status"] == "pass" else 1
        else:
            payload = rollback_receipt(args.platform, args.receipt, args.approve_receipt_sha256)
            code = 0 if payload["status"] == "pass" else 1
    except (NativeSuiteError, WorkstationError, OSError, ValueError, json.JSONDecodeError) as error:
        payload = {"version": "MoradinForgeToolingResultV2", "status": "error", "error": str(error)}
        code = 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
