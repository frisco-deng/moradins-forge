#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()


def _templates_root() -> Path:
    for env_name in ("TPL_ROOT", "TPLDECK_ROOT"):
        value = os.environ.get(env_name)
        if value:
            candidate = Path(value).expanduser().resolve()
            if (candidate / "catalog" / "active_workspace_roots.yaml").exists():
                return candidate
    for candidate in (SCRIPT_PATH.parent, *SCRIPT_PATH.parents):
        if (candidate / "catalog" / "active_workspace_roots.yaml").exists() and (candidate / "scripts").exists():
            return candidate
    if SCRIPT_PATH.parent.name == "scripts":
        return SCRIPT_PATH.parent.parent
    return SCRIPT_PATH.parent.parent


TEMPLATES_ROOT = _templates_root()
ACTIVE_ROOTS = TEMPLATES_ROOT / "catalog" / "active_workspace_roots.yaml"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a comparative diagnostic brief for a failing subject and known-good control.")
    parser.add_argument("--repo", required=True, help="Repo id, for example waifu-stack.")
    parser.add_argument("--subject", required=True, help="Failing subject, for example vix.")
    parser.add_argument("--control", required=True, help="Known-good control, for example Nova Anime.")
    parser.add_argument("--symptom", required=True, help="Observed symptom, for example black-frame or NaN at KSampler.")
    parser.add_argument("--repo-root", type=Path, default=None, help="Repo root. Defaults to the active workspace registry when available.")
    parser.add_argument("--profile", default="generic", help="Diagnostic profile. Use checkpoint for checkpoint/render failures.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override artifact output directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of the concise text brief.")
    return parser.parse_args()


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def _workspace_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "shared-tooling-source").exists():
            return candidate
    return TEMPLATES_ROOT.parent


def _repo_registry_paths() -> dict[str, Path]:
    if not ACTIVE_ROOTS.exists():
        return {}
    paths: dict[str, Path] = {}
    current_id = ""
    for line in ACTIVE_ROOTS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- repo_id:"):
            current_id = stripped.split(":", 1)[1].strip().strip('"')
            continue
        if current_id and stripped.startswith("path:"):
            raw_path = stripped.split(":", 1)[1].strip().strip('"')
            paths[current_id] = _workspace_root() / raw_path
            current_id = ""
    return paths


def _resolve_repo_root(repo_id: str, explicit_root: Path | None) -> Path:
    if explicit_root is not None:
        return explicit_root.resolve()
    registry_path = _repo_registry_paths().get(repo_id)
    if registry_path is not None:
        return registry_path.resolve()
    return Path.cwd().resolve()


def _git_state(repo_root: Path) -> dict[str, Any]:
    if _run(["git", "rev-parse", "--git-dir"], cwd=repo_root).returncode != 0:
        return {"available": False, "branch": "not-git", "head_sha": "", "dirty": None, "state_fingerprint": ""}
    branch = _run(["git", "branch", "--show-current"], cwd=repo_root).stdout.strip() or "detached"
    head = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
    status = _run(["git", "status", "--short"], cwd=repo_root).stdout
    dirty = bool(status.strip())
    material = json.dumps({"branch": branch, "head": head, "dirty": dirty, "status": status.splitlines()}, sort_keys=True)
    return {
        "available": True,
        "branch": branch,
        "head_sha": head,
        "dirty": dirty,
        "status_lines": [line for line in status.splitlines() if line.strip()],
        "state_fingerprint": hashlib.sha256(material.encode("utf-8")).hexdigest()[:16],
    }


def _latest_artifacts(repo_root: Path) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for root in [
        repo_root / "artifacts" / "tooling" / "latest",
        repo_root / "artifacts" / "task_lanes",
        repo_root / "artifacts" / "diagnostics",
    ]:
        if root.exists():
            candidates.extend(path for path in root.rglob("*.json") if path.is_file())
    artifacts: list[dict[str, Any]] = []
    for path in sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[:12]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        artifacts.append(
            {
                "path": str(path),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "target": payload.get("target") or payload.get("brief") or payload.get("diagnostic", {}).get("profile") or path.stem,
                "status": payload.get("status", "unknown"),
                "failure_fingerprint": payload.get("analysis", {}).get("failure_fingerprint", ""),
                "repo_state_fingerprint": payload.get("analysis", {}).get("repo_state_fingerprint", ""),
            }
        )
    return artifacts


def _checkpoint_axes(subject: str, control: str, symptom: str) -> list[dict[str, str]]:
    subject_label = subject.strip() or "subject"
    control_label = control.strip() or "control"
    subject_lower = subject_label.lower()
    control_lower = control_label.lower()
    vix_subject = "vix" in subject_lower
    nova_control = "nova" in control_lower
    return [
        {
            "axis": "source metadata",
            "subject": f"{subject_label}: inspect checkpoint recipe metadata and imported Civitai translation fields",
            "control": f"{control_label}: inspect the same fields from the known-good recipe",
            "diagnostic_question": "Are both recipes being normalized through the same semantic translation layer?",
        },
        {
            "axis": "clipSkip",
            "subject": f"{subject_label}: clipSkip 1 should be identity/default semantics; do not emit CLIPSetLastLayer(-1)" if vix_subject else f"{subject_label}: determine whether the value means identity/default or an actual skip",
            "control": f"{control_label}: clipSkip 2 is a real skip and maps to CLIPSetLastLayer(stop_at_clip_layer=-2)" if nova_control else f"{control_label}: confirm whether the control value is an actual skip",
            "diagnostic_question": "Is a UI identity value being translated into a runtime mutation?",
        },
        {
            "axis": "scheduler",
            "subject": f"{subject_label}: compare scheduler value at the first sampler boundary",
            "control": f"{control_label}: compare scheduler value at the first sampler boundary",
            "diagnostic_question": "Does the failure begin before scheduler choice matters?",
        },
        {
            "axis": "sampler",
            "subject": f"{subject_label}: inspect KSampler inputs and first emitted latent statistics",
            "control": f"{control_label}: inspect KSampler inputs and first emitted latent statistics",
            "diagnostic_question": "Is the first invalid stage KSampler rather than image save or hires routing?",
        },
        {
            "axis": "CFG",
            "subject": f"{subject_label}: compare CFG against recipe/control",
            "control": f"{control_label}: compare CFG against recipe/control",
            "diagnostic_question": "Is guidance strength actually divergent?",
        },
        {
            "axis": "dimensions",
            "subject": f"{subject_label}: compare base and hires dimensions",
            "control": f"{control_label}: compare base and hires dimensions",
            "diagnostic_question": "Do dimensions change the failure, or is it invariant across dimensions?",
        },
        {
            "axis": "hires route",
            "subject": f"{subject_label}: bypass hires and verify whether the black frame still occurs",
            "control": f"{control_label}: compare without changing unrelated checkpoint settings",
            "diagnostic_question": "Was the first hires-path fix plausible but downstream of the real invalid stage?",
        },
        {
            "axis": "VAE",
            "subject": f"{subject_label}: compare VAE source and decode boundary",
            "control": f"{control_label}: compare VAE source and decode boundary",
            "diagnostic_question": "Does the invalid tensor exist before VAE decode?",
        },
        {
            "axis": "tensor validity",
            "subject": f"{subject_label}: record finite/NaN/Inf counts at CLIP, KSampler, VAE decode, and SaveImage",
            "control": f"{control_label}: record the same finite/NaN/Inf counts",
            "diagnostic_question": "What is the first invalid tensor stage?",
        },
        {
            "axis": "image extrema",
            "subject": f"{subject_label}: record min/max/mean of the saved image and pre-save tensor",
            "control": f"{control_label}: record min/max/mean of the saved image and pre-save tensor",
            "diagnostic_question": "Is the black frame a rendering symptom of NaN-to-zero conversion?",
        },
        {
            "axis": "symptom",
            "subject": symptom,
            "control": "control remains image-producing under the same narrow matrix",
            "diagnostic_question": "Which single semantic delta explains subject failure while the control passes?",
        },
    ]


def _generic_axes(subject: str, control: str, symptom: str) -> list[dict[str, str]]:
    return [
        {"axis": "input contract", "subject": subject, "control": control, "diagnostic_question": "Are both paths receiving equivalent inputs?"},
        {"axis": "runtime/config semantics", "subject": subject, "control": control, "diagnostic_question": "Does one config value mean identity/default while another means mutate runtime state?"},
        {"axis": "first-invalid-stage", "subject": symptom, "control": "known-good output", "diagnostic_question": "Where does the first invalid value appear?"},
        {"axis": "artifact evidence", "subject": "latest failing artifact", "control": "latest passing artifact", "diagnostic_question": "Which prior artifact is still fresh for the current repo state?"},
    ]


def _build_payload(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    profile = args.profile.strip().lower() or "generic"
    use_checkpoint = profile in {"checkpoint", "waifu-stack-checkpoint"} or args.repo == "waifu-stack"
    axes = _checkpoint_axes(args.subject, args.control, args.symptom) if use_checkpoint else _generic_axes(args.subject, args.control, args.symptom)
    symptom_lower = args.symptom.lower()
    hypothesis = (
        "Treat the first sampler/tensor-validity boundary as suspect: black-frame/NaN symptoms often mean SaveImage exposed a downstream conversion symptom after an upstream invalid latent."
        if any(term in symptom_lower for term in ["black", "nan", "invalid", "sampler", "checkpoint"])
        else "Find the first stage where the failing subject diverges from the known-good control before changing downstream code."
    )
    if use_checkpoint and "vix" in args.subject.lower() and "nova" in args.control.lower():
        hypothesis = (
            "Compare clipSkip semantics first: Vix clipSkip 1 is identity/default and should not emit CLIPSetLastLayer(-1), "
            "while Nova Anime clipSkip 2 is a real skip and should emit CLIPSetLastLayer(stop_at_clip_layer=-2)."
        )
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "diagnostic": {
            "profile": "waifu-stack-checkpoint" if use_checkpoint else profile,
            "repo": args.repo,
            "subject": args.subject,
            "control": args.control,
            "symptom": args.symptom,
            "first_invalid_stage_hypothesis": hypothesis,
        },
        "repo": {"root": str(repo_root), "git": _git_state(repo_root)},
        "prior_artifacts": _latest_artifacts(repo_root),
        "control_matrix": axes,
        "next_actions": [
            "compare the subject and control on one axis at a time; do not patch broad verify/runtime code until the first-invalid-stage is identified",
            "reuse prior artifacts above when their repo_state_fingerprint matches the current state; otherwise rerun the narrow domain brief first",
            "for Waifu Stack checkpoint failures, verify clipSkip identity/default semantics before changing hires routing, sampler, or VAE code",
        ],
    }


def _write_artifact(payload: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = output_root / stamp
    latest_dir = output_root / "latest"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_json = artifact_dir / "summary.json"
    summary_md = artifact_dir / "summary.md"
    payload["artifacts"] = {"summary_json": str(summary_json), "summary_md": str(summary_md)}
    summary_json.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    _write_markdown(payload, summary_md)
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(artifact_dir, latest_dir)
    return summary_json, summary_md


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    diag = payload["diagnostic"]
    git = payload["repo"]["git"]
    lines = [
        "# Diagnostic Brief",
        "",
        f"- repo: `{diag['repo']}`",
        f"- profile: `{diag['profile']}`",
        f"- subject: `{diag['subject']}`",
        f"- control: `{diag['control']}`",
        f"- symptom: `{diag['symptom']}`",
        f"- branch: `{git.get('branch', 'unknown')}`",
        f"- dirty: `{git.get('dirty')}`",
        f"- repo_state_fingerprint: `{git.get('state_fingerprint', '') or 'unknown'}`",
        "",
        "## First Invalid Stage Hypothesis",
        "",
        diag["first_invalid_stage_hypothesis"],
        "",
        "## Control Matrix",
        "",
    ]
    for row in payload["control_matrix"]:
        lines.append(f"- `{row['axis']}`: subject `{row['subject']}`; control `{row['control']}`; question {row['diagnostic_question']}")
    lines.extend(["", "## Prior Artifacts", ""])
    for artifact in payload["prior_artifacts"] or [{"path": "none", "target": "none", "status": "none"}]:
        lines.append(f"- `{artifact['target']}`: `{artifact['status']}`; `{artifact['path']}`")
    lines.extend(["", "## Next Actions", ""])
    for action in payload["next_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = _parse_args()
    repo_root = _resolve_repo_root(args.repo, args.repo_root)
    output_root = args.output_dir or (repo_root / "artifacts" / "diagnostics" / "diagnostic-brief")
    payload = _build_payload(args, repo_root)
    summary_json, summary_md = _write_artifact(payload, output_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(f"[diagnostic-brief] repo={args.repo} subject={args.subject} control={args.control} symptom={args.symptom}")
        print(f"[diagnostic-brief] hypothesis={payload['diagnostic']['first_invalid_stage_hypothesis']}")
        print(f"[diagnostic-brief] summary_json={summary_json}")
        print(f"[diagnostic-brief] summary_md={summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
