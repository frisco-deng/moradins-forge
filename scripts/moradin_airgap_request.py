#!/usr/bin/env python3
"""Python 3.9-compatible, disconnected AirgapRequestV1 generator."""

from __future__ import print_function

import argparse
import ast
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


SUPPORTED_TARGETS = {
    ("ubuntu", "24.04"): "apt",
    ("debian", "12"): "apt",
    ("fedora", "44"): "dnf",
    ("rocky", "9"): "dnf",
    ("arch", "rolling"): "pacman",
}
INSTALLER_FILES = (
    "install/tooling-suite.sh",
    "install/airgap-container-build.sh",
    "scripts/moradin_airgap_request.py",
    "scripts/moradin_airgap_bootstrap.py",
    "scripts/moradin_airgap.py",
    "scripts/moradin_tooling_suite.py",
    "scripts/moradin_workstation.py",
    "catalog/workstation-tools.toml",
)
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
PACKAGE_RE = re.compile(r"[A-Za-z0-9@._+:-]+")


class RequestError(RuntimeError):
    """Raised when a disconnected request cannot be generated safely."""


def canonical_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(argv):
    return subprocess.run(
        argv,
        env={"PATH": SAFE_PATH, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=300,
    )


def parse_os_release():
    values = {}
    try:
        lines = Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RequestError("/etc/os-release is unavailable") from error
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value.strip().strip('"')
    return values


def target_facts():
    release = parse_os_release()
    os_id = release.get("ID", "").lower()
    version = release.get("VERSION_ID", "")
    if os_id in {"rockylinux", "rhel", "almalinux"}:
        os_id = "rocky"
    if os_id == "arch":
        version = "rolling"
    if os_id == "rocky":
        version = version.split(".", 1)[0]
    machine = platform.machine().lower()
    arch = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine, "")
    manager = SUPPORTED_TARGETS.get((os_id, version), "")
    if not manager or not arch:
        raise RequestError(
            "supported targets are Ubuntu 24.04, Debian 12, Fedora 44, "
            "Rocky Linux 9, and Arch on amd64 or arm64"
        )
    return {
        "system": "linux",
        "os_id": os_id,
        "version_id": version,
        "package_manager": manager,
        "arch": arch,
    }


def parse_value(value):
    value = value.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError) as error:
        raise RequestError("workstation catalog contains unsupported TOML") from error


def load_catalog(path):
    if path.is_symlink() or not path.is_file():
        raise RequestError("workstation catalog must be a regular file")
    tools = []
    current = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[tools]]":
            if current is not None:
                tools.append(current)
            current = {}
            continue
        if current is None:
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise RequestError("workstation catalog contains malformed data")
        current[key.strip()] = parse_value(value)
    if current is not None:
        tools.append(current)
    ids = [str(tool.get("id", "")) for tool in tools]
    if not tools or len(ids) != len(set(ids)) or any(
        not re.fullmatch(r"[a-z][a-z0-9_]*", tool_id) for tool_id in ids
    ):
        raise RequestError("workstation catalog tool identifiers are malformed")
    return tools


def selected_tools(catalog, profile, excluded, requested_engine):
    by_id = {tool["id"]: tool for tool in catalog}
    unknown = sorted(set(excluded) - set(by_id))
    if unknown:
        raise RequestError("unknown tooling ids: " + ", ".join(unknown))
    existing = ""
    engine = ""
    if profile == "practical":
        selected = {
            tool["id"] for tool in catalog if "practical" in tool.get("profiles", [])
        }
    else:
        existing = next(
            (candidate for candidate in ("podman", "docker") if shutil.which(candidate)),
            "",
        )
        engine = requested_engine or existing or "podman"
        if engine not in {"podman", "docker"}:
            raise RequestError("extended requests require podman or docker")
        if existing and engine != existing:
            raise RequestError("the existing container engine must be preserved")
        selected = {
            tool["id"]
            for tool in catalog
            if set(tool.get("profiles", [])).intersection({"practical", "extended"})
        }
        selected.difference_update({"podman", "docker"})
        selected.add(engine)
        if engine == "podman" and not existing:
            selected.update(
                {"rootless_uidmap", "rootless_network", "rootless_storage"}
            )
    selected.difference_update(excluded)
    rows = sorted(
        (by_id[tool_id] for tool_id in selected),
        key=lambda tool: (str(tool.get("category", "")), str(tool["id"])),
    )
    manual = sorted(
        str(tool["id"])
        for tool in rows
        if tool.get("manual_only") is True and tool["id"] != existing
    )
    if manual:
        raise RequestError(
            "manual-only selections must be explicitly excluded: "
            + ", ".join(manual)
        )
    return rows, engine, existing


def installed_version(package, manager):
    commands = {
        "apt": ["dpkg-query", "-W", "-f=${Status}\t${Version}", "--", package],
        "dnf": ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", "--", package],
        "pacman": ["pacman", "-Q", "--", package],
    }
    result = run(commands[manager])
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


def installed_inventory(manager):
    commands = {
        "apt": ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"],
        "dnf": ["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"],
        "pacman": ["pacman", "-Q"],
    }
    result = run(commands[manager])
    if result.returncode != 0:
        raise RequestError("installed package inventory could not be read")
    packages = {}
    for line in result.stdout.splitlines():
        if manager == "pacman":
            package, separator, version = line.partition(" ")
        else:
            package, separator, version = line.partition("\t")
            package = package.split(":", 1)[0]
        if not separator or not PACKAGE_RE.fullmatch(package) or not version:
            raise RequestError("installed package inventory is malformed")
        packages[package] = version
    return [
        {"package": package, "version": packages[package]}
        for package in sorted(packages)
    ]


def installer_digest(forge_root):
    manifest = {}
    for relative in INSTALLER_FILES:
        path = forge_root / relative
        if path.is_symlink() or not path.is_file():
            raise RequestError("installer file must be regular: " + relative)
        manifest[relative] = sha256_file(path)
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def build_request(args):
    forge_root = args.forge_root.resolve()
    catalog_path = forge_root / "catalog/workstation-tools.toml"
    catalog = load_catalog(catalog_path)
    target = target_facts()
    tools, engine, existing_engine = selected_tools(
        catalog, args.profile, args.exclude, args.container_engine
    )
    if set(args.approve_repository) - {"epel"}:
        raise RequestError("only EPEL repository approval is supported")
    if args.approve_repository and target["os_id"] != "rocky":
        raise RequestError("EPEL approval applies only to Rocky Linux 9")
    if target["package_manager"] == "pacman":
        if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", args.arch_snapshot):
            raise RequestError("Arch requests require --arch-snapshot YYYY/MM/DD")
        if not args.approve_arch_package_inventory:
            raise RequestError(
                "Arch requests require --approve-arch-package-inventory"
            )
    elif args.arch_snapshot or args.approve_arch_package_inventory:
        raise RequestError("Arch-only options are not valid for this target")
    manager = target["package_manager"]
    package_key = {"apt": "apt_package", "dnf": "dnf_package", "pacman": "pacman_package"}[manager]
    direct_packages = sorted(
        {str(tool.get(package_key, "")) for tool in tools if tool.get(package_key)}
    )
    installed = []
    for package in direct_packages:
        version = installed_version(package, manager)
        if version:
            installed.append({"package": package, "version": version})
    inventory = installed_inventory(manager)
    payload = {
        "version": "AirgapRequestV1",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).replace(microsecond=0).isoformat(),
        "profile": args.profile,
        "selected_tools": [str(tool["id"]) for tool in tools],
        "explicitly_excluded_tools": sorted(set(args.exclude)),
        "container_engine": engine,
        "existing_container_engine": existing_engine,
        "target": target,
        "installed_packages": installed,
        "installed_package_inventory": inventory,
        "approved_repositories": sorted(set(args.approve_repository)),
        "arch_snapshot": args.arch_snapshot,
        "arch_package_inventory": inventory if manager == "pacman" else [],
        "catalog_sha256": sha256_file(catalog_path),
        "installer_manifest_sha256": installer_digest(forge_root),
        "privacy": (
            "Contains selected tooling and relevant package state only; no workspace "
            "contents, hostnames, machine identifiers, credentials, prompts, or paths."
        ),
    }
    payload["request_sha256"] = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    output = args.output
    if output.exists() or output.is_symlink():
        raise RequestError("request output already exists: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def parser():
    result = argparse.ArgumentParser(
        description="Generate a sanitized Moradin Forge air-gap request"
    )
    result.add_argument("--forge-root", type=Path, required=True)
    result.add_argument("--json", action="store_true")
    subparsers = result.add_subparsers(dest="command", required=True)
    request = subparsers.add_parser("airgap-request")
    request.add_argument("--profile", choices=("practical", "extended"), required=True)
    request.add_argument("--output", type=Path, required=True)
    request.add_argument("--exclude", action="append", default=[])
    request.add_argument("--container-engine", choices=("podman", "docker"), default="")
    request.add_argument("--approve-repository", choices=("epel",), action="append", default=[])
    request.add_argument("--arch-snapshot", default="")
    request.add_argument("--approve-arch-package-inventory", action="store_true")
    return result


def main(argv=None):
    os.umask(0o077)
    args = parser().parse_args(argv)
    try:
        payload = build_request(args)
    except RequestError as error:
        print("air-gap request failed closed: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
