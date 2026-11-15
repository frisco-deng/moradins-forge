"""Discover owned UI environments by receipt identity, never by recency."""

from pathlib import Path
import json
import os
import re

from dev_tools_catalog import digest, load, sha
from dev_tools_doctor import ui_check


def discover(root, native):
    data, state, _ = native._user_roots()
    owned, receipts = data / "ui", state / "ui"
    groups = {name: [] for name in load(root)["ui_profiles"]}
    conflicts = []
    for path in sorted(receipts.glob("*.json")):
        if not re.fullmatch("[0-9a-f]{64}", path.stem):
            continue
        try:
            if path.is_symlink() or path.stat().st_uid != os.getuid():
                raise ValueError("foreign UI receipt")
            value = json.loads(path.read_text())
            if value.get("schema_version") != "forge-ui-tooling-receipt-v1":
                continue
            profile = value["profile"]
            generation = owned / path.stem[:16]
            if (
                profile not in groups
                or value["uid"] != os.getuid()
                or value["plan_sha256"] != path.stem
                or Path(value["generation"]) != generation
                or generation.is_symlink()
                or not generation.is_dir()
                or generation.stat().st_uid != os.getuid()
                or value["state"] not in {"verified", "interrupted_or_failed"}
            ):
                raise ValueError("UI receipt identity or state conflict")
            nodes = list(generation.glob("node-v*/bin/node"))
            if len(nodes) != 1:
                raise ValueError("UI runtime is missing or ambiguous")
            observed = ui_check(root, profile, generation, nodes[0])
            fingerprint = digest(
                {
                    "lock": sha(generation / "package-lock.json"),
                    "package": sha(generation / "package.json"),
                    "node": sha(nodes[0]),
                    "packages": observed.get("observed", {}).get("packages"),
                    "browsers": {
                        k: sha(v["path"]) if v.get("present") else None
                        for k, v in observed.get("observed", {})
                        .get("browsers", {})
                        .items()
                        if isinstance(v, dict)
                    },
                }
            )
            groups[profile].append(
                {
                    "profile": profile,
                    "receipt": str(path),
                    "receipt_sha256": sha(path),
                    "generation": str(generation),
                    "node": str(nodes[0]),
                    "state": value["state"],
                    "observed": observed,
                    "fingerprint": fingerprint,
                }
            )
        except (ValueError, KeyError, OSError) as error:
            conflicts.append({"path": str(path), "reason": str(error)})
    selected = []
    for profile, rows in groups.items():
        pointer = owned / profile
        if pointer.is_symlink():
            matches = [x for x in rows if Path(x["generation"]) == pointer.resolve()]
            if len(matches) != 1 or matches[0]["state"] != "verified":
                conflicts.append(
                    {
                        "profile": profile,
                        "reason": "active UI pointer has no unique verified receipt",
                    }
                )
                continue
            selected.append(matches[0])
        elif pointer.exists():
            conflicts.append(
                {
                    "profile": profile,
                    "reason": "UI activation path is not an owned pointer",
                }
            )
        elif rows:
            if len({x["fingerprint"] for x in rows}) != 1:
                conflicts.append(
                    {
                        "profile": profile,
                        "reason": "conflicting UI acquisitions; no current activation",
                    }
                )
            else:
                # Equivalent critical inputs; the sorted receipt id is a stable tie-breaker.
                selected.append(rows[0])
    return {"environments": selected, "conflicts": conflicts}


def prepare(root, native, environment, output):
    """Reuse an exact acquisition only with its original hash-bound plan."""
    import dev_tools_ui as ui

    receipt = Path(environment["receipt"])
    if sha(receipt) != environment["receipt_sha256"]:
        raise ValueError("UI receipt changed after review")
    original = receipt.with_suffix(".plan.json")
    if environment["state"] != "verified" and original.is_file():
        return ui.plan(
            root,
            environment["profile"],
            output,
            reuse_receipt=receipt,
            prior_plan=original,
        )
    # Legacy failed acquisitions without a bound plan are not silently adopted.
    return ui.plan(root, environment["profile"], output)
