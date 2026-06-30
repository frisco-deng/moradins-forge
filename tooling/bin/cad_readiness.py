#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import glob
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ALLOWED_ENGINES = {"build123d", "cadquery", "openscad", "freecad"}
PYTHON_ENGINES = {
    "build123d": "build123d",
    "cadquery": "cadquery",
}
COMMAND_ENGINES = {
    "openscad": ("openscad",),
    "freecad": ("FreeCADCmd", "freecadcmd", "freecad"),
}
COMMAND_VERSION_ARGS = {
    "openscad": ("--version",),
}
COMMAND_PROBE_TIMEOUT_SECONDS = 5
DEFAULT_SOURCE_GLOBS = [
    "cad/**/*.py",
    "cad/**/*.scad",
    "models/**/*.py",
    "models/**/*.scad",
    "parts/**/*.py",
    "parts/**/*.scad",
]
DEFAULT_EXPORT_GLOBS = [
    "artifacts/tooling/cad/exports/**/*",
    "artifacts/cad/**/*",
]
GENERATED_SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "artifacts",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "required", "on"}
    return bool(value)


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def load_cad_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = read_json(config_path)
    repo_cfg = payload.get("repo", {}) if isinstance(payload.get("repo"), dict) else {}
    cad_cfg = {}
    if isinstance(repo_cfg.get("cad"), dict):
        cad_cfg.update(repo_cfg["cad"])
    if isinstance(payload.get("cad"), dict):
        cad_cfg.update(payload["cad"])

    aliases = {
        "cad_profile": "profile",
        "cad_engine": "engine",
        "cad_required": "required",
        "cad_unit": "unit",
        "unit_policy": "unit",
    }
    for source in (repo_cfg, payload):
        for source_key, dest_key in aliases.items():
            if source_key in source and source[source_key] not in ("", None):
                cad_cfg[dest_key] = source[source_key]
    return cad_cfg, payload


def python_module_available(module_name: str, repo_root: Path) -> tuple[bool, str, str]:
    spec = importlib.util.find_spec(module_name)
    source = "python_environment"
    if spec is None:
        spec = importlib.machinery.PathFinder.find_spec(module_name, [str(repo_root)])
        source = "repo_root"
    if spec is None:
        return False, "", ""
    try:
        version = importlib.metadata.version(module_name)
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    return True, source, version


def command_version_probe(engine: str, executable_path: str) -> dict[str, Any]:
    args = COMMAND_VERSION_ARGS.get(engine)
    if not args:
        return {
            "smoke_status": "skipped",
            "smoke_command": "",
            "version": "unknown_not_probed",
            "message": "no version smoke is configured for this CAD engine",
        }
    command = [executable_path, *args]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "smoke_status": "fail",
            "smoke_command": " ".join(command),
            "version": "unknown",
            "message": f"version smoke failed: {exc}",
        }
    combined_output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    version_line = combined_output.splitlines()[0].strip() if combined_output else "unknown"
    return {
        "smoke_status": "pass" if result.returncode == 0 else "fail",
        "smoke_command": " ".join(command),
        "version": version_line,
        "message": "version smoke passed" if result.returncode == 0 else f"version smoke exited {result.returncode}",
    }


def engine_availability(engine: str, repo_root: Path) -> dict[str, Any]:
    normalized = engine.strip().lower()
    if not normalized:
        return {
            "engine": "",
            "available": False,
            "availability_class": "not_declared",
            "path_or_source": "",
            "version": "",
            "smoke_status": "skipped",
            "smoke_command": "",
            "message": "no CAD engine declared",
        }
    if normalized not in ALLOWED_ENGINES:
        return {
            "engine": normalized,
            "available": False,
            "availability_class": "unsupported_engine",
            "path_or_source": "",
            "version": "",
            "smoke_status": "skipped",
            "smoke_command": "",
            "message": f"unsupported CAD engine `{normalized}`",
        }
    if normalized in PYTHON_ENGINES:
        module_name = PYTHON_ENGINES[normalized]
        available, source, version = python_module_available(module_name, repo_root)
        return {
            "engine": normalized,
            "available": available,
            "availability_class": "available" if available else "missing_python_module",
            "path_or_source": source,
            "version": version if available else "",
            "smoke_status": "skipped",
            "smoke_command": "",
            "message": f"Python module `{module_name}` is {'available' if available else 'missing'}",
        }

    for executable in COMMAND_ENGINES.get(normalized, ()):
        resolved = shutil.which(executable)
        if resolved:
            probe = command_version_probe(normalized, resolved)
            return {
                "engine": normalized,
                "available": True,
                "availability_class": "available" if probe["smoke_status"] != "fail" else "available_probe_failed",
                "path_or_source": resolved,
                "version": probe["version"],
                "smoke_status": probe["smoke_status"],
                "smoke_command": probe["smoke_command"],
                "message": f"command `{executable}` is available; {probe['message']}",
            }
    return {
        "engine": normalized,
        "available": False,
        "availability_class": "missing_executable",
        "path_or_source": "",
        "version": "",
        "smoke_status": "skipped",
        "smoke_command": "",
        "message": "no matching CAD executable found on PATH",
    }


def glob_files(repo_root: Path, patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        for raw in glob.glob(str(repo_root / pattern), recursive=True):
            path = Path(raw)
            if not path.is_file():
                continue
            try:
                parts = path.resolve().relative_to(repo_root.resolve()).parts
            except ValueError:
                parts = path.parts
            if any(part in GENERATED_SKIP_PARTS for part in parts):
                continue
            files.append(path)
    return sorted(set(files))


def newest_mtime(paths: list[Path]) -> float:
    mtimes: list[float] = []
    for path in paths:
        try:
            mtimes.append(path.stat().st_mtime)
        except OSError:
            continue
    return max(mtimes) if mtimes else 0.0


def summary_exports(summary: dict[str, Any], repo_root: Path) -> list[Path]:
    candidates: list[str] = []
    for key in ("exports", "export_paths", "generated_exports"):
        value = summary.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    candidate = item.get("path") or item.get("file")
                else:
                    candidate = item
                if candidate:
                    candidates.append(str(candidate))
    cad = summary.get("cad")
    if isinstance(cad, dict):
        candidates.extend(str(item) for item in as_list(cad.get("exports")))
    paths: list[Path] = []
    for candidate in candidates:
        path = Path(candidate)
        paths.append(path if path.is_absolute() else repo_root / path)
    return paths


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.expanduser().resolve()
    config_path = args.config.expanduser().resolve() if args.config else repo_root / "tooling" / "configs" / "tooling-targets.json"
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else repo_root / "artifacts" / "tooling" / "cad"
    configured, target_config = load_cad_config(config_path)

    if args.profile:
        configured["profile"] = args.profile
    if args.engine:
        configured["engine"] = args.engine
    if args.unit:
        configured["unit"] = args.unit
    if args.required:
        configured["required"] = True

    profile = str(configured.get("profile") or "").strip()
    engine = str(configured.get("engine") or "").strip().lower()
    required = as_bool(configured.get("required", False))
    unit = str(configured.get("unit") or configured.get("unit_policy") or "mm").strip() or "mm"
    source_globs = as_list(configured.get("source_globs")) or DEFAULT_SOURCE_GLOBS
    export_globs = as_list(configured.get("export_globs")) or as_list(configured.get("exports")) or DEFAULT_EXPORT_GLOBS
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary
        else repo_root / str(configured.get("summary_path") or "artifacts/tooling/cad/summary.json")
    )

    cad_configured = bool(profile or engine or configured)
    source_files = glob_files(repo_root, source_globs)
    export_files = glob_files(repo_root, export_globs)
    artifact_summary = read_json(summary_path)
    if artifact_summary:
        export_files = sorted(set(export_files + [path for path in summary_exports(artifact_summary, repo_root) if path.exists()]))

    availability = engine_availability(engine, repo_root)
    newest_source = newest_mtime(source_files)
    newest_export = newest_mtime(export_files)
    summary_mtime = 0.0
    try:
        summary_mtime = summary_path.stat().st_mtime
    except OSError:
        summary_mtime = 0.0
    summary_fresh = bool(summary_mtime and (not newest_source or summary_mtime >= newest_source))
    exports_fresh = bool(export_files and (not newest_source or newest_export >= newest_source))

    findings: list[str] = []
    blockers: list[str] = []
    next_actions: list[str] = []
    status = "pass"
    if not cad_configured:
        status = "not_configured"
        findings.append("no CAD profile is declared for this repo")
        next_actions.append("declare cad_profile and cad_engine in the repo catalog or adapter only when CAD evidence is needed")
    else:
        if not profile:
            findings.append("CAD profile is missing; expected mechanical-parametric for mechanical CAD repos")
        if not engine:
            findings.append("CAD engine is missing; expected build123d, cadquery, openscad, or freecad")
        if availability["availability_class"] == "unsupported_engine":
            message = availability["message"]
            (blockers if required else findings).append(message)
            status = "fail" if required else "warn"
        elif not availability["available"]:
            message = f"CAD engine unavailable: {availability['message']}"
            (blockers if required else findings).append(message)
            status = "fail" if required else "warn"
        elif availability.get("smoke_status") == "fail":
            message = f"CAD engine version smoke failed: {availability['message']}"
            (blockers if required else findings).append(message)
            status = "fail" if required else "warn"
        if not source_files:
            findings.append("no CAD source files matched the configured source globs")
        if not artifact_summary:
            message = f"CAD summary artifact is missing: {relpath(summary_path, repo_root)}"
            (blockers if required else findings).append(message)
            status = "fail" if required else ("warn" if status == "pass" else status)
        elif not summary_fresh:
            message = "CAD summary artifact is older than CAD source files"
            (blockers if required else findings).append(message)
            status = "fail" if required else ("warn" if status == "pass" else status)
        if required and not export_files:
            blockers.append("required CAD profile has no export artifacts")
            status = "fail"
        elif artifact_summary and not export_files:
            findings.append("CAD summary exists but no export artifact paths were found")
            if status == "pass":
                status = "warn"
        elif export_files and not exports_fresh:
            message = "CAD export artifacts are older than CAD source files"
            (blockers if required else findings).append(message)
            status = "fail" if required else ("warn" if status == "pass" else status)

        if status == "fail":
            next_actions.append("run the repo-declared CAD export/check target after installing repo-local CAD dependencies")
        elif status == "warn":
            next_actions.append("refresh CAD summary/export artifacts before treating CAD evidence as current")
        else:
            next_actions.append("reuse the CAD summary artifact before reading raw CAD logs or exports")

    safety = {
        "cad_scripts_are_code": True,
        "untrusted_conversion_recommendation": "use existing sandbox/container lanes before running untrusted CAD scripts or converters",
        "large_outputs_policy": "keep generated CAD exports under artifacts/ unless a design review explicitly requires a tracked document",
        "raw_log_policy": "prefer artifacts/tooling/cad/summary.json over raw CAD/export logs when the summary is fresh",
    }
    report = {
        "schema_version": 1,
        "report": "cad-readiness",
        "generated_at": utc_now(),
        "repo_root": str(repo_root),
        "status": status,
        "cad_configured": cad_configured,
        "cad_profile": profile,
        "cad_engine": engine,
        "cad_required": required,
        "unit_policy": unit,
        "config_path": str(config_path) if config_path.exists() else "",
        "engine_availability": availability,
        "source_globs": source_globs,
        "source_files": [relpath(path, repo_root) for path in source_files],
        "export_globs": export_globs,
        "exports": [relpath(path, repo_root) for path in export_files],
        "artifact_summary": {
            "path": relpath(summary_path, repo_root),
            "exists": bool(artifact_summary),
            "fresh_for_sources": summary_fresh,
            "summary_status": str(artifact_summary.get("status") or "") if artifact_summary else "",
            "reported_engine": str(artifact_summary.get("cad_engine") or artifact_summary.get("engine") or "") if artifact_summary else "",
        },
        "artifact_freshness": {
            "source_file_count": len(source_files),
            "export_count": len(export_files),
            "summary_fresh_for_sources": summary_fresh,
            "exports_fresh_for_sources": exports_fresh,
        },
        "safety": safety,
        "findings": findings,
        "blockers": blockers,
        "next_actions": next_actions,
        "artifacts": {
            "summary_json": str(output_dir / "summary.json"),
            "summary_md": str(output_dir / "summary.md"),
            "cad_summary_json": relpath(summary_path, repo_root),
        },
        "target_config_seen": bool(target_config),
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    availability = report["engine_availability"]
    lines = [
        "# CAD Readiness",
        "",
        f"- status: `{report['status']}`",
        f"- cad_configured: `{str(report['cad_configured']).lower()}`",
        f"- profile: `{report['cad_profile'] or 'not_declared'}`",
        f"- engine: `{report['cad_engine'] or 'not_declared'}`",
        f"- required: `{str(report['cad_required']).lower()}`",
        f"- unit_policy: `{report['unit_policy']}`",
        f"- engine_available: `{str(availability['available']).lower()}`",
        f"- engine_availability_class: `{availability['availability_class']}`",
        f"- engine_version: `{availability.get('version') or 'not_observed'}`",
        f"- engine_smoke_status: `{availability.get('smoke_status') or 'skipped'}`",
        f"- source_files: `{len(report['source_files'])}`",
        f"- exports: `{len(report['exports'])}`",
        f"- cad_summary: `{report['artifact_summary']['path']}`",
        "",
        "Safety:",
        "",
        f"- {report['safety']['untrusted_conversion_recommendation']}",
        f"- {report['safety']['large_outputs_policy']}",
        f"- {report['safety']['raw_log_policy']}",
        "",
        "Findings:",
        "",
    ]
    lines.extend(f"- {item}" for item in report["findings"][:8])
    if not report["findings"]:
        lines.append("- none")
    if report["blockers"]:
        lines.extend(["", "Blockers:", ""])
        lines.extend(f"- {item}" for item in report["blockers"][:8])
    lines.extend(["", "Next Actions:", ""])
    lines.extend(f"- {item}" for item in report["next_actions"][:8])
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    (output_dir / "summary.md").write_text(render_markdown(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report optional mechanical CAD readiness for a repo.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root to inspect.")
    parser.add_argument("--config", type=Path, help="Path to tooling-targets.json.")
    parser.add_argument("--summary", type=Path, help="Existing CAD summary artifact to inspect.")
    parser.add_argument("--output-dir", type=Path, help="Directory for summary.json and summary.md.")
    parser.add_argument("--profile", choices=["mechanical-parametric"], help="Override or declare CAD profile for this run.")
    parser.add_argument("--engine", choices=sorted(ALLOWED_ENGINES), help="Override or declare CAD engine for this run.")
    parser.add_argument("--unit", help="Override unit policy, such as mm or inch.")
    parser.add_argument("--required", action="store_true", help="Treat missing engine, summary, or exports as failures.")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    args = parser.parse_args(argv)

    report = build_report(args)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else args.repo_root.expanduser().resolve() / "artifacts" / "tooling" / "cad"
    write_outputs(report, output_dir)

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=False))
    else:
        print(render_markdown(report), end="")
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
