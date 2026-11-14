"""Network-free command inventory; package presence is not execution proof."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import platform
import re
import shutil
import subprocess

from dev_tools_catalog import load, sha


VERSION = re.compile(r"(?<![\w.])v?(\d+\.\d+\.\d+)(?![\w.])")


def version(text):
    match = VERSION.search(text)
    return match.group(1) if match else None


def command_check(spec, pins, timeout=5):
    candidates = spec.get("command_candidates") or [spec["command"]]
    executable = next(
        (shutil.which(n) for n in candidates if n and shutil.which(n)), None
    )
    row = {
        "id": spec["id"],
        "category": spec["category"],
        "required": spec.get("required", False),
        "path": executable,
        "expected_version": pins.get(spec["id"]),
        "upstream_freshness": "unverified",
        "runtime_execution": "not_tested",
        "integrity": "not_established_by_version_probe",
    }
    row["remediation_command"] = (
        "setup-dev-tools plan --custom --select "
        + spec["id"]
        + " --output TOOL-PLAN.json"
    )
    if not spec["command"]:
        return {**row, "status": "package_manager_verification_required"}
    if not executable:
        return {**row, "status": "missing"}
    special = {
        "cosign": ["version"],
        "scorecard": ["version"],
        "syft": ["version"],
        "grype": ["version"],
        "kubectl": ["version", "--client", "--output=json"],
        "kind": ["version"],
        "helm": ["version", "--short"],
        "kubeconform": ["-v"],
    }
    argv = spec.get("verification_argv") or [
        spec["command"],
        *special.get(spec["id"], ["--version"]),
    ]
    try:
        command = argv if spec.get("verification_argv") else [executable, *argv[1:]]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
        observed = version((result.stdout + result.stderr)[:8000])
        status = (
            "probe_failed"
            if result.returncode
            else (
                "version_mismatch"
                if row["expected_version"] and observed != row["expected_version"]
                else "version_matched"
                if row["expected_version"]
                else "installed_version_unpinned"
                if observed
                else "presence_probe_passed"
            )
        )
        return {
            **row,
            "status": status,
            "observed_version": observed,
            "executable_sha256": sha(Path(executable).resolve()),
            "exit_code": result.returncode,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {**row, "status": "unverified", "reason": type(error).__name__}


def ui_check(root, profile, ui_root, node):
    data = load(root)
    if not profile:
        return {"status": "not_selected", "execution": "not_run"}
    expected = data["ui_profiles"][profile]
    node = node or shutil.which("node")
    if not node or not ui_root:
        return {"status": "missing_runtime_or_profile", "execution": "not_run"}
    if not Path(ui_root).is_dir():
        return {
            "status": "selected_profile_not_activated_or_unavailable",
            "execution": "not_run",
            "first_action": "Inspect the approved cohort receipt and scoped blockers; absence of activation does not establish a missing SDK.",
        }
    try:
        ui_root = Path(ui_root).resolve()
        env = dict(os.environ)
        if (ui_root / "browsers").is_dir():
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(ui_root / "browsers")
        r = subprocess.run(
            [
                str(node),
                str(Path(root) / "scripts/lib/dev_tools_probe.cjs"),
                str(ui_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        observed = (
            json.loads(r.stdout) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        )
        packages = {
            "playwright": expected["playwright"],
            "vitest": expected["vitest"],
            "@vitest/browser-playwright": expected["provider"],
            "@axe-core/playwright": expected["axe"],
        }
        missing = [
            name
            for name, wanted in packages.items()
            if observed.get("packages", {}).get(name) != wanted
        ]
        if observed.get("node") != expected["node"]:
            missing.append("node")
        missing += [
            b
            for b in [
                "chromium",
                "chromium-headless-shell",
                "firefox",
                "webkit",
                "ffmpeg",
            ]
            if not observed.get("browsers", {}).get(b, {}).get("present")
        ]
        return {
            "status": "missing_or_mismatched" if missing else "installed_unverified",
            "missing": missing,
            "expected": expected,
            "observed": observed,
            "execution": "not_run",
        }
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {"status": "unverified", "reason": str(error), "execution": "not_run"}


def doctor(root, *, profile=None, ui_root=None, node=None, repo_root=None):
    data = load(root)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(
            pool.map(
                lambda row: command_check(row, data["validated_versions"]),
                data["tools"],
            )
        )
    repository = {"status": "not_selected"}
    if repo_root:
        repo = Path(repo_root).resolve()
        manifest = repo / "package.json"
        if manifest.is_file():
            package = json.loads(manifest.read_text())
            dependencies = {
                **package.get("dependencies", {}),
                **package.get("devDependencies", {}),
            }
            repository = {
                "status": "declared_not_execution_proof",
                "manifest_sha256": sha(manifest),
                "versions": {
                    k: v
                    for k, v in dependencies.items()
                    if k
                    in [
                        "playwright",
                        "@playwright/test",
                        "vitest",
                        "@vitest/browser-playwright",
                        "@axe-core/playwright",
                    ]
                },
                "locks": {
                    p.name: sha(p)
                    for p in [
                        repo / "package-lock.json",
                        repo / "pnpm-lock.yaml",
                        repo / "yarn.lock",
                    ]
                    if p.is_file()
                },
                "policy": "Repository locks stay authoritative; shared UI cohorts are separate opt-in environments.",
            }
        else:
            repository = {"status": "unverified_missing_package_manifest"}
    return {
        "schema_version": "dev-tools-doctor-v1",
        "status": "inventory_complete",
        "inventory_scope": "Current operator PATH; global-command absence does not establish a missing repo-owned SDK. Selected UI cohorts are reported separately.",
        "host": {
            "system": platform.system(),
            "architecture": platform.machine(),
            "uid": os.getuid() if hasattr(os, "getuid") else None,
        },
        "catalog_sha256": sha(Path(root) / "catalog/workstation-tools.toml"),
        "checks": rows,
        "ui": ui_check(root, profile, ui_root, node),
        "repository": repository,
        "security_content": "unverified; use scanner-native database freshness checks",
        "summary": {
            status: sum(r["status"] == status for r in rows)
            for status in sorted({r["status"] for r in rows})
        },
        "installs_performed": 0,
        "freshness_claim": "Declared pins only. Upstream freshness requires explicit native refresh planning.",
    }
