"""Shared workstation metadata and bounded, hash-bound Forge materialization."""

from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
import tomllib


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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


def save(path, value, *, mode=0o600):
    """Private atomic state; checkpoint content and parent directory durably."""
    path = Path(path)
    if mode not in {0o600, 0o644}:
        raise ValueError("unsupported_checkpoint_permissions")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        if os.name == "posix":
            os.fchmod(fd, mode)
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
    "scripts/lib/dev_tools_runtime.py",
    "scripts/lib/dev_tools_acceptance.py",
    "scripts/lib/dev_tools_probe.cjs",
    "scripts/lib/dev_tools_smoke.cjs",
    "scripts/lib/dev_tools_launcher.py",
    "scripts/lib/dev_tools_dependencies.py",
    "scripts/lib/dev_tools_review.py",
    "scripts/lib/dev_tools_workflow.py",
    "scripts/lib/dev_tools_environments.py",
]


def source_identity(root):
    argv = ["git", "--no-optional-locks", "-C", str(root)]
    try:
        boundary = subprocess.check_output([*argv, "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL, text=True).strip()
        if Path(boundary).resolve() == root:
            revision = subprocess.check_output([*argv, "rev-parse", "HEAD"], text=True).strip()
            dirty = bool(subprocess.check_output([*argv, "status", "--porcelain"]))
            return {"source_revision": revision, "source_revision_state": "dirty_hash_bound_candidate" if dirty else "clean"}
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"source_revision": None, "source_revision_state": "source_export_no_native_revision"}


def _read_owned(root, name):
    path = root / name
    if (not path.resolve().is_relative_to(root)
            or any((root / p).is_symlink() for p in Path(name).parents)
            or path.is_symlink()):
        raise ValueError("payload_path_conflict:" + name)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("unexpected_payload_type_or_size:" + name)
    return path.read_bytes()


def _hash(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def materialize(source, target, *, apply=False):
    source, target = Path(source).resolve(), Path(target).resolve()
    load(source)
    if source == target or not (target / "scripts/moradin_tooling_suite.py").is_file():
        raise ValueError("expected_existing_forge_target")
    identity = source_identity(source)
    receipt_name = "catalog/templates-tooling-source.json"
    prior_data = _read_owned(target, receipt_name)
    prior = json.loads(prior_data) if prior_data is not None else {}
    if prior and (prior.get("source_repository") != "templates-deck"
                  or set(prior.get("files", {})) != set(PAYLOAD)):
        raise ValueError("invalid_materialization_receipt")
    rows, selected = [], {}
    for name in PAYLOAD:
        selected[name] = _read_owned(source, name)
        expected = _hash(selected[name])
        if expected is None:
            raise ValueError("canonical_payload_missing:" + name)
        actual = _hash(_read_owned(target, name))
        previous = prior.get("files", {}).get(name)
        state = ("match" if actual == expected else "missing" if actual is None
                 else "older_managed_bytes" if actual == previous else "conflict")
        rows.append({"path": name, "sha256": expected, "previous_sha256": actual,
                     "matches": state == "match", "status": state})
    conflicts = [r["path"] for r in rows if r["status"] == "conflict"]
    if apply:
        if conflicts:
            raise ValueError("generated_payload_drift:" + conflicts[0])
        if source_identity(source) != identity or any(_read_owned(source, name) != data for name, data in selected.items()):
            raise ValueError("canonical_payload_changed_before_write")
        for row in rows:
            if _hash(_read_owned(target, row["path"])) != row["previous_sha256"]:
                raise ValueError("payload_changed_before_write:" + row["path"])
            if row["matches"]:
                continue
            dst = target / row["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=dst.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(selected[row["path"]])
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(tmp, 0o755 if row["path"] == "scripts/setup-dev-tools" else 0o644)
                os.replace(tmp, dst)
            finally:
                Path(tmp).unlink(missing_ok=True)
        if (source_identity(source) != identity
                or _read_owned(target, receipt_name) != prior_data
                or any(_read_owned(source, name) != data or _read_owned(target, name) != data
                       for name, data in selected.items())):
            raise ValueError("materialized_payload_or_receipt_changed")
        save(target / receipt_name, {"schema_version": 1, "source_repository": "templates-deck",
                                     **identity, "files": {r["path"]: r["sha256"] for r in rows},
                                     "authority": "Shared definitions; Forge retains native installation and trust gates."}, mode=0o644)
    status = ("applied" if apply else "conflict" if conflicts
              else "match" if all(r["matches"] for r in rows) else "drift")
    return {"status": status, "canonical": identity, "previous_receipt_sha256": _hash(prior_data),
            "previous_source_revision": prior.get("source_revision"), "files": rows}


def distribution_status(source, release_manifest, downstream_lock=None, intake_receipt=None):
    """Compare package bytes and an explicit downstream pin without activating either."""
    source = Path(source).resolve()
    manifest_path = Path(release_manifest).absolute()
    manifest = json.loads(manifest_path.read_bytes())
    release, commit = manifest["release"], manifest["source_sha"]
    if (not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?", release)
            or not re.fullmatch(r"[a-f0-9]{40}", commit)):
        raise ValueError("invalid_forge_release_identity")
    prefix = f"moradins-forge-{release[1:]}"
    archive_name = prefix + ".tar.gz"
    archive = manifest_path.parent / archive_name
    if (manifest["archive"]["path"] != archive_name or archive.is_symlink()
            or not archive.is_file() or sha(archive) != manifest["archive"]["sha256"]):
        raise ValueError("forge_archive_identity_conflict")
    receipt_name = "catalog/templates-tooling-source.json"
    wanted = {*PAYLOAD, receipt_name}
    observed = {}
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            lead, _, name = member.name.partition("/")
            if lead != prefix or name not in wanted:
                continue
            if not member.isfile() or member.size > 4 * 1024 * 1024 or name in observed:
                raise ValueError("forge_payload_member_conflict:" + name)
            with bundle.extractfile(member) as stream:
                observed[name] = stream.read()
    expected = {name: _hash(_read_owned(source, name)) for name in PAYLOAD}
    if any(checksum is None for checksum in expected.values()):
        raise ValueError("canonical_payload_missing")
    actual = {name: _hash(observed.get(name)) for name in PAYLOAD}
    receipt = json.loads(observed[receipt_name]) if receipt_name in observed else None
    missing = [name for name in PAYLOAD if actual[name] is None]
    different = [name for name in PAYLOAD if actual[name] not in (None, expected[name])]
    packaged = ("missing_payload" if missing else "missing_receipt" if receipt is None
                else "receipt_conflict" if receipt.get("source_repository") != "templates-deck" or receipt.get("files") != actual
                else "different_managed_bytes" if different else "match")
    pin = {"status": "unobserved", "import": "unobserved", "activation": "unobserved"}
    if downstream_lock:
        lock_path = Path(downstream_lock)
        raw = lock_path.read_bytes()
        lock = json.loads(raw)
        checksum = _hash(raw)
        pinned = lock.get("source_commit")
        same = lock.get("release") == release and pinned == commit
        match = same and lock.get("assets", {}).get(archive_name, {}).get("sha256") == manifest["archive"]["sha256"]
        pin.update(release=lock.get("release"), source_commit=pinned, lock_sha256=checksum,
                   status="match" if match else "pin_asset_conflict" if same or lock.get("release") == release else "different_pin")
        if intake_receipt:
            evidence = json.loads(Path(intake_receipt).read_bytes())
            binding = (evidence.get("release_lock_sha256"), evidence.get("release"), evidence.get("source_commit"))
            verified = (binding == (checksum, lock.get("release"), pinned)
                        and evidence.get("integrity") == "passed")
            pin["import"] = "verified" if verified else "evidence_conflict"
    elif intake_receipt:
        raise ValueError("intake_evidence_requires_downstream_lock")
    return {"status": packaged, "canonical": {**source_identity(source), "files": expected},
            "package": {"release": release, "source_commit": commit, "manifest_sha256": sha(manifest_path),
                        "archive_sha256": manifest["archive"]["sha256"], "source_receipt_sha256": _hash(observed.get(receipt_name)),
                        "source_revision": receipt.get("source_revision") if receipt else None,
                        "files": actual, "missing": missing, "different": different},
            "downstream": pin}


def inputs(root):
    names = PAYLOAD + [
        n
        for n in ["scripts/moradin_tooling_suite.py", "scripts/moradin_workstation.py"]
        if (Path(root) / n).is_file()
    ]
    return {name: sha(Path(root) / name) for name in names}
