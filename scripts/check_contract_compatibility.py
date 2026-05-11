#!/usr/bin/env python3
"""Validate contract bundle compatibility and publish report output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from rag_pipeline.contracts.compatibility import check_contract_bundle, write_compatibility_report
except ModuleNotFoundError:  # Harness-core seed mode (no product runtime package).
    check_contract_bundle = None
    write_compatibility_report = None

REQUIRED_SCHEMA_NAMES = {
    "DocumentEnvelopeV1",
    "RetrievalRequestV1",
    "RetrievalCandidateV1",
    "GroundedAnswerV1",
}


def _default_bundle_path(repo_root: Path) -> Path:
    return repo_root / "Harness" / "artifacts" / "schemas" / "contracts.bundle.json"


def _default_report_path(repo_root: Path) -> Path:
    return repo_root / "Harness" / "artifacts" / "schemas" / "compatibility_report.md"


def _fallback_check(bundle_path: Path) -> tuple[str, list[str]]:
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    schemas = payload.get("schemas", [])
    names = {item.get("name") for item in schemas if isinstance(item, dict)}
    missing = sorted(REQUIRED_SCHEMA_NAMES.difference(names))
    if missing:
        return "fail", [f"missing required schema: {name}" for name in missing]
    return "pass", []


def _fallback_write_report(report_path: Path, result: str, errors: list[str]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Compatibility Report",
        "",
        f"- Result: {result}",
        "- Source: harness-core fallback validator",
    ]
    if errors:
        lines.extend(["", "## Errors"])
        lines.extend([f"- {err}" for err in errors])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Path to contract bundle JSON (default: Harness/artifacts/schemas/contracts.bundle.json).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to markdown report output (default: Harness/artifacts/schemas/compatibility_report.md).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when compatibility checks fail.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    bundle_path = args.bundle or _default_bundle_path(repo_root)
    report_path = args.report or _default_report_path(repo_root)

    if check_contract_bundle and write_compatibility_report:
        result = check_contract_bundle(bundle_path)
        write_compatibility_report(result, report_path)

        print(f"[compat] bundle={bundle_path}")
        print(f"[compat] report={report_path}")
        print(f"[compat] result={result.result}")
        if result.errors:
            for error in result.errors:
                print(f"[compat] error: {error}")

        if args.strict and not result.passed:
            return 1
        return 0

    result, errors = _fallback_check(bundle_path)
    _fallback_write_report(report_path, result, errors)
    print(f"[compat] bundle={bundle_path}")
    print(f"[compat] report={report_path}")
    print(f"[compat] result={result}")
    for error in errors:
        print(f"[compat] error: {error}")
    if args.strict and result != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
