"""Install only the requested launcher snapshots using Forge-owned pointers."""

from pathlib import Path
import json
import os
import shutil

from dev_tools_catalog import PAYLOAD, save, sha, digest


def install(root, native, destination=None):
    root = Path(root)
    if os.geteuid() == 0:
        raise ValueError("launcher_requires_target_user")
    expected = {p: sha(root / p) for p in PAYLOAD}
    identity = digest(expected)
    data, state, _ = native._user_roots()
    owned = data / "dev-tools"
    generation = owned / identity[:16]
    target = generation / "scripts/setup-dev-tools"
    primary = Path.home() / "dev/tooling/scripts/setup-dev-tools"
    if destination and destination != primary:
        raise ValueError("launcher_destination_not_declared")
    paths = [primary, Path.home() / ".local/bin/setup-dev-tools"]
    previous = [native._owned_symlink_target(p, owned) for p in paths]
    receipt = state / "dev-tools" / (identity + ".json")
    if receipt.exists():
        r = json.loads(receipt.read_text())
        if (
            r["state"] != "verified"
            or r["files"] != expected
            or any(not p.is_symlink() or p.resolve() != target.resolve() for p in paths)
        ):
            raise ValueError("launcher_transaction_needs_explicit_reconciliation")
        if any(sha(generation / p) != h for p, h in expected.items()):
            raise ValueError("launcher_generation_drift")
        return {
            "status": "verified_unchanged",
            "launcher": str(primary),
            "receipt": str(receipt),
        }
    record = {
        "schema_version": "forge-dev-launcher-v1",
        "uid": os.getuid(),
        "state": "prepared",
        "generation": str(generation),
        "identity": identity,
        "files": expected,
        "pointers": [
            {"path": str(p), "previous": old} for p, old in zip(paths, previous)
        ],
    }
    save(receipt, record)
    try:
        if generation.exists() or generation.is_symlink():
            raise ValueError("launcher_generation_exists_without_receipt")
        for name in PAYLOAD:
            path = generation / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, path)
        origin = generation / "scripts/forge-root.json"
        save(origin, str(root.resolve()))
        if any(
            sha(generation / p) != h or sha(root / p) != h for p, h in expected.items()
        ):
            raise ValueError("launcher_source_changed_during_copy")
        record["origin_sha256"] = sha(origin)
        record["state"] = "files_verified"
        save(receipt, record)
        for index, path in enumerate(paths):
            if native._owned_symlink_target(path, owned) != previous[index]:
                raise ValueError("launcher_pointer_changed_before_write")
            native._switch_owned_symlink(path, target, owned)
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            record["state"] = "pointer_" + str(index + 1) + "_activated"
            save(receipt, record)
        record["state"] = "verified"
        save(receipt, record)
        return {"status": "verified", "launcher": str(primary), "receipt": str(receipt)}
    except BaseException as error:
        record["reason"] = str(error)
        save(receipt, record)
        raise


def rollback(path, approval, native):
    path = Path(path)
    if sha(path) != approval:
        raise ValueError("launcher_receipt_digest_mismatch")
    r = json.loads(path.read_text())
    data, _, _ = native._user_roots()
    owned = data / "dev-tools"
    generation = Path(r["generation"])
    target = generation / "scripts/setup-dev-tools"
    paths = [
        Path.home() / "dev/tooling/scripts/setup-dev-tools",
        Path.home() / ".local/bin/setup-dev-tools",
    ]
    if (
        r["uid"] != os.getuid()
        or generation != owned / r["identity"][:16]
        or [str(p) for p in paths] != [v["path"] for v in r["pointers"]]
    ):
        raise ValueError("launcher_rollback_scope_conflict")
    for name, expected in r["files"].items():
        p = generation / name
        if p.exists() and sha(p) != expected:
            raise ValueError("launcher_rollback_external_drift")
    for item, pointer in zip(r["pointers"], paths):
        current = native._owned_symlink_target(pointer, owned)
        if current == item["previous"]:
            continue
        if not pointer.is_symlink() or pointer.resolve() != target.resolve():
            raise ValueError("launcher_rollback_pointer_conflict")
        previous = Path(item["previous"]) if item["previous"] else None
        if previous:
            if not previous.is_absolute():
                previous = pointer.parent / previous
            if not previous.resolve().is_relative_to(owned.resolve()):
                raise ValueError("launcher_rollback_previous_conflict")
            native._switch_owned_symlink(pointer, previous, owned)
        else:
            pointer.unlink()
    r["state"] = "rolled_back_evidence_retained"
    save(path, r)
    return {"status": r["state"], "receipt_sha256": sha(path)}
