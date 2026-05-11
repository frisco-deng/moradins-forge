#!/usr/bin/env python3
"""Write a deterministic new-repo onboarding brief."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Iterable


ARTIFACT_ROOT = Path("Harness/artifacts/task_lanes/onboarding")


@dataclass(frozen=True)
class OnboardingBrief:
    version: str
    generated_at: str
    repo_root: str
    repo_name: str
    summary: str
    first_run_path: list[str]
    deterministic_commands: list[str]
    source_docs: list[str]
    artifact_paths: dict[str, str]


def _git(repo_root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def build_onboarding_brief(repo_root: Path) -> OnboardingBrief:
    generated_at = datetime.now(timezone.utc).isoformat()
    repo_name = repo_root.name
    branch = _git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    summary = (
        f"{repo_name} is ready for Moradin onboarding through the first-run path. "
        f"Current branch: {branch}."
    )
    return OnboardingBrief(
        version="MoradinNewRepoOnboardingBriefV1",
        generated_at=generated_at,
        repo_root=str(repo_root),
        repo_name=repo_name,
        summary=summary,
        first_run_path=[
            "Home",
            "Quick Start",
            "Readiness",
            "Deploy Map",
            "Builder",
            "Verify",
        ],
        deterministic_commands=[
            "make payload-validate",
            "make repo-brief",
            "make verify-fast",
        ],
        source_docs=[
            "docs/11_ops/quick_start.md",
            "docs/references/moradin_payload_contract_v1.md",
            "docs/references/repo_registry_adapter_contract_v1.md",
        ],
        artifact_paths={
            "json": str((ARTIFACT_ROOT / "brief.json")),
            "markdown": str((ARTIFACT_ROOT / "brief.md")),
        },
    )


def render_markdown(brief: OnboardingBrief) -> str:
    lines = [
        "# New Repo Onboarding Brief",
        "",
        f"- generated_at: {brief.generated_at}",
        f"- repo_name: {brief.repo_name}",
        "",
        "## Summary",
        "",
        brief.summary,
        "",
        "## First-Run Path",
        "",
    ]
    lines.extend(
        f"{index}. {step}" for index, step in enumerate(brief.first_run_path, start=1)
    )
    lines.extend(["", "## Deterministic Commands", ""])
    lines.extend(f"- `{command}`" for command in brief.deterministic_commands)
    lines.extend(["", "## Source Docs", ""])
    lines.extend(f"- `{doc}`" for doc in brief.source_docs)
    return "\n".join(lines).strip() + "\n"


def write_onboarding_brief(repo_root: Path) -> OnboardingBrief:
    brief = build_onboarding_brief(repo_root)
    output_dir = repo_root / ARTIFACT_ROOT
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "brief.json").write_text(
        json.dumps(asdict(brief), indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "brief.md").write_text(render_markdown(brief), encoding="utf-8")
    return brief


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="Repository root."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    brief = write_onboarding_brief(args.repo_root.resolve())
    if args.json:
        print(json.dumps(asdict(brief), indent=2))
    else:
        print(f"[new-repo-onboarding] wrote {brief.artifact_paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
