"""Small, non-executing policy helpers shared by primers and rendered briefs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import socket
import os
import tempfile
import tomllib
from datetime import UTC, datetime
from typing import Any


def execution_context(root: Path, repo: dict[str, Any] | None = None) -> dict[str, Any]:
    repo = repo or {}
    declared = str(repo.get("container_runtime") or repo.get("runtime") or "")
    detected = [name for name in ("podman", "docker") if shutil.which(name)]
    authorization_path = root / "artifacts/tooling/task-authorization/latest/summary.json"
    try:
        record = json.loads(authorization_path.read_text())
    except (OSError, ValueError):
        record = {}
    # A document is evidence to inspect, never a new execution grant.
    authorization = {
        "status": "record_present_requires_scope_validation" if record else "current_prompt_only",
        "evidence_path": str(authorization_path) if record else "",
        "grants_execution": False,
        "boundary": "continue scoped reversible alternatives; reconcile uncertain outcomes before retry; ask before privilege, credential, destructive, upgrade or spending changes",
    }
    return {
        "host_key": hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16],
        "canonical_repo_root": str(root.resolve()),
        "project_guidance": str(root / "AGENTS.md") if (root / "AGENTS.md").is_file() else "missing",
        "tool_lookup_order": ["repo_native", "shared_tooling", "installed_tool"],
        "container_runtime": {"declared": declared or "not_declared", "detected_clis": detected,
                              "runtime_ready": "not_probed", "automatic_substitution": False},
        "authorization": authorization,
        "testing": "focused behavior checks first; reuse unchanged proof; required security/release gates remain authoritative",
        "completion": "successful safeguard rejection does not prove the requested capability works",
        "subagents": "explicit_current_prompt_only",
    }


def classify_pause(*, mode: str = "", evidence: str = "") -> dict[str, str]:
    supported = {"necessary_clarification", "policy_conflict", "avoidable_reconfirmation",
                 "external_dependency", "missing_executor", "completed_outcome"}
    if mode.lower() == "plan":
        return {"class": "plan_mode_interaction", "confidence": "observed_mode"}
    if evidence in supported:
        return {"class": evidence, "confidence": "explicit_classification"}
    return {"class": "unclassified", "confidence": "insufficient_evidence"}


def migrate_codex_config(path: Path) -> dict[str, Any]:
    """Explicit operator-invoked migration; never called by a brief or gate."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("config_regular_file_required")
    original = path.read_text()
    before = tomllib.loads(original)
    desired_profile = {"model": "gpt-6-astra", "model_reasoning_effort": "high"}
    current_profile = before.get("profiles", {}).get("astra-high")
    if current_profile is not None and current_profile != desired_profile:
        raise ValueError("existing_astra_high_profile_conflict")
    lines = original.splitlines(keepends=True)
    top = True
    result = []
    replaced = set()
    values = {"model": "gpt-6-astra", "model_reasoning_effort": "ultra"}
    for line in lines:
        if line.lstrip().startswith("["):
            top = False
        key = line.split("=", 1)[0].strip()
        if top and key in values:
            result.append(f'{key} = "{values[key]}"\n')
            replaced.add(key)
        else:
            result.append(line)
    text = "".join(f'{k} = "{v}"\n' for k, v in values.items() if k not in replaced) + "".join(result)
    if current_profile is None:
        text = text.rstrip() + '\n\n[profiles.astra-high]\nmodel = "gpt-6-astra"\nmodel_reasoning_effort = "high"\n'
    expected = {**before, **values, "profiles": {**before.get("profiles", {}), "astra-high": desired_profile}}
    if tomllib.loads(text) != expected:
        raise ValueError("unrelated_config_change_refused")
    if text == original:
        return {"status": "already_current", "backup": "", "model": values["model"]}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup = path.with_name(path.name + ".pre-astra-" + stamp)
    with backup.open("x") as handle:
        os.chmod(backup, 0o600)
        handle.write(original)
    fd, temporary = tempfile.mkstemp(prefix=".astra-config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if path.read_text() != original:
            raise ValueError("concurrent_config_change_refused")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"status": "migrated", "backup": str(backup), "model": values["model"],
            "effort": "ultra", "high_profile": "astra-high", "unrelated_settings_preserved": True}
