"""One-confirmation developer upgrades composed from existing native actions."""

from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except (
    ModuleNotFoundError
):  # Windows supports read-only inventory, not this Linux installer.
    fcntl = None
import json
import os
import sys
import uuid

from dev_tools_catalog import inputs, save, sha
from dev_tools_dependencies import selected_ids
from dev_tools_environments import prepare as prepare_ui
from dev_tools_review import review, table
import dev_tools_ui as ui


@contextmanager
def exclusive(state):
    if fcntl is None:
        raise ValueError(
            "developer-tool upgrades require the supported Linux installer"
        )
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (
        state.is_symlink()
        or state.stat().st_uid != os.getuid()
        or state.stat().st_mode & 0o022
    ):
        raise ValueError("upgrade state directory ownership or permissions conflict")
    lock = state / "upgrade.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise ValueError("upgrade lock has foreign ownership")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("another developer-tool upgrade is active") from error
        yield
    finally:
        os.close(fd)


def native_plan(root, native, path, *, include=(), exclude=(), profile="practical"):
    value = native.build_suite_plan(
        forge_root=Path(root),
        profile=profile,
        include_tools=include,
        exclude_tools=exclude,
        refresh_versions=True,
    )
    native.write_suite_plan(value, path)
    return {
        "kind": "native",
        "path": str(path),
        "sha256": sha(path),
        "approval": value["plan_sha256"],
        "plan": value,
        "state": "prepared" if value["status"] == "ready" else "blocked",
        "reason": "; ".join(value["blockers"]),
    }


def reconcile(root, native, state):
    """Inspect the explicitly indexed run. Never retry an uncertain mutation."""
    pointer = state / "current-upgrade.json"
    if not pointer.exists():
        return {}
    if pointer.is_symlink() or pointer.stat().st_uid != os.getuid():
        raise ValueError("upgrade index ownership conflict")
    index = json.loads(pointer.read_text())
    identity = index.get("run_id", "")
    if len(identity) != 32 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("invalid upgrade run identity")
    path = state / "runs" / identity / "execution.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        raise ValueError("upgrade checkpoint ownership conflict")
    record = json.loads(path.read_text())
    if record["uid"] != os.getuid():
        raise ValueError("upgrade checkpoint identity conflict")
    blocked = {}
    _, native_state, _ = native._user_roots()
    for lane in record["lanes"]:
        if lane["state"] != "applying" and not lane.get("requires_reconciliation"):
            continue
        try:
            if lane["kind"] == "ui-check":
                lane["state"] = "interrupted_read_only"
                continue
            if lane["kind"] == "native":
                matches = []
                for candidate in (native_state / "receipts").glob("*/receipt.json"):
                    data = json.loads(candidate.read_text())
                    if data.get("plan_sha256") == lane["approval"]:
                        matches.append(candidate)
                if len(matches) != 1:
                    raise ValueError(
                        "uncertain native transaction has no unique receipt"
                    )
                verified = native.verify_suite_receipt(str(matches[0]))
                if verified["status"] != "pass":
                    raise ValueError("interrupted native transaction did not verify")
                lane.update(
                    state="verified",
                    receipt=str(matches[0]),
                    recovery="receipt reconciled",
                )
            else:
                receipt = native_state / "ui" / (lane["approval"] + ".json")
                value = json.loads(receipt.read_text())
                if value.get("state") == "interrupted_or_failed":
                    data, _, _ = native._user_roots()
                    pointer = data / "ui" / value["profile"]
                    current = native._owned_symlink_target(pointer, data / "ui")
                    if (
                        value["uid"] != os.getuid()
                        or value["plan_sha256"] != lane["approval"]
                        or current != value["previous_pointer"]
                    ):
                        raise ValueError(
                            "failed UI transaction has an unexpected activation state"
                        )
                    lane.update(
                        state="failed",
                        requires_reconciliation=False,
                        recovery="known failed acquisition; no activation; fresh hash-bound plan required",
                    )
                else:
                    ui.verify(receipt)
                    lane.update(
                        state="verified",
                        requires_reconciliation=False,
                        receipt=str(receipt),
                        recovery="receipt reconciled",
                    )
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            blocked[lane["id"]] = str(error)
    if blocked:
        record["status"] = "partial"
    save(path, record)
    return blocked


def prepare(root, native, report, run, blocked):
    lanes = []
    external = [
        r["id"]
        for r in report["rows"]
        if r["owner"] == "external"
        or r["action"] in {"downgrade blocked", "version comparison unknown"}
    ]
    owned = [r["id"] for r in report["rows"] if r["owner"] == "forge"]
    try:
        host = native_plan(
            root, native, run / "host.json", include=owned, exclude=external
        )
    except (ValueError, OSError, RuntimeError) as error:
        host = {"kind": "native", "state": "blocked", "reason": str(error)}
    host["id"] = "host"
    lanes.append(host)
    profiles = [r["profile"] for r in report["ui"]["environments"]]
    dependencies = None
    if profiles:
        try:
            ids = selected_ids(root, report["platform"], profiles)
            dependencies = native_plan(
                root,
                native,
                run / "ui-dependencies.json",
                include=ids,
                profile="custom",
            )
            dependencies["id"] = "ui-dependencies"
        except (ValueError, OSError, RuntimeError) as error:
            dependencies = {
                "id": "ui-dependencies",
                "kind": "native",
                "state": "blocked",
                "reason": str(error),
            }
        lanes.append(dependencies)
    for environment in report["ui"]["environments"]:
        profile = environment["profile"]
        lane = {
            "id": "ui:" + profile,
            "kind": "ui",
            "profile": profile,
            "requires": "ui-dependencies",
            "state": "prepared",
        }
        try:
            if dependencies["state"] != "prepared":
                raise ValueError("UI dependency planning is blocked")
            if (
                environment["state"] == "verified"
                and environment["observed"]["status"] == "installed_unverified"
            ):
                lane.update(kind="ui-check", environment=environment)
            else:
                path = run / (profile + ".json")
                result = prepare_ui(root, native, environment, path)
                lane.update(
                    path=str(path), sha256=sha(path), approval=result["plan_sha256"]
                )
        except (ValueError, OSError, RuntimeError) as error:
            lane.update(state="blocked", reason=str(error))
        lanes.append(lane)
    for lane in lanes:
        if lane["id"] in blocked:
            lane.update(
                state="blocked",
                reason="Prior uncertain mutation: " + blocked[lane["id"]],
            )
    return lanes


def changes(lanes):
    result = []
    for lane in lanes:
        if lane["state"] == "blocked":
            result.append({"id": lane["id"], "action": "blocked: " + lane["reason"]})
        elif lane["kind"] == "native":
            for row in lane["plan"]["tools"]:
                if row["install_action"]["kind"] in {
                    "none",
                    "manual",
                    "protected-existing",
                }:
                    continue
                result.append(
                    {
                        "id": row["id"],
                        "installed": row.get("installed_version"),
                        "available": row["resolved"].get("version"),
                        "channel": row["resolved"].get("source"),
                        "owner": row["install_action"].get("manager", "forge")
                        if row["install_action"]["kind"] == "system-package"
                        else "forge",
                        "action": row["status"],
                    }
                )
        else:
            result.append(
                {"id": lane["id"], "owner": "forge-ui", "action": "verify/repair"}
            )
    return result


def execute(root, native, record, path):
    if inputs(root) != record["implementation"]:
        raise ValueError("source changed after confirmation; review a fresh plan")
    states = {}
    for lane in record["lanes"]:
        if lane["state"] == "blocked":
            states[lane["id"]] = "blocked"
            continue
        mutation_started = False
        try:
            if lane.get("requires") and states.get(lane["requires"]) != "verified":
                raise ValueError("prerequisite did not complete: " + lane["requires"])
            if lane.get("path") and sha(lane["path"]) != lane["sha256"]:
                raise ValueError("plan changed after confirmation")
            lane["state"] = "applying"
            save(path, record)
            print("Running " + lane["id"] + "…", file=sys.stderr, flush=True)
            if lane["kind"] == "native":
                actionable = any(
                    r["install_action"]["kind"]
                    not in {"none", "manual", "protected-existing"}
                    for r in lane["plan"]["tools"]
                )
                if actionable:
                    mutation_started = True
                    result = native.apply_suite_plan(
                        Path(lane["path"]),
                        approved_sha256=lane["approval"],
                        forge_root=Path(root),
                    )
                    lane["receipt"] = result["receipt"]
                    if (
                        result["status"] != "pass"
                        or native.verify_suite_receipt(result["receipt"])["status"]
                        != "pass"
                    ):
                        raise ValueError(
                            "native application or verification did not pass"
                        )
                    skipped = (result.get("root_receipt") or {}).get("skipped", [])
                    if any(r.get("reason") != "already current" for r in skipped):
                        raise ValueError(
                            "native installer retained a component: "
                            + "; ".join(r["reason"] for r in skipped)
                        )
                else:
                    lane["unchanged"] = True
            elif lane["kind"] == "ui-check":
                env = lane["environment"]
                ui.verify(env["receipt"])
                ui.smoke(
                    root,
                    env["generation"],
                    env["node"],
                    path.parent / (lane["profile"] + "-acceptance"),
                )
            else:
                mutation_started = True
                result = ui.apply(root, lane["path"], lane["approval"], native)
                lane["receipt"] = result["receipt"]
                ui.verify(result["receipt"])
            lane["state"] = "verified"
        except (ValueError, OSError, RuntimeError) as error:
            lane.update(
                state="failed",
                reason=str(error),
                requires_reconciliation=mutation_started,
            )
        states[lane["id"]] = lane["state"]
        save(path, record)
    record["status"] = (
        "pass"
        if all(x["state"] == "verified" for x in record["lanes"])
        and not record["conflicts"]
        else "partial"
    )
    save(path, record)
    return record


def upgrade(root, native, *, confirm=input, report=None):
    if os.geteuid() == 0:
        raise ValueError(
            "Run setup-dev-tools as your normal user; sudo is requested only inside the native installer."
        )
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError(
            "--upgrade needs a terminal for one confirmation; --review works noninteractively"
        )
    _, state_root, _ = native._user_roots()
    state = state_root / "dev-tools"
    with exclusive(state):
        blocked = reconcile(root, native, state)
        report = report or review(root, native)
        identity = uuid.uuid4().hex
        run = state / "runs" / identity
        run.mkdir(parents=True, mode=0o700)
        lanes = prepare(root, native, report, run, blocked)
        record = {
            "schema_version": "dev-tools-upgrade-v1",
            "run_id": identity,
            "uid": os.getuid(),
            "implementation": inputs(root),
            "status": "prepared",
            "lanes": lanes,
            "conflicts": report["ui"]["conflicts"],
            "protected_tools": [
                r["id"] for r in report["rows"] if r["owner"] == "external"
            ],
            "excluded_comparisons": [
                r["id"]
                for r in report["rows"]
                if r["action"] in {"downgrade blocked", "version comparison unknown"}
            ],
            "unavailable_tools": [
                r["id"]
                for r in report["rows"]
                if r["owner"] == "forge"
                and (
                    not r.get("available")
                    or r.get("freshness") not in {"fresh", "refreshed"}
                )
            ],
        }
        record["conflicts"] += [
            {"reason": "Version comparison needs review: " + x}
            for x in record["excluded_comparisons"]
        ]
        record["conflicts"] += [
            {"reason": "Available version is unverified: " + x}
            for x in record["unavailable_tools"]
        ]
        path = run / "execution.json"
        save(path, record)
        table(changes(lanes))
        for lane in lanes:
            if lane["state"] == "blocked":
                print(lane["id"] + ": " + lane["reason"])
        print(
            str(len(record["protected_tools"]))
            + " externally managed tools protected; unrelated optional tools are not installed."
        )
        for conflict in record["conflicts"]:
            print("Blocked UI environment: " + conflict["reason"])
        if not changes(lanes):
            record["status"] = "partial" if record["conflicts"] else "unchanged"
            save(path, record)
            print(
                "No eligible installation changes. External and unavailable items remain unchanged."
            )
            return record
        if not any(x["state"] == "prepared" for x in lanes):
            record["status"] = "blocked"
            save(path, record)
            return record
        if confirm(
            "Apply these changes and verify them? [y/N] "
        ).strip().lower() not in {"y", "yes"}:
            record["status"] = "cancelled"
            save(path, record)
            print("Cancelled. No installation changes made.")
            return record
        record["status"] = "approved"
        save(path, record)
        save(state / "current-upgrade.json", {"run_id": identity})
        try:
            result = execute(root, native, record, path)
        except BaseException:
            record["status"] = "interrupted"
            save(path, record)
            raise
        for lane in result["lanes"]:
            print(
                lane["id"]
                + ": "
                + ("unchanged" if lane.get("unchanged") else lane["state"])
                + (" — " + lane["reason"] if lane.get("reason") else "")
            )
        print(
            "Upgrade complete and verified."
            if result["status"] == "pass"
            else "Upgrade partial; blocked/failed components remain explicit."
        )
        counts = {
            "installed": 0,
            "upgraded": 0,
            "unchanged": 0,
            "external": len(record["protected_tools"]),
            "blocked_components": 0,
            "failed_components": 0,
        }
        for lane in result["lanes"]:
            if lane["state"] in {"blocked", "failed"}:
                counts[lane["state"] + "_components"] += 1
            if lane["kind"] == "native":
                for row in lane.get("plan", {}).get("tools", []):
                    if lane["state"] == "verified" and row["status"] in {
                        "install",
                        "upgrade",
                    }:
                        counts[
                            {"install": "installed", "upgrade": "upgraded"}[
                                row["status"]
                            ]
                        ] += 1
                    elif row["status"] == "current":
                        counts["unchanged"] += 1
        result["summary"] = counts
        save(path, result)
        print(
            "; ".join(str(n) + " " + key.replace("_", " ") for key, n in counts.items())
        )
        print("Detailed execution record: " + str(path))
        return result
