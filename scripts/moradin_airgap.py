#!/usr/bin/env python3
"""Target-bound, deterministic air-gap kits for Moradin Forge."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import lzma
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

try:
    from scripts import public_export
    from scripts.moradin_tooling_suite import (
        BOOTSTRAP_UV_BINARY_SHA256,
        BOOTSTRAP_UV_VERSION,
        PLAN_TTL,
        SUPPORTED_ARCHES,
        ToolingSuiteError,
        _package_versions,
        _expected_stage_items,
        _expected_constraints,
        _record_digest as suite_record_digest,
        _resolved_package,
        _package_name,
        _user_roots,
        apply_suite_plan,
        build_suite_plan,
        host_facts,
        installer_manifest_sha256,
        rollback_suite_receipt,
        stage_suite_assets,
        validate_suite_plan_contents,
        validate_staged_assets,
        verify_suite_receipt,
    )
    from scripts.moradin_workstation import (
        CATALOG_PATH,
        TOOL_CATALOG,
        canonical_json_bytes,
        command_present,
        sha256_bytes,
        sha256_file,
        plan_digest,
        utc_now,
        write_json,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import public_export  # type: ignore[no-redef]
    from moradin_tooling_suite import (  # type: ignore[no-redef]
        BOOTSTRAP_UV_BINARY_SHA256,
        BOOTSTRAP_UV_VERSION,
        PLAN_TTL,
        SUPPORTED_ARCHES,
        ToolingSuiteError,
        _package_versions,
        _expected_stage_items,
        _expected_constraints,
        _record_digest as suite_record_digest,
        _resolved_package,
        _package_name,
        _user_roots,
        apply_suite_plan,
        build_suite_plan,
        host_facts,
        installer_manifest_sha256,
        rollback_suite_receipt,
        stage_suite_assets,
        validate_suite_plan_contents,
        validate_staged_assets,
        verify_suite_receipt,
    )
    from moradin_workstation import (  # type: ignore[no-redef]
        CATALOG_PATH,
        TOOL_CATALOG,
        canonical_json_bytes,
        command_present,
        sha256_bytes,
        sha256_file,
        plan_digest,
        utc_now,
        write_json,
    )


AIRGAP_REQUEST_VERSION = "AirgapRequestV1"
AIRGAP_LOCK_VERSION = "AirgapLockV1"
AIRGAP_BUNDLE_VERSION = "AirgapBundleV1"
AIRGAP_VERIFY_VERSION = "AirgapVerifyV1"
AIRGAP_APPLY_VERSION = "AirgapApplyV1"
PYTHON_RUNTIME_MANIFEST_VERSION = "MoradinForgePythonRuntimeManifestV1"
AIRGAP_MAX_AGE = timedelta(days=30)
AIRGAP_MAX_MEMBERS = 50_000
AIRGAP_MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
AIRGAP_MAX_TOTAL_BYTES = 32 * 1024 * 1024 * 1024
AIRGAP_MAX_RECORD_BYTES = 16 * 1024 * 1024
AIRGAP_MAX_PACKAGE_RECORDS = 100_000
AIRGAP_SOURCE_DATE_EPOCH = 946684800
REPO_ROOT = Path(__file__).resolve().parents[1]
APT_PACKAGE_STATE_FIELDS = (
    "package",
    "version",
    "architecture",
    "essential",
    "multi_arch",
    "provides",
    "depends",
    "pre_depends",
    "conflicts",
    "breaks",
    "replaces",
)
APT_DPKG_QUERY_FORMAT = (
    "${Package}\t${Version}\t${Architecture}\t${Essential}\t${Multi-Arch}\t"
    "${Provides}\t${Depends}\t${Pre-Depends}\t${Conflicts}\t${Breaks}\t"
    "${Replaces}\n"
)

SUPPORTED_TARGETS: dict[tuple[str, str], str] = {
    ("ubuntu", "24.04"): "apt",
    ("debian", "12"): "apt",
    ("fedora", "44"): "dnf",
    ("rocky", "9"): "dnf",
    ("arch", "rolling"): "pacman",
}

TARGET_IMAGES: dict[tuple[str, str], str] = {
    (
        "ubuntu",
        "24.04",
    ): "ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90",
    (
        "debian",
        "12",
    ): "debian@sha256:9344f8b8992482f80cba753f323adeaf17690076c095ccff6cc9536be98185dc",
    (
        "fedora",
        "44",
    ): "fedora@sha256:6c75d5bf57cb0fa5aa4b92c6a83c86c791644496d9ac230de7711f5b8ec3b898",
    (
        "rocky",
        "9",
    ): "rockylinux/rockylinux@sha256:8101994123cf3d0a8fee517bee7f39e555c7d92bd2d9eb3303cc988a0eeed00f",
    (
        "arch",
        "rolling",
    ): "archlinux/archlinux@sha256:a1416966c943087a2339f1d6d6119a591e7e9a2daa2c2f310b6ad84a6042b2ca",
}

BOOTSTRAP_UV_ARCHIVE_SHA256 = {
    "amd64": "ec72570c9d1f33021aa80b176d7baba390de2cfeb1abcbefca346d563bf17484",
    "arm64": "0ed7d20f49f6b9b60d45fdfcac28f3ac01a671a6ef08672401ed2833423fea2a",
}


class AirgapError(RuntimeError):
    """Raised when an air-gap request, lock, kit, or apply is unsafe."""


def _record_digest(payload: dict[str, Any], field: str) -> str:
    return sha256_bytes(
        canonical_json_bytes({key: value for key, value in payload.items() if key != field})
    )


def _assert_digest(value: object, *, label: str) -> str:
    rendered = str(value)
    if not re.fullmatch(r"[0-9a-f]{64}", rendered):
        raise AirgapError(f"{label} must be a lowercase SHA-256 digest")
    return rendered


def _load_json_record(path: Path, *, version: str, digest_field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AirgapError(f"record must be a regular file: {path}")
    if not 0 < path.stat().st_size <= AIRGAP_MAX_RECORD_BYTES:
        raise AirgapError("record size exceeds the air-gap safety limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AirgapError(f"record is not valid JSON: {path}") from error
    if not isinstance(payload, dict) or payload.get("version") != version:
        raise AirgapError(f"record version must be {version}")
    recorded = _assert_digest(payload.get(digest_field), label=digest_field)
    if recorded != _record_digest(payload, digest_field):
        raise AirgapError(f"{digest_field} does not match the record contents")
    return payload


def _validated_package_rows(value: object, *, label: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > AIRGAP_MAX_PACKAGE_RECORDS:
        raise AirgapError(f"{label} is not a bounded package list")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {"package", "version"}:
            raise AirgapError(f"{label} contains a malformed package row")
        package = str(row.get("package", ""))
        version = str(row.get("version", ""))
        if (
            not re.fullmatch(r"[A-Za-z0-9@._+:-]+", package)
            or package in seen
            or not version
            or len(version) > 512
            or any(ord(character) < 32 or ord(character) == 127 for character in version)
        ):
            raise AirgapError(f"{label} contains unsafe package metadata")
        seen.add(package)
        normalized.append({"package": package, "version": version})
    if normalized != sorted(normalized, key=lambda row: row["package"]):
        raise AirgapError(f"{label} must be sorted by package")
    return normalized


def _validated_apt_package_state(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > AIRGAP_MAX_PACKAGE_RECORDS:
        raise AirgapError("apt_package_state is not a bounded package list")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != set(APT_PACKAGE_STATE_FIELDS):
            raise AirgapError("apt_package_state contains a malformed package row")
        parsed = {field: str(row.get(field, "")) for field in APT_PACKAGE_STATE_FIELDS}
        identity = (parsed["package"], parsed["architecture"])
        if (
            not re.fullmatch(r"[A-Za-z0-9@._+:-]+", parsed["package"])
            or not re.fullmatch(r"[A-Za-z0-9._-]+", parsed["architecture"])
            or not parsed["version"]
            or len(parsed["version"]) > 512
            or parsed["essential"] not in {"", "no", "yes"}
            or parsed["multi_arch"] not in {"", "allowed", "foreign", "no", "same"}
            or identity in seen
        ):
            raise AirgapError("apt_package_state contains unsafe package metadata")
        for field, rendered in parsed.items():
            limit = 65_536 if field in {
                "breaks",
                "conflicts",
                "depends",
                "pre_depends",
                "provides",
                "replaces",
            } else 512
            if len(rendered) > limit or any(
                ord(character) < 32 or ord(character) > 126
                for character in rendered
            ) or "/" in rendered or "\\" in rendered:
                raise AirgapError(
                    "apt_package_state contains unsafe package metadata"
                )
        seen.add(identity)
        normalized.append(parsed)
    if normalized != sorted(
        normalized,
        key=lambda row: (row["package"], row["architecture"]),
    ):
        raise AirgapError("apt_package_state must be sorted by package and architecture")
    return normalized


def _normalized_target_facts(facts: dict[str, Any]) -> dict[str, str]:
    os_id = str(facts.get("os_id", "")).lower()
    version = str(facts.get("version_id", facts.get("os_version", "")))
    if os_id in {"rockylinux", "rhel", "almalinux"}:
        os_id = "rocky"
    if os_id == "arch":
        version = "rolling"
    if os_id == "rocky":
        version = version.split(".", maxsplit=1)[0]
    target = (os_id, version)
    manager = str(facts.get("package_manager", ""))
    arch = str(facts.get("arch", ""))
    if target not in SUPPORTED_TARGETS or SUPPORTED_TARGETS[target] != manager:
        raise AirgapError(
            "air-gap kits support Ubuntu 24.04, Debian 12, Fedora 44, "
            "Rocky Linux 9, or a frozen Arch snapshot"
        )
    if arch not in SUPPORTED_ARCHES:
        raise AirgapError("air-gap kits support only amd64 and arm64")
    if target == ("arch", "rolling") and arch != "amd64":
        raise AirgapError(
            "frozen Arch air-gap kits currently require amd64; the official "
            "Arch snapshot/container trust lane is x86-64-only"
        )
    return {
        "system": "linux",
        "os_id": os_id,
        "version_id": version,
        "package_manager": manager,
        "arch": arch,
    }


def _run(
    argv: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout: int = 120,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    return runner(
        list(argv),
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _installed_package_version(
    package: str,
    manager: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    if not package:
        return ""
    commands = {
        "apt": ["dpkg-query", "-W", "-f=${Status}\t${Version}", "--", package],
        "dnf": ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", "--", package],
        "pacman": ["pacman", "-Q", "--", package],
    }
    result = _run(commands[manager], runner=runner)
    if result.returncode != 0:
        return ""
    value = result.stdout.strip()
    if manager == "apt":
        status, separator, version = value.partition("\t")
        return version if separator and status == "install ok installed" else ""
    if manager == "pacman":
        name, separator, version = value.partition(" ")
        return version if separator and name == package else ""
    return value


def _full_arch_inventory(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, str]]:
    result = _run(["pacman", "-Q"], runner=runner)
    if result.returncode != 0:
        raise AirgapError("Arch package inventory could not be read")
    inventory: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        package, separator, version = line.partition(" ")
        if not separator or not re.fullmatch(r"[A-Za-z0-9@._+:-]+", package):
            raise AirgapError("Arch package inventory contains malformed data")
        inventory.append({"package": package, "version": version})
    return sorted(inventory, key=lambda row: row["package"])


def _installed_package_inventory(
    manager: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, str]]:
    commands = {
        "apt": ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"],
        "dnf": ["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"],
        "pacman": ["pacman", "-Q"],
    }
    result = _run(commands[manager], runner=runner)
    if result.returncode != 0:
        raise AirgapError("installed package inventory could not be read")
    inventory: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if manager == "pacman":
            package, separator, version = line.partition(" ")
        else:
            package, separator, version = line.partition("\t")
            package = package.split(":", maxsplit=1)[0]
        if (
            not separator
            or not re.fullmatch(r"[A-Za-z0-9@._+:-]+", package)
            or not version
        ):
            raise AirgapError("installed package inventory contains malformed data")
        inventory[package] = version
    return [
        {"package": package, "version": inventory[package]}
        for package in sorted(inventory)
    ]


def _installed_apt_package_state(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, str]]:
    result = _run(
        ["dpkg-query", "-W", f"-f={APT_DPKG_QUERY_FORMAT}"],
        runner=runner,
    )
    if result.returncode != 0:
        raise AirgapError("APT package solver state could not be read")
    rows: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != len(APT_PACKAGE_STATE_FIELDS):
            raise AirgapError("APT package solver state is malformed")
        rows.append(dict(zip(APT_PACKAGE_STATE_FIELDS, fields, strict=True)))
    return _validated_apt_package_state(
        sorted(rows, key=lambda row: (row["package"], row["architecture"]))
    )


def _airgap_selected_specs(
    profile: str,
    *,
    exclude_tools: Sequence[str],
    container_engine: str,
    existing_container_engine: str,
) -> list[Any]:
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    unknown = sorted(set(exclude_tools) - set(catalog))
    if unknown:
        raise AirgapError("unknown tooling ids: " + ", ".join(unknown))
    if profile == "practical":
        if container_engine or existing_container_engine:
            raise AirgapError("practical air-gap requests must not select an engine")
        selected = {
            spec.id for spec in TOOL_CATALOG if "practical" in spec.profiles
        }
    elif profile == "extended":
        if container_engine not in {"podman", "docker"}:
            raise AirgapError("extended air-gap requests require a container engine")
        if existing_container_engine not in {"", "podman", "docker"}:
            raise AirgapError("existing container-engine evidence is malformed")
        if existing_container_engine and container_engine != existing_container_engine:
            raise AirgapError("an existing container engine must be preserved")
        selected = {
            spec.id
            for spec in TOOL_CATALOG
            if set(spec.profiles).intersection({"practical", "extended"})
        }
        selected.difference_update({"podman", "docker"})
        selected.add(container_engine)
        if container_engine == "podman" and not existing_container_engine:
            selected.update(
                {"rootless_uidmap", "rootless_network", "rootless_storage"}
            )
    else:
        raise AirgapError("air-gap requests support practical or extended profiles")
    selected.difference_update(exclude_tools)
    return sorted(
        (catalog[tool_id] for tool_id in selected),
        key=lambda item: (item.category, item.id),
    )


def build_airgap_request(
    *,
    forge_root: Path,
    profile: str,
    output: Path,
    exclude_tools: Sequence[str] = (),
    container_engine: str = "",
    approved_repositories: Sequence[str] = (),
    arch_snapshot: str = "",
    approve_arch_package_inventory: bool = False,
    facts: dict[str, Any] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if profile not in {"practical", "extended"}:
        raise AirgapError("air-gap requests support practical or extended profiles")
    raw_facts = dict(facts or host_facts())
    target = _normalized_target_facts(raw_facts)
    existing_container_engine = ""
    if profile == "extended":
        existing = [name for name in ("podman", "docker") if command_present(name)]
        existing_container_engine = existing[0] if existing else ""
        if not container_engine:
            container_engine = existing_container_engine or "podman"
    specs = _airgap_selected_specs(
        profile,
        exclude_tools=exclude_tools,
        container_engine=container_engine,
        existing_container_engine=existing_container_engine,
    )
    manual = sorted(
        spec.id
        for spec in specs
        if spec.manual_only and spec.id != existing_container_engine
    )
    if manual:
        raise AirgapError(
            "manual-only selections must be explicitly excluded before an air-gap "
            "request can be complete: " + ", ".join(manual)
        )
    manager = target["package_manager"]
    relevant_packages = sorted(
        {
            package
            for spec in specs
            if (package := _package_name(spec, manager))
        }
    )
    installed = [
        {"package": package, "version": version}
        for package in relevant_packages
        if (version := _installed_package_version(package, manager, runner=runner))
    ]
    package_inventory: list[dict[str, str]] = []
    arch_inventory: list[dict[str, str]] = []
    apt_package_state: list[dict[str, str]] = []
    if manager == "pacman":
        if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", arch_snapshot):
            raise AirgapError("Arch requests require --arch-snapshot YYYY/MM/DD")
        if not approve_arch_package_inventory:
            raise AirgapError(
                "Arch requests require separate --approve-arch-package-inventory consent"
            )
        arch_inventory = _full_arch_inventory(runner=runner)
        package_inventory = arch_inventory
    else:
        package_inventory = _installed_package_inventory(manager, runner=runner)
        if manager == "apt":
            apt_package_state = _installed_apt_package_state(runner=runner)
    if set(approved_repositories) - {"epel"}:
        raise AirgapError("only the separately approved EPEL repository is supported")
    if target["os_id"] != "rocky" and approved_repositories:
        raise AirgapError("EPEL approval applies only to Rocky Linux 9 requests")
    payload: dict[str, Any] = {
        "version": AIRGAP_REQUEST_VERSION,
        "generated_at": utc_now(),
        "profile": profile,
        "selected_tools": [spec.id for spec in specs],
        "explicitly_excluded_tools": sorted(set(exclude_tools)),
        "container_engine": container_engine,
        "existing_container_engine": existing_container_engine,
        "target": target,
        "installed_packages": installed,
        "installed_package_inventory": package_inventory,
        "apt_package_state": apt_package_state,
        "approved_repositories": sorted(set(approved_repositories)),
        "arch_snapshot": arch_snapshot,
        "arch_package_inventory": arch_inventory,
        "catalog_sha256": sha256_file(CATALOG_PATH),
        "installer_manifest_sha256": installer_manifest_sha256(forge_root),
        "privacy": (
            "Contains selected tooling and relevant package state only; no workspace "
            "contents, hostnames, machine identifiers, credentials, prompts, or paths."
        ),
    }
    payload["request_sha256"] = _record_digest(payload, "request_sha256")
    if output.exists() or output.is_symlink():
        raise AirgapError(f"request output already exists: {output}")
    write_json(output, payload)
    return payload


def load_airgap_request(
    path: Path,
    *,
    forge_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    payload = _load_json_record(
        path,
        version=AIRGAP_REQUEST_VERSION,
        digest_field="request_sha256",
    )
    required_fields = {
        "version",
        "generated_at",
        "profile",
        "selected_tools",
        "explicitly_excluded_tools",
        "container_engine",
        "existing_container_engine",
        "target",
        "installed_packages",
        "installed_package_inventory",
        "apt_package_state",
        "approved_repositories",
        "arch_snapshot",
        "arch_package_inventory",
        "catalog_sha256",
        "installer_manifest_sha256",
        "privacy",
        "request_sha256",
    }
    if set(payload) != required_fields:
        raise AirgapError("air-gap request fields do not match AirgapRequestV1")
    target = _normalized_target_facts(payload.get("target", {}))
    if payload.get("target") != target:
        raise AirgapError("air-gap request target fields are not canonical")
    profile = str(payload.get("profile", ""))
    if profile not in {"practical", "extended"}:
        raise AirgapError("air-gap request profile is unsupported")
    try:
        generated_at = datetime.fromisoformat(str(payload["generated_at"]))
    except (TypeError, ValueError) as error:
        raise AirgapError("air-gap request generation time is malformed") from error
    if generated_at.tzinfo is None:
        raise AirgapError("air-gap request generation time must include a timezone")
    selected = payload.get("selected_tools")
    catalog_ids = {spec.id for spec in TOOL_CATALOG}
    excluded = payload.get("explicitly_excluded_tools")
    if (
        not isinstance(excluded, list)
        or excluded != sorted(set(excluded))
        or set(excluded) - catalog_ids
    ):
        raise AirgapError("air-gap request excluded tools are malformed")
    container_engine = str(payload.get("container_engine", ""))
    existing_container_engine = str(payload.get("existing_container_engine", ""))
    expected_specs = _airgap_selected_specs(
        profile,
        exclude_tools=excluded,
        container_engine=container_engine,
        existing_container_engine=existing_container_engine,
    )
    expected_selected = [spec.id for spec in expected_specs]
    if (
        not isinstance(selected, list)
        or not selected
        or selected != expected_selected
        or any(
            spec.manual_only and spec.id != existing_container_engine
            for spec in expected_specs
        )
    ):
        raise AirgapError("air-gap request selected tools do not match its profile")
    approved_repositories = payload.get("approved_repositories")
    if (
        not isinstance(approved_repositories, list)
        or approved_repositories != sorted(set(approved_repositories))
        or set(approved_repositories) - {"epel"}
        or (approved_repositories and target["os_id"] != "rocky")
    ):
        raise AirgapError("air-gap request repository approvals are malformed")
    installed = _validated_package_rows(
        payload.get("installed_packages"),
        label="installed_packages",
    )
    inventory = _validated_package_rows(
        payload.get("installed_package_inventory"),
        label="installed_package_inventory",
    )
    apt_package_state = _validated_apt_package_state(
        payload.get("apt_package_state")
    )
    if target["package_manager"] == "apt":
        if not apt_package_state:
            raise AirgapError("APT requests require sanitized package solver state")
        apt_versions = {
            (row["package"], row["version"])
            for row in apt_package_state
        }
        if any(
            (row["package"].split(":", maxsplit=1)[0], row["version"])
            not in apt_versions
            for row in inventory
        ):
            raise AirgapError("APT package inventory and solver state do not match")
    elif apt_package_state:
        raise AirgapError("non-APT requests must not contain APT solver state")
    installed_map = {row["package"]: row["version"] for row in installed}
    inventory_map = {row["package"]: row["version"] for row in inventory}
    expected_direct_packages = {
        package
        for spec in expected_specs
        if (package := _package_name(spec, target["package_manager"]))
    }
    if set(installed_map) - expected_direct_packages or any(
        inventory_map.get(package) != version
        for package, version in installed_map.items()
    ):
        raise AirgapError("air-gap request installed package state is inconsistent")
    arch_inventory = _validated_package_rows(
        payload.get("arch_package_inventory"),
        label="arch_package_inventory",
    )
    arch_snapshot = str(payload.get("arch_snapshot", ""))
    if target["package_manager"] == "pacman":
        if (
            not re.fullmatch(r"\d{4}/\d{2}/\d{2}", arch_snapshot)
            or arch_inventory != inventory
        ):
            raise AirgapError("Arch request snapshot or package inventory is malformed")
    elif arch_snapshot or arch_inventory:
        raise AirgapError("non-Arch requests must not contain Arch package state")
    if payload.get("catalog_sha256") != sha256_file(CATALOG_PATH):
        raise AirgapError("air-gap request catalog does not match this Forge checkout")
    if payload.get("installer_manifest_sha256") != installer_manifest_sha256(
        forge_root
    ):
        raise AirgapError("air-gap request installer does not match this Forge checkout")
    return payload


def _non_executable_action(tool_id: str, *, kind: str, reason: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "tool_id": tool_id,
        "package": "",
        "version": "",
        "manager": "",
        "repository": "",
        "requires_elevation": False,
        "auto_execute": False,
        "reason": reason,
    }


def _retarget_suite_plan(
    plan: dict[str, Any],
    request: dict[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Replace disposable-builder package state with request-recorded target state."""

    manager = str(request["target"]["package_manager"])
    installed = {
        str(row["package"]): str(row["version"])
        for row in request.get("installed_packages", [])
    }
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    manual: list[str] = []
    root_actions: list[dict[str, Any]] = []
    for row in plan["tools"]:
        spec = catalog[str(row["id"])]
        package = _package_name(spec, manager)
        previous = installed.get(package, "") if package else ""
        if spec.id == request.get("existing_container_engine"):
            row["present"] = True
            row["installed_version"] = previous or "present-preserved"
            row["status"] = "protected-existing"
            row["install_action"] = _non_executable_action(
                spec.id,
                kind="protected-existing",
                reason="existing container engine and configuration are preserved",
            )
            continue
        _builder_installed, candidate = _package_versions(
            package,
            manager,
            runner=runner,
        )
        if package and candidate and not spec.python_package:
            row["resolved"] = _resolved_package(package, manager, candidate)
            row["resolved"].update(
                {
                    "download_size": int(row.get("resolved", {}).get("download_size", 0)),
                    "installed_size": int(row.get("resolved", {}).get("installed_size", 0)),
                }
            )
            if previous == candidate:
                row["present"] = True
                row["installed_version"] = previous
                row["status"] = "current"
                row["install_action"] = _non_executable_action(
                    spec.id,
                    kind="none",
                    reason="signed package is already at the frozen version",
                )
            else:
                row["present"] = bool(previous)
                row["installed_version"] = previous
                row["status"] = "upgrade" if previous else "install"
                row["install_action"] = {
                    "kind": "system-package",
                    "tool_id": spec.id,
                    "package": package,
                    "version": candidate,
                    "manager": manager,
                    "repository": spec.dnf_repository,
                    "requires_elevation": True,
                    "auto_execute": True,
                    "previous_version": previous,
                    "rollback_closure": (
                        "frozen-previous-package" if previous else "remove-owned-package"
                    ),
                    "reason": "exact signed operating-system package in the sealed kit",
                }
        elif row["install_action"]["kind"] == "manual":
            manual.append(spec.id)
        if row["install_action"]["kind"] in {"system-package", "forge-global"}:
            root_actions.append(row["install_action"])
    if manual:
        raise AirgapError(
            "automatic air-gap selections did not resolve completely: "
            + ", ".join(sorted(manual))
        )
    plan["root_actions"] = root_actions
    plan["manual_tools"] = []
    plan["blockers"] = []
    plan["status"] = "ready"
    plan["selected_tools"] = list(request["selected_tools"])
    plan["explicitly_excluded_tools"] = list(
        request.get("explicitly_excluded_tools", [])
    )
    plan["approved_repositories"] = list(request.get("approved_repositories", []))
    plan["repository_bootstrap"] = None
    plan["approve_arch_system_upgrade"] = manager == "pacman"
    plan.pop("plan_sha256", None)
    try:
        validate_suite_plan_contents(plan)
    except ToolingSuiteError as error:
        raise AirgapError(f"resolved air-gap plan is unsafe: {error}") from error
    plan["plan_sha256"] = plan_digest(plan)
    return plan


def _debian_package_fields(
    package_path: Path,
    fields: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    allowed = {"Architecture", "Package", "Version"}
    if not fields or set(fields) - allowed:
        raise AirgapError("unsupported Debian package metadata field")
    values: list[str] = []
    for field in fields:
        result = _run(
            ["dpkg-deb", "-f", package_path.as_posix(), field],
            runner=runner,
        )
        value = result.stdout.strip()
        if result.returncode != 0 or not value or "\n" in value:
            raise AirgapError(
                f"downloaded Debian package metadata is malformed: {package_path.name}"
            )
        values.append(value)
    return values


def _write_apt_solver_status(
    rows: Sequence[dict[str, str]],
    destination: Path,
) -> None:
    field_names = {
        "essential": "Essential",
        "multi_arch": "Multi-Arch",
        "provides": "Provides",
        "depends": "Depends",
        "pre_depends": "Pre-Depends",
        "conflicts": "Conflicts",
        "breaks": "Breaks",
        "replaces": "Replaces",
    }
    stanzas: list[str] = []
    for row in _validated_apt_package_state(list(rows)):
        lines = [
            f"Package: {row['package']}",
            "Status: install ok installed",
            f"Architecture: {row['architecture']}",
            f"Version: {row['version']}",
        ]
        lines.extend(
            f"{field_names[field]}: {row[field]}"
            for field in field_names
            if row[field]
        )
        stanzas.append("\n".join(lines))
    destination.write_text("\n\n".join(stanzas) + "\n", encoding="utf-8")


def _apt_transaction_closure(
    packages: Sequence[str],
    target_state: Sequence[dict[str, str]],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    requested: list[str] = []
    for package in packages:
        _installed, candidate = _package_versions(package, "apt", runner=runner)
        if not candidate:
            raise AirgapError(f"APT package candidate is unavailable: {package}")
        requested.append(f"{package}={candidate}")
    with tempfile.TemporaryDirectory(prefix="moradin-apt-solver-") as temporary:
        status = Path(temporary) / "status"
        _write_apt_solver_status(target_state, status)
        result = _run(
            [
                "apt-get",
                "-o",
                f"Dir::State::status={status.as_posix()}",
                "-o",
                "Dir::State::extended_states=/dev/null",
                "--simulate",
                "--no-install-recommends",
                "install",
                "--",
                *requested,
            ],
            runner=runner,
            timeout=600,
        )
    if result.returncode != 0:
        raise AirgapError("APT target-bound dependency resolution failed")
    resolved: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if line.startswith(("Remv ", "Purg ")):
            raise AirgapError("APT target-bound transaction would remove packages")
        if not line.startswith("Inst "):
            continue
        match = re.fullmatch(
            r"Inst ([A-Za-z0-9@._+:-]+)(?: \[[^\]]+\])? "
            r"\(([^ )]+)(?: [^)]*)?\)",
            line,
        )
        if match is None:
            raise AirgapError("APT target-bound transaction output is malformed")
        package, version = match.groups()
        if package in resolved and resolved[package] != version:
            raise AirgapError("APT target-bound transaction is ambiguous")
        resolved[package] = version
    if any(
        package.split(":", maxsplit=1)[0]
        not in {name.split(":", maxsplit=1)[0] for name in resolved}
        for package in packages
    ):
        raise AirgapError("APT target-bound transaction omitted a selected package")
    return [f"{package}={resolved[package]}" for package in sorted(resolved)]


def _download_apt_packages(
    packages: Sequence[str],
    output: Path,
    *,
    target_state: Sequence[dict[str, str]],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    output.mkdir(parents=True, exist_ok=False)
    closure = _apt_transaction_closure(
        packages,
        target_state,
        runner=runner,
    )
    for package in closure:
        result = _run(
            ["apt-get", "download", "--", package],
            runner=runner,
            timeout=900,
            cwd=output,
        )
        if result.returncode != 0:
            raise AirgapError(f"APT package download failed: {package}")
    records: list[dict[str, Any]] = []
    for path in sorted(output.glob("*.deb")):
        fields = _debian_package_fields(
            path,
            ["Package", "Version", "Architecture"],
            runner=runner,
        )
        metadata = _run(
            [
                "apt-cache",
                "show",
                "--no-all-versions",
                f"{fields[0]}={fields[1]}",
            ],
            runner=runner,
        )
        authenticated_hashes = {
            line.partition(":")[2].strip()
            for line in metadata.stdout.splitlines()
            if line.startswith("SHA256:")
        }
        digest = sha256_file(path)
        if metadata.returncode != 0 or digest not in authenticated_hashes:
            raise AirgapError(
                f"Debian package is absent from authenticated APT metadata: {path.name}"
            )
        records.append(
            {
                "package": fields[0],
                "version": fields[1],
                "arch": fields[2],
                "filename": path.name,
                "sha256": digest,
                "size": path.stat().st_size,
                "signature": "apt-signed-index",
                "repository_sha256": digest,
            }
        )
    if not records:
        raise AirgapError("APT closure did not produce package assets")
    return records


def _download_dnf_packages(
    packages: Sequence[str],
    output: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    output.mkdir(parents=True, exist_ok=False)
    result = _run(
        [
            "dnf",
            "download",
            "--resolve",
            "--alldeps",
            "--destdir",
            output.as_posix(),
            "--",
            *packages,
        ],
        runner=runner,
        timeout=1800,
    )
    if result.returncode != 0:
        raise AirgapError("DNF dependency closure download failed")
    records: list[dict[str, Any]] = []
    for path in sorted(output.glob("*.rpm")):
        signature = _run(["rpmkeys", "--checksig", path.as_posix()], runner=runner)
        if signature.returncode != 0 or "pgp" not in signature.stdout.lower():
            raise AirgapError(f"RPM signature verification failed: {path.name}")
        query = _run(
            [
                "rpm",
                "-qp",
                "--qf",
                "%{NAME}\n%{VERSION}-%{RELEASE}\n%{ARCH}\n",
                path.as_posix(),
            ],
            runner=runner,
        )
        fields = query.stdout.splitlines()
        if query.returncode != 0 or len(fields) != 3:
            raise AirgapError(f"downloaded RPM is malformed: {path.name}")
        records.append(
            {
                "package": fields[0],
                "version": fields[1],
                "arch": fields[2],
                "filename": path.name,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "signature": "rpm-package-signature",
            }
        )
    if not records:
        raise AirgapError("DNF closure did not produce package assets")
    return records


def _download_pacman_packages(
    packages: Sequence[str],
    output: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    output.mkdir(parents=True, exist_ok=False)
    closure: set[str] = set(packages)
    for package in packages:
        tree = _run(["pactree", "-s", "-u", package], runner=runner)
        if tree.returncode != 0:
            raise AirgapError(f"Pacman dependency closure failed: {package}")
        closure.update(
            line.strip()
            for line in tree.stdout.splitlines()
            if re.fullmatch(r"[A-Za-z0-9@._+:-]+", line.strip())
        )
    result = _run(
        [
            "pacman",
            "-Sw",
            "--cachedir",
            output.as_posix(),
            "--noconfirm",
            "--",
            *sorted(closure),
        ],
        runner=runner,
        timeout=1800,
    )
    if result.returncode != 0:
        raise AirgapError("Pacman synchronized closure download failed")
    records: list[dict[str, Any]] = []
    package_paths = sorted(
        path
        for path in output.iterdir()
        if path.is_file() and not path.name.endswith(".sig")
    )
    for path in package_paths:
        signature_path = path.with_name(path.name + ".sig")
        if not signature_path.is_file():
            raise AirgapError(f"Pacman package signature is missing: {path.name}")
        signature = _run(
            ["pacman-key", "--verify", signature_path.as_posix(), path.as_posix()],
            runner=runner,
        )
        if signature.returncode != 0:
            raise AirgapError(f"Pacman package signature failed: {path.name}")
        query = _run(
            ["pacman", "-Qp", "--print-format", "%n\n%v\n%a", path.as_posix()],
            runner=runner,
        )
        fields = query.stdout.splitlines()
        if query.returncode != 0 or len(fields) != 3:
            raise AirgapError(f"downloaded Pacman package is malformed: {path.name}")
        records.append(
            {
                "package": fields[0],
                "version": fields[1],
                "arch": fields[2],
                "filename": path.name,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "signature_filename": signature_path.name,
                "signature_sha256": sha256_file(signature_path),
                "signature_size": signature_path.stat().st_size,
                "signature": "pacman-package-signature",
            }
        )
    if not records:
        raise AirgapError("Pacman closure did not produce package assets")
    return records


def _download_previous_package(
    *,
    manager: str,
    package: str,
    version: str,
    output: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[Path, Path | None]:
    output.mkdir(parents=True, exist_ok=False)
    if manager == "apt":
        result = _run(
            ["apt-get", "download", "--", f"{package}={version}"],
            runner=runner,
            timeout=900,
            cwd=output,
        )
        candidates = sorted(output.glob("*.deb"))
    elif manager == "dnf":
        result = _run(
            [
                "dnf",
                "download",
                "--destdir",
                output.as_posix(),
                "--",
                f"{package}-{version}",
            ],
            runner=runner,
            timeout=900,
        )
        candidates = sorted(output.glob("*.rpm"))
    else:
        result = _run(
            [
                "pacman",
                "-Sw",
                "--cachedir",
                output.as_posix(),
                "--noconfirm",
                "--",
                package,
            ],
            runner=runner,
            timeout=900,
        )
        candidates = sorted(
            path
            for path in output.iterdir()
            if path.is_file() and not path.name.endswith(".sig")
        )
    if result.returncode != 0 or len(candidates) != 1:
        raise AirgapError(
            f"rollback closure is unavailable for {package} at {version}"
        )
    candidate = candidates[0]
    signature = candidate.with_name(candidate.name + ".sig")
    metadata_commands = {
        "dnf": [
            "rpm",
            "-qp",
            "--qf",
            "%{NAME}\n%{VERSION}-%{RELEASE}\n",
            candidate.as_posix(),
        ],
        "pacman": [
            "pacman",
            "-Qp",
            "--print-format",
            "%n\n%v",
            candidate.as_posix(),
        ],
    }
    if manager == "apt":
        fields = _debian_package_fields(
            candidate,
            ["Package", "Version"],
            runner=runner,
        )
        metadata_returncode = 0
    else:
        metadata = _run(metadata_commands[manager], runner=runner)
        fields = metadata.stdout.splitlines()
        metadata_returncode = metadata.returncode
    if (
        metadata_returncode != 0
        or fields != [package, version]
        or (manager == "pacman" and not signature.is_file())
    ):
        raise AirgapError(
            f"rollback package does not match {package} at {version}"
        )
    if manager == "dnf":
        check = _run(["rpmkeys", "--checksig", candidate.as_posix()], runner=runner)
        if check.returncode != 0 or "pgp" not in check.stdout.lower():
            raise AirgapError(f"rollback RPM signature failed: {package}")
    if manager == "pacman":
        check = _run(
            ["pacman-key", "--verify", signature.as_posix(), candidate.as_posix()],
            runner=runner,
        )
        if check.returncode != 0:
            raise AirgapError(f"rollback Pacman signature failed: {package}")
    return candidate, signature if signature.is_file() else None


def _attach_rollback_closure(
    records: list[dict[str, Any]],
    request: dict[str, Any],
    package_root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    manager = str(request["target"]["package_manager"])
    if manager == "apt":
        installed = {
            (str(row["package"]), str(row["architecture"])): str(row["version"])
            for row in request.get("apt_package_state", [])
        }
    else:
        installed = {
            str(row["package"]): str(row["version"])
            for row in request.get("installed_package_inventory", [])
        }
    for record in records:
        if manager == "apt":
            previous = installed.get(
                (str(record["package"]), str(record["arch"])),
                "",
            )
        else:
            previous = installed.get(str(record["package"]), "")
        record["previous_version"] = previous
        if not previous or previous == record["version"]:
            record["rollback_filename"] = ""
            record["rollback_sha256"] = ""
            record["rollback_size"] = 0
            continue
        with tempfile.TemporaryDirectory(
            prefix="moradin-airgap-rollback-",
            dir=package_root.parent,
        ) as temporary:
            candidate, signature = _download_previous_package(
                manager=manager,
                package=str(record["package"]),
                version=previous,
                output=Path(temporary) / "download",
                runner=runner,
            )
            digest = sha256_file(candidate)
            filename = f"rollback-{record['package']}-{digest[:12]}-{candidate.name}"
            destination = package_root / filename
            shutil.copyfile(candidate, destination)
            record["rollback_filename"] = filename
            record["rollback_sha256"] = digest
            record["rollback_size"] = destination.stat().st_size
            if manager == "apt":
                package_metadata = _run(
                    [
                        "dpkg-deb",
                        "-f",
                        candidate.as_posix(),
                        "Architecture",
                    ],
                    runner=runner,
                )
                authenticated = _run(
                    [
                        "apt-cache",
                        "show",
                        "--no-all-versions",
                        f"{record['package']}={previous}",
                    ],
                    runner=runner,
                )
                authenticated_hashes = {
                    line.partition(":")[2].strip()
                    for line in authenticated.stdout.splitlines()
                    if line.startswith("SHA256:")
                }
                if (
                    package_metadata.returncode != 0
                    or len(package_metadata.stdout.splitlines()) != 1
                    or authenticated.returncode != 0
                    or digest not in authenticated_hashes
                ):
                    raise AirgapError(
                        f"rollback Debian package lacks authenticated metadata: {record['package']}"
                    )
                record["rollback_arch"] = package_metadata.stdout.strip()
                record["rollback_repository_sha256"] = digest
            if signature is not None:
                signature_filename = filename + ".sig"
                signature_destination = package_root / signature_filename
                shutil.copyfile(signature, signature_destination)
                record["rollback_signature_filename"] = signature_filename
                record["rollback_signature_sha256"] = sha256_file(
                    signature_destination
                )
                record["rollback_signature_size"] = signature_destination.stat().st_size


def _apt_keyrings() -> list[Path]:
    return sorted(
        {
            *Path("/usr/share/keyrings").glob("*archive*.gpg"),
            *Path("/etc/apt/trusted.gpg.d").glob("*.gpg"),
        }
    )


def _copy_decompressed_apt_index(source: Path, target: Path) -> None:
    """Copy one APT Packages index while enforcing the bundle member limit."""

    total = 0

    def copy_chunks(stream: Any) -> None:
        nonlocal total
        with target.open("wb") as output:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > AIRGAP_MAX_FILE_BYTES:
                    raise AirgapError(
                        f"APT Packages index exceeds the safety limit: {source.name}"
                    )
                output.write(chunk)

    try:
        if source.suffix == ".lz4":
            process = subprocess.Popen(  # noqa: S603 - fixed argv, container-local file
                ["lz4", "-d", "-c", "--", source.as_posix()],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
            )
            assert process.stdout is not None
            try:
                copy_chunks(process.stdout)
            except Exception:
                process.kill()
                process.wait(timeout=30)
                raise
            stderr = process.communicate(timeout=300)[1]
            if process.returncode != 0:
                detail = stderr.decode("utf-8", errors="replace").strip()
                raise AirgapError(
                    f"APT Packages decompression failed: {source.name}: {detail}"
                )
        elif source.suffix == ".xz":
            with lzma.open(source, "rb") as stream:
                copy_chunks(stream)
        elif source.suffix == ".gz":
            with gzip.open(source, "rb") as stream:
                copy_chunks(stream)
        else:
            if source.stat().st_size > AIRGAP_MAX_FILE_BYTES:
                raise AirgapError(
                    f"APT Packages index exceeds the safety limit: {source.name}"
                )
            shutil.copyfile(source, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _copy_apt_trust_evidence(
    destination: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    releases = sorted(Path("/var/lib/apt/lists").glob("*InRelease"))
    keyrings = [
        path for path in _apt_keyrings() if path.is_file() and not path.is_symlink()
    ]
    if not releases or not keyrings:
        raise AirgapError("APT signed release metadata or archive keys are unavailable")
    records: list[dict[str, Any]] = []
    release_texts: list[str] = []
    for index, source in enumerate(releases, start=1):
        if source.is_symlink() or not source.is_file():
            raise AirgapError("APT InRelease evidence is unsafe")
        verification_argv = ["gpgv"]
        for keyring in keyrings:
            verification_argv.extend(["--keyring", keyring.as_posix()])
        verification_argv.append(source.as_posix())
        verified = _run(verification_argv, runner=runner)
        if verified.returncode != 0:
            raise AirgapError(f"APT InRelease signature failed: {source.name}")
        destination_name = f"inrelease-{index:03d}"
        target = destination / destination_name
        shutil.copyfile(source, target)
        release_texts.append(target.read_text(encoding="utf-8"))
        records.append(
            {
                "path": destination_name,
                "kind": "apt-inrelease",
                "sha256": sha256_file(target),
                "size": target.stat().st_size,
            }
        )
    for index, source in enumerate(keyrings, start=1):
        destination_name = f"archive-keyring-{index:03d}.gpg"
        target = destination / destination_name
        shutil.copyfile(source, target)
        records.append(
            {
                "path": destination_name,
                "kind": "apt-keyring",
                "sha256": sha256_file(target),
                "size": target.stat().st_size,
            }
        )
    package_indexes = sorted(Path("/var/lib/apt/lists").glob("*_Packages*"))
    for index, source in enumerate(package_indexes, start=1):
        if source.is_symlink() or not source.is_file():
            raise AirgapError("APT Packages evidence is unsafe")
        destination_name = f"packages-{index:03d}.txt"
        target = destination / destination_name
        _copy_decompressed_apt_index(source, target)
        digest = sha256_file(target)
        if not any(digest in release for release in release_texts):
            target.unlink(missing_ok=True)
            continue
        records.append(
            {
                "path": destination_name,
                "kind": "apt-packages-index",
                "sha256": digest,
                "size": target.stat().st_size,
            }
        )
    if not any(record["kind"] == "apt-packages-index" for record in records):
        raise AirgapError("APT authenticated Packages indexes were not available")
    return records


def _copy_trust_evidence(
    manager: str,
    destination: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    destination.mkdir(parents=True, exist_ok=False)
    if manager == "apt":
        return _copy_apt_trust_evidence(destination, runner=runner)
    sources: list[Path] = []
    if manager == "dnf":
        sources.extend(sorted(Path("/etc/pki/rpm-gpg").glob("*")))
        sources.extend(sorted(Path("/etc/yum.repos.d").glob("*.repo")))
        sources.extend(sorted(Path("/var/cache/dnf").glob("**/repomd.xml*")))
    else:
        sources.extend(sorted(Path("/etc/pacman.d/gnupg").glob("pubring.gpg")))
        sources.extend(sorted(Path("/var/lib/pacman/sync").glob("*.db*")))
    records: list[dict[str, Any]] = []
    used: set[str] = set()
    for source in sources:
        if source.is_symlink() or not source.is_file():
            continue
        base = re.sub(r"[^A-Za-z0-9._-]", "_", source.name)
        name = base
        index = 1
        while name in used:
            index += 1
            name = f"{index}-{base}"
        used.add(name)
        target = destination / name
        shutil.copyfile(source, target)
        records.append(
            {
                "path": name,
                "kind": f"{manager}-repository-trust",
                "sha256": sha256_file(target),
                "size": target.stat().st_size,
            }
        )
    if not records:
        raise AirgapError(f"{manager} trust evidence was not available")
    return records


def build_target_payload(
    request_path: Path,
    *,
    output: Path,
    forge_root: Path = REPO_ROOT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Internal container-side resolver for one target/platform request."""

    request = load_airgap_request(request_path, forge_root=forge_root)
    actual = _normalized_target_facts(host_facts())
    if actual != request["target"]:
        raise AirgapError("air-gap builder container does not match the request target")
    if output.exists() or output.is_symlink():
        raise AirgapError(f"target payload output already exists: {output}")
    output.mkdir(parents=True)
    try:
        builder_excludes = list(request.get("explicitly_excluded_tools", []))
        if request.get("existing_container_engine") == "podman":
            builder_excludes.extend(
                ["rootless_uidmap", "rootless_network", "rootless_storage"]
            )
        plan = build_suite_plan(
            forge_root=forge_root,
            profile=str(request["profile"]),
            exclude_tools=builder_excludes,
            container_engine=str(request.get("container_engine", "")),
            approved_repositories=request.get("approved_repositories", []),
            approve_arch_system_upgrade=request["target"]["package_manager"]
            == "pacman",
            refresh_versions=True,
            facts=host_facts(),
            runner=runner,
        )
        plan = _retarget_suite_plan(plan, request, runner=runner)
        write_json(output / "suite-plan.json", plan)
        stage_suite_assets(
            plan,
            output=output / "stage",
            forge_root=forge_root,
        )
        package_names = sorted(
            {
                str(action["package"])
                for action in plan["root_actions"]
                if action["kind"] == "system-package"
            }
        )
        manager = str(request["target"]["package_manager"])
        package_root = output / "os-packages"
        if package_names:
            if manager == "apt":
                package_records = _download_apt_packages(
                    package_names,
                    package_root,
                    target_state=request["apt_package_state"],
                    runner=runner,
                )
            else:
                downloaders = {
                    "dnf": _download_dnf_packages,
                    "pacman": _download_pacman_packages,
                }
                package_records = downloaders[manager](
                    package_names,
                    package_root,
                    runner=runner,
                )
            _attach_rollback_closure(
                package_records,
                request,
                package_root,
                runner=runner,
            )
        else:
            package_root.mkdir()
            package_records = []
        trust_records = _copy_trust_evidence(
            manager,
            output / "trust",
            runner=runner,
        )
        uv_path = os.environ.get("MORADIN_FORGE_BOOTSTRAP_UV", "")
        uv = Path(uv_path) if uv_path else Path()
        if (
            not uv_path
            or uv.is_symlink()
            or not uv.is_file()
            or sha256_file(uv) != BOOTSTRAP_UV_BINARY_SHA256[request["target"]["arch"]]
        ):
            raise AirgapError("pinned uv bootstrap binary is unavailable in the builder")
        bootstrap_root = output / "bootstrap"
        bootstrap_root.mkdir()
        uv_copy = bootstrap_root / "uv"
        shutil.copyfile(uv, uv_copy)
        os.chmod(uv_copy, 0o755)
        python_install_value = os.environ.get("UV_PYTHON_INSTALL_DIR", "")
        python_install = Path(python_install_value) if python_install_value else Path()
        if (
            not python_install_value
            or python_install.is_symlink()
            or not python_install.is_dir()
        ):
            raise AirgapError("pinned managed Python is unavailable in the builder")
        python_archive = bootstrap_root / "python-3.12.8.tar.gz"
        python_manifest_path = bootstrap_root / "python-3.12.8.manifest.json"
        with tempfile.TemporaryDirectory(
            prefix="moradin-python-materialized-",
            dir=output.parent,
        ) as temporary:
            materialized_python = Path(temporary) / "python"
            _materialize_managed_python(python_install, materialized_python)
            python_manifest = _python_runtime_manifest(materialized_python)
            write_deterministic_tar(materialized_python, python_archive)
            write_json(python_manifest_path, python_manifest)
        resolved: dict[str, Any] = {
            "version": "AirgapTargetPayloadV1",
            "request_sha256": request["request_sha256"],
            "target": request["target"],
            "suite_plan_sha256": plan["plan_sha256"],
            "package_assets": package_records,
            "trust_assets": trust_records,
            "uv": {
                "version": BOOTSTRAP_UV_VERSION,
                "path": "bootstrap/uv",
                "sha256": sha256_file(uv_copy),
                "size": uv_copy.stat().st_size,
                "archive_sha256": BOOTSTRAP_UV_ARCHIVE_SHA256[
                    request["target"]["arch"]
                ],
            },
            "python": {
                "version": "3.12.8",
                "path": "bootstrap/python-3.12.8.tar.gz",
                "sha256": sha256_file(python_archive),
                "size": python_archive.stat().st_size,
                "manifest_path": "bootstrap/python-3.12.8.manifest.json",
                "manifest_sha256": sha256_file(python_manifest_path),
                "manifest_size": python_manifest_path.stat().st_size,
                "executable": python_manifest["executable"],
                "trust": "uv-python-managed-verified-download",
            },
        }
        resolved["payload_sha256"] = _record_digest(resolved, "payload_sha256")
        write_json(output / "resolved.json", resolved)
        return resolved
    except Exception:
        if output.is_dir() and not output.is_symlink():
            shutil.rmtree(output)
        raise


def _rootless_engine(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    if shutil.which("podman"):
        result = _run(
            ["podman", "info", "--format", "{{.Host.Security.Rootless}}"],
            runner=runner,
        )
        if result.returncode == 0 and result.stdout.strip().lower() == "true":
            return "podman"
    if shutil.which("docker"):
        result = _run(
            ["docker", "info", "--format", "{{json .SecurityOptions}}"],
            runner=runner,
        )
        if result.returncode == 0 and "rootless" in result.stdout.lower():
            return "docker"
    raise AirgapError(
        "air-gap builds require an existing rootless Podman or Docker engine"
    )


def run_target_builder(
    request_path: Path,
    *,
    output: Path,
    forge_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    request = load_airgap_request(request_path, forge_root=forge_root)
    target_key = (
        str(request["target"]["os_id"]),
        str(request["target"]["version_id"]),
    )
    image = TARGET_IMAGES[target_key]
    engine = _rootless_engine(runner=runner)
    platform_name = {
        "amd64": "linux/amd64",
        "arm64": "linux/arm64",
    }[str(request["target"]["arch"])]
    output.mkdir(parents=True, exist_ok=False)
    argv = [
        engine,
        "run",
        "--rm",
        "--platform",
        platform_name,
        "--security-opt",
        "no-new-privileges",
        "--network",
        "bridge",
        "--volume",
        f"{forge_root.resolve()}:/forge:ro",
        "--volume",
        f"{request_path.resolve()}:/request/request.json:ro",
        "--volume",
        f"{output.resolve()}:/output",
        "--env",
        f"AIRGAP_ARCH_SNAPSHOT={request.get('arch_snapshot', '')}",
        image,
        "/forge/install/airgap-container-build.sh",
        "/request/request.json",
        "/output/target-payload",
    ]
    result = _run(argv, runner=runner, timeout=7200)
    if result.returncode != 0:
        if output.is_dir() and not output.is_symlink():
            shutil.rmtree(output)
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
        raise AirgapError(f"rootless target builder failed: {detail or 'unknown error'}")
    payload_root = output / "target-payload"
    resolved = _load_json_record(
        payload_root / "resolved.json",
        version="AirgapTargetPayloadV1",
        digest_field="payload_sha256",
    )
    if resolved.get("request_sha256") != request["request_sha256"]:
        raise AirgapError("target builder output is not bound to the request")
    return resolved


def _portable_suite_plan(plan: dict[str, Any]) -> dict[str, Any]:
    portable = json.loads(json.dumps(plan))
    source_sha = portable.pop("plan_sha256", "")
    portable.pop("expires_at", None)
    portable.pop("generated_at", None)
    portable["approved_workspaces"] = []
    portable["repositories"] = []
    platform_row = portable.get("platform", {})
    if isinstance(platform_row, dict):
        platform_row["host_fingerprint_sha256"] = "<host-bound-at-apply>"
    portable["target_uid"] = "<target-uid>"
    portable["source_plan_sha256"] = source_sha
    portable["portable"] = True
    return portable


def _airgap_cache_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "moradins-forge" / "airgap" / "assets"


def _cache_file(path: Path, digest: str) -> None:
    _assert_digest(digest, label="asset digest")
    cache_root = _airgap_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    destination = cache_root / digest
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise AirgapError("air-gap content cache contains an unsafe entry")
    if destination.is_file():
        if sha256_file(destination) != digest:
            raise AirgapError("air-gap content cache digest mismatch")
        return
    temporary = destination.with_name(f".{digest}.tmp")
    shutil.copyfile(path, temporary)
    os.chmod(temporary, 0o600)
    if sha256_file(temporary) != digest:
        temporary.unlink(missing_ok=True)
        raise AirgapError("air-gap cache copy changed unexpectedly")
    os.replace(temporary, destination)


def _cache_tree(root: Path, *, prefix: str) -> list[dict[str, Any]]:
    records = file_records(root)
    for row in records:
        _cache_file(root / str(row["path"]), str(row["sha256"]))
        row["path"] = f"{prefix}/{row['path']}"
    return records


def _restore_locked_files(
    records: Sequence[dict[str, Any]],
    destination: Path,
) -> None:
    cache_root = _airgap_cache_root()
    for row in records:
        relative = _safe_member_name(str(row.get("path", "")))
        digest = _assert_digest(row.get("sha256"), label="locked asset digest")
        size = int(row.get("size", -1))
        source = cache_root / digest
        if (
            source.is_symlink()
            or not source.is_file()
            or source.stat().st_size != size
            or sha256_file(source) != digest
        ):
            url = str(row.get("url", ""))
            if not url:
                raise AirgapError(
                    f"frozen asset is unavailable from cache: {relative.as_posix()}"
                )
            download_locked_asset(url, source, digest, size)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise AirgapError("locked air-gap asset would replace a path")
        shutil.copyfile(source, target)
        os.chmod(target, int(row.get("mode", 0o644)))


def _prepare_target_payload_for_lock(
    payload_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan_path = payload_root / "suite-plan.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AirgapError("target builder suite plan is invalid") from error
    portable = _portable_suite_plan(plan)
    plan_path.unlink()
    for relative in ("stage/plan.json", "stage/stage-manifest.json"):
        path = payload_root / relative
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise AirgapError("target builder stage control path is unsafe")
            path.unlink()
    hits = public_export.scan_tree(payload_root)
    if hits:
        raise AirgapError(
            "target payload failed the public leak scan: "
            + ", ".join(sorted({hit.path for hit in hits})[:5])
        )
    records = _cache_tree(payload_root, prefix="payload")
    return portable, records


def _validate_lock_contents(lock: dict[str, Any]) -> None:
    target = _normalized_target_facts(lock.get("target", {}))
    if lock.get("target") != target:
        raise AirgapError("air-gap lock target fields are not canonical")
    if lock.get("profile") not in {"practical", "extended"}:
        raise AirgapError("air-gap lock profile is unsupported")
    if lock.get("status") != "complete":
        raise AirgapError("only complete air-gap locks can produce installation kits")
    _assert_digest(lock.get("request_sha256"), label="request_sha256")
    _assert_digest(lock.get("catalog_sha256"), label="catalog_sha256")
    _assert_digest(
        lock.get("installer_manifest_sha256"),
        label="installer_manifest_sha256",
    )
    if not re.fullmatch(r"[0-9a-f]{40}", str(lock.get("source_sha", ""))):
        raise AirgapError("air-gap lock source commit is malformed")
    if int(lock.get("stale_after_days", -1)) != AIRGAP_MAX_AGE.days:
        raise AirgapError("air-gap lock stale-kit policy is malformed")
    selected = lock.get("selected_tools")
    catalog_ids = {spec.id for spec in TOOL_CATALOG}
    if (
        not isinstance(selected, list)
        or not selected
        or len(selected) != len(set(selected))
        or set(selected) - catalog_ids
    ):
        raise AirgapError("air-gap lock selected tools are malformed")
    excluded = lock.get("explicitly_excluded_tools")
    if (
        not isinstance(excluded, list)
        or excluded != sorted(set(excluded))
        or set(excluded) - catalog_ids
    ):
        raise AirgapError("air-gap lock excluded tools are malformed")
    approved = lock.get("approved_repositories")
    if (
        not isinstance(approved, list)
        or approved != sorted(set(approved))
        or set(approved) - {"epel"}
        or (approved and target["os_id"] != "rocky")
    ):
        raise AirgapError("air-gap lock repository approvals are malformed")
    existing_container_engine = str(lock.get("existing_container_engine", ""))
    if existing_container_engine not in {"", "podman", "docker"}:
        raise AirgapError("air-gap lock container-engine evidence is malformed")
    _validated_package_rows(
        lock.get("expected_package_state"),
        label="expected_package_state",
    )
    arch_inventory = _validated_package_rows(
        lock.get("arch_package_inventory"),
        label="arch_package_inventory",
    )
    if target["package_manager"] == "pacman":
        if not arch_inventory:
            raise AirgapError("Arch air-gap lock requires its package inventory")
    elif arch_inventory:
        raise AirgapError("non-Arch air-gap lock must not contain Arch package state")
    try:
        created = datetime.fromisoformat(str(lock["created_at"]))
    except (KeyError, TypeError, ValueError) as error:
        raise AirgapError("air-gap lock creation time is malformed") from error
    if created.tzinfo is None:
        raise AirgapError("air-gap lock creation time must include a timezone")
    files = lock.get("payload_files")
    if not isinstance(files, list) or not files:
        raise AirgapError("air-gap lock payload file closure is empty")
    seen: set[str] = set()
    file_bindings: dict[str, tuple[str, int]] = {}
    total_size = 0
    for row in files:
        if not isinstance(row, dict):
            raise AirgapError("air-gap lock contains a malformed file record")
        path = _safe_member_name(str(row.get("path", ""))).as_posix()
        if not path.startswith(("payload/", "forge/")) or path in seen:
            raise AirgapError("air-gap lock file paths are unsafe or duplicated")
        seen.add(path)
        _assert_digest(row.get("sha256"), label="locked file digest")
        size = int(row.get("size", -1))
        if size < 0 or size > AIRGAP_MAX_FILE_BYTES:
            raise AirgapError("air-gap lock file size is unsafe")
        total_size += size
        if total_size > AIRGAP_MAX_TOTAL_BYTES:
            raise AirgapError("air-gap lock total file size is unsafe")
        file_bindings[path] = (str(row["sha256"]), size)
    source = lock.get("source")
    if not isinstance(source, dict) or set(source) != {
        "sanitized_commit",
        "git_bundle",
        "source_snapshot",
        "copied_file_count",
    }:
        raise AirgapError("air-gap lock sanitized source record is malformed")
    if not re.fullmatch(r"[0-9a-f]{40}", str(source["sanitized_commit"])):
        raise AirgapError("air-gap lock sanitized commit is malformed")
    if int(source["copied_file_count"]) <= 0:
        raise AirgapError("air-gap lock sanitized source is empty")
    for label in ("git_bundle", "source_snapshot"):
        record = source.get(label)
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
            raise AirgapError(f"air-gap lock {label} record is malformed")
        name = str(record["path"])
        digest = _assert_digest(record["sha256"], label=f"{label} digest")
        size = int(record["size"])
        if Path(name).name != name or file_bindings.get(f"forge/{name}") != (
            digest,
            size,
        ):
            raise AirgapError(f"air-gap lock {label} is not payload-bound")
    bootstrap = lock.get("bootstrap")
    if not isinstance(bootstrap, dict) or set(bootstrap) != {"uv", "python"}:
        raise AirgapError("air-gap lock bootstrap closure is malformed")
    for label in ("uv", "python"):
        record = bootstrap.get(label)
        if not isinstance(record, dict):
            raise AirgapError(f"air-gap lock {label} bootstrap is malformed")
        relative = _safe_member_name(str(record.get("path", ""))).as_posix()
        digest = _assert_digest(record.get("sha256"), label=f"{label} digest")
        size = int(record.get("size", -1))
        if file_bindings.get(f"payload/{relative}") != (digest, size):
            raise AirgapError(f"air-gap lock {label} bootstrap is not payload-bound")
    python_record = bootstrap["python"]
    if set(python_record) != {
        "version",
        "path",
        "sha256",
        "size",
        "manifest_path",
        "manifest_sha256",
        "manifest_size",
        "executable",
        "trust",
    }:
        raise AirgapError("air-gap lock Python bootstrap fields are malformed")
    if (
        python_record.get("version") != "3.12.8"
        or python_record.get("trust") != "uv-python-managed-verified-download"
    ):
        raise AirgapError("air-gap lock Python bootstrap trust is malformed")
    manifest_relative = _safe_member_name(
        str(python_record["manifest_path"])
    ).as_posix()
    manifest_digest = _assert_digest(
        python_record["manifest_sha256"],
        label="Python runtime manifest digest",
    )
    manifest_size = int(python_record["manifest_size"])
    if file_bindings.get(f"payload/{manifest_relative}") != (
        manifest_digest,
        manifest_size,
    ):
        raise AirgapError("air-gap lock Python runtime manifest is not payload-bound")
    executable = _safe_member_name(str(python_record["executable"])).as_posix()
    if not executable.endswith("/bin/python3.12"):
        raise AirgapError("air-gap lock Python executable is malformed")
    suite_plan = lock.get("suite_plan")
    if (
        not isinstance(suite_plan, dict)
        or suite_plan.get("portable") is not True
        or suite_plan.get("platform", {}).get("host_fingerprint_sha256")
        != "<host-bound-at-apply>"
        or suite_plan.get("target_uid") != "<target-uid>"
    ):
        raise AirgapError("air-gap suite-plan template is not portable")
    package_assets = lock.get("package_assets")
    if not isinstance(package_assets, list):
        raise AirgapError("air-gap lock package closure is malformed")
    for asset in package_assets:
        if (
            not isinstance(asset, dict)
            or not re.fullmatch(
                r"[A-Za-z0-9@._+:-]+", str(asset.get("package", ""))
            )
            or Path(str(asset.get("filename", ""))).name
            != str(asset.get("filename", ""))
        ):
            raise AirgapError("air-gap lock package asset is malformed")
        for filename_key, digest_key, size_key in (
            ("filename", "sha256", "size"),
            ("signature_filename", "signature_sha256", "signature_size"),
            ("rollback_filename", "rollback_sha256", "rollback_size"),
            (
                "rollback_signature_filename",
                "rollback_signature_sha256",
                "rollback_signature_size",
            ),
        ):
            filename = str(asset.get(filename_key, ""))
            if not filename:
                continue
            digest = _assert_digest(asset.get(digest_key), label=digest_key)
            size = int(asset.get(size_key, -1))
            if Path(filename).name != filename or file_bindings.get(
                f"payload/os-packages/{filename}"
            ) != (digest, size):
                raise AirgapError("air-gap package asset is not payload-bound")
    trust_assets = lock.get("trust_assets")
    if not isinstance(trust_assets, list) or not trust_assets:
        raise AirgapError("air-gap lock repository trust closure is empty")
    for asset in trust_assets:
        if not isinstance(asset, dict):
            raise AirgapError("air-gap lock trust asset is malformed")
        name = str(asset.get("path", ""))
        digest = _assert_digest(asset.get("sha256"), label="trust asset digest")
        size = int(asset.get("size", -1))
        if (
            Path(name).name != name
            or not str(asset.get("kind", ""))
            or file_bindings.get(f"payload/trust/{name}") != (digest, size)
        ):
            raise AirgapError("air-gap trust asset is not payload-bound")


def load_airgap_lock(path: Path) -> dict[str, Any]:
    lock = _load_json_record(
        path,
        version=AIRGAP_LOCK_VERSION,
        digest_field="lock_sha256",
    )
    _validate_lock_contents(lock)
    return lock


def _assemble_airgap_kit(
    lock: dict[str, Any],
    *,
    output: Path,
    forge_root: Path,
) -> dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise AirgapError(f"air-gap kit output already exists: {output}")
    _validate_lock_contents(lock)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="moradin-airgap-assemble-",
        dir=output.parent,
    ) as temporary:
        root = Path(temporary) / "kit"
        root.mkdir()
        _restore_locked_files(lock["payload_files"], root)
        write_json(root / "AIRGAP-LOCK.json", lock)
        (root / "README-AIRGAP.md").write_text(
            airgap_readme(lock),
            encoding="utf-8",
        )
        manifest: dict[str, Any] = {
            "version": AIRGAP_BUNDLE_VERSION,
            "created_at": lock["created_at"],
            "status": "complete",
            "lock_sha256": lock["lock_sha256"],
            "source_sha": lock["source_sha"],
            "target": lock["target"],
            "profile": lock["profile"],
            "network_apply": "disabled",
            "privacy": (
                "Contains Forge, tool assets, package closure, trust evidence, and "
                "verification metadata only; no projects, credentials, prompts, host "
                "identity, raw paths, or machine history."
            ),
        }
        manifest["manifest_sha256"] = _record_digest(
            manifest,
            "manifest_sha256",
        )
        write_json(root / "airgap-manifest.json", manifest)
        write_json(
            root / "airgap.spdx.json",
            build_spdx(root, source_sha=str(lock["source_sha"])),
        )
        write_sha256sums(root)
        bundle_sha = write_deterministic_tar(root, output)
    verification = verify_airgap_bundle(output, expected_sha256=bundle_sha)
    return {
        "version": AIRGAP_BUNDLE_VERSION,
        "status": "complete",
        "output": output.as_posix(),
        "bundle_sha256": bundle_sha,
        "lock_sha256": lock["lock_sha256"],
        "lock_output": output.with_suffix(output.suffix + ".lock.json").as_posix(),
        "verification": verification,
    }


def build_airgap_bundle_from_request(
    request_path: Path,
    *,
    output: Path,
    forge_root: Path,
    target_builder: Callable[..., dict[str, Any]] = run_target_builder,
) -> dict[str, Any]:
    request = load_airgap_request(request_path, forge_root=forge_root)
    source_sha = assert_clean_public_forge(forge_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="moradin-airgap-build-",
        dir=output.parent,
    ) as temporary:
        work = Path(temporary)
        builder_root = work / "builder"
        target_builder(
            request_path,
            output=builder_root,
            forge_root=forge_root,
        )
        target_payload = builder_root / "target-payload"
        resolved_payload = _load_json_record(
            target_payload / "resolved.json",
            version="AirgapTargetPayloadV1",
            digest_field="payload_sha256",
        )
        portable_plan, payload_records = _prepare_target_payload_for_lock(
            target_payload
        )
        source_root = work / "source"
        source_root.mkdir()
        source = build_sanitized_source(forge_root, source_root)
        source_records = _cache_tree(source_root, prefix="forge")
        lock: dict[str, Any] = {
            "version": AIRGAP_LOCK_VERSION,
            "created_at": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
            "status": "complete",
            "source_sha": source_sha,
            "request_sha256": request["request_sha256"],
            "target": request["target"],
            "profile": request["profile"],
            "selected_tools": request["selected_tools"],
            "explicitly_excluded_tools": request.get(
                "explicitly_excluded_tools", []
            ),
            "approved_repositories": request.get("approved_repositories", []),
            "existing_container_engine": request.get(
                "existing_container_engine", ""
            ),
            "arch_snapshot": request.get("arch_snapshot", ""),
            "arch_package_inventory": request.get(
                "arch_package_inventory", []
            ),
            "expected_package_state": request.get("installed_packages", []),
            "catalog_sha256": request["catalog_sha256"],
            "installer_manifest_sha256": request["installer_manifest_sha256"],
            "source": source,
            "suite_plan": portable_plan,
            "package_assets": resolved_payload.get("package_assets", []),
            "trust_assets": resolved_payload.get("trust_assets", []),
            "bootstrap": {
                "uv": resolved_payload.get("uv", {}),
                "python": resolved_payload.get("python", {}),
            },
            "payload_files": sorted(
                [*payload_records, *source_records],
                key=lambda row: str(row["path"]),
            ),
            "stale_after_days": AIRGAP_MAX_AGE.days,
            "privacy": request["privacy"],
        }
        lock["lock_sha256"] = _record_digest(lock, "lock_sha256")
        lock_path = output.with_suffix(output.suffix + ".lock.json")
        if lock_path.exists() or lock_path.is_symlink():
            raise AirgapError(f"air-gap lock output already exists: {lock_path}")
        write_json(lock_path, lock)
        try:
            return _assemble_airgap_kit(
                lock,
                output=output,
                forge_root=forge_root,
            )
        except Exception:
            lock_path.unlink(missing_ok=True)
            raise


def build_airgap_bundle_from_lock(
    lock_path: Path,
    *,
    output: Path,
    forge_root: Path,
) -> dict[str, Any]:
    lock = load_airgap_lock(lock_path)
    source_sha = assert_clean_public_forge(forge_root)
    if source_sha != lock["source_sha"]:
        raise AirgapError("air-gap lock source commit does not match this Forge checkout")
    if lock["catalog_sha256"] != sha256_file(CATALOG_PATH):
        raise AirgapError("air-gap lock catalog no longer matches this Forge checkout")
    if lock["installer_manifest_sha256"] != installer_manifest_sha256(forge_root):
        raise AirgapError(
            "air-gap lock installer no longer matches this Forge checkout"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="moradin-airgap-source-proof-",
        dir=output.parent,
    ) as temporary:
        current_source = build_sanitized_source(
            forge_root,
            Path(temporary) / "source",
        )
        if current_source != lock["source"]:
            raise AirgapError(
                "air-gap lock sanitized source does not match this Forge commit"
            )
    result = _assemble_airgap_kit(lock, output=output, forge_root=forge_root)
    copied_lock = output.with_suffix(output.suffix + ".lock.json")
    if copied_lock.exists() or copied_lock.is_symlink():
        output.unlink(missing_ok=True)
        raise AirgapError(f"air-gap lock output already exists: {copied_lock}")
    shutil.copyfile(lock_path, copied_lock)
    return {**result, "lock_output": copied_lock.as_posix()}


def _current_package_state_matches(lock: dict[str, Any]) -> None:
    manager = str(lock["target"]["package_manager"])
    if manager == "pacman":
        current_inventory = _installed_package_inventory("pacman")
        if current_inventory != lock.get("arch_package_inventory", []):
            raise AirgapError(
                "Arch package inventory changed after the air-gap request"
            )
    drift: list[str] = []
    for asset in lock.get("package_assets", []):
        package = str(asset["package"])
        expected = str(asset.get("previous_version", ""))
        actual = _installed_package_version(package, manager)
        if actual != expected:
            drift.append(package)
    if drift:
        raise AirgapError(
            "target package state changed after the air-gap request: "
            + ", ".join(sorted(drift)[:20])
        )


def rebind_airgap_plan(
    lock: dict[str, Any],
    *,
    bundle_sha256: str,
    forge_root: Path,
) -> dict[str, Any]:
    _validate_lock_contents(lock)
    current_facts = host_facts()
    current_target = _normalized_target_facts(current_facts)
    if current_target != lock["target"]:
        raise AirgapError("air-gap kit does not match this target platform")
    if lock["catalog_sha256"] != sha256_file(CATALOG_PATH):
        raise AirgapError("air-gap kit catalog does not match the executing Forge")
    if lock["installer_manifest_sha256"] != installer_manifest_sha256(forge_root):
        raise AirgapError("air-gap kit installer does not match the executing Forge")
    _current_package_state_matches(lock)
    plan = json.loads(json.dumps(lock["suite_plan"]))
    plan.pop("portable", None)
    plan.pop("source_plan_sha256", None)
    now = datetime.now(tz=UTC).replace(microsecond=0)
    plan["generated_at"] = now.isoformat()
    plan["expires_at"] = (now + PLAN_TTL).isoformat()
    plan["platform"] = current_facts
    plan["target_uid"] = os.getuid()
    plan["approved_workspaces"] = []
    plan["repositories"] = []
    plan["offline"] = {
        "version": "AirgapOfflinePlanV1",
        "network": "disabled",
        "bundle_sha256": _assert_digest(
            bundle_sha256,
            label="bundle_sha256",
        ),
        "lock_sha256": lock["lock_sha256"],
        "package_assets": lock.get("package_assets", []),
        "trust_assets": lock.get("trust_assets", []),
    }
    plan.pop("plan_sha256", None)
    try:
        validate_suite_plan_contents(plan)
    except ToolingSuiteError as error:
        raise AirgapError(f"host-bound offline plan is invalid: {error}") from error
    plan["plan_sha256"] = plan_digest(plan)
    return plan


def _build_rebound_stage(
    extracted: Path,
    plan: dict[str, Any],
    destination: Path,
) -> None:
    template = extracted / "payload" / "stage"
    packages = extracted / "payload" / "os-packages"
    trust = extracted / "payload" / "trust"
    if template.is_symlink() or not template.is_dir():
        raise AirgapError("air-gap stage template is missing")
    if packages.is_symlink() or not packages.is_dir():
        raise AirgapError("air-gap package closure is missing")
    if trust.is_symlink() or not trust.is_dir():
        raise AirgapError("air-gap repository trust closure is missing")
    if destination.exists() or destination.is_symlink():
        try:
            validate_staged_assets(destination, plan)
        except ToolingSuiteError as error:
            raise AirgapError(
                "an existing air-gap stage conflicts with this exact plan"
            ) from error
        return
    with tempfile.TemporaryDirectory(
        prefix="moradin-airgap-stage-",
        dir=destination.parent,
    ) as temporary:
        stage = Path(temporary) / "stage"
        shutil.copytree(template, stage)
        package_destination = stage / "os-packages"
        package_destination.mkdir()
        for source in sorted(packages.iterdir(), key=lambda item: item.name):
            if source.is_symlink() or not source.is_file():
                raise AirgapError("air-gap package closure contains an unsafe entry")
            shutil.copyfile(source, package_destination / source.name)
        trust_destination = stage / "trust"
        trust_destination.mkdir()
        for source in sorted(trust.iterdir(), key=lambda item: item.name):
            if source.is_symlink() or not source.is_file():
                raise AirgapError(
                    "air-gap repository trust closure contains an unsafe entry"
                )
            shutil.copyfile(source, trust_destination / source.name)
        write_json(stage / "plan.json", plan)
        (stage / "constraints.txt").write_text(
            _expected_constraints(plan),
            encoding="utf-8",
        )
        requirements = str(plan.get("python_tool_lock", {}).get("requirements", ""))
        requirements_path = stage / "requirements.lock"
        if requirements:
            requirements_path.write_text(requirements, encoding="utf-8")
        elif requirements_path.exists():
            requirements_path.unlink()
        included = [
            {
                "tool_id": tool_id,
                "kind": kind,
                "path": relative,
                "sha256": digest,
                "size": size,
            }
            for (tool_id, kind, relative), (digest, size) in sorted(
                _expected_stage_items(plan).items()
            )
        ]
        manifest: dict[str, Any] = {
            "version": 1,
            "plan_sha256": plan["plan_sha256"],
            "included": included,
        }
        manifest["manifest_sha256"] = suite_record_digest(
            manifest,
            "manifest_sha256",
        )
        write_json(stage / "stage-manifest.json", manifest)
        try:
            validate_staged_assets(stage, plan)
        except ToolingSuiteError as error:
            raise AirgapError(f"rebound air-gap stage is invalid: {error}") from error
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, destination)


def _tree_digest(root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(file_records(root)))


def _python_runtime_manifest(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise AirgapError("managed Python runtime root is unsafe")
    files: list[dict[str, Any]] = []
    for row in file_records(root):
        path = root / str(row["path"])
        files.append(
            {
                **row,
                "mode": 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644,
            }
        )
    candidates = [
        str(row["path"])
        for row in files
        if str(row["path"]).endswith("/bin/python3.12")
        and int(row["mode"]) == 0o755
    ]
    if len(candidates) != 1:
        raise AirgapError("managed Python runtime has an unexpected executable layout")
    manifest: dict[str, Any] = {
        "version": PYTHON_RUNTIME_MANIFEST_VERSION,
        "python_version": "3.12.8",
        "executable": candidates[0],
        "files": files,
    }
    manifest["manifest_sha256"] = _record_digest(manifest, "manifest_sha256")
    return manifest


def _validate_python_runtime_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "python_version",
        "executable",
        "files",
        "manifest_sha256",
    }:
        raise AirgapError("managed Python runtime manifest fields are malformed")
    if (
        payload.get("version") != PYTHON_RUNTIME_MANIFEST_VERSION
        or payload.get("python_version") != "3.12.8"
        or payload.get("manifest_sha256")
        != _record_digest(payload, "manifest_sha256")
    ):
        raise AirgapError("managed Python runtime manifest binding is invalid")
    executable = _safe_member_name(str(payload.get("executable", ""))).as_posix()
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise AirgapError("managed Python runtime manifest is empty")
    observed: list[str] = []
    executable_record: dict[str, Any] | None = None
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size", "mode"}:
            raise AirgapError("managed Python runtime file record is malformed")
        relative = _safe_member_name(str(row["path"])).as_posix()
        digest = _assert_digest(row["sha256"], label="managed Python file digest")
        size = int(row["size"])
        mode = int(row["mode"])
        if size < 0 or size > AIRGAP_MAX_FILE_BYTES or mode not in {0o644, 0o755}:
            raise AirgapError("managed Python runtime file metadata is unsafe")
        if relative in observed:
            raise AirgapError("managed Python runtime manifest contains duplicates")
        observed.append(relative)
        if relative == executable:
            executable_record = {
                "path": relative,
                "sha256": digest,
                "size": size,
                "mode": mode,
            }
    if observed != sorted(observed):
        raise AirgapError("managed Python runtime manifest is not canonical")
    if executable_record is None or executable_record["mode"] != 0o755:
        raise AirgapError("managed Python runtime executable is not bound")
    return payload


def _validate_python_runtime_tree(root: Path, manifest: dict[str, Any]) -> None:
    expected = {
        str(row["path"]): (
            str(row["sha256"]),
            int(row["size"]),
            int(row["mode"]),
        )
        for row in manifest["files"]
    }
    observed: dict[str, tuple[str, int, int]] = {}
    for row in file_records(root):
        path = root / str(row["path"])
        observed[str(row["path"])] = (
            str(row["sha256"]),
            int(row["size"]),
            0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644,
        )
    if observed != expected:
        raise AirgapError("managed Python runtime does not match its frozen manifest")


def _materialize_managed_python(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise AirgapError("managed Python source is unsafe")
    resolved_root = source.resolve(strict=True)
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            try:
                target = path.resolve(strict=True)
            except OSError as error:
                raise AirgapError("managed Python contains a broken link") from error
            if not target.is_relative_to(resolved_root):
                raise AirgapError("managed Python link escapes its runtime root")
        elif not path.is_dir() and not path.is_file():
            raise AirgapError("managed Python contains a special file")
    destination.mkdir()
    for current, directory_names, file_names in os.walk(
        source,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        relative = current_path.relative_to(source)
        destination_directory = destination / relative
        destination_directory.mkdir(parents=True, exist_ok=True)
        retained_directories: list[str] = []
        for name in sorted(directory_names):
            candidate = current_path / name
            if candidate.is_symlink():
                # uv adds a version-family directory alias. The canonical pinned
                # runtime is already copied, so retaining the alias would duplicate
                # the entire tree and create ambiguous executable paths.
                continue
            (destination_directory / name).mkdir(exist_ok=True)
            retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in sorted(file_names):
            candidate = current_path / name
            resolved = candidate.resolve(strict=True) if candidate.is_symlink() else candidate
            target = destination_directory / name
            shutil.copyfile(resolved, target)
            os.chmod(
                target,
                0o755 if resolved.stat().st_mode & stat.S_IXUSR else 0o644,
            )
    file_records(destination)


def _install_airgap_bootstrap(
    extracted: Path,
    lock: dict[str, Any],
) -> dict[str, Any]:
    data_root, _state_root, bin_root = _user_roots()
    bootstrap = lock.get("bootstrap", {})
    uv_record = bootstrap.get("uv", {})
    python_record = bootstrap.get("python", {})
    source_uv = extracted / "payload" / str(uv_record.get("path", ""))
    source_python = extracted / "payload" / str(python_record.get("path", ""))
    source_python_manifest = (
        extracted / "payload" / str(python_record.get("manifest_path", ""))
    )
    if (
        source_uv.is_symlink()
        or not source_uv.is_file()
        or sha256_file(source_uv) != uv_record.get("sha256")
        or source_python.is_symlink()
        or not source_python.is_file()
        or sha256_file(source_python) != python_record.get("sha256")
        or source_python_manifest.is_symlink()
        or not source_python_manifest.is_file()
        or source_python_manifest.stat().st_size
        != int(python_record.get("manifest_size", -1))
        or sha256_file(source_python_manifest)
        != python_record.get("manifest_sha256")
    ):
        raise AirgapError("air-gap bootstrap assets do not match the frozen lock")
    try:
        python_manifest = _validate_python_runtime_manifest(
            json.loads(source_python_manifest.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AirgapError("air-gap Python runtime manifest is invalid") from error
    if python_manifest["executable"] != python_record.get("executable"):
        raise AirgapError("air-gap Python executable binding does not match")
    uv_root = data_root / "bootstrap" / "uv" / str(uv_record["version"])
    uv_destination = uv_root / "uv"
    python_root = data_root / "bootstrap" / "python"
    runtime_digest = str(python_record["manifest_sha256"])
    python_generation = python_root / runtime_digest
    runtime_python = python_generation / str(python_manifest["executable"])
    record: dict[str, Any] = {
        "uv_relative": uv_destination.relative_to(data_root).as_posix(),
        "uv_sha256": str(uv_record["sha256"]),
        "uv_created": False,
        "uv_shim": "unchanged",
        "uv_shim_previous_relative": "",
        "python_created_directories": [],
        "runtime_uv_path": uv_destination.as_posix(),
        "runtime_python_source": python_generation.as_posix(),
        "runtime_python_manifest": source_python_manifest.as_posix(),
        "runtime_python_manifest_sha256": runtime_digest,
        "runtime_python_executable": str(python_manifest["executable"]),
    }
    try:
        if uv_destination.exists() or uv_destination.is_symlink():
            if (
                uv_destination.is_symlink()
                or not uv_destination.is_file()
                or sha256_file(uv_destination) != uv_record["sha256"]
            ):
                raise AirgapError("existing Forge uv bootstrap conflicts with the kit")
        else:
            uv_root.mkdir(parents=True, exist_ok=True)
            temporary_uv = uv_destination.with_suffix(".new")
            shutil.copyfile(source_uv, temporary_uv)
            os.chmod(temporary_uv, 0o755)
            os.replace(temporary_uv, uv_destination)
            record["uv_created"] = True

        python_root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="moradin-airgap-python-",
            dir=python_root.parent,
        ) as temporary:
            extracted_python = Path(temporary) / "python"
            safe_extract_bundle(source_python, extracted_python)
            _validate_python_runtime_tree(extracted_python, python_manifest)
            python_root.mkdir(parents=True, exist_ok=True)
            runtime_tree_digest = _tree_digest(extracted_python)
            if python_generation.exists() or python_generation.is_symlink():
                if (
                    python_generation.is_symlink()
                    or not python_generation.is_dir()
                    or _tree_digest(python_generation) != runtime_tree_digest
                ):
                    raise AirgapError(
                        "existing Forge managed Python conflicts with the kit"
                    )
                _validate_python_runtime_tree(python_generation, python_manifest)
            else:
                os.replace(extracted_python, python_generation)
                record["python_created_directories"].append(
                    {
                        "path": python_generation.relative_to(data_root).as_posix(),
                        "tree_sha256": runtime_tree_digest,
                    }
                )
        if (
            runtime_python.is_symlink()
            or not runtime_python.is_file()
            or not os.access(runtime_python, os.X_OK)
        ):
            raise AirgapError("installed managed Python executable is unavailable")

        bin_root.mkdir(parents=True, exist_ok=True)
        uv_shim = bin_root / "uv"
        owned_uv_root = (data_root / "bootstrap" / "uv").resolve()
        if uv_shim.is_symlink():
            current = uv_shim.resolve(strict=True)
            if not current.is_relative_to(owned_uv_root):
                raise AirgapError("refusing to replace an unowned uv shim")
            record["uv_shim_previous_relative"] = current.relative_to(
                data_root.resolve()
            ).as_posix()
            temporary_shim = uv_shim.with_name(".uv.moradin-airgap")
            temporary_shim.symlink_to(uv_destination)
            os.replace(temporary_shim, uv_shim)
            record["uv_shim"] = "updated"
        elif uv_shim.exists():
            raise AirgapError("refusing to replace an unowned uv command")
        else:
            temporary_shim = uv_shim.with_name(".uv.moradin-airgap")
            temporary_shim.symlink_to(uv_destination)
            os.replace(temporary_shim, uv_shim)
            record["uv_shim"] = "created"
        return record
    except Exception:
        _rollback_airgap_bootstrap(record)
        raise


def _rollback_airgap_bootstrap(record: dict[str, Any]) -> None:
    """Remove only unchanged bootstrap objects created by this transaction."""

    data_root, _state_root, bin_root = _user_roots()
    relative_uv = Path(str(record.get("uv_relative", "")))
    if relative_uv.is_absolute() or ".." in relative_uv.parts:
        raise AirgapError("air-gap bootstrap rollback metadata is unsafe")
    uv_destination = (data_root / relative_uv).resolve()
    if not uv_destination.is_relative_to(data_root.resolve()):
        raise AirgapError("air-gap bootstrap rollback escaped its prefix")
    uv_shim = bin_root / "uv"
    shim_status = str(record.get("uv_shim", ""))
    if shim_status in {"created", "updated"}:
        if uv_shim.is_symlink() and uv_shim.resolve() == uv_destination:
            previous_relative = Path(
                str(record.get("uv_shim_previous_relative", ""))
            )
            if shim_status == "updated" and str(previous_relative) not in {"", "."}:
                if previous_relative.is_absolute() or ".." in previous_relative.parts:
                    raise AirgapError("air-gap bootstrap predecessor is unsafe")
                previous = (data_root / previous_relative).resolve()
                if not previous.is_relative_to(
                    (data_root / "bootstrap" / "uv").resolve()
                ):
                    raise AirgapError("air-gap bootstrap predecessor is unowned")
                temporary = uv_shim.with_name(".uv.moradin-rollback")
                temporary.symlink_to(previous)
                os.replace(temporary, uv_shim)
            else:
                uv_shim.unlink()

    for row in reversed(list(record.get("python_created_directories", []))):
        if not isinstance(row, dict):
            raise AirgapError("air-gap Python rollback metadata is malformed")
        relative = Path(str(row.get("path", "")))
        destination = (data_root / relative).resolve()
        python_root = (data_root / "bootstrap" / "python").resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or destination.parent != python_root
        ):
            raise AirgapError("air-gap Python rollback path is unsafe")
        if (
            destination.is_dir()
            and not destination.is_symlink()
            and _tree_digest(destination) == row.get("tree_sha256")
        ):
            shutil.rmtree(destination)

    if (
        record.get("uv_created") is True
        and uv_destination.is_file()
        and not uv_destination.is_symlink()
        and sha256_file(uv_destination) == record.get("uv_sha256")
        and not (uv_shim.is_symlink() and uv_shim.resolve() == uv_destination)
    ):
        uv_destination.unlink()
        for parent in (uv_destination.parent, uv_destination.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                break


def _portable_bootstrap_receipt(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if not key.startswith("runtime_")
    }


def _airgap_receipt_path(bundle_sha256: str) -> Path:
    _data_root, state_root, _bin_root = _user_roots()
    return state_root / "airgap" / bundle_sha256 / "receipt.json"


def _verify_existing_airgap_apply(
    receipt_path: Path,
    *,
    bundle_sha256: str,
) -> dict[str, Any] | None:
    if not receipt_path.exists() and not receipt_path.is_symlink():
        return None
    receipt = _load_json_record(
        receipt_path,
        version="AirgapApplyReceiptV1",
        digest_field="receipt_sha256",
    )
    if receipt.get("bundle_sha256") != bundle_sha256:
        raise AirgapError("existing air-gap apply receipt is bound to another kit")
    try:
        suite = verify_suite_receipt(str(receipt["suite_receipt_id"]))
    except ToolingSuiteError as error:
        raise AirgapError(f"existing air-gap installation failed verification: {error}") from error
    if suite["status"] != "pass":
        raise AirgapError("existing air-gap installation no longer verifies")
    data_root, _state_root, _bin_root = _user_roots()
    uv_relative = Path(str(receipt["bootstrap"].get("uv_relative", "")))
    if uv_relative.is_absolute() or ".." in uv_relative.parts:
        raise AirgapError("existing air-gap bootstrap receipt is unsafe")
    uv = (data_root / uv_relative).resolve()
    if (
        uv.is_symlink()
        or not uv.is_file()
        or sha256_file(uv) != receipt["bootstrap"]["uv_sha256"]
    ):
        raise AirgapError("existing air-gap uv bootstrap no longer verifies")
    return {
        "version": AIRGAP_APPLY_VERSION,
        "status": "verified-existing",
        "mutated": False,
        "bundle_sha256": bundle_sha256,
        "suite_verification": suite,
    }


def apply_airgap_bundle(
    bundle: Path,
    *,
    approved_bundle_sha256: str,
    forge_root: Path,
    approved_plan_sha256: str = "",
    approved_stale_bundle_sha256: str = "",
) -> dict[str, Any]:
    bundle_sha = _assert_digest(
        approved_bundle_sha256,
        label="approved bundle digest",
    )
    verification = verify_airgap_bundle(bundle, expected_sha256=bundle_sha)
    if verification["stale"] and approved_stale_bundle_sha256 != bundle_sha:
        raise AirgapError(
            "kits older than 30 days require a second exact "
            "--approve-stale-bundle-sha256 approval"
        )
    receipt_path = _airgap_receipt_path(bundle_sha)
    existing = _verify_existing_airgap_apply(
        receipt_path,
        bundle_sha256=bundle_sha,
    )
    if existing is not None:
        return existing
    cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    extract_root = cache_base / "moradins-forge" / "airgap" / "kits" / bundle_sha
    if extract_root.exists() or extract_root.is_symlink():
        if extract_root.is_symlink() or not extract_root.is_dir():
            raise AirgapError("air-gap extraction cache is unsafe")
        extracted = verify_extracted_bundle(extract_root)
    else:
        extract_root.parent.mkdir(parents=True, exist_ok=True)
        safe_extract_bundle(bundle, extract_root)
        extracted = verify_extracted_bundle(extract_root)
    lock = extracted["lock"]
    plan = rebind_airgap_plan(
        lock,
        bundle_sha256=bundle_sha,
        forge_root=forge_root,
    )
    if approved_plan_sha256 and approved_plan_sha256 != plan["plan_sha256"]:
        raise AirgapError("approved offline plan digest does not match this target plan")
    if not approved_plan_sha256:
        raise AirgapError(
            "offline apply requires the displayed exact --approve-offline-plan-sha256 digest"
        )
    _data_root, state_root, _bin_root = _user_roots()
    plan_path = state_root / "airgap" / bundle_sha / "host-plan.json"
    if plan_path.exists() or plan_path.is_symlink():
        raise AirgapError("an unreceipted host-bound air-gap plan already exists")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(plan_path, plan)
    stage_root = (
        cache_base
        / "moradins-forge"
        / "tooling-suite"
        / str(plan["plan_sha256"])[:16]
    )
    bootstrap: dict[str, Any] = {}
    suite_receipt: dict[str, Any] = {}
    runtime_environment_names = (
        "MORADIN_FORGE_BOOTSTRAP_UV",
        "MORADIN_FORGE_ROOT_PYTHON_SOURCE",
        "MORADIN_FORGE_ROOT_PYTHON_MANIFEST",
        "MORADIN_FORGE_ROOT_PYTHON_MANIFEST_SHA256",
        "MORADIN_FORGE_ROOT_PYTHON_EXECUTABLE",
    )
    previous_runtime_environment = {
        name: os.environ.get(name) for name in runtime_environment_names
    }
    try:
        _build_rebound_stage(extract_root, plan, stage_root)
        bootstrap = _install_airgap_bootstrap(extract_root, lock)
        os.environ["MORADIN_FORGE_BOOTSTRAP_UV"] = str(
            bootstrap["runtime_uv_path"]
        )
        os.environ["MORADIN_FORGE_ROOT_PYTHON_SOURCE"] = str(
            bootstrap["runtime_python_source"]
        )
        os.environ["MORADIN_FORGE_ROOT_PYTHON_MANIFEST"] = str(
            bootstrap["runtime_python_manifest"]
        )
        os.environ["MORADIN_FORGE_ROOT_PYTHON_MANIFEST_SHA256"] = str(
            bootstrap["runtime_python_manifest_sha256"]
        )
        os.environ["MORADIN_FORGE_ROOT_PYTHON_EXECUTABLE"] = str(
            bootstrap["runtime_python_executable"]
        )
        suite_receipt = apply_suite_plan(
            plan_path,
            approved_sha256=str(plan["plan_sha256"]),
            forge_root=forge_root,
        )
        suite_receipt_id = Path(str(suite_receipt["receipt"])).parent.name
        suite_verification = verify_suite_receipt(suite_receipt_id)
        if suite_verification["status"] != "pass":
            raise AirgapError("post-install tooling-suite verification failed")
        receipt: dict[str, Any] = {
            "version": "AirgapApplyReceiptV1",
            "generated_at": utc_now(),
            "bundle_sha256": bundle_sha,
            "lock_sha256": lock["lock_sha256"],
            "plan_sha256": plan["plan_sha256"],
            "suite_receipt_id": suite_receipt_id,
            "suite_receipt_sha256": suite_receipt["receipt_sha256"],
            "bootstrap": _portable_bootstrap_receipt(bootstrap),
            "status": "pass",
            "privacy": (
                "Local receipt contains digests and Forge-owned installation state only; "
                "no workspace content, prompts, credentials, or telemetry."
            ),
        }
        receipt["receipt_sha256"] = _record_digest(receipt, "receipt_sha256")
        write_json(receipt_path, receipt)
        return {
            "version": AIRGAP_APPLY_VERSION,
            "status": "pass",
            "mutated": True,
            "bundle_sha256": bundle_sha,
            "lock_sha256": lock["lock_sha256"],
            "plan_sha256": plan["plan_sha256"],
            "receipt_sha256": receipt["receipt_sha256"],
            "suite_receipt": suite_receipt,
            "verification": suite_verification,
        }
    except Exception as apply_error:
        recovery_errors: list[str] = []
        if suite_receipt.get("receipt") and suite_receipt.get("receipt_sha256"):
            try:
                rollback_suite_receipt(
                    Path(str(suite_receipt["receipt"])).parent.name,
                    approved_sha256=str(suite_receipt["receipt_sha256"]),
                    forge_root=forge_root,
                )
            except Exception as error:  # preserve exact recovery evidence
                recovery_errors.append(f"suite rollback: {error}")
        if bootstrap:
            try:
                _rollback_airgap_bootstrap(bootstrap)
            except Exception as error:  # preserve exact recovery evidence
                recovery_errors.append(f"bootstrap rollback: {error}")
        if plan_path.is_file() and not receipt_path.exists():
            plan_path.unlink()
        if recovery_errors:
            raise AirgapError(
                "air-gap apply failed and automatic recovery was incomplete: "
                + "; ".join(recovery_errors)
            ) from apply_error
        raise
    finally:
        for name, previous in previous_runtime_environment.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


def preview_airgap_apply(
    bundle: Path,
    *,
    expected_sha256: str,
    forge_root: Path,
) -> dict[str, Any]:
    verification = verify_airgap_bundle(
        bundle,
        expected_sha256=expected_sha256,
    )
    with tempfile.TemporaryDirectory(prefix="moradin-airgap-preview-") as temporary:
        root = Path(temporary) / "kit"
        safe_extract_bundle(bundle, root)
        extracted = verify_extracted_bundle(root)
        plan = rebind_airgap_plan(
            extracted["lock"],
            bundle_sha256=verification["bundle_sha256"],
            forge_root=forge_root,
        )
    package_assets = plan.get("offline", {}).get("package_assets", [])
    additions = [
        asset["package"]
        for asset in package_assets
        if not asset.get("previous_version")
    ]
    upgrades = [
        asset["package"]
        for asset in package_assets
        if asset.get("previous_version")
        and asset.get("previous_version") != asset.get("version")
    ]
    return {
        "version": "AirgapApplyPreviewV1",
        "status": "ready",
        "bundle": verification,
        "plan": plan,
        "plan_sha256": plan["plan_sha256"],
        "package_additions": additions,
        "package_upgrades": upgrades,
        "disk_bytes": sum(int(asset.get("size", 0)) for asset in package_assets),
        "repository_actions": "offline-only; all configured online repositories disabled",
        "rollback": (
            "new closure-owned packages are removed explicitly; upgraded packages use "
            "the sealed prior package; no autoremove is used"
        ),
    }


def _git_output(
    forge_root: Path,
    argv: Sequence[str],
    *,
    check: bool = True,
) -> str:
    result = _run(["git", *argv], cwd=forge_root)
    if check and result.returncode != 0:
        raise AirgapError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def assert_clean_public_forge(forge_root: Path) -> str:
    head = _git_output(forge_root, ["rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise AirgapError("Forge source commit is malformed")
    if _git_output(forge_root, ["status", "--porcelain=v1"]):
        raise AirgapError("air-gap builds require a clean public Forge commit")
    remote = _git_output(
        forge_root,
        ["config", "--get", "remote.origin.url"],
        check=False,
    )
    normalized_remote = remote.removesuffix("/").removesuffix(".git")
    if normalized_remote != "https://github.com/frisco-deng/moradins-forge":
        raise AirgapError(
            "air-gap builds require the canonical public Forge HTTPS origin"
        )
    return head


def _safe_relative_file(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if relative.is_absolute() or ".." in relative.parts:
        raise AirgapError("air-gap payload escaped its root")
    return relative.as_posix()


def file_records(root: Path, *, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    excluded = set(exclude)
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = _safe_relative_file(path, root)
        if path.is_symlink():
            raise AirgapError(f"air-gap payload contains a symbolic link: {relative}")
        if path.is_file() and relative not in excluded:
            size = path.stat().st_size
            if size > AIRGAP_MAX_FILE_BYTES:
                raise AirgapError(f"air-gap payload file is too large: {relative}")
            records.append(
                {
                    "path": relative,
                    "sha256": sha256_file(path),
                    "size": size,
                }
            )
    return records


def _deterministic_tar_bytes(root: Path) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(root.rglob("*")):
            relative = _safe_relative_file(path, root)
            if path.is_symlink():
                raise AirgapError(f"refusing symbolic link in air-gap archive: {relative}")
            info = tarfile.TarInfo(relative + ("/" if path.is_dir() else ""))
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = AIRGAP_SOURCE_DATE_EPOCH
            if path.is_dir():
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.size = 0
                archive.addfile(info)
                continue
            if not path.is_file():
                raise AirgapError(f"unsupported air-gap payload entry: {relative}")
            info.type = tarfile.REGTYPE
            info.mode = 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644
            info.size = path.stat().st_size
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=output,
        mtime=0,
        compresslevel=9,
    ) as compressed:
        compressed.write(stream.getvalue())
    return output.getvalue()


def write_deterministic_tar(root: Path, output: Path) -> str:
    payload = _deterministic_tar_bytes(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.write_bytes(payload)
    os.replace(temporary, output)
    return sha256_file(output)


def _init_sanitized_git(export_root: Path) -> dict[str, str]:
    environment = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    }
    commands = [
        ["git", "init", "-b", "main"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Moradin Forge Public Export",
            "-c",
            "user.email=forge-export@example.invalid",
            "commit",
            "-m",
            "Sanitized Moradin Forge air-gap export",
        ],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=export_root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AirgapError(result.stderr.strip() or "sanitized Git export failed")
    commit = _git_output(export_root, ["rev-parse", "HEAD"])
    count = _git_output(export_root, ["rev-list", "--count", "HEAD"])
    if count != "1":
        raise AirgapError("sanitized Git export must contain exactly one commit")
    return {"commit": commit, "commit_count": count}


def build_sanitized_source(
    forge_root: Path,
    destination: Path,
) -> dict[str, Any]:
    export_root = destination / "public-export"
    export_root.mkdir(parents=True)
    copied = public_export.copy_public_tree(forge_root, export_root)
    public_export.write_public_workbench_stubs(export_root)
    hits = public_export.scan_tree(export_root)
    if hits:
        raise AirgapError(
            "sanitized public source failed the leak scan: "
            + ", ".join(sorted({hit.path for hit in hits})[:5])
        )
    git_result = _init_sanitized_git(export_root)
    bundle_path = destination / "moradins-forge-public.bundle"
    bundle_result = _run(
        ["git", "bundle", "create", bundle_path.as_posix(), "--all"],
        cwd=export_root,
    )
    if bundle_result.returncode != 0:
        raise AirgapError(bundle_result.stderr.strip() or "Git bundle creation failed")
    snapshot_root = destination / "source-snapshot"
    snapshot_root.mkdir()
    for child in sorted(export_root.iterdir(), key=lambda item: item.name):
        if child.name == ".git":
            continue
        destination_path = snapshot_root / child.name
        if child.is_dir():
            shutil.copytree(child, destination_path)
        else:
            shutil.copy2(child, destination_path)
    snapshot_path = destination / "moradins-forge-source.tar.gz"
    write_deterministic_tar(snapshot_root, snapshot_path)
    shutil.rmtree(snapshot_root)
    shutil.rmtree(export_root)
    return {
        "sanitized_commit": git_result["commit"],
        "git_bundle": {
            "path": bundle_path.name,
            "sha256": sha256_file(bundle_path),
            "size": bundle_path.stat().st_size,
        },
        "source_snapshot": {
            "path": snapshot_path.name,
            "sha256": sha256_file(snapshot_path),
            "size": snapshot_path.stat().st_size,
        },
        "copied_file_count": len(copied),
    }


def _safe_member_name(name: str) -> Path:
    if not name or "\x00" in name or "\\" in name:
        raise AirgapError("air-gap archive contains an unsafe member name")
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise AirgapError("air-gap archive contains traversal")
    return path


def safe_extract_bundle(bundle: Path, destination: Path) -> None:
    if bundle.is_symlink() or not bundle.is_file():
        raise AirgapError("air-gap bundle must be a regular file")
    destination.mkdir(parents=True, exist_ok=False)
    total = 0
    seen: set[str] = set()
    try:
        with tarfile.open(bundle, mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > AIRGAP_MAX_MEMBERS:
                raise AirgapError("air-gap archive contains too many members")
            for member in members:
                relative = _safe_member_name(member.name.rstrip("/"))
                normalized = relative.as_posix()
                if normalized in seen:
                    raise AirgapError("air-gap archive contains duplicate members")
                seen.add(normalized)
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise AirgapError("air-gap archive contains links or special files")
                if member.size < 0 or member.size > AIRGAP_MAX_FILE_BYTES:
                    raise AirgapError("air-gap archive member is too large")
                total += member.size
                if total > AIRGAP_MAX_TOTAL_BYTES:
                    raise AirgapError("air-gap archive exceeds the extraction limit")
                target = destination / relative
                resolved_parent = target.parent.resolve()
                if not resolved_parent.is_relative_to(destination.resolve()):
                    raise AirgapError("air-gap extraction escaped its destination")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    os.chmod(target, 0o755)
                    continue
                if not member.isfile():
                    raise AirgapError("air-gap archive contains an unsupported entry")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    raise AirgapError("air-gap extraction would replace a path")
                source = archive.extractfile(member)
                if source is None:
                    raise AirgapError("air-gap archive member could not be read")
                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                with os.fdopen(descriptor, "wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                os.chmod(target, 0o755 if member.mode & 0o111 else 0o644)
    except Exception:
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        raise


def _parse_sha256sums(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise AirgapError("air-gap bundle is missing SHA256SUMS")
    records: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        _assert_digest(digest, label="SHA256SUMS entry")
        safe = _safe_member_name(relative).as_posix()
        if not separator or safe == "SHA256SUMS" or safe in records:
            raise AirgapError("air-gap SHA256SUMS is malformed")
        records[safe] = digest
    return records


def verify_extracted_bundle(root: Path) -> dict[str, Any]:
    sums = _parse_sha256sums(root / "SHA256SUMS")
    observed = {
        record["path"]: record["sha256"]
        for record in file_records(root, exclude={"SHA256SUMS"})
    }
    if observed != sums:
        raise AirgapError("air-gap bundle files do not exactly match SHA256SUMS")
    manifest = _load_json_record(
        root / "airgap-manifest.json",
        version=AIRGAP_BUNDLE_VERSION,
        digest_field="manifest_sha256",
    )
    lock = _load_json_record(
        root / "AIRGAP-LOCK.json",
        version=AIRGAP_LOCK_VERSION,
        digest_field="lock_sha256",
    )
    if manifest.get("lock_sha256") != lock["lock_sha256"]:
        raise AirgapError("air-gap manifest is not bound to its lock")
    source = lock.get("source", {})
    for key in ("git_bundle", "source_snapshot"):
        row = source.get(key, {})
        path = root / "forge" / str(row.get("path", ""))
        if (
            not path.is_file()
            or path.is_symlink()
            or sha256_file(path) != row.get("sha256")
            or path.stat().st_size != row.get("size")
        ):
            raise AirgapError(f"air-gap {key} does not match the frozen lock")
    if shutil.which("git"):
        result = _run(["git", "bundle", "verify", (root / "forge" / source["git_bundle"]["path"]).as_posix()])
        if result.returncode != 0:
            raise AirgapError("sanitized Forge Git bundle verification failed")
    return {"manifest": manifest, "lock": lock, "file_count": len(observed)}


def verify_airgap_bundle(
    bundle: Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    expected = _assert_digest(expected_sha256, label="expected bundle digest")
    actual = sha256_file(bundle)
    if actual != expected:
        raise AirgapError("air-gap bundle digest does not match the out-of-band digest")
    with tempfile.TemporaryDirectory(prefix="moradin-airgap-verify-") as temporary:
        root = Path(temporary) / "kit"
        safe_extract_bundle(bundle, root)
        verified = verify_extracted_bundle(root)
    lock = verified["lock"]
    created = datetime.fromisoformat(str(lock["created_at"]))
    if created.tzinfo is None:
        raise AirgapError("air-gap lock creation time is malformed")
    age_days = max(0, (datetime.now(tz=UTC) - created).days)
    return {
        "version": AIRGAP_VERIFY_VERSION,
        "status": "pass",
        "bundle_sha256": actual,
        "lock_sha256": lock["lock_sha256"],
        "target": lock["target"],
        "profile": lock["profile"],
        "complete": lock.get("status") == "complete",
        "age_days": age_days,
        "stale": datetime.now(tz=UTC) - created > AIRGAP_MAX_AGE,
        "file_count": verified["file_count"],
    }


def write_sha256sums(root: Path) -> None:
    records = file_records(root, exclude={"SHA256SUMS"})
    (root / "SHA256SUMS").write_text(
        "".join(f"{row['sha256']}  {row['path']}\n" for row in records),
        encoding="utf-8",
    )


def build_spdx(root: Path, *, source_sha: str) -> dict[str, Any]:
    files = file_records(
        root,
        exclude={"SHA256SUMS", "airgap.spdx.json"},
    )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "Moradin Forge air-gap kit",
        "documentNamespace": f"https://github.com/frisco-deng/moradins-forge/airgap/{source_sha}",
        "creationInfo": {
            "created": "2000-01-01T00:00:00Z",
            "creators": ["Tool: Moradin-Forge-Airgap-V1"],
        },
        "files": [
            {
                "fileName": f"./{row['path']}",
                "SPDXID": f"SPDXRef-File-{index}",
                "checksums": [
                    {"algorithm": "SHA256", "checksumValue": row["sha256"]}
                ],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
            for index, row in enumerate(files, start=1)
        ],
    }


def download_locked_asset(url: str, destination: Path, digest: str, size: int) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise AirgapError("frozen asset URL must use credential-free HTTPS")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "moradins-forge-airgap/0.2.0-beta.3"},
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or not final.hostname:
            raise AirgapError("frozen asset redirected outside HTTPS")
        shutil.copyfileobj(response, output, length=1024 * 1024)
    if destination.stat().st_size != size or sha256_file(destination) != digest:
        destination.unlink(missing_ok=True)
        raise AirgapError("downloaded frozen asset failed size or digest verification")


def airgap_readme(lock: dict[str, Any]) -> str:
    target = lock["target"]
    return "\n".join(
        [
            "# Moradin Forge Air-Gap Kit",
            "",
            f"- Target: `{target['os_id']} {target['version_id']} / {target['arch']}`",
            f"- Profile: `{lock['profile']}`",
            f"- Lock SHA-256: `{lock['lock_sha256']}`",
            "- Status: `complete`",
            "",
            "Transport the kit and its SHA-256 digest through separate trusted channels.",
            "A root-owned Python 3.9+ can verify and launch the sealed Python 3.12.8 runtime.",
            "On the disconnected target, run:",
            "",
            "```sh",
            "./install/tooling-suite.sh airgap-verify --bundle <kit.tar.gz> --expected-sha256 <sha256>",
            "./install/tooling-suite.sh airgap-apply --bundle <kit.tar.gz> --approve-bundle-sha256 <sha256>",
            "scripts/moradin_forge.sh onboard --workspace <approved-workspace> --offline",
            "```",
            "",
            "The apply path rejects network URLs, incompatible targets, package-state drift,",
            "unsafe archives, and stale kits without a second exact digest approval.",
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moradin Forge air-gap kit engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    container = subparsers.add_parser("_container-build", help=argparse.SUPPRESS)
    container.add_argument("--request", type=Path, required=True)
    container.add_argument("--output", type=Path, required=True)
    container.add_argument("--forge-root", type=Path, default=REPO_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "_container-build":
            payload = build_target_payload(
                args.request,
                output=args.output,
                forge_root=args.forge_root,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
    except AirgapError as error:
        print(f"moradin-airgap: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())
