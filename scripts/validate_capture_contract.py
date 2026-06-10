#!/usr/bin/env python3
"""Validate harness capture manifest contract for portability handoff."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path


LEGACY_PATH_MARKERS = (
    "docs/99_generated",
    "docs/capability_pipeline",
    "docs/archive/records",
)
TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".json",
    ".mjs",
    ".js",
    ".ts",
    ".tsx",
    ".css",
    ".svg",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
}


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


def section_by_heading(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    start_index = -1
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start_index = index
            break
    if start_index == -1:
        return ""

    collected: list[str] = []
    for index in range(start_index + 1, len(lines)):
        line = lines[index]
        if line.startswith("## "):
            break
        collected.append(line)
    return "\n".join(collected)


def parse_bullet_rows(section: str) -> list[str]:
    rows: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        rows.append(stripped[2:].strip().strip("`"))
    return rows


def load_manifest(manifest_path: Path) -> tuple[list[str], list[str], list[str]]:
    markdown = manifest_path.read_text(encoding="utf-8")
    include_patterns = parse_bullet_rows(section_by_heading(markdown, "## Include Globs"))
    exclude_patterns = parse_bullet_rows(section_by_heading(markdown, "## Exclude Globs"))
    allowed_legacy_refs = parse_bullet_rows(section_by_heading(markdown, "## Allowed Legacy Reference Files"))
    return include_patterns, exclude_patterns, allowed_legacy_refs


def expand_patterns(repo_root: Path, patterns: list[str]) -> tuple[dict[str, list[str]], set[Path]]:
    matches_by_pattern: dict[str, list[str]] = {}
    files: set[Path] = set()

    for pattern in patterns:
        matched_paths = sorted(repo_root.glob(pattern))
        matches_by_pattern[pattern] = [path.relative_to(repo_root).as_posix() for path in matched_paths]
        for path in matched_paths:
            if path.is_file():
                files.add(path.resolve())
                continue
            if path.is_dir():
                for nested in path.rglob("*"):
                    if nested.is_file():
                        files.add(nested.resolve())
    return matches_by_pattern, files


def is_allowed_legacy_reference(relative_path: str, allowlist: list[str]) -> bool:
    return any(fnmatch(relative_path, pattern) for pattern in allowlist)


def should_scan_for_legacy_refs(path: Path) -> bool:
    if path.name == "Makefile":
        return True
    return path.suffix in TEXT_EXTENSIONS


def validate_capture_manifest(
    repo_root: Path,
    manifest_path: Path,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []

    if not manifest_path.is_file():
        return [ValidationIssue(path=manifest_path.as_posix(), message="capture manifest is missing")], []

    include_patterns, exclude_patterns, allowed_legacy_refs = load_manifest(manifest_path)
    if not include_patterns:
        issues.append(ValidationIssue(path=manifest_path.relative_to(repo_root).as_posix(), message="no include globs declared"))
        return issues, []
    if not exclude_patterns:
        issues.append(ValidationIssue(path=manifest_path.relative_to(repo_root).as_posix(), message="no exclude globs declared"))

    include_matches, included_raw = expand_patterns(repo_root, include_patterns)
    exclude_matches, excluded_files = expand_patterns(repo_root, exclude_patterns)

    for pattern, matches in include_matches.items():
        if not matches:
            issues.append(ValidationIssue(path=manifest_path.relative_to(repo_root).as_posix(), message=f"include glob has no matches: {pattern}"))
    included_files = sorted(path for path in included_raw if path not in excluded_files)
    if not included_files:
        issues.append(ValidationIssue(path=manifest_path.relative_to(repo_root).as_posix(), message="no files remain after applying exclude globs"))
        return issues, []

    for file_path in included_files:
        relative_path = file_path.relative_to(repo_root).as_posix()
        if not should_scan_for_legacy_refs(file_path):
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in LEGACY_PATH_MARKERS:
            if marker not in content:
                continue
            if is_allowed_legacy_reference(relative_path, allowed_legacy_refs):
                continue
            issues.append(
                ValidationIssue(
                    path=relative_path,
                    message=f"contains legacy path marker '{marker}' without allowlist entry",
                )
            )

    return issues, [path.relative_to(repo_root).as_posix() for path in included_files]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/references/generic_harness_capture_manifest_v1.md"),
        help="Capture manifest path relative to repo root.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    manifest_path = (repo_root / args.manifest).resolve() if not args.manifest.is_absolute() else args.manifest.resolve()

    issues, included_files = validate_capture_manifest(repo_root, manifest_path)
    if issues:
        print("[capture-contract] fail")
        for issue in issues:
            print(f"[capture-contract] {issue.path}: {issue.message}")
        return 1

    print(f"[capture-contract] pass files={len(included_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
