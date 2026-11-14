"""Shared workstation metadata and bounded, hash-bound Forge materialization."""

from pathlib import Path
import hashlib
import json
import os
import tempfile
import tomllib


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(root):
    path = Path(root) / "catalog/workstation-tools.toml"
    if path.is_symlink():
        raise ValueError("catalog_symlink")
    data = tomllib.loads(path.read_text())
    ids = [r["id"] for r in data["tools"]]
    if data["schema_version"] != 1 or len(ids) != len(set(ids)):
        raise ValueError("invalid_workstation_catalog")
    for name, profile in data["ui_profiles"].items():
        if profile["vitest"] != profile["provider"] or profile["browsers"] != [
            "chromium",
            "firefox",
            "webkit",
        ]:
            raise ValueError("incompatible_ui_profile:" + name)
    manifest = (
        Path(root)
        / "runbooks/ubuntu_24_04_wsl2_tooling_pack/manifests/tool_versions.env"
    )
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if key.endswith("_VERSION") and data["validated_versions"].get(
                    key[:-8].lower()
                ) != value.removeprefix("v"):
                    raise ValueError("host_pack_version_drift:" + key)
    return data


def save(path, value):
    """Private atomic state; checkpoint content and parent directory durably."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


PAYLOAD = [
    "catalog/workstation-tools.toml",
    "scripts/setup-dev-tools",
    "scripts/lib/dev_tools_catalog.py",
    "scripts/lib/dev_tools_doctor.py",
    "scripts/lib/dev_tools_ui.py",
    "scripts/lib/dev_tools_probe.cjs",
    "scripts/lib/dev_tools_smoke.cjs",
    "scripts/lib/dev_tools_launcher.py",
]


def materialize(source, target, *, apply=False):
    source, target = Path(source).resolve(), Path(target).resolve()
    load(source)
    if source == target or not (target / "scripts/moradin_tooling_suite.py").is_file():
        raise ValueError("expected_existing_forge_target")
    prior_path = target / "catalog/templates-tooling-source.json"
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    rows = []
    for name in PAYLOAD:
        src, dst = source / name, target / name
        if (
            src.is_symlink()
            or dst.is_symlink()
            or not dst.resolve().is_relative_to(target)
        ):
            raise ValueError("payload_path_conflict:" + name)
        digest = sha(src)
        previous = sha(dst) if dst.exists() else None
        if prior and previous not in (prior["files"].get(name), digest, None):
            raise ValueError("generated_payload_drift:" + name)
        rows.append(
            {
                "path": name,
                "sha256": digest,
                "previous_sha256": previous,
                "matches": previous == digest,
            }
        )
    if apply:
        for row in rows:
            dst = target / row["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Preserve an exact reviewable migration receipt before replacements.
            data = (source / row["path"]).read_bytes()
            if (sha(dst) if dst.exists() else None) != row["previous_sha256"]:
                raise ValueError("payload_changed_before_write:" + row["path"])
            fd, tmp = tempfile.mkstemp(dir=dst.parent)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(tmp, 0o755 if row["path"] == "scripts/setup-dev-tools" else 0o644)
            os.replace(tmp, dst)
        import subprocess

        identity = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        native_identity = (
            identity.returncode == 0
            and Path(identity.stdout.strip()).resolve() == source
        )
        revision = (
            subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
            ).strip()
            if native_identity
            else None
        )
        dirty = (
            bool(
                subprocess.check_output(
                    ["git", "-C", str(source), "status", "--porcelain"], text=True
                )
            )
            if native_identity
            else None
        )
        save(
            prior_path,
            {
                "schema_version": 1,
                "source_repository": "templates-deck",
                "source_revision": revision,
                "source_revision_state": "source_export_no_native_revision"
                if not native_identity
                else "dirty_hash_bound_candidate"
                if dirty
                else "clean",
                "files": {r["path"]: r["sha256"] for r in rows},
                "authority": "Shared definitions; Forge retains native installation and trust gates.",
            },
        )
    return {
        "status": "applied"
        if apply
        else "match"
        if all(r["matches"] for r in rows)
        else "drift",
        "files": rows,
    }
