#!/usr/bin/env python3
"""Python 3.9-compatible launcher for sealed offline verify/apply operations."""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path


LOCK_VERSION = "AirgapLockV1"
RUNTIME_MANIFEST_VERSION = "MoradinForgePythonRuntimeManifestV1"
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
MAX_MEMBERS = 100000
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
HEX64 = re.compile(r"[0-9a-f]{64}")


class BootstrapError(RuntimeError):
    """Raised when a transferred runtime cannot be trusted."""


def canonical_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def record_digest(payload, field):
    return hashlib.sha256(
        canonical_bytes({key: value for key, value in payload.items() if key != field})
    ).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(value):
    if not value or "\\" in value or "\x00" in value:
        raise BootstrapError("air-gap archive contains an unsafe path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise BootstrapError("air-gap archive contains traversal")
    return relative


def parse_sums(payload):
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise BootstrapError("air-gap SHA256SUMS is invalid") from error
    result = {}
    for line in lines:
        digest, separator, relative = line.partition("  ")
        path = safe_relative(relative).as_posix()
        if (
            not separator
            or not HEX64.fullmatch(digest)
            or path == "SHA256SUMS"
            or path in result
        ):
            raise BootstrapError("air-gap SHA256SUMS is malformed")
        result[path] = digest
    return result


def read_member(archive, member, limit):
    if not member.isfile() or member.size < 0 or member.size > limit:
        raise BootstrapError("air-gap bootstrap member is unsafe")
    source = archive.extractfile(member)
    if source is None:
        raise BootstrapError("air-gap bootstrap member cannot be read")
    payload = source.read(limit + 1)
    if len(payload) != member.size or len(payload) > limit:
        raise BootstrapError("air-gap bootstrap member changed while reading")
    return payload


def inspect_outer_bundle(bundle, expected_digest, staging):
    if bundle.is_symlink() or not bundle.is_file():
        raise BootstrapError("air-gap bundle must be a regular file")
    if not HEX64.fullmatch(expected_digest) or sha256_file(bundle) != expected_digest:
        raise BootstrapError("air-gap bundle does not match its out-of-band digest")
    required = {
        "AIRGAP-LOCK.json",
        "SHA256SUMS",
        "payload/bootstrap/python-3.12.8.tar.gz",
        "payload/bootstrap/python-3.12.8.manifest.json",
    }
    selected = {}
    total = 0
    seen = set()
    try:
        archive = tarfile.open(bundle, mode="r:gz")
    except (OSError, tarfile.TarError) as error:
        raise BootstrapError("air-gap bundle cannot be opened") from error
    with archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS:
            raise BootstrapError("air-gap bundle contains too many members")
        for member in members:
            name = safe_relative(member.name.rstrip("/")).as_posix()
            if name in seen:
                raise BootstrapError("air-gap bundle contains duplicate members")
            seen.add(name)
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise BootstrapError("air-gap bundle contains links or special files")
            if member.size < 0 or member.size > MAX_FILE_BYTES:
                raise BootstrapError("air-gap bundle member exceeds the safety limit")
            total += member.size
            if total > MAX_TOTAL_BYTES:
                raise BootstrapError("air-gap bundle exceeds the extraction limit")
            if name in required:
                selected[name] = member
        if set(selected) != required:
            raise BootstrapError("air-gap bundle lacks its managed Python closure")
        lock_bytes = read_member(archive, selected["AIRGAP-LOCK.json"], 16 * 1024 * 1024)
        sums_bytes = read_member(archive, selected["SHA256SUMS"], 16 * 1024 * 1024)
        manifest_bytes = read_member(
            archive,
            selected["payload/bootstrap/python-3.12.8.manifest.json"],
            16 * 1024 * 1024,
        )
        archive_member = selected["payload/bootstrap/python-3.12.8.tar.gz"]
        runtime_archive = staging / "python-runtime.tar.gz"
        source = archive.extractfile(archive_member)
        if source is None:
            raise BootstrapError("managed Python archive cannot be read")
        digest = hashlib.sha256()
        copied = 0
        with runtime_archive.open("xb") as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > MAX_FILE_BYTES:
                    raise BootstrapError("managed Python archive exceeds the safety limit")
                digest.update(chunk)
                output.write(chunk)
        if copied != archive_member.size:
            raise BootstrapError("managed Python archive changed while reading")
    sums = parse_sums(sums_bytes)
    calculated = {
        "AIRGAP-LOCK.json": hashlib.sha256(lock_bytes).hexdigest(),
        "payload/bootstrap/python-3.12.8.manifest.json": hashlib.sha256(
            manifest_bytes
        ).hexdigest(),
        "payload/bootstrap/python-3.12.8.tar.gz": digest.hexdigest(),
    }
    for name, observed in calculated.items():
        if sums.get(name) != observed:
            raise BootstrapError("air-gap bootstrap member fails SHA256SUMS")
    try:
        lock = json.loads(lock_bytes)
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BootstrapError("air-gap bootstrap records are invalid") from error
    if (
        not isinstance(lock, dict)
        or lock.get("version") != LOCK_VERSION
        or lock.get("lock_sha256") != record_digest(lock, "lock_sha256")
    ):
        raise BootstrapError("air-gap lock binding is invalid")
    python_record = lock.get("bootstrap", {}).get("python", {})
    try:
        archive_size = int(python_record.get("size", -1))
        manifest_size = int(python_record.get("manifest_size", -1))
    except (AttributeError, TypeError, ValueError) as error:
        raise BootstrapError("air-gap lock Python sizes are malformed") from error
    if (
        not isinstance(python_record, dict)
        or python_record.get("path") != "bootstrap/python-3.12.8.tar.gz"
        or python_record.get("manifest_path")
        != "bootstrap/python-3.12.8.manifest.json"
        or python_record.get("sha256")
        != calculated["payload/bootstrap/python-3.12.8.tar.gz"]
        or python_record.get("manifest_sha256")
        != calculated["payload/bootstrap/python-3.12.8.manifest.json"]
        or archive_size != copied
        or manifest_size != len(manifest_bytes)
    ):
        raise BootstrapError("air-gap lock does not bind the managed Python closure")
    return runtime_archive, manifest, python_record


def validate_manifest(manifest, python_record):
    if not isinstance(manifest, dict) or set(manifest) != {
        "version",
        "python_version",
        "executable",
        "files",
        "manifest_sha256",
    }:
        raise BootstrapError("managed Python manifest fields are malformed")
    if (
        manifest.get("version") != RUNTIME_MANIFEST_VERSION
        or manifest.get("python_version") != "3.12.8"
        or manifest.get("manifest_sha256") != record_digest(manifest, "manifest_sha256")
        or manifest.get("executable") != python_record.get("executable")
    ):
        raise BootstrapError("managed Python manifest binding is invalid")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise BootstrapError("managed Python manifest is empty")
    seen = []
    executable = safe_relative(str(manifest["executable"])).as_posix()
    executable_bound = False
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size", "mode"}:
            raise BootstrapError("managed Python file record is malformed")
        relative = safe_relative(str(row["path"])).as_posix()
        if (
            relative in seen
            or not HEX64.fullmatch(str(row["sha256"]))
            or not isinstance(row["size"], int)
            or row["size"] < 0
            or row["size"] > MAX_FILE_BYTES
            or row["mode"] not in {0o644, 0o755}
        ):
            raise BootstrapError("managed Python file metadata is unsafe")
        seen.append(relative)
        if relative == executable and row["mode"] == 0o755:
            executable_bound = True
    if seen != sorted(seen) or not executable_bound:
        raise BootstrapError("managed Python manifest ordering or executable is invalid")
    return executable


def extract_runtime(archive_path, destination, manifest):
    expected = {str(row["path"]): row for row in manifest["files"]}
    seen = set()
    total = 0
    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (OSError, tarfile.TarError) as error:
        raise BootstrapError("managed Python archive cannot be opened") from error
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with archive:
            members = archive.getmembers()
            if len(members) > MAX_MEMBERS:
                raise BootstrapError("managed Python archive has too many members")
            for member in members:
                relative = safe_relative(member.name.rstrip("/")).as_posix()
                if relative in seen:
                    raise BootstrapError("managed Python archive has duplicate members")
                seen.add(relative)
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise BootstrapError("managed Python archive contains links")
                target = destination / relative
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    os.chmod(target, stat.S_IRWXU)
                    continue
                row = expected.get(relative)
                if not member.isfile() or row is None or member.size != row["size"]:
                    raise BootstrapError("managed Python archive differs from its manifest")
                total += member.size
                if total > MAX_TOTAL_BYTES:
                    raise BootstrapError("managed Python archive exceeds the extraction limit")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise BootstrapError("managed Python member cannot be read")
                digest = hashlib.sha256()
                size = 0
                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    int(row["mode"]),
                )
                with os.fdopen(descriptor, "wb") as output:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                        output.write(chunk)
                if size != row["size"] or digest.hexdigest() != row["sha256"]:
                    raise BootstrapError("managed Python member digest mismatch")
                os.chmod(target, int(row["mode"]))
        files = {
            path.relative_to(destination).as_posix()
            for path in destination.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        if files != set(expected):
            raise BootstrapError("managed Python runtime closure is incomplete")
    except Exception:
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        raise


def runtime_for_bundle(bundle, expected_digest):
    cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_root = cache_base / "moradins-forge/airgap/bootstrap-runtime"
    cache_root.mkdir(parents=True, exist_ok=True)
    destination = cache_root / expected_digest
    with tempfile.TemporaryDirectory(prefix=".bootstrap-", dir=cache_root) as temporary:
        staging = Path(temporary)
        runtime_archive, manifest, python_record = inspect_outer_bundle(
            bundle, expected_digest, staging
        )
        executable = validate_manifest(manifest, python_record)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise BootstrapError("managed Python cache is unsafe")
            verify = staging / "verify"
            extract_runtime(runtime_archive, verify, manifest)
            if sha256_tree(verify) != sha256_tree(destination):
                raise BootstrapError("managed Python cache conflicts with the kit")
        else:
            extracted = staging / "runtime"
            extract_runtime(runtime_archive, extracted, manifest)
            os.replace(extracted, destination)
    runtime = destination / executable
    if runtime.is_symlink() or not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise BootstrapError("managed Python executable is unavailable")
    return runtime


def sha256_tree(root):
    rows = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise BootstrapError("managed Python cache contains a link")
        if path.is_file():
            rows.append(
                {
                    "path": relative,
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                    "mode": 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644,
                }
            )
        elif not path.is_dir():
            raise BootstrapError("managed Python cache contains a special file")
    return hashlib.sha256(canonical_bytes(rows)).hexdigest()


def parser():
    result = argparse.ArgumentParser(
        description="Bootstrap sealed Moradin Forge air-gap verification and apply"
    )
    result.add_argument("--forge-root", type=Path, required=True)
    result.add_argument("--json", action="store_true")
    subparsers = result.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("airgap-verify")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--expected-sha256", required=True)
    apply = subparsers.add_parser("airgap-apply")
    apply.add_argument("--bundle", type=Path, required=True)
    apply.add_argument("--approve-bundle-sha256", required=True)
    apply.add_argument("--approve-offline-plan-sha256")
    apply.add_argument("--approve-stale-bundle-sha256")
    return result


def main(argv=None):
    os.umask(0o077)
    original = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(original)
    expected = (
        args.expected_sha256
        if args.command == "airgap-verify"
        else args.approve_bundle_sha256
    )
    try:
        runtime = runtime_for_bundle(args.bundle.resolve(), expected)
    except BootstrapError as error:
        print("air-gap bootstrap failed closed: " + str(error), file=sys.stderr)
        return 2
    forge_root = args.forge_root.resolve()
    main_script = forge_root / "scripts/moradin_tooling_suite.py"
    if main_script.is_symlink() or not main_script.is_file():
        print("air-gap bootstrap failed closed: Forge entrypoint is unsafe", file=sys.stderr)
        return 2
    environment = {
        "PATH": str(Path.home() / ".local/bin") + os.pathsep + SAFE_PATH,
        "HOME": str(Path.home()),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    for name in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        if os.environ.get(name):
            environment[name] = os.environ[name]
    os.execve(
        runtime,
        [runtime.as_posix(), main_script.as_posix(), *original],
        environment,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
