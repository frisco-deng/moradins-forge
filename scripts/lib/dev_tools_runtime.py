"""Exact Node/npm acquisition and bounded UI dependency locks."""

from pathlib import Path
from contextlib import contextmanager
import hashlib
import base64
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dev_tools_catalog import sha


def environment(node, cache):
    # No inherited credentials, npm config, loader options or browser sessions.
    return {
        "HOME": str(Path.home()),
        "PATH": str(Path(node).parent) + ":/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PLAYWRIGHT_BROWSERS_PATH": str(cache),
        "NPM_CONFIG_USERCONFIG": str(Path(cache).parent / "npm-userconfig"),
        "NPM_CONFIG_GLOBALCONFIG": str(Path(cache).parent / "npm-globalconfig"),
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/",
        "NPM_CONFIG_IGNORE_SCRIPTS": "true",
    }


def npm_configs(env):
    for key in ["NPM_CONFIG_USERCONFIG", "NPM_CONFIG_GLOBALCONFIG"]:
        path = Path(env[key])
        if path.is_symlink() or (path.exists() and path.read_bytes()):
            raise ValueError("npm_configuration_conflict")
        if not path.exists():
            with path.open("x") as stream:
                stream.write("")
            path.chmod(0o600)


def run(argv, cwd, env, *, timeout=900, log=None):
    result = subprocess.run(
        [str(x) for x in argv],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if log:
        Path(log).write_text((result.stdout + "\n" + result.stderr)[-100000:])
        Path(log).chmod(0o600)
    if result.returncode:
        raise ValueError(
            "ui_command_failed:"
            + Path(str(argv[0])).name
            + ":"
            + str(result.returncode)
        )
    return result


def validate_lock(lock, expected):
    if (
        lock.get("lockfileVersion") != 3
        or lock.get("packages", {}).get("", {}).get("dependencies") != expected
    ):
        raise ValueError("ui_lock_direct_requirements_mismatch")
    for name, row in lock["packages"].items():
        if not name:
            continue
        integrity = row.get("integrity", "")
        try:
            encoded = integrity.removeprefix("sha512-")
            decoded = base64.b64decode(encoded, validate=True)
            valid_integrity = (
                integrity.startswith("sha512-")
                and len(decoded) == 64
                and base64.b64encode(decoded).decode() == encoded
            )
        except (ValueError, TypeError):
            valid_integrity = False
        if (
            not row.get("resolved", "").startswith("https://registry.npmjs.org/")
            or not valid_integrity
            or row.get("link")
        ):
            raise ValueError("ui_lock_unverified_asset:" + name)


def node_archive(asset, destination):
    destination = Path(destination)
    if destination.exists():
        if destination.is_symlink() or sha(destination) != asset["sha256"]:
            raise ValueError("node_staged_asset_drift")
        return destination
    cached = Path(asset.get("cache_path", destination))
    if cached.exists() and cached != destination:
        if cached.is_symlink() or sha(cached) != asset["sha256"]:
            raise ValueError("node_staged_asset_drift")
        shutil.copyfile(cached, destination)
        return destination
    match = re.fullmatch(
        r"node-v([0-9]+\.[0-9]+\.[0-9]+)-linux-(x64|arm64)\.tar\.xz", asset["archive"]
    )
    if (
        not match
        or asset["url"]
        != "https://nodejs.org/dist/v" + match[1] + "/" + asset["archive"]
    ):
        raise ValueError("node_asset_source_mismatch")
    with node_https(match[1], asset["archive"]) as response:
        with destination.open("xb") as stream:
            shutil.copyfileobj(response, stream)
    if sha(destination) != asset["sha256"]:
        raise ValueError("node_asset_hash_mismatch")
    return destination


@contextmanager
def node_https(version, filename):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or filename not in (
        "SHASUMS256.txt",
        "node-v" + version + "-linux-x64.tar.xz",
        "node-v" + version + "-linux-arm64.tar.xz",
    ):
        raise ValueError("node_https_path_not_declared")
    # Match Forge's native curl transport. No redirects, user curl config,
    # inherited credentials or arbitrary schemes/hosts enter this request.
    with tempfile.NamedTemporaryFile(prefix="forge-node-https-") as response:
        result = subprocess.run(
            [
                "/usr/bin/curl",
                "--disable",
                "--proto",
                "=https",
                "--tlsv1.2",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "60",
                "--max-filesize",
                "209715200",
                "--output",
                response.name,
                "--write-out",
                "%{http_code}",
                "https://nodejs.org/dist/v" + version + "/" + filename,
            ],
            capture_output=True,
            text=True,
            timeout=65,
            env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LANG": "C.UTF-8"},
        )
        if result.returncode or result.stdout != "200":
            raise ValueError(
                "node_https_failed:" + str(result.returncode) + ":" + result.stdout[:3]
            )
        response.seek(0)
        yield response


def extract_node(archive, destination):
    destination = Path(destination).resolve()
    prefix = Path(archive).name.removesuffix(".tar.xz")
    runtime = destination / prefix
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 512 * 1024 * 1024:
            raise ValueError("node_archive_over_bound")
        links = []
        for member in members:
            relative = Path(member.name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or relative.parts[0] != prefix
            ):
                raise ValueError("node_archive_root_mismatch")
            target = destination / relative
            if not target.resolve().is_relative_to(runtime):
                raise ValueError("node_archive_external_path")
            if member.issym():
                links.append((member, target))
                continue
            if member.isdir():
                if target.is_symlink():
                    raise ValueError("node_archive_directory_link")
                target.mkdir(parents=True, exist_ok=True)
                continue
            if (
                not member.isfile()
                or member.size > 200 * 1024 * 1024
                or target.is_symlink()
            ):
                raise ValueError("node_archive_unsupported_entry")
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as source:
                if target.exists():
                    expected = hashlib.sha256()
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        expected.update(chunk)
                    if sha(target) != expected.hexdigest():
                        raise ValueError("node_existing_runtime_drift")
                else:
                    with target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(member.mode & 0o755)
        for member, target in links:
            if Path(member.linkname).is_absolute() or not (
                target.parent / member.linkname
            ).resolve().is_relative_to(runtime):
                raise ValueError("node_archive_external_link")
            if target.exists() or target.is_symlink():
                if not target.is_symlink() or os.readlink(target) != member.linkname:
                    raise ValueError("node_existing_link_drift")
            else:
                target.symlink_to(member.linkname)
    return runtime


def resolve_lock(staged, output, dependencies):
    with tempfile.TemporaryDirectory(prefix="ui-lock-", dir=output.parent) as temporary:
        work = Path(temporary)
        package = {
            "name": "forge-ui-toolchain",
            "version": "1.0.0",
            "private": True,
            "dependencies": dependencies,
        }
        runtime = extract_node(staged, work)
        node = runtime / "bin/node"
        (work / "package.json").write_text(json.dumps(package))
        env = environment(node, work / "unused")
        npm_configs(env)
        run(
            [
                node,
                runtime / "lib/node_modules/npm/bin/npm-cli.js",
                "install",
                "--package-lock-only",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ],
            work,
            env,
            log=output.with_suffix(".resolve.log"),
        )
        lock = json.loads((work / "package-lock.json").read_text())
    validate_lock(lock, dependencies)
    return package, lock
