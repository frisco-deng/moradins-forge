#!/usr/bin/env python3
"""Validate repository-local skill folder contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

REQUIRED_FRONTMATTER_KEYS = {"name", "description"}


@dataclass
class ValidationIssue:
    path: Path
    message: str


def parse_frontmatter(markdown: str) -> dict[str, str]:
    if not markdown.startswith("---\n"):
        return {}
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return {}
    block = markdown[4:end]
    data: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not match:
            continue
        data[match.group(1)] = match.group(2).strip().strip('"').strip("'")
    return data


def validate_skills_root(repo_root: Path) -> list[ValidationIssue]:
    skills_root = repo_root / "skills"
    issues: list[ValidationIssue] = []

    if not skills_root.exists():
        issues.append(ValidationIssue(path=skills_root, message="skills root is missing"))
        return issues

    for required in ("README.md", "index.md"):
        if not (skills_root / required).is_file():
            issues.append(ValidationIssue(path=skills_root / required, message="required skills root file missing"))

    for entry in sorted(skills_root.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            issues.append(ValidationIssue(path=entry, message="skill directory missing SKILL.md"))
            continue

        raw = skill_md.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(raw)
        missing = REQUIRED_FRONTMATTER_KEYS.difference(frontmatter.keys())
        if missing:
            issues.append(
                ValidationIssue(
                    path=skill_md,
                    message=f"SKILL.md missing frontmatter key(s): {', '.join(sorted(missing))}",
                )
            )

    return issues


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    issues = validate_skills_root(repo_root)

    if not issues:
        print("[skills] pass")
        return 0

    print("[skills] fail")
    for issue in issues:
        print(f"[skills] {issue.path.relative_to(repo_root)}: {issue.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
