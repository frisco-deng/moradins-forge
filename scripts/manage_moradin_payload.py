from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = REPO_ROOT / ".harness_template"
MORADIN_PAYLOAD_MANIFEST = REPO_ROOT / "Harness" / "moradin_payload" / "manifest.yaml"
MIGRATION_REPORTS_ROOT = REPO_ROOT / "public_audit"
HARNESS_GENERATED_ROOT = REPO_ROOT / "Harness" / "generated"
EXPECTED_TEMPLATE_VERSION = "0.2.0-beta.1"
EXPECTED_RELEASE_STAGE = "beta"
TEXT_EXTENSIONS = {
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".mjs",
    ".js",
    ".ts",
    ".tsx",
    ".css",
    ".svg",
}
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
PATH_REFERENCE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./-])(?:docs|Harness|\.harness_template)/[A-Za-z0-9_./-]+"
)
ALLOWED_MISSING_REFERENCE_PREFIXES = [
    "Harness/artifacts/control/discovery_sessions/",
    "docs/product_specs/discovery_",
    "docs/design_docs/discovery_",
    "docs/exec_plans/implementation/active/plan_",
    "docs/exec_plans/implementation/completed/plan_",
    "docs/exec_plans/implementation/active/sug_",
    "docs/11_ops/day",
    "docs/archive/records/",
    "docs/99_generated/",
    "docs/capability_pipeline/",
]
ALLOWED_MISSING_REFERENCE_EXACT = {
    "docs/product_specs/generated_profile_overlay.md",
    "docs/rules",
    "docs/plans",
}

REQUIRED_MANAGER_FILES = [
    Path("AGENTS.md"),
    Path("Harness/README.md"),
    Path("Harness/manifest.yaml"),
    Path("Harness/version.lock"),
    Path("Harness/moradin_payload/manifest.yaml"),
    Path("Harness/entrypoints/agent.md"),
    Path("Harness/routing/context_routes.yaml"),
    Path("Harness/routing/load_order.md"),
    Path("Harness/schemas/canonical_paths.yaml"),
    Path("docs/index.md"),
    Path("docs/01_principles/foundational_principles.md"),
    Path("docs/design_docs/index.md"),
    Path("docs/entrypoint_guide/index.md"),
    Path("docs/exec_plans/index.md"),
    Path("docs/product_specs/index.md"),
    Path("docs/references/index.md"),
    Path("docs/references/foundational_principles_source_synthesis.md"),
]

REQUIRED_MANAGER_DIRS = [
    Path("Harness/artifacts/control"),
    Path("Harness/artifacts/openapi"),
    Path("Harness/artifacts/reports"),
    Path("Harness/artifacts/schemas"),
    Path("docs/00_overview"),
    Path("docs/01_principles"),
    Path("docs/02_contracts"),
    Path("docs/03_architecture"),
    Path("docs/04_services"),
    Path("docs/05_ingestion"),
    Path("docs/06_retrieval"),
    Path("docs/07_storage"),
    Path("docs/08_observability"),
    Path("docs/09_evaluation"),
    Path("docs/10_security"),
    Path("docs/11_ops"),
    Path("docs/12_pipelines"),
    Path("docs/13_style_guides"),
    Path("docs/14_adrs"),
    Path("docs/15_checklists"),
    Path("docs/16_examples"),
    Path("docs/design_docs"),
    Path("docs/engineer_entry"),
    Path("docs/entrypoint_guide"),
    Path("docs/exec_plans"),
    Path("docs/product_specs"),
    Path("docs/generated"),
    Path("docs/archive"),
]

LEGACY_ALIAS_PATHS = [
    Path("docs/Entrypoint_guide"),
    Path("docs/design-docs"),
    Path("docs/exec-plans"),
    Path("docs/product-specs"),
    Path("docs/harness_artifacts"),
    Path("Harness/automation/upgrades/path_compat_map.yaml"),
]

LEGACY_MARKERS = [
    "docs/Entrypoint_guide",
    "docs/design-docs",
    "docs/exec-plans",
    "docs/product-specs",
    "docs/harness_artifacts",
    "path_compat_map.yaml",
]

ACTIVE_SCAN_ROOTS = [
    Path("AGENTS.md"),
    Path("README.md"),
    Path("Harness"),
    Path("docs/01_principles"),
    Path("docs/00_overview"),
    Path("docs/11_ops"),
    Path("docs/15_checklists"),
    Path("docs/index.md"),
    Path("docs/design_docs"),
    Path("docs/entrypoint_guide"),
    Path("docs/product_specs"),
    Path("docs/references"),
    Path("dev_tracker/ui/scripts"),
    Path("dev_tracker/ui/src"),
    Path("tests/contracts"),
    Path("tests/scripts"),
    Path("scripts"),
]

MANAGER_ONLY_SCAN_SKIP_PREFIXES = [
    Path("Harness/artifacts/control/review_hardening"),
    Path("public_audit/release_reports_excluded"),
    Path("public_audit/release_evidence_excluded"),
]

PUBLIC_FORGE_REQUIRED_FILES = [
    Path("AGENTS.md"),
    Path("FORGE.md"),
    Path("README.md"),
    Path("Makefile"),
    Path("pyproject.toml"),
    Path("Harness/moradin_payload/manifest.yaml"),
    Path("Harness/entrypoints/forge.md"),
    Path("scripts/moradin_forge.py"),
    Path("scripts/moradin_forge.sh"),
    Path("scripts/moradin_forge.ps1"),
    Path("scripts/manage_moradin_payload.py"),
    Path("scripts/public_export.py"),
]

PUBLIC_FORGE_REQUIRED_DIRS = [
    Path("Harness/entrypoints"),
    Path("Harness/moradin_payload"),
    Path("Harness/artifacts/control"),
    Path("Harness/artifacts/schemas"),
    Path("docs/11_ops"),
    Path("docs/design_docs"),
    Path("docs/engineer_entry"),
    Path("docs/product_specs"),
    Path("docs/references"),
    Path("dev_tracker/ui/scripts"),
    Path("dev_tracker/ui/src"),
    Path("dev_tracker/ui/tests"),
    Path("tests/contracts"),
    Path("tests/scripts"),
]

PUBLIC_ACTIVE_SCAN_ROOTS = [
    Path("AGENTS.md"),
    Path("FORGE.md"),
    Path("README.md"),
    Path("Harness/entrypoints"),
    Path("Harness/moradin_payload"),
    Path("Harness/artifacts/control"),
    Path("docs/11_ops"),
    Path("docs/design_docs"),
    Path("docs/product_specs"),
    Path("docs/references"),
    Path("dev_tracker/ui/scripts"),
    Path("dev_tracker/ui/src"),
    Path("tests/contracts"),
    Path("tests/scripts"),
    Path("scripts/moradin_forge.py"),
    Path("scripts/public_export.py"),
    Path("scripts/manage_moradin_payload.py"),
]

PUBLIC_REQUIRED_PAYLOAD_ROOTS = {
    "AGENTS.md",
    "FORGE.md",
    "Harness/moradin_payload/manifest.yaml",
    "Harness/entrypoints",
    "docs/references",
    "scripts/moradin_forge.py",
    "scripts/moradin_forge.sh",
    "scripts/moradin_forge.ps1",
}

REQUIRED_TEMPLATE_DIRS = [
    Path("Harness"),
    Path("Harness/entrypoints"),
    Path("Harness/routing"),
    Path("Harness/views"),
    Path("Harness/automation"),
    Path("Harness/automation/checks"),
    Path("Harness/automation/upgrades"),
    Path("Harness/automation/scripts"),
    Path("Harness/automation/cli"),
    Path("Harness/schemas"),
    Path("docs"),
    Path("docs/00_overview"),
    Path("docs/01_principles"),
    Path("docs/02_contracts"),
    Path("docs/03_architecture"),
    Path("docs/04_services"),
    Path("docs/05_ingestion"),
    Path("docs/06_retrieval"),
    Path("docs/07_storage"),
    Path("docs/08_observability"),
    Path("docs/09_evaluation"),
    Path("docs/10_security"),
    Path("docs/11_ops"),
    Path("docs/12_pipelines"),
    Path("docs/13_style_guides"),
    Path("docs/14_adrs"),
    Path("docs/15_checklists"),
    Path("docs/16_examples"),
    Path("docs/design_docs"),
    Path("docs/engineer_entry"),
    Path("docs/entrypoint_guide"),
    Path("docs/exec_plans"),
    Path("docs/product_specs"),
    Path("docs/references"),
    Path("docs/generated"),
    Path("docs/archive"),
]

REQUIRED_TEMPLATE_FILES = [
    Path("AGENTS.md"),
    Path("Harness/manifest.yaml"),
    Path("Harness/version.lock"),
    Path("Harness/entrypoints/agent.md"),
    Path("Harness/routing/context_routes.yaml"),
    Path("Harness/routing/load_order.md"),
    Path("docs/index.md"),
    Path("docs/00_overview/index.md"),
    Path("docs/01_principles/index.md"),
    Path("docs/01_principles/foundational_principles.md"),
    Path("docs/02_contracts/index.md"),
    Path("docs/03_architecture/index.md"),
    Path("docs/04_services/index.md"),
    Path("docs/05_ingestion/index.md"),
    Path("docs/06_retrieval/index.md"),
    Path("docs/07_storage/index.md"),
    Path("docs/08_observability/index.md"),
    Path("docs/09_evaluation/index.md"),
    Path("docs/10_security/index.md"),
    Path("docs/11_ops/index.md"),
    Path("docs/12_pipelines/index.md"),
    Path("docs/13_style_guides/index.md"),
    Path("docs/14_adrs/index.md"),
    Path("docs/15_checklists/index.md"),
    Path("docs/16_examples/index.md"),
    Path("docs/design_docs/index.md"),
    Path("docs/engineer_entry/index.md"),
    Path("docs/entrypoint_guide/index.md"),
    Path("docs/exec_plans/index.md"),
    Path("docs/product_specs/index.md"),
    Path("docs/references/index.md"),
    Path("docs/generated/index.md"),
    Path("docs/archive/index.md"),
]

TEMPLATE_PLACEHOLDER_INDEXES = [
    Path("docs/00_overview/index.md"),
    Path("docs/02_contracts/index.md"),
    Path("docs/03_architecture/index.md"),
    Path("docs/04_services/index.md"),
    Path("docs/05_ingestion/index.md"),
    Path("docs/06_retrieval/index.md"),
    Path("docs/07_storage/index.md"),
    Path("docs/08_observability/index.md"),
    Path("docs/09_evaluation/index.md"),
    Path("docs/10_security/index.md"),
    Path("docs/11_ops/index.md"),
    Path("docs/12_pipelines/index.md"),
    Path("docs/13_style_guides/index.md"),
    Path("docs/14_adrs/index.md"),
    Path("docs/15_checklists/index.md"),
    Path("docs/16_examples/index.md"),
    Path("docs/design_docs/index.md"),
    Path("docs/engineer_entry/index.md"),
    Path("docs/entrypoint_guide/index.md"),
    Path("docs/exec_plans/index.md"),
    Path("docs/product_specs/index.md"),
    Path("docs/references/index.md"),
    Path("docs/generated/index.md"),
    Path("docs/archive/index.md"),
]

FORBIDDEN_TEMPLATE_PATHS = [
    Path("dev_tracker"),
    Path("public_audit"),
    Path(".harness_devops"),
    Path(".builder_projects"),
    Path("skills"),
    Path("docs/Entrypoint_guide"),
    Path("docs/design-docs"),
    Path("docs/exec-plans"),
    Path("docs/product-specs"),
    Path("docs/harness_artifacts"),
]

FORBIDDEN_TEMPLATE_FILES = [
    Path("ARCHITECTURE.md"),
    Path("DESIGN.md"),
    Path("FRONTEND.md"),
    Path("HUMAN_REVIEW.md"),
    Path("PLANS.md"),
    Path("PRODUCT_SENSE.md"),
    Path("QUALITY_SCORE.md"),
    Path("RELIABILITY.md"),
    Path("SECURITY.md"),
]


@dataclass
class ValidationResult:
    ok: bool
    messages: list[str]


@dataclass
class SmokeTestResult:
    blank_target: str
    existing_target: str
    blank_ok: bool
    existing_ok: bool
    messages: list[str]


@dataclass
class DryRunSummary:
    available: bool
    blank_ok: bool
    existing_ok: bool
    blank_target: str
    existing_target: str
    messages: list[str]


def parse_simple_yaml(path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    current_list_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        if stripped.startswith("- "):
            if current_list_key is None:
                continue
            data.setdefault(current_list_key, [])
            assert isinstance(data[current_list_key], list)
            data[current_list_key].append(stripped[2:].strip())
            continue
        current_list_key = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            normalized = value.strip("'\"")
            if normalized.isdigit():
                data[key] = int(normalized)
            else:
                data[key] = normalized
        else:
            data[key] = []
            current_list_key = key
    return data


def read_dry_run_summary(report_path: Path) -> DryRunSummary:
    try:
        markdown = report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DryRunSummary(
            available=False,
            blank_ok=False,
            existing_ok=False,
            blank_target="",
            existing_target="",
            messages=[],
        )

    blank_target = re.search(r"- Blank target: `([^`]+)`", markdown)
    existing_target = re.search(r"- Existing fixture target: `([^`]+)`", markdown)
    messages = [
        line.replace("- ", "", 1).strip()
        for line in markdown.splitlines()
        if line.startswith("- ")
    ][4:12]
    return DryRunSummary(
        available=True,
        blank_ok="- Blank deployment: pass" in markdown,
        existing_ok="- Existing fixture overlay: pass" in markdown,
        blank_target=blank_target.group(1) if blank_target else "",
        existing_target=existing_target.group(1) if existing_target else "",
        messages=messages,
    )


def resolve_latest_existing_fixture_target(repo_root: Path) -> Path:
    dry_run_summary = read_dry_run_summary(
        repo_root / "public_audit" / "dry_run_smoke_test_report.md",
    )
    candidates: list[Path] = []
    if dry_run_summary.existing_target:
        candidates.append(resolve_reported_target(repo_root, dry_run_summary.existing_target))

    template_studio_path = (
        repo_root
        / "dev_tracker"
        / "ui"
        / "public"
        / "generated"
        / "template_studio_v1.json"
    )
    try:
        template_studio_payload = json.loads(
            template_studio_path.read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        template_studio_payload = {}
    except json.JSONDecodeError:
        template_studio_payload = {}
    template_studio_existing_target = str(
        template_studio_payload.get("dry_run", {}).get("existing_target", "")
    ).strip()
    if template_studio_existing_target:
        candidates.append(resolve_reported_target(repo_root, template_studio_existing_target))

    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        "Could not resolve the latest existing-project dry-run fixture from "
        "public_audit/dry_run_smoke_test_report.md or "
        "dev_tracker/ui/public/generated/template_studio_v1.json."
    )


def iter_text_files(scan_root: Path) -> list[Path]:
    files: list[Path] = []
    if not scan_root.exists():
        return files
    if scan_root.is_file():
        return (
            [scan_root]
            if scan_root.suffix in TEXT_EXTENSIONS
            or scan_root.name in {"AGENTS.md", "Makefile", "README.md"}
            else []
        )
    for root, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix in TEXT_EXTENSIONS or filename in {
                "AGENTS.md",
                "Makefile",
                "README.md",
            }:
                files.append(file_path)
    return files


def validate_manifest(
    path: Path, expected_kind: str, expected_project_type: str
) -> list[str]:
    errors: list[str] = []
    manifest = parse_simple_yaml(path)
    required = {
        "manifest_version",
        "name",
        "kind",
        "project_type",
        "docs_truth_root",
        "control_plane_root",
        "entrypoint",
        "template_id",
        "template_version",
        "path_convention",
        "release_stage",
    }
    missing = sorted(required - set(manifest))
    if missing:
        errors.append(f"{path}: missing manifest keys: {', '.join(missing)}")
    if manifest.get("kind") != expected_kind:
        errors.append(
            f"{path}: expected kind={expected_kind}, found {manifest.get('kind')!r}"
        )
    if manifest.get("project_type") != expected_project_type:
        errors.append(
            f"{path}: expected project_type={expected_project_type}, found {manifest.get('project_type')!r}"
        )
    if manifest.get("docs_truth_root") != "docs":
        errors.append(f"{path}: docs_truth_root must be 'docs'")
    if manifest.get("control_plane_root") != "Harness":
        errors.append(f"{path}: control_plane_root must be 'Harness'")
    if manifest.get("entrypoint") != "Harness/entrypoints/agent.md":
        errors.append(f"{path}: entrypoint must be 'Harness/entrypoints/agent.md'")
    if manifest.get("template_id") != "base_app":
        errors.append(f"{path}: template_id must be 'base_app'")
    if manifest.get("template_version") != EXPECTED_TEMPLATE_VERSION:
        errors.append(f"{path}: template_version must be {EXPECTED_TEMPLATE_VERSION!r}")
    if manifest.get("path_convention") != "snake_case":
        errors.append(f"{path}: path_convention must be 'snake_case'")
    if manifest.get("release_stage") != EXPECTED_RELEASE_STAGE:
        errors.append(f"{path}: release_stage must be {EXPECTED_RELEASE_STAGE!r}")
    if manifest.get("compatibility_mode") not in {None, "canonical_only"}:
        errors.append(
            f"{path}: compatibility_mode must be omitted or set to 'canonical_only'"
        )
    return errors


def validate_payload_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing Moradin payload manifest: {path.relative_to(REPO_ROOT)}"]
    manifest = parse_simple_yaml(path)
    if manifest.get("manifest_version") != 1:
        errors.append(f"{path}: manifest_version must be 1")
    if manifest.get("kind") != "moradin_payload":
        errors.append(f"{path}: kind must be 'moradin_payload'")
    if manifest.get("payload_id") != "moradin_harness_payload":
        errors.append(f"{path}: payload_id must be 'moradin_harness_payload'")
    if str(manifest.get("source_root", "")).strip() != ".":
        errors.append(
            f"{path}: source_root must be '.' during the bridge-first migration"
        )
    include_paths = manifest.get("include_paths", [])
    if not isinstance(include_paths, list) or not include_paths:
        errors.append(f"{path}: include_paths must be a non-empty list")
    else:
        missing = sorted(
            PUBLIC_REQUIRED_PAYLOAD_ROOTS.difference(str(item) for item in include_paths)
        )
        if missing:
            errors.append(
                f"{path}: include_paths missing required payload roots: {', '.join(missing)}"
            )
    return errors


def collect_path_references(base_root: Path, scan_roots: list[Path]) -> list[str]:
    missing: list[str] = []
    for relative_root in scan_roots:
        root = (
            relative_root if relative_root.is_absolute() else base_root / relative_root
        )
        for file_path in iter_text_files(root):
            if file_path.name == "canonical_paths.yaml":
                continue
            if is_manager_generated_output(base_root, file_path):
                continue
            if is_manager_only_scan_skip_path(base_root, file_path):
                continue
            text = file_path.read_text(encoding="utf-8")
            for raw_match in PATH_REFERENCE_PATTERN.findall(text):
                normalized = raw_match.rstrip(".,)")
                candidate = base_root / normalized
                if not candidate.exists() and not is_allowed_missing_reference(
                    normalized
                ):
                    missing.append(
                        f"{file_path.relative_to(base_root)} -> missing reference {normalized}"
                    )
    return missing


def is_allowed_missing_reference(relative_path: str) -> bool:
    if relative_path in ALLOWED_MISSING_REFERENCE_EXACT:
        return True
    return any(
        relative_path.startswith(prefix)
        for prefix in ALLOWED_MISSING_REFERENCE_PREFIXES
    )


def is_manager_generated_output(base_root: Path, file_path: Path) -> bool:
    try:
        relative = file_path.relative_to(base_root)
    except ValueError:
        return False
    return relative.parts[:2] == ("Harness", "generated")


def is_manager_only_scan_skip_path(base_root: Path, file_path: Path) -> bool:
    try:
        relative = file_path.relative_to(base_root)
    except ValueError:
        return False

    for prefix in MANAGER_ONLY_SCAN_SKIP_PREFIXES:
        if relative.parts[: len(prefix.parts)] == prefix.parts:
            return True
    return False


def collect_legacy_marker_hits(base_root: Path) -> list[str]:
    hits: list[str] = []
    for relative_root in ACTIVE_SCAN_ROOTS:
        root = base_root / relative_root
        for file_path in iter_text_files(root):
            if file_path.name in {"manage_harness_template.py", "canonical_paths.yaml"}:
                continue
            if is_manager_generated_output(base_root, file_path):
                continue
            if is_manager_only_scan_skip_path(base_root, file_path):
                continue
            text = file_path.read_text(encoding="utf-8")
            for marker in LEGACY_MARKERS:
                if marker in text:
                    hits.append(
                        f"{file_path.relative_to(base_root)} -> legacy marker {marker}"
                    )
    return hits


def validate_placeholder_metadata(template_root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path in TEMPLATE_PLACEHOLDER_INDEXES:
        content = (template_root / relative_path).read_text(encoding="utf-8")
        for required_marker in [
            "status: placeholder",
            "owner: ui_builder",
            "questions:",
        ]:
            if required_marker not in content:
                errors.append(
                    f"{relative_path}: missing placeholder marker {required_marker!r}"
                )
    return errors


def validate_template_root(template_root: Path) -> ValidationResult:
    messages: list[str] = []
    for required_dir in REQUIRED_TEMPLATE_DIRS:
        if not (template_root / required_dir).is_dir():
            messages.append(f"missing template directory: {required_dir}")
    for required_file in REQUIRED_TEMPLATE_FILES:
        if not (template_root / required_file).is_file():
            messages.append(f"missing template file: {required_file}")
    for forbidden in FORBIDDEN_TEMPLATE_PATHS:
        if (template_root / forbidden).exists():
            messages.append(f"forbidden source path leaked into template: {forbidden}")
    for forbidden in FORBIDDEN_TEMPLATE_FILES:
        if (template_root / forbidden).exists():
            messages.append(
                f"forbidden source-only file leaked into template: {forbidden}"
            )
    for directory in template_root.rglob("*"):
        if directory.is_dir() and "_placeholder" in directory.name:
            messages.append(
                f"forbidden placeholder directory name: {directory.relative_to(template_root)}"
            )
    agents_path = template_root / "AGENTS.md"
    if agents_path.is_file():
        agents_text = agents_path.read_text(encoding="utf-8")
        if "Harness/entrypoints/agent.md" not in agents_text:
            messages.append(
                "template AGENTS.md does not route to Harness/entrypoints/agent.md"
            )
    manifest_path = template_root / "Harness/manifest.yaml"
    if manifest_path.is_file():
        messages.extend(
            validate_manifest(manifest_path, "deployable_template", "base_app")
        )
    messages.extend(validate_placeholder_metadata(template_root))
    messages.extend(collect_path_references(template_root, [Path(".")]))
    return ValidationResult(ok=not messages, messages=messages)


def is_public_forge_repo(repo_root: Path) -> bool:
    return (repo_root / "FORGE.md").is_file() and not (repo_root / ".harness_template").exists()


def validate_manager_repo(repo_root: Path) -> ValidationResult:
    messages: list[str] = []
    public_mode = is_public_forge_repo(repo_root)
    required_files = PUBLIC_FORGE_REQUIRED_FILES if public_mode else REQUIRED_MANAGER_FILES
    required_dirs = PUBLIC_FORGE_REQUIRED_DIRS if public_mode else REQUIRED_MANAGER_DIRS
    active_scan_roots = PUBLIC_ACTIVE_SCAN_ROOTS if public_mode else ACTIVE_SCAN_ROOTS

    for required_file in required_files:
        if not (repo_root / required_file).exists():
            label = "public Forge" if public_mode else "source"
            messages.append(f"missing {label} file: {required_file}")
    for required_dir in required_dirs:
        if not (repo_root / required_dir).is_dir():
            label = "public Forge" if public_mode else "source"
            messages.append(f"missing {label} directory: {required_dir}")
    if not public_mode:
        for legacy_path in LEGACY_ALIAS_PATHS:
            if (repo_root / legacy_path).exists():
                messages.append(f"legacy alias path remains: {legacy_path}")
    agents_path = repo_root / "AGENTS.md"
    if agents_path.is_file():
        agents_text = agents_path.read_text(encoding="utf-8")
        required_entrypoint = (
            "Harness/entrypoints/forge.md" if public_mode else "Harness/entrypoints/agent.md"
        )
        if required_entrypoint not in agents_text:
            messages.append(
                f"root AGENTS.md does not route to {required_entrypoint}"
            )
    if not public_mode:
        manifest_path = repo_root / "Harness/manifest.yaml"
        if manifest_path.is_file():
            messages.extend(
                validate_manifest(manifest_path, "manager_repo", "manager_repo")
            )
    messages.extend(
        validate_payload_manifest(
            repo_root / "Harness" / "moradin_payload" / "manifest.yaml"
        )
    )
    if not public_mode:
        messages.extend(collect_path_references(repo_root, active_scan_roots))
        messages.extend(collect_legacy_marker_hits(repo_root))
    return ValidationResult(ok=not messages, messages=messages)


def materialize_template(template_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for child in template_root.iterdir():
        destination = target_root / child.name
        if destination.exists():
            raise FileExistsError(f"target already contains {destination}")
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)


def validate_materialized_target(target_root: Path) -> ValidationResult:
    messages: list[str] = []
    for required in [Path("AGENTS.md"), Path("Harness"), Path("docs")]:
        if not (target_root / required).exists():
            messages.append(f"materialized target missing {required}")
    if (target_root / ".harness_template").exists():
        messages.append(
            "materialized target must not contain a nested .harness_template directory"
        )
    for forbidden in FORBIDDEN_TEMPLATE_PATHS:
        if (target_root / forbidden).exists():
            messages.append(
                f"materialized target leaked source-only path: {forbidden}"
            )
    for forbidden in FORBIDDEN_TEMPLATE_FILES:
        if (target_root / forbidden).exists():
            messages.append(
                f"materialized target leaked source-only file: {forbidden}"
            )
    for legacy_path in LEGACY_ALIAS_PATHS:
        if (target_root / legacy_path).exists():
            messages.append(
                f"materialized target contains removed legacy alias: {legacy_path}"
            )
    messages.extend(collect_path_references(target_root, [Path(".")]))
    return ValidationResult(ok=not messages, messages=messages)


def default_dry_run_target(repo_root: Path, prefix: str = "blank_project") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (repo_root.parent / "moradin_tmp_runs" / f"{prefix}_{stamp}").resolve()


def repo_relative_display_path(repo_root: Path, target: Path | str) -> str:
    target_path = Path(target)
    if not target_path.is_absolute():
        return target_path.as_posix()
    return os.path.relpath(target_path, repo_root).replace(os.sep, "/")


def resolve_reported_target(repo_root: Path, target: str) -> Path:
    target_path = Path(target)
    if target_path.is_absolute():
        return target_path
    return (repo_root / target_path).resolve()


def build_existing_project_fixture(target_root: Path) -> None:
    (target_root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (target_root / "src").mkdir(parents=True, exist_ok=True)
    (target_root / "tests").mkdir(parents=True, exist_ok=True)
    (target_root / "README.md").write_text("# Existing Fixture\n", encoding="utf-8")
    (target_root / "src" / "app.py").write_text("print('fixture')\n", encoding="utf-8")
    (target_root / "tests" / "test_fixture.py").write_text(
        "def test_fixture():\n    assert True\n", encoding="utf-8"
    )
    (target_root / ".github" / "workflows" / "ci.yml").write_text(
        "name: ci\non: [push]\n",
        encoding="utf-8",
    )


def write_validation_outputs(
    manager_result: ValidationResult, template_result: ValidationResult
) -> None:
    HARNESS_GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    MIGRATION_REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "overall_ok": manager_result.ok and template_result.ok,
        "source": asdict(manager_result),
        "template": asdict(template_result),
    }
    (HARNESS_GENERATED_ROOT / "validation_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "---",
        'title: "Alpha Validation Report"',
        "status: completed" if payload["overall_ok"] else "status: blocked",
        "owner: docs-build-pipeline",
        f"last_reviewed: {datetime.now().date().isoformat()}",
        "source_refs: []",
        "related_docs:",
        "  - ../Harness/manifest.yaml",
        "  - ../.harness_template/Harness/manifest.yaml",
        "---",
        "",
        "# Alpha Validation Report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Overall status: {'pass' if payload['overall_ok'] else 'fail'}",
        "",
        "## Manager Validation",
        "",
    ]
    lines.extend([f"- {message}" for message in (manager_result.messages or ["pass"])])
    lines.extend(["", "## Template Validation", ""])
    lines.extend([f"- {message}" for message in (template_result.messages or ["pass"])])
    (MIGRATION_REPORTS_ROOT / "alpha_validation_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def write_smoke_test_report(repo_root: Path, result: SmokeTestResult) -> None:
    MIGRATION_REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        'title: "Dry Run Smoke Test Report"',
        "status: completed"
        if result.blank_ok and result.existing_ok
        else "status: blocked",
        "owner: docs-build-pipeline",
        f"last_reviewed: {datetime.now().date().isoformat()}",
        "source_refs: []",
        "related_docs:",
        "  - ../.harness_template/AGENTS.md",
        "  - ../Harness/manifest.yaml",
        "---",
        "",
        "# Dry Run Smoke Test Report",
        "",
        f"- Blank target: `{repo_relative_display_path(repo_root, result.blank_target)}`",
        f"- Existing fixture target: `{repo_relative_display_path(repo_root, result.existing_target)}`",
        f"- Blank deployment: {'pass' if result.blank_ok else 'fail'}",
        f"- Existing fixture overlay: {'pass' if result.existing_ok else 'fail'}",
        "",
        "## Findings",
        "",
    ]
    lines.extend([f"- {message}" for message in (result.messages or ["pass"])])
    (MIGRATION_REPORTS_ROOT / "dry_run_smoke_test_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run_smoke_tests(repo_root: Path, template_root: Path) -> SmokeTestResult:
    messages: list[str] = []
    blank_target = default_dry_run_target(repo_root, "blank_project")
    existing_target = default_dry_run_target(repo_root, "existing_project_fixture")

    materialize_template(template_root, blank_target)
    blank_result = validate_materialized_target(blank_target)
    if not blank_result.ok:
        messages.extend([f"blank: {message}" for message in blank_result.messages])

    build_existing_project_fixture(existing_target)
    materialize_template(template_root, existing_target)
    existing_result = validate_materialized_target(existing_target)
    if not existing_result.ok:
        messages.extend(
            [f"existing: {message}" for message in existing_result.messages]
        )

    if not (existing_target / "src" / "app.py").is_file():
        messages.append("existing: src/app.py was not preserved")
    if not (existing_target / "tests" / "test_fixture.py").is_file():
        messages.append("existing: tests/test_fixture.py was not preserved")
    if (existing_target / ".harness_template").exists():
        messages.append("existing: nested .harness_template directory was created")

    result = SmokeTestResult(
        blank_target=str(blank_target),
        existing_target=str(existing_target),
        blank_ok=blank_result.ok,
        existing_ok=existing_result.ok
        and not any(message.startswith("existing:") for message in messages),
        messages=messages,
    )
    write_smoke_test_report(repo_root, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and dry-run the Moradin Forge payload."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate the Forge repo, Moradin payload manifest, and compatibility scaffold.",
    )
    validate_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)

    dry_run_parser = subparsers.add_parser(
        "dry-run",
        help="Materialize the compatibility scaffold into an external dry-run target.",
    )
    dry_run_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    dry_run_parser.add_argument("--target-root", type=Path, default=None)

    alpha_validate_parser = subparsers.add_parser(
        "alpha-validate", help="Run strict alpha validation and write reports."
    )
    alpha_validate_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)

    smoke_test_parser = subparsers.add_parser(
        "smoke-test", help="Run blank and existing-project Moradin payload smoke tests."
    )
    smoke_test_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser


def print_result(name: str, result: ValidationResult) -> None:
    state = "PASS" if result.ok else "FAIL"
    print(f"[{state}] {name}")
    for message in result.messages:
        print(f"  - {message}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    template_root = repo_root / ".harness_template"
    public_mode = is_public_forge_repo(repo_root)

    manager_result = validate_manager_repo(repo_root)
    template_result = (
        ValidationResult(ok=True, messages=["compat-template skipped in public Forge mode"])
        if public_mode
        else validate_template_root(template_root)
    )
    print_result("source", manager_result)
    print_result("compat-template", template_result)

    if not manager_result.ok or not template_result.ok:
        if args.command == "alpha-validate":
            write_validation_outputs(manager_result, template_result)
        return 1

    if args.command == "validate":
        return 0

    if args.command == "alpha-validate":
        write_validation_outputs(manager_result, template_result)
        return 0

    if args.command == "smoke-test":
        if public_mode:
            from scripts.public_export import sidecar_smoke

            smoke_root = (
                repo_root.parent
                / "moradin_tmp_runs"
                / f"public_payload_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            smoke_payload = sidecar_smoke(repo_root, smoke_root, force=True)
            state = "PASS" if smoke_payload["status"] == "pass" else "FAIL"
            print(f"[{state}] public-sidecar-smoke")
            print(f"  - sidecar root: {smoke_payload['root']}")
            print(f"  - forbidden hits: {len(smoke_payload['forbidden_hits'])}")
            print(f"  - root mutations: {', '.join(smoke_payload['root_mutations']) or 'none'}")
            return 0 if smoke_payload["status"] == "pass" else 1

        smoke_result = run_smoke_tests(repo_root, template_root)
        state = "PASS" if smoke_result.blank_ok and smoke_result.existing_ok else "FAIL"
        print(f"[{state}] smoke-test")
        print(f"  - blank target: {smoke_result.blank_target}")
        print(f"  - existing target: {smoke_result.existing_target}")
        for message in smoke_result.messages:
            print(f"  - {message}")
        return 0 if smoke_result.blank_ok and smoke_result.existing_ok else 1

    target_root = (
        args.target_root.resolve()
        if args.target_root
        else default_dry_run_target(repo_root)
    )
    if target_root.exists():
        raise FileExistsError(f"dry-run target already exists: {target_root}")

    materialize_template(template_root, target_root)
    materialized_result = validate_materialized_target(target_root)
    print(f"[INFO] dry-run target: {target_root}")
    print_result("materialized-target", materialized_result)
    return 0 if materialized_result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
