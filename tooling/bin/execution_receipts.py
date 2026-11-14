"""Receipt-backed native stages; process exit is not nested acceptance."""

import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_hash(path, root):
    path = Path(path)
    if not path.is_absolute():
        path = Path(root) / path
    if (
        path.is_symlink()
        or not path.resolve().is_relative_to(Path(root).resolve())
        or not path.is_file()
        or path.stat().st_size > 8 * 1024 * 1024
    ):
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child_acceptance(child, parent, step):
    """Reject incomplete descendants and keep inherited reuse out of new work."""
    native = child.get("execution_receipt", {})
    if (
        not isinstance(native, dict)
        or native.get("schema_version") != "native-execution-stages-v1"
    ):
        return False, "unverified"
    stages = native.get("stages", [])
    if (
        not isinstance(stages, list)
        or not stages
        or not all(isinstance(s, dict) for s in stages)
    ):
        return False, "unverified"
    ids = [s.get("id") for s in stages]
    if not all(
        isinstance(i, str) and len(i) == 64 and all(c in "0123456789abcdef" for c in i)
        for i in ids
    ) or len(ids) != len(set(ids)):
        return False, "unverified"
    accepted = (
        step.get("status") == child.get("status") == "pass"
        and child.get("target") == step["name"]
        and bool(parent.get("repo", {}).get("repo_id"))
        and child.get("repo", {}).get("repo_id") == parent["repo"]["repo_id"]
        and bool(parent.get("git", {}).get("state_fingerprint"))
        and child.get("git", {}).get("state_fingerprint")
        == parent["git"]["state_fingerprint"]
        and native.get("status") == "complete"
        and not native.get("conflicts")
        and all(
            s.get("lifecycle") in ("new", "reused")
            and (
                s.get("acceptance_scope") == "process_exit_only"
                or s.get("acceptance_scope") == "native_child_boundary"
                and s.get("accepted_workflow_boundary") is True
            )
            and all(v == "pass" for v in s.get("prerequisites", {}).values())
            for s in stages
        )
        and all(v == "pass" for v in step.get("prerequisite_results", {}).values())
    )
    origin = (
        "new"
        if any(s.get("work_provenance", s.get("lifecycle")) == "new" for s in stages)
        else "reused"
    )
    return accepted, origin if accepted else "unverified"


def workflow_receipt(summary, root):
    rows, seen, conflicts = [], set(), []
    for bucket in ("prep_steps", "steps"):
        for step in summary.get(bucket, []):
            key = digest([summary["target"], bucket, step["name"]])
            if key in seen:
                conflicts.append("duplicate_stage_identity:" + step["name"])
                continue
            seen.add(key)
            state = step.get("status", "pending")
            reused = step.get("reused_previous_step_artifact") is True
            lifecycle = (
                "failed"
                if state in ("fail", "blocked")
                else "pending"
                if state != "pass"
                else "reused"
                if reused
                else "new"
            )
            scope, accepted, child_hash = "process_exit_only", False, None
            work_provenance = lifecycle
            if step.get("summary_path"):
                child_hash = file_hash(step["summary_path"], root)
                expected = step.get("nested_summary_sha256")
                if not child_hash or not expected or child_hash != expected:
                    scope = "nested_receipt_unverified"
                else:
                    path = Path(step["summary_path"])
                    path = path if path.is_absolute() else Path(root) / path
                    raw = path.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != child_hash:
                        conflicts.append("child_changed_during_receipt:" + step["name"])
                        raw = b"{}"
                    child = json.loads(raw)
                    accepted, work_provenance = child_acceptance(child, summary, step)
                    if reused:
                        work_provenance = "reused"
                    scope = (
                        "native_child_boundary"
                        if accepted
                        else "nested_acceptance_incomplete"
                    )
            rows.append(
                {
                    "id": key,
                    "name": step["name"],
                    "lifecycle": lifecycle,
                    "work_provenance": work_provenance,
                    "prerequisites": step.get("prerequisite_results", {}),
                    "input_sha256": digest(
                        {
                            "state": summary.get("git", {}).get("state_fingerprint"),
                            "inputs": summary.get("validation_inputs"),
                            "command": step.get("command"),
                        }
                    ),
                    "output_sha256": child_hash
                    or (
                        file_hash(step["log_path"], root)
                        if step.get("log_path")
                        else None
                    ),
                    "acceptance_scope": scope,
                    "accepted_workflow_boundary": accepted,
                }
            )
    return {
        "schema_version": "native-execution-stages-v1",
        "status": "conflict"
        if conflicts
        else "complete"
        if rows
        and all(
            r["lifecycle"] in ("new", "reused")
            and r["acceptance_scope"] in ("process_exit_only", "native_child_boundary")
            for r in rows
        )
        else "partial",
        "stages": rows,
        "conflicts": conflicts,
        "new_accepted_boundaries": None
        if conflicts
        else sum(
            r["accepted_workflow_boundary"] and r["work_provenance"] == "new"
            for r in rows
        ),
        "reused_accepted_boundaries": None
        if conflicts
        else sum(
            r["accepted_workflow_boundary"] and r["work_provenance"] == "reused"
            for r in rows
        ),
        "reused_stages": sum(r["lifecycle"] == "reused" for r in rows),
        "limit": "Leaf command receipts prove process exit only; hidden nested steps and application acceptance remain unverified.",
    }
