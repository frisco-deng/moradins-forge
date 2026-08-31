#!/usr/bin/env python3
"""Network-free lockfile policy checks for dependency automation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_PACKAGE = REPO_ROOT / "dev_tracker" / "ui" / "package.json"
UI_LOCK = REPO_ROOT / "dev_tracker" / "ui" / "package-lock.json"
UV_LOCK = REPO_ROOT / "uv.lock"
MINIMUM_NANOID = (3, 3, 18)
VERSION = "MoradinForgeDependencyReadinessV1"


class DependencyReadinessError(RuntimeError):
    """A dependency lock violates the reviewed repository policy."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_semver(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise DependencyReadinessError(f"unsupported dependency version: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def inspect_locks(
    *,
    package_path: Path = UI_PACKAGE,
    lock_path: Path = UI_LOCK,
    uv_lock_path: Path = UV_LOCK,
) -> dict[str, Any]:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if int(lock.get("lockfileVersion", 0)) < 3:
        raise DependencyReadinessError("npm lockfileVersion 3 or newer is required")
    if package.get("overrides", {}).get("nanoid") != "3.3.18":
        raise DependencyReadinessError("package.json must pin the reviewed nanoid override")

    versions = sorted(
        {
            str(row.get("version", ""))
            for name, row in lock.get("packages", {}).items()
            if name.endswith("node_modules/nanoid") and isinstance(row, dict)
        }
    )
    if not versions:
        raise DependencyReadinessError("npm lock contains no nanoid resolution")
    vulnerable = [version for version in versions if stable_semver(version) < MINIMUM_NANOID]
    if vulnerable:
        raise DependencyReadinessError(
            "nanoid must resolve to 3.3.18 or newer; found " + ", ".join(vulnerable)
        )
    if not uv_lock_path.is_file():
        raise DependencyReadinessError("uv.lock is required")

    return {
        "version": VERSION,
        "status": "pass",
        "locks": {
            "npm": sha256(lock_path),
            "uv": sha256(uv_lock_path),
        },
        "nanoid": {
            "minimum": ".".join(str(part) for part in MINIMUM_NANOID),
            "resolved": versions,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = inspect_locks()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
