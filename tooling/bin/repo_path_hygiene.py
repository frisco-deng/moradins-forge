#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
PLACEHOLDER = "<workspace-root>"
TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".csv",
    ".cxx",
    ".env",
    ".example",
    ".go",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".mjs",
    ".cjs",
    ".md",
    ".ndjson",
    ".py",
    ".rb",
    ".rego",
    ".rs",
    ".rst",
    ".sh",
    ".sql",
    ".svg",
    ".tf",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".rb",
    ".rego",
    ".rs",
    ".sh",
    ".sql",
    ".ts",
    ".tsx",
}
EXCLUDE_GLOBS = (
    ".git/**",
    ".venv/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    ".ruff_cache/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".next/**",
    ".turbo/**",
    "coverage/**",
    ".cache/**",
    "Harness/artifacts/reports/**",
    "migration" + "_reports/**",
)
LINUX_HOME_PREFIX = "/" + "home" + "/"
MAC_HOME_PREFIX = "/" + "Users" + "/"
PATH_PATTERNS = (
    re.compile(re.escape(LINUX_HOME_PREFIX) + r"[^/\s]+/code(?P<suffix>(?:/[A-Za-z0-9._%+@~=-]+)*)"),
    re.compile(re.escape(MAC_HOME_PREFIX) + r"[^/\s]+/code(?P<suffix>(?:/[A-Za-z0-9._%+@~=-]+)*)"),
)
SAFE_AUTO_FIX_CLASSES = {"docs_or_agents", "generated_report"}
GENERATOR_FIX_REQUIRED_CLASSES = {"generated_evidence", "shared_control_plane"}
MANUAL_CODE_FIX_CLASSES = {"source_or_test", "config_or_env_example"}
MANUAL_ARCHIVE_DECISION_CLASSES = {"archive_or_notebook"}


def tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        capture_output=True,
        text=False,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [repo_root / Path(chunk.decode("utf-8")) for chunk in result.stdout.split(b"\x00") if chunk]


def classify(relative_path: Path) -> str:
    relative = relative_path.as_posix()
    parts = set(relative_path.parts)
    suffix = relative_path.suffix.lower()
    name = relative_path.name
    if relative.startswith("docs/observability/generated/") or relative.startswith("systems_improvements/"):
        return "generated_report"
    if any(part in parts for part in {"artifacts", "reports", "public_audit", "release"}) and suffix in {
        ".json",
        ".jsonl",
        ".ndjson",
        ".md",
        ".csv",
        ".svg",
        ".html",
    }:
        return "generated_evidence"
    if suffix == ".ipynb" or any(part in parts for part in {"archive", "_archive", "notebooks"}):
        return "archive_or_notebook"
    if name in {"AGENTS.md", "README.md"} or "docs" in parts or suffix == ".md":
        return "docs_or_agents"
    if name.startswith(".env") or name.endswith(".env.example") or name.endswith(".example"):
        return "config_or_env_example"
    if suffix in CODE_EXTENSIONS or any(part in parts for part in {"tests", "test", "__tests__", "__mocks__"}):
        return "source_or_test"
    return "source_or_test"


def remediation_for(class_name: str) -> str:
    if class_name in SAFE_AUTO_FIX_CLASSES:
        return "safe_auto_fix"
    if class_name in GENERATOR_FIX_REQUIRED_CLASSES:
        return "generator_fix_required"
    if class_name in MANUAL_ARCHIVE_DECISION_CLASSES:
        return "manual_archive_decision"
    if class_name in MANUAL_CODE_FIX_CLASSES:
        return "manual_code_fix"
    return "manual_code_fix"


def _should_skip(relative_path: str) -> bool:
    return any(fnmatch(relative_path, pattern) for pattern in EXCLUDE_GLOBS)


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {"AGENTS.md", "README.md"}:
        return None
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _find_matches(text: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for pattern in PATH_PATTERNS:
        for match in pattern.finditer(text):
            matches.append((match.group(0), match.group("suffix") or ""))
    return matches


def collect_findings(repo_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for tracked in tracked_files(repo_root):
        relative = tracked.relative_to(repo_root)
        relative_text = relative.as_posix()
        if _should_skip(relative_text):
            continue
        text = _read_text(tracked)
        if text is None:
            continue
        matches = _find_matches(text)
        if not matches:
            continue
        class_name = classify(relative)
        findings.append(
            {
                "file_path": relative_text,
                "class_name": class_name,
                "remediation": remediation_for(class_name),
                "hit_count": len(matches),
                "sample": matches[0][0].replace(matches[0][0], f"{PLACEHOLDER}{matches[0][1]}"),
            }
        )
    return findings


def rewrite_safe(repo_root: Path, findings: list[dict[str, Any]]) -> list[str]:
    rewritten: list[str] = []
    for finding in findings:
        if finding["remediation"] != "safe_auto_fix":
            continue
        file_path = repo_root / finding["file_path"]
        original = file_path.read_text(encoding="utf-8")
        updated = original
        for pattern in PATH_PATTERNS:
            updated = pattern.sub(lambda match: f"{PLACEHOLDER}{match.group('suffix') or ''}", updated)
        if updated != original:
            file_path.write_text(updated, encoding="utf-8")
            rewritten.append(finding["file_path"])
    return rewritten


def artifact_dir(repo_root: Path) -> Path:
    target_root = repo_root / "artifacts" / "tooling" / "path-hygiene"
    target_root.mkdir(parents=True, exist_ok=True)
    return target_root


def write_report(repo_root: Path, findings: list[dict[str, Any]]) -> dict[str, str]:
    output_dir = artifact_dir(repo_root)
    summary = {
        "total_hits": sum(item["hit_count"] for item in findings),
        "total_files": len(findings),
        "hits_by_class": {
            class_name: sum(item["hit_count"] for item in findings if item["class_name"] == class_name)
            for class_name in sorted({item["class_name"] for item in findings})
        },
        "hits_by_remediation": {
            remediation: sum(item["hit_count"] for item in findings if item["remediation"] == remediation)
            for remediation in sorted({item["remediation"] for item in findings})
        },
        "placeholder": PLACEHOLDER,
    }
    summary_path = output_dir / "summary.json"
    findings_path = output_dir / "findings.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    findings_path.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"summary_json": str(summary_path), "findings_json": str(findings_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Repo-local path hygiene checker for rendered adapters.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rewrite-safe", action="store_true")
    parser.add_argument("--refresh-report", action="store_true")
    args = parser.parse_args()
    findings = collect_findings(REPO_ROOT)
    rewritten: list[str] = []
    if args.rewrite_safe:
        rewritten = rewrite_safe(REPO_ROOT, findings)
        findings = collect_findings(REPO_ROOT)
    report_paths = write_report(REPO_ROOT, findings) if args.refresh_report or args.check or args.rewrite_safe else {}
    payload = {
        "status": "pass" if not findings else "fail",
        "findings": findings,
        "rewritten": rewritten,
        "artifacts": report_paths,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.check and findings:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
