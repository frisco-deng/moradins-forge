"""Bound native validation receipts to explicit repository configuration inputs."""

import hashlib
import json
import os
import platform
import sys
from pathlib import Path


INPUT_PATHS = (
    "Makefile",
    "tooling/configs/tooling-targets.json",
    "tooling/adapter.toml",
    "tooling/adapter.yaml",
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "pnpm-lock.yaml",
    "package-lock.json",
    "Cargo.toml",
    "Cargo.lock",
    ".pymarkdown.json",
    ".pre-commit-config.yaml",
)


def runtime_identity():
    """Hash routing environment only; never serialize credentials or values."""
    names = (
        "PATH",
        "CI_LOCAL_MODE",
        "REVIEW_READY_SCOPE",
        "TOOLING_ALLOW_MISSING_TOOLS",
        "TOOLING_ALLOW_PLAIN_DOCKER",
        "TOOLING_ALLOW_MUTATING_CHECKS",
        "GITHUB_ACTIONS",
    )
    return {
        "python": hashlib.sha256(sys.version.encode()).hexdigest(),
        "platform": hashlib.sha256(
            (sys.platform + ":" + platform.machine()).encode()
        ).hexdigest(),
        "environment": {
            n: hashlib.sha256(os.environ[n].encode()).hexdigest()
            if n in os.environ
            else None
            for n in names
        },
    }


def input_receipt(root, paths=INPUT_PATHS):
    root = Path(root).resolve()
    rows = []
    read_bytes = 0
    for name in paths:
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            rows.append(
                {
                    "path": name,
                    "status": "unverified",
                    "reason": "symlink_or_external_input",
                }
            )
        elif not path.exists():
            rows.append({"path": name, "status": "absent", "sha256": None})
        elif (
            not path.is_file()
            or path.stat().st_size > 4 * 1024 * 1024
            or read_bytes + path.stat().st_size > 8 * 1024 * 1024
        ):
            rows.append(
                {
                    "path": name,
                    "status": "unverified",
                    "reason": "nonfile_or_over_4MiB_read_bound",
                }
            )
        else:
            read_bytes += path.stat().st_size
            rows.append(
                {
                    "path": name,
                    "status": "present",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return {
        "schema_version": "validation-inputs-v2",
        "runtime": runtime_identity(),
        "status": "unverified"
        if any(r["status"] == "unverified" for r in rows)
        else "bound",
        "inputs": rows,
        "coverage": "Declared native build/config/lock inputs only; repository state, environment, external services and native freshness gates remain separate.",
    }


def compare_inputs(root, recorded):
    if recorded is None:
        return {"status": "legacy_not_declared", "reasons": []}
    if (
        not isinstance(recorded, dict)
        or recorded.get("schema_version")
        not in ("validation-inputs-v1", "validation-inputs-v2")
        or not recorded.get("inputs")
    ):
        return {
            "status": "unverified",
            "reasons": ["validation input receipt incompatible"],
        }
    names = [r.get("path") for r in recorded["inputs"]]
    if (
        any(
            not isinstance(n, str)
            or not n
            or Path(n).is_absolute()
            or ".." in Path(n).parts
            for n in names
        )
        or len(set(names)) != len(names)
        or len(names) > 32
    ):
        return {"status": "unverified", "reasons": ["validation input paths invalid"]}
    current = input_receipt(root, names)
    reasons = []
    gaps = (
        ["runtime_environment_not_bound"]
        if recorded["schema_version"] == "validation-inputs-v1"
        else []
    )
    if (
        recorded["schema_version"] == "validation-inputs-v2"
        and recorded.get("runtime") != current["runtime"]
    ):
        reasons.append("runtime or execution environment changed or unverified")
    if current["status"] != "bound" or recorded.get("status") != "bound":
        reasons.append("validation inputs incompletely observed")
    for old, new in zip(recorded["inputs"], current["inputs"]):
        if old != new:
            reasons.append("validation input changed: " + new["path"])
    return {
        "status": "changed" if reasons else "matched",
        "reasons": reasons,
        "coverage_gaps": gaps,
    }


def input_fingerprint(root):
    receipt = input_receipt(root)
    return (
        hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
        if receipt["status"] == "bound"
        else ""
    )
