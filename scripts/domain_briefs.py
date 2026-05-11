#!/usr/bin/env python3
"""Write deterministic Moradin domain briefs for assistant handoff."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Iterable


BRIEF_ROOT = Path("Harness/artifacts/task_lanes")


@dataclass(frozen=True)
class Brief:
    version: str
    brief_id: str
    generated_at: str
    repo_root: str
    title: str
    summary: str
    deterministic_commands: list[str]
    source_docs: list[str]
    artifact_paths: dict[str, str]


BRIEF_SPECS = {
    "builder": {
        "title": "Builder Brief",
        "summary": "Guided deploy state for readiness, payload materialization, sidecar adoption, and verification.",
        "commands": ["make payload-validate", "make payload-smoke", "make verify-fast"],
        "docs": [
            "docs/11_ops/project_builder_runbook.md",
            "docs/design_docs/project_builder_control_api.md",
            "docs/product_specs/project_builder_ui.md",
        ],
    },
    "adoption": {
        "title": "Adoption Brief",
        "summary": "Existing-repo adoption posture, repo registry reuse, sidecar boundary, and next rerun advice.",
        "commands": ["make repo-brief", "make verify-fast", "make review-ready"],
        "docs": [
            "docs/references/repo_registry_adapter_contract_v1.md",
            "docs/11_ops/project_builder_runbook.md",
            "docs/11_ops/quick_start.md",
        ],
    },
    "release": {
        "title": "Release Brief",
        "summary": "Release evidence gates, payload compatibility bridge, and human-gated promotion posture.",
        "commands": [
            "make review-ready",
            "make verify-security",
            "make release-check",
            "make alignment-proof",
        ],
        "docs": [
            "docs/references/moradin_payload_contract_v1.md",
            "docs/15_checklists/project_builder_release_checklist.md",
            "docs/11_ops/quick_start.md",
        ],
    },
}


def _run_git(repo_root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _read_first_heading(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        return ""
    return ""


def build_brief(repo_root: Path, brief_id: str) -> Brief:
    spec = BRIEF_SPECS[brief_id]
    generated_at = datetime.now(timezone.utc).isoformat()
    output_dir = repo_root / BRIEF_ROOT / brief_id
    json_path = output_dir / "brief.json"
    md_path = output_dir / "brief.md"
    branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    dirty = bool(_run_git(repo_root, ["status", "--porcelain=v1"]))
    doc_titles = [
        _read_first_heading(repo_root / doc_path) or doc_path
        for doc_path in spec["docs"]
    ]
    summary = (
        f"{spec['summary']} Branch={branch}; dirty={dirty}; docs={len(doc_titles)}."
    )
    return Brief(
        version="MoradinDomainBriefV1",
        brief_id=brief_id,
        generated_at=generated_at,
        repo_root=str(repo_root),
        title=spec["title"],
        summary=summary,
        deterministic_commands=list(spec["commands"]),
        source_docs=list(spec["docs"]),
        artifact_paths={
            "json": str(json_path.relative_to(repo_root)),
            "markdown": str(md_path.relative_to(repo_root)),
        },
    )


def render_markdown(brief: Brief) -> str:
    lines = [
        f"# {brief.title}",
        "",
        f"- brief_id: {brief.brief_id}",
        f"- generated_at: {brief.generated_at}",
        "",
        "## Summary",
        "",
        brief.summary,
        "",
        "## Deterministic Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in brief.deterministic_commands)
    lines.extend(["", "## Source Docs", ""])
    lines.extend(f"- `{doc}`" for doc in brief.source_docs)
    return "\n".join(lines).strip() + "\n"


def write_brief(repo_root: Path, brief_id: str) -> Brief:
    brief = build_brief(repo_root, brief_id)
    output_dir = repo_root / BRIEF_ROOT / brief_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "brief.json").write_text(
        json.dumps(asdict(brief), indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "brief.md").write_text(render_markdown(brief), encoding="utf-8")
    return brief


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", choices=sorted(BRIEF_SPECS), help="Brief to generate.")
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="Repository root."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    brief = write_brief(args.repo_root.resolve(), args.brief)
    if args.json:
        print(json.dumps(asdict(brief), indent=2))
    else:
        print(f"[domain-brief] wrote {brief.artifact_paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
