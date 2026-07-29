#!/usr/bin/env python3
"""Portable workstation planning and agent-efficiency helpers for Moradin Forge."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


WORKSTATION_PLAN_VERSION = "MoradinForgeToolingPlanV1"
ONBOARD_PLAN_VERSION = "MoradinForgeOnboardPlanV1"
TOOLING_RECEIPT_VERSION = "MoradinForgeToolingReceiptV1"
TOOLING_BUNDLE_VERSION = "MoradinForgeToolingBundleV1"
EFFICIENCY_METRICS_VERSION = "MoradinForgeEfficiencyMetricsV1"
TOOLING_ROLLBACK_VERSION = "MoradinForgeToolingRollbackV1"
AGENT_MARKER_BEGIN = "<!-- moradin-forge:start -->"
AGENT_MARKER_END = "<!-- moradin-forge:end -->"
PATH_MARKER_BEGIN = "# moradin-forge:path:start"
PATH_MARKER_END = "# moradin-forge:path:end"
DEFAULT_PROFILE = "practical-full"
VERSION_CACHE_TTL = timedelta(hours=24)
MAX_REPOSITORIES = 200
MAX_DISCOVERY_DEPTH = 8
MAX_GUIDANCE_BYTES = 256 * 1024
CONTEXT_PRIMER_LIMIT = 6 * 1024
MAX_BUNDLE_PACKAGES = 250

OFFICIAL_DOWNLOAD_HOSTS = {
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "pypi.org",
    "files.pythonhosted.org",
    "formulae.brew.sh",
    "astral.sh",
    "dl.k8s.io",
    "get.helm.sh",
}

DISCOVERY_SKIP_DIRS = {
    ".cache",
    ".git",
    ".hg",
    ".moradins-harness",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}

STANDARD_AGENT_FILES = ("AGENTS.md", "CLAUDE.md")
LOWERCASE_AGENT_FILES = ("agents.md", "agent.md", "claude.md", "claud.md")


class WorkstationError(RuntimeError):
    """Raised when a workstation plan or approved action cannot proceed safely."""


@dataclass(frozen=True)
class ToolSpec:
    id: str
    label: str
    command: str
    category: str
    reason: str
    always_consider: bool = False
    required: bool = False
    triggers: tuple[str, ...] = ()
    python_package: str = ""
    github_repo: str = ""
    apt_package: str = ""
    brew_formula: str = ""
    winget_id: str = ""
    manual_only: bool = False


TOOL_CATALOG: tuple[ToolSpec, ...] = (
    ToolSpec(
        "git",
        "Git",
        "git",
        "core",
        "source control and deterministic repository state",
        always_consider=True,
        required=True,
        apt_package="git",
        brew_formula="git",
        winget_id="Git.Git",
    ),
    ToolSpec(
        "python",
        "Python 3",
        "python3",
        "core",
        "portable Forge runtime and Python project validation",
        always_consider=True,
        required=True,
        apt_package="python3",
        brew_formula="python",
        winget_id="Python.Python.3.12",
    ),
    ToolSpec(
        "uv",
        "uv",
        "uv",
        "core",
        "reproducible Python environments and isolated user tools",
        always_consider=True,
        github_repo="astral-sh/uv",
        winget_id="astral-sh.uv",
    ),
    ToolSpec(
        "ripgrep",
        "ripgrep",
        "rg",
        "core",
        "fast bounded source and guidance search",
        always_consider=True,
        apt_package="ripgrep",
        brew_formula="ripgrep",
        winget_id="BurntSushi.ripgrep.MSVC",
    ),
    ToolSpec(
        "fd",
        "fd",
        "fd",
        "core",
        "fast bounded file discovery",
        always_consider=True,
        apt_package="fd-find",
        brew_formula="fd",
        winget_id="sharkdp.fd",
    ),
    ToolSpec(
        "jq",
        "jq",
        "jq",
        "structured-data",
        "deterministic JSON inspection",
        always_consider=True,
        apt_package="jq",
        brew_formula="jq",
        winget_id="jqlang.jq",
    ),
    ToolSpec(
        "yq",
        "yq",
        "yq",
        "structured-data",
        "deterministic YAML inspection",
        always_consider=True,
        apt_package="yq",
        brew_formula="yq",
        winget_id="MikeFarah.yq",
    ),
    ToolSpec(
        "shellcheck",
        "ShellCheck",
        "shellcheck",
        "shell-qa",
        "shell installer and automation validation",
        always_consider=True,
        apt_package="shellcheck",
        brew_formula="shellcheck",
        winget_id="koalaman.shellcheck",
    ),
    ToolSpec(
        "shfmt",
        "shfmt",
        "shfmt",
        "shell-qa",
        "stable shell formatting",
        always_consider=True,
        apt_package="shfmt",
        brew_formula="shfmt",
        winget_id="mvdan.shfmt",
    ),
    ToolSpec(
        "yamllint",
        "yamllint",
        "yamllint",
        "shell-qa",
        "YAML validation for workflows and deployment files",
        always_consider=True,
        python_package="yamllint",
        apt_package="yamllint",
        brew_formula="yamllint",
    ),
    ToolSpec(
        "pre_commit",
        "pre-commit",
        "pre-commit",
        "core",
        "repeatable local repository gates",
        always_consider=True,
        python_package="pre-commit",
        apt_package="pre-commit",
        brew_formula="pre-commit",
    ),
    ToolSpec(
        "gh",
        "GitHub CLI",
        "gh",
        "core",
        "bounded pull-request and workflow inspection",
        always_consider=True,
        apt_package="gh",
        brew_formula="gh",
        winget_id="GitHub.cli",
    ),
    ToolSpec(
        "gitleaks",
        "Gitleaks",
        "gitleaks",
        "security",
        "secret scanning before publication",
        triggers=("git", "ci", "release"),
        apt_package="gitleaks",
        brew_formula="gitleaks",
        winget_id="Gitleaks.Gitleaks",
        github_repo="gitleaks/gitleaks",
    ),
    ToolSpec(
        "semgrep",
        "Semgrep CE",
        "semgrep",
        "security",
        "portable static analysis",
        triggers=("python", "node", "go", "rust", "java"),
        python_package="semgrep",
        brew_formula="semgrep",
    ),
    ToolSpec(
        "pip_audit",
        "pip-audit",
        "pip-audit",
        "security",
        "Python dependency vulnerability scanning",
        triggers=("python",),
        python_package="pip-audit",
    ),
    ToolSpec(
        "actionlint",
        "actionlint",
        "actionlint",
        "security",
        "GitHub Actions syntax and semantic validation",
        triggers=("github-actions",),
        brew_formula="actionlint",
        winget_id="rhysd.actionlint",
        github_repo="rhysd/actionlint",
    ),
    ToolSpec(
        "zizmor",
        "zizmor",
        "zizmor",
        "security",
        "GitHub Actions security analysis",
        triggers=("github-actions",),
        python_package="zizmor",
        brew_formula="zizmor",
        github_repo="woodruffw/zizmor",
    ),
    ToolSpec(
        "hadolint",
        "Hadolint",
        "hadolint",
        "security",
        "Dockerfile policy validation",
        triggers=("container",),
        brew_formula="hadolint",
        winget_id="hadolint.hadolint",
        github_repo="hadolint/hadolint",
    ),
    ToolSpec(
        "conftest",
        "Conftest",
        "conftest",
        "security",
        "policy-as-code validation for structured configuration",
        triggers=("container", "kubernetes", "terraform"),
        brew_formula="conftest",
        github_repo="open-policy-agent/conftest",
    ),
    ToolSpec(
        "trivy",
        "Trivy",
        "trivy",
        "security",
        "filesystem, container, dependency, and IaC scanning",
        triggers=("container", "kubernetes", "terraform", "release"),
        apt_package="trivy",
        brew_formula="trivy",
        winget_id="AquaSecurity.Trivy",
        github_repo="aquasecurity/trivy",
    ),
    ToolSpec(
        "syft",
        "Syft",
        "syft",
        "supply-chain",
        "SPDX and CycloneDX software bills of materials",
        triggers=("container", "release", "production"),
        brew_formula="syft",
        winget_id="Anchore.Syft",
        github_repo="anchore/syft",
    ),
    ToolSpec(
        "grype",
        "Grype",
        "grype",
        "supply-chain",
        "SBOM and filesystem vulnerability scanning",
        triggers=("container", "release", "production"),
        brew_formula="grype",
        winget_id="Anchore.Grype",
        github_repo="anchore/grype",
    ),
    ToolSpec(
        "osv_scanner",
        "OSV-Scanner",
        "osv-scanner",
        "supply-chain",
        "open-source dependency vulnerability scanning",
        triggers=("python", "node", "go", "rust", "release"),
        brew_formula="osv-scanner",
        winget_id="Google.OSV-Scanner",
        github_repo="google/osv-scanner",
    ),
    ToolSpec(
        "docker",
        "Docker",
        "docker",
        "container",
        "container build and reproducible test environments",
        triggers=("container",),
        apt_package="docker.io",
        brew_formula="docker",
        winget_id="Docker.DockerDesktop",
        manual_only=True,
    ),
    ToolSpec(
        "kubectl",
        "kubectl",
        "kubectl",
        "kubernetes",
        "Kubernetes manifest and cluster validation",
        triggers=("kubernetes",),
        apt_package="kubectl",
        brew_formula="kubectl",
        winget_id="Kubernetes.kubectl",
        github_repo="kubernetes/kubernetes",
    ),
    ToolSpec(
        "helm",
        "Helm",
        "helm",
        "kubernetes",
        "Helm chart validation and packaging",
        triggers=("helm", "kubernetes"),
        brew_formula="helm",
        winget_id="Helm.Helm",
        github_repo="helm/helm",
    ),
    ToolSpec(
        "kind",
        "kind",
        "kind",
        "kubernetes",
        "disposable Kubernetes integration tests",
        triggers=("kubernetes",),
        brew_formula="kind",
        winget_id="Kubernetes.kind",
        github_repo="kubernetes-sigs/kind",
    ),
    ToolSpec(
        "kubeconform",
        "kubeconform",
        "kubeconform",
        "kubernetes",
        "offline Kubernetes schema validation",
        triggers=("kubernetes",),
        brew_formula="kubeconform",
        github_repo="yannh/kubeconform",
    ),
    ToolSpec(
        "cosign",
        "Cosign",
        "cosign",
        "release",
        "artifact and container signature verification",
        triggers=("signing", "release"),
        brew_formula="cosign",
        winget_id="Sigstore.Cosign",
        github_repo="sigstore/cosign",
    ),
    ToolSpec(
        "scorecard",
        "OpenSSF Scorecard",
        "scorecard",
        "release",
        "repository supply-chain posture checks",
        triggers=("release", "github-actions"),
        brew_formula="scorecard",
        github_repo="ossf/scorecard",
    ),
    ToolSpec(
        "sops",
        "SOPS",
        "sops",
        "release",
        "encrypted configuration workflows",
        triggers=("sops", "kubernetes", "production"),
        brew_formula="sops",
        winget_id="Mozilla.SOPS",
        github_repo="getsops/sops",
    ),
    ToolSpec(
        "just",
        "just",
        "just",
        "developer-experience",
        "deterministic project command entrypoints",
        triggers=("just",),
        apt_package="just",
        brew_formula="just",
        winget_id="Casey.Just",
        github_repo="casey/just",
    ),
    ToolSpec(
        "watchexec",
        "watchexec",
        "watchexec",
        "developer-experience",
        "bounded watch-mode validation",
        triggers=("watch",),
        apt_package="watchexec",
        brew_formula="watchexec",
        winget_id="Watchexec.Watchexec",
        github_repo="watchexec/watchexec",
    ),
    ToolSpec(
        "node",
        "Node.js",
        "node",
        "ui",
        "Node and browser project validation",
        triggers=("node", "ui"),
        apt_package="nodejs",
        brew_formula="node",
        winget_id="OpenJS.NodeJS.LTS",
    ),
    ToolSpec(
        "playwright",
        "Playwright",
        "playwright",
        "ui",
        "headless browser and visual validation",
        triggers=("ui",),
        manual_only=True,
    ),
    ToolSpec(
        "sandbox",
        "Sandbox runtime",
        "",
        "sandbox",
        "isolation for untrusted tools and destructive tests",
        triggers=("untrusted-tools",),
        manual_only=True,
    ),
    ToolSpec(
        "cad",
        "CAD validation lane",
        "",
        "cad",
        "mechanical CAD validation and export",
        triggers=("cad",),
        manual_only=True,
    ),
)


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def plan_digest(payload: dict[str, Any]) -> str:
    canonical = {
        key: value
        for key, value in payload.items()
        if key not in {"plan_sha256", "artifacts"}
    }
    return sha256_bytes(canonical_json_bytes(canonical))


def write_json(path: Path, payload: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )


def atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.moradin-",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
        if path.is_file() and not path.is_symlink():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def normalized_platform(system: str | None = None) -> str:
    value = (system or platform.system()).lower()
    if value.startswith("win"):
        return "windows"
    if value == "darwin":
        return "macos"
    return "linux"


def normalized_arch(machine: str | None = None) -> str:
    value = (machine or platform.machine()).lower()
    if value in {"aarch64", "arm64"}:
        return "arm64"
    if value in {"amd64", "x86_64", "x64"}:
        return "amd64"
    return value or "unknown"


def ensure_approved_workspace(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.exists() or not expanded.is_dir():
        raise WorkstationError(f"approved workspace must be an existing directory: {path}")
    resolved = expanded.resolve()
    if resolved == Path(resolved.anchor):
        raise WorkstationError("filesystem roots cannot be approved as Forge workspaces")
    if resolved == Path.home().resolve():
        raise WorkstationError(
            "the full home directory is too broad; approve one or more workspace subdirectories"
        )
    return resolved


def _depth_from(root: Path, path: Path) -> int:
    return len(path.relative_to(root).parts)


def discover_repositories(
    workspaces: Sequence[Path],
    *,
    max_depth: int = MAX_DISCOVERY_DEPTH,
    max_repositories: int = MAX_REPOSITORIES,
) -> list[Path]:
    """Discover git repositories only below explicitly approved workspace roots."""

    approved = sorted({ensure_approved_workspace(path) for path in workspaces})
    repositories: set[Path] = set()
    for workspace in approved:
        for current_raw, dirnames, _filenames in os.walk(
            workspace,
            topdown=True,
            followlinks=False,
        ):
            current = Path(current_raw)
            depth = _depth_from(workspace, current)
            if depth > max_depth:
                dirnames[:] = []
                continue
            git_marker = current / ".git"
            if git_marker.is_dir() or git_marker.is_file():
                repositories.add(current.resolve())
                dirnames[:] = []
                if len(repositories) > max_repositories:
                    raise WorkstationError(
                        f"workspace discovery exceeded {max_repositories} repositories"
                    )
                continue
            kept: list[str] = []
            for name in sorted(dirnames):
                child = current / name
                if name in DISCOVERY_SKIP_DIRS or child.is_symlink():
                    continue
                kept.append(name)
            dirnames[:] = kept
    return sorted(repositories)


def _is_file(root: Path, relative: str) -> bool:
    path = root / relative
    return path.is_file() and not path.is_symlink()


def _has_any_file(root: Path, relatives: Iterable[str]) -> bool:
    return any(_is_file(root, relative) for relative in relatives)


def _directory_has_suffix(root: Path, relative: str, suffixes: tuple[str, ...]) -> bool:
    directory = root / relative
    if not directory.is_dir() or directory.is_symlink():
        return False
    return any(
        child.is_file() and child.suffix.lower() in suffixes
        for child in directory.iterdir()
    )


def inspect_repository_capabilities(repo_root: Path) -> dict[str, Any]:
    """Inspect standard manifests and guidance without reading arbitrary source files."""

    capabilities: set[str] = {"git"}
    markers: dict[str, bool] = {}

    marker_groups: dict[str, tuple[str, ...]] = {
        "python": ("pyproject.toml", "requirements.txt", "Pipfile", "uv.lock"),
        "node": ("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"),
        "rust": ("Cargo.toml", "Cargo.lock"),
        "go": ("go.mod", "go.sum"),
        "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
        "container": (
            "Dockerfile",
            "Containerfile",
            "compose.yaml",
            "compose.yml",
            "docker-compose.yaml",
            "docker-compose.yml",
        ),
        "terraform": ("main.tf", "terraform.tf", ".terraform.lock.hcl"),
        "helm": ("Chart.yaml",),
        "sops": (".sops.yaml", ".sops.yml"),
        "just": ("justfile", "Justfile"),
        "release": ("CHANGELOG.md", "RELEASE.md", ".release-please-manifest.json"),
        "ui": (
            "vite.config.ts",
            "vite.config.js",
            "next.config.js",
            "next.config.mjs",
            "playwright.config.ts",
            "playwright.config.js",
        ),
        "cad": ("pyproject-cad.toml", "model.scad", "model.FCStd"),
    }
    for capability, names in marker_groups.items():
        present = _has_any_file(repo_root, names)
        markers[capability] = present
        if present:
            capabilities.add(capability)

    github_actions = _directory_has_suffix(repo_root, ".github/workflows", (".yml", ".yaml"))
    kubernetes = any(
        (repo_root / directory).is_dir()
        for directory in ("k8s", "kubernetes", "manifests", "charts")
    ) or markers["helm"]
    production = _has_any_file(
        repo_root,
        (
            "Procfile",
            "fly.toml",
            "render.yaml",
            "app.yaml",
            "helmfile.yaml",
            "helmfile.yml",
        ),
    )
    signing = _has_any_file(repo_root, ("cosign.pub", "cosign.key", "signing-policy.yaml"))
    untrusted_tools = (repo_root / "plugins").is_dir() or (repo_root / "extensions").is_dir()
    watch = _has_any_file(repo_root, ("watchexec.toml", ".watchexec.toml"))
    for capability, present in (
        ("github-actions", github_actions),
        ("kubernetes", kubernetes),
        ("production", production),
        ("signing", signing),
        ("untrusted-tools", untrusted_tools),
        ("watch", watch),
    ):
        markers[capability] = present
        if present:
            capabilities.add(capability)

    agent_files: dict[str, dict[str, Any]] = {}
    for name in STANDARD_AGENT_FILES:
        path = repo_root / name
        agent_files[name] = {
            "present": path.is_file() and not path.is_symlink(),
            "symlink": path.is_symlink(),
        }
    lowercase_variants = sorted(
        name
        for name in LOWERCASE_AGENT_FILES
        if (repo_root / name).is_file() and name not in STANDARD_AGENT_FILES
    )
    return {
        "capabilities": sorted(capabilities),
        "markers": dict(sorted(markers.items())),
        "agent_files": agent_files,
        "lowercase_agent_file_warnings": lowercase_variants,
    }


def repository_id(repo_root: Path) -> str:
    return sha256_bytes(repo_root.resolve().as_posix().encode("utf-8"))[:16]


def command_present(command: str) -> bool:
    if not command:
        return False
    candidates = [command]
    if command == "python3":
        candidates.extend(["python", "py"])
    if command == "fd":
        candidates.append("fdfind")
    return any(shutil.which(item) is not None for item in candidates)


def _cache_payload(cache_path: Path) -> dict[str, Any]:
    if not cache_path.is_file() or cache_path.is_symlink():
        return {"version": 1, "tools": {}}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "tools": {}}
    return payload if isinstance(payload, dict) else {"version": 1, "tools": {}}


def _cache_entry_fresh(entry: dict[str, Any], now: datetime) -> bool:
    try:
        checked = datetime.fromisoformat(str(entry["checked_at"]))
    except (KeyError, TypeError, ValueError):
        return False
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    return now - checked <= VERSION_CACHE_TTL


def _assert_official_https_url(url: str, *, purpose: str) -> str:
    if not url or any(ord(character) < 32 for character in url):
        raise WorkstationError(f"{purpose} must be a printable HTTPS URL")
    parsed = urllib.parse.urlsplit(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise WorkstationError(f"{purpose} has an invalid port") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in OFFICIAL_DOWNLOAD_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
    ):
        raise WorkstationError(f"{purpose} is not from an official host: {url}")
    return url


class _OfficialSourceRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        _assert_official_https_url(new_url, purpose="redirect target")
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            new_url,
        )


def _open_official_url(
    request: urllib.request.Request,
    *,
    timeout: float,
) -> Any:
    _assert_official_https_url(request.full_url, purpose="network source")
    opener = urllib.request.build_opener(_OfficialSourceRedirectHandler())
    response = opener.open(request, timeout=timeout)
    try:
        _assert_official_https_url(response.geturl(), purpose="network response")
    except WorkstationError:
        response.close()
        raise
    return response


def _fetch_json(url: str, timeout: float = 8.0) -> dict[str, Any]:
    _assert_official_https_url(url, purpose="version metadata source")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "moradins-forge-version-resolver/0.2.0-beta.3",
        },
    )
    with _open_official_url(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise WorkstationError(f"version metadata response must be an object: {url}")
    return payload


def _run_metadata_command(argv: list[str]) -> str:
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WorkstationError(
            f"package metadata command failed: {argv[0]}"
        ) from error
    if completed.returncode != 0:
        raise WorkstationError(
            f"package metadata command failed: {argv[0]} exited {completed.returncode}"
        )
    return completed.stdout


def resolve_package_manager_version(
    spec: ToolSpec,
    *,
    system: str,
    now: datetime,
) -> dict[str, Any] | None:
    checked_at = now.replace(microsecond=0).isoformat()
    if system == "linux" and spec.apt_package and shutil.which("apt-cache"):
        output = _run_metadata_command(["apt-cache", "policy", spec.apt_package])
        candidate = ""
        for line in output.splitlines():
            if line.strip().startswith("Candidate:"):
                candidate = line.split(":", 1)[1].strip()
                break
        if candidate and candidate != "(none)":
            return {
                "version": candidate,
                "source": "apt",
                "source_url": "",
                "asset_url": "",
                "sha256": "",
                "artifact_sha256s": [],
                "trust": "signed-package-manager",
                "checked_at": checked_at,
            }
    if system == "macos" and spec.brew_formula and shutil.which("brew"):
        payload = json.loads(
            _run_metadata_command(
                ["brew", "info", "--json=v2", "--formula", spec.brew_formula]
            )
        )
        formulae = payload.get("formulae", [])
        formula = formulae[0] if isinstance(formulae, list) and formulae else {}
        version = str(formula.get("versions", {}).get("stable", "")).strip()
        digests: set[str] = set()
        bottle_files = formula.get("bottle", {}).get("stable", {}).get("files", {})
        if isinstance(bottle_files, dict):
            for item in bottle_files.values():
                if isinstance(item, dict) and item.get("sha256"):
                    digests.add(str(item["sha256"]))
        if version:
            return {
                "version": version,
                "source": "homebrew",
                "source_url": (
                    "https://formulae.brew.sh/api/formula/"
                    + urllib.parse.quote(spec.brew_formula, safe="")
                    + ".json"
                ),
                "asset_url": "",
                "sha256": next(iter(digests)) if len(digests) == 1 else "",
                "artifact_sha256s": sorted(digests),
                "trust": "signed-package-manager",
                "checked_at": checked_at,
            }
    if system == "windows" and spec.winget_id and shutil.which("winget"):
        output = _run_metadata_command(
            [
                "winget",
                "show",
                "--exact",
                "--id",
                spec.winget_id,
                "--source",
                "winget",
                "--accept-source-agreements",
            ]
        )
        metadata: dict[str, str] = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip().lower()] = value.strip()
        version = metadata.get("version", "")
        if version:
            digest = metadata.get("installer sha256", "").lower()
            digest_valid = bool(re.fullmatch(r"[0-9a-f]{64}", digest))
            return {
                "version": version,
                "source": "winget",
                "source_url": metadata.get("installer url", ""),
                "asset_url": metadata.get("installer url", ""),
                "sha256": digest if digest_valid else "",
                "artifact_sha256s": [digest] if digest_valid else [],
                "trust": "signed-package-manager",
                "checked_at": checked_at,
            }
    return None


def _wheel_platform_score(filename: str, *, system: str, arch: str) -> int | None:
    lowered = filename.lower()
    if not lowered.endswith(".whl"):
        return None
    python_version = f"cp{platform.python_version_tuple()[0]}{platform.python_version_tuple()[1]}"
    if "-py3-none-any.whl" in lowered:
        return 0
    if f"-{python_version}-" not in lowered and "-abi3-" not in lowered:
        return None
    arch_tokens = {
        "amd64": ("x86_64", "amd64", "win_amd64", "universal2"),
        "arm64": ("aarch64", "arm64", "win_arm64", "universal2"),
    }.get(arch, (arch,))
    if not any(token and token in lowered for token in arch_tokens):
        return None
    if system == "linux" and ("manylinux" in lowered or "linux_" in lowered):
        return 10 if "manylinux" in lowered else 20
    if system == "macos" and "macosx" in lowered:
        return 10 if "universal2" in lowered else 20
    if system == "windows" and "-win_" in lowered:
        return 10
    return None


def select_pypi_wheel(
    files: Sequence[dict[str, Any]],
    *,
    system: str,
    arch: str,
) -> dict[str, str] | None:
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for item in files:
        if not isinstance(item, dict) or item.get("yanked"):
            continue
        filename = str(item.get("filename", ""))
        score = _wheel_platform_score(filename, system=system, arch=arch)
        digest = str(item.get("digests", {}).get("sha256", "")).lower()
        url = str(item.get("url", ""))
        if (
            score is None
            or not filename
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not url
        ):
            continue
        candidates.append((score, filename, item))
    if not candidates:
        return None
    _score, filename, selected = sorted(candidates, key=lambda row: (row[0], row[1]))[0]
    return {
        "filename": filename,
        "url": str(selected["url"]),
        "sha256": str(selected["digests"]["sha256"]).lower(),
    }


def select_github_asset(
    assets: Sequence[dict[str, Any]],
    *,
    system: str,
    arch: str,
) -> dict[str, str] | None:
    system_tokens = {
        "linux": ("linux",),
        "macos": ("darwin", "macos", "mac"),
        "windows": ("windows", "win"),
    }[system]
    arch_tokens = {
        "amd64": ("x86_64", "amd64", "x64"),
        "arm64": ("aarch64", "arm64"),
    }.get(arch, (arch,))
    candidates: list[tuple[str, dict[str, Any], str]] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        lowered = name.lower()
        if (
            not any(token in lowered for token in system_tokens)
            or not any(token in lowered for token in arch_tokens)
            or any(
                token in lowered
                for token in ("checksum", "checksums", "sha256", "sbom", ".sig")
            )
        ):
            continue
        digest_raw = str(item.get("digest", "")).lower()
        digest = digest_raw.removeprefix("sha256:")
        url = str(item.get("browser_download_url", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not url:
            continue
        candidates.append((name, item, digest))
    if not candidates:
        return None
    name, item, digest = sorted(candidates, key=lambda row: row[0])[0]
    return {
        "filename": name,
        "url": str(item["browser_download_url"]),
        "sha256": digest,
    }


def resolve_latest_version(
    spec: ToolSpec,
    *,
    cache_path: Path,
    refresh: bool,
    system: str | None = None,
    arch: str | None = None,
    prefer_python: bool = True,
    now: datetime | None = None,
    fetch_json: Callable[[str], dict[str, Any]] = _fetch_json,
) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    system = system or normalized_platform()
    arch = arch or normalized_arch()
    cache = _cache_payload(cache_path)
    tools = cache.setdefault("tools", {})
    cache_key = (
        f"{system}:{arch}:{'python' if prefer_python else 'native'}:{spec.id}"
    )
    cached = tools.get(cache_key)
    if isinstance(cached, dict) and not refresh and _cache_entry_fresh(cached, now):
        return {**cached, "cache": "fresh"}

    resolved: dict[str, Any] = {
        "version": "latest-stable",
        "source": "signed-package-manager",
        "source_url": "",
        "asset_url": "",
        "sha256": "",
        "trust": "signed-package-manager",
        "checked_at": now.replace(microsecond=0).isoformat(),
        "cache": "refreshed",
    }
    try:
        package_manager = (
            None
            if spec.python_package and prefer_python
            else resolve_package_manager_version(spec, system=system, now=now)
        )
        if package_manager:
            resolved.update(package_manager)
        elif spec.python_package and prefer_python:
            source_url = f"https://pypi.org/pypi/{spec.python_package}/json"
            payload = fetch_json(source_url)
            version = str(payload.get("info", {}).get("version", "")).strip()
            releases = payload.get("releases", {}).get(version, [])
            hashes = sorted(
                {
                    str(item.get("digests", {}).get("sha256", ""))
                    for item in releases
                    if isinstance(item, dict)
                    and item.get("digests", {}).get("sha256")
                }
            )
            if not version:
                raise WorkstationError(f"PyPI did not report a stable version for {spec.id}")
            resolved.update(
                {
                    "version": version,
                    "source": "pypi",
                    "source_url": source_url,
                    "sha256": hashes[0] if len(hashes) == 1 else "",
                    "artifact_sha256s": hashes,
                    "trust": "pypi-hash-verified",
                }
            )
            selected = select_pypi_wheel(
                [item for item in releases if isinstance(item, dict)],
                system=system,
                arch=arch,
            )
            if selected:
                resolved.update(
                    {
                        "asset_url": selected["url"],
                        "asset_filename": selected["filename"],
                        "sha256": selected["sha256"],
                    }
                )
        elif spec.github_repo:
            source_url = f"https://api.github.com/repos/{spec.github_repo}/releases/latest"
            payload = fetch_json(source_url)
            version = str(payload.get("tag_name", "")).strip()
            html_url = str(payload.get("html_url", "")).strip()
            if not version:
                raise WorkstationError(
                    f"GitHub did not report a stable release for {spec.id}"
                )
            resolved.update(
                {
                    "version": version,
                    "source": "github-release",
                    "source_url": html_url or source_url,
                    "trust": "official-release-metadata",
                }
            )
            selected = select_github_asset(
                [
                    item
                    for item in payload.get("assets", [])
                    if isinstance(item, dict)
                ],
                system=system,
                arch=arch,
            )
            if selected:
                resolved.update(
                    {
                        "asset_url": selected["url"],
                        "asset_filename": selected["filename"],
                        "sha256": selected["sha256"],
                        "trust": "official-release-digest",
                    }
                )
    except (WorkstationError, urllib.error.URLError, TimeoutError, ValueError) as error:
        if isinstance(cached, dict):
            return {
                **cached,
                "cache": "stale",
                "resolution_warning": str(error),
            }
        resolved.update(
            {
                "cache": "unavailable",
                "resolution_warning": str(error),
                "trust": "manual-review",
            }
        )

    tools[cache_key] = {
        key: value
        for key, value in resolved.items()
        if key != "cache"
    }
    cache["updated_at"] = now.replace(microsecond=0).isoformat()
    write_json(cache_path, cache)
    return resolved


def _install_action(
    spec: ToolSpec,
    *,
    system: str,
    resolved: dict[str, Any],
    uv_present: bool,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "tool_id": spec.id,
        "kind": "manual",
        "argv": [],
        "requires_elevation": False,
        "auto_execute": False,
        "package": "",
        "reason": "",
    }
    version = str(resolved.get("version", "latest-stable"))
    resolution_current = resolved.get("cache") in {"fresh", "refreshed"}
    if spec.manual_only:
        action["reason"] = "capability requires environment-specific human review"
        return action
    if (
        spec.python_package
        and uv_present
        and resolution_current
        and version not in {"", "latest-stable"}
        and resolved.get("source") == "pypi"
        and resolved.get("trust") == "pypi-hash-verified"
        and bool(resolved.get("artifact_sha256s") or resolved.get("sha256"))
    ):
        action.update(
            {
                "kind": "user-local",
                "argv": [
                    "uv",
                    "tool",
                    "install",
                    "--force",
                    f"{spec.python_package}=={version}",
                ],
                "auto_execute": True,
                "package": f"{spec.python_package}=={version}",
                "reason": "isolated Forge-owned uv tool environment",
            }
        )
        return action
    if (
        system == "linux"
        and spec.apt_package
        and resolution_current
        and resolved.get("source") == "apt"
        and resolved.get("trust") == "signed-package-manager"
        and version not in {"", "latest-stable"}
    ):
        action.update(
            {
                "kind": "privileged-script",
                "package": spec.apt_package,
                "version": version,
                "requires_elevation": True,
                "reason": "signed operating-system package manager",
            }
        )
        return action
    if (
        system == "macos"
        and spec.brew_formula
        and resolution_current
        and shutil.which("brew") is not None
        and version not in {"", "latest-stable"}
        and resolved.get("source") == "homebrew"
        and resolved.get("trust") == "signed-package-manager"
    ):
        action.update(
            {
                "kind": "user-package-manager",
                "argv": ["brew", "install", spec.brew_formula],
                "auto_execute": True,
                "package": spec.brew_formula,
                "version": version,
                "reason": "Homebrew formula under explicit user approval",
            }
        )
        return action
    if (
        system == "windows"
        and spec.winget_id
        and resolution_current
        and resolved.get("source") == "winget"
        and resolved.get("trust") == "signed-package-manager"
        and version not in {"", "latest-stable"}
    ):
        action.update(
            {
                "kind": "privileged-script",
                "argv": [],
                "requires_elevation": True,
                "auto_execute": False,
                "package": spec.winget_id,
                "version": version,
                "reason": (
                    "WinGet elevation behavior varies by package; "
                    "the user runs the reviewed PowerShell script"
                ),
            }
        )
        return action
    action["reason"] = (
        "version metadata is stale or unavailable; refresh before automatic execution"
        if not resolution_current
        else "no verified automatic installer is available for this host"
    )
    return action


def recommended_tool_specs(capabilities: set[str]) -> list[ToolSpec]:
    selected = [
        spec
        for spec in TOOL_CATALOG
        if spec.always_consider or bool(capabilities.intersection(spec.triggers))
    ]
    return sorted(selected, key=lambda item: (item.category, item.id))


def parse_hashed_requirements(lock_text: str) -> list[tuple[str, str]]:
    pinned: list[tuple[str, str]] = []
    for raw_line in lock_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("--hash=sha256:"):
            continue
        match = re.match(
            r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)"
            r"(?:\s|\\|$)",
            line,
        )
        if not match:
            raise WorkstationError(
                "compiled Python tool lock contains a non-registry requirement"
            )
        pinned.append((match.group(1), match.group(2)))
    if len(pinned) > MAX_BUNDLE_PACKAGES:
        raise WorkstationError(
            f"Python tool lock exceeds {MAX_BUNDLE_PACKAGES} packages"
        )
    return pinned


def normalized_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _resolve_python_bundle_asset(
    package: str,
    version: str,
    *,
    system: str,
    arch: str,
    fetch_json: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, str] | None, str]:
    source_url = (
        "https://pypi.org/pypi/"
        + urllib.parse.quote(package, safe="")
        + "/"
        + urllib.parse.quote(version, safe="")
        + "/json"
    )
    try:
        payload = fetch_json(source_url)
        selected = select_pypi_wheel(
            [
                item
                for item in payload.get("urls", [])
                if isinstance(item, dict)
            ],
            system=system,
            arch=arch,
        )
    except (WorkstationError, urllib.error.URLError, TimeoutError, ValueError) as error:
        return None, str(error)
    if not selected:
        return None, "no compatible hash-verified wheel was published"
    try:
        _assert_official_asset(selected["url"])
    except WorkstationError as error:
        return None, str(error)
    return {
        "package": package,
        "version": version,
        "filename": selected["filename"],
        "url": selected["url"],
        "sha256": selected["sha256"],
        "source": "pypi",
    }, ""


def build_python_tool_lock(
    tool_rows: Sequence[dict[str, Any]],
    *,
    system: str,
    arch: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    fetch_json: Callable[[str], dict[str, Any]] = _fetch_json,
) -> dict[str, Any]:
    direct_requirements = sorted(
        {
            str(row["install_action"]["package"])
            for row in tool_rows
            if not row["present"]
            and row["install_action"]["kind"] == "user-local"
            and row["install_action"].get("auto_execute")
        }
    )
    if not direct_requirements:
        return {
            "status": "not-required",
            "direct_requirements": [],
            "requirements": "",
            "requirements_sha256": "",
            "assets": [],
            "blockers": [],
        }
    if shutil.which("uv") is None:
        return {
            "status": "unavailable",
            "direct_requirements": direct_requirements,
            "requirements": "",
            "requirements_sha256": "",
            "assets": [],
            "blockers": [{"reason": "uv is required to freeze the dependency closure"}],
        }
    with tempfile.TemporaryDirectory(prefix="moradin-python-lock-") as temporary:
        requirements_in = Path(temporary) / "requirements.in"
        requirements_in.write_text(
            "\n".join(direct_requirements) + "\n",
            encoding="utf-8",
        )
        completed = runner(
            [
                "uv",
                "pip",
                "compile",
                requirements_in.as_posix(),
                "--generate-hashes",
                "--no-annotate",
                "--no-header",
                "--only-binary",
                ":all:",
                "--python-platform",
                system,
                "--python-version",
                ".".join(platform.python_version_tuple()[:2]),
                "--default-index",
                "https://pypi.org/simple",
                "--no-config",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    if completed.returncode != 0:
        return {
            "status": "unavailable",
            "direct_requirements": direct_requirements,
            "requirements": "",
            "requirements_sha256": "",
            "assets": [],
            "blockers": [
                {
                    "reason": (
                        "uv could not freeze a wheel-only dependency closure "
                        f"(exit {completed.returncode})"
                    )
                }
            ],
        }
    lock_text = completed.stdout
    try:
        pinned = parse_hashed_requirements(lock_text)
    except WorkstationError as error:
        return {
            "status": "unavailable",
            "direct_requirements": direct_requirements,
            "requirements": "",
            "requirements_sha256": "",
            "assets": [],
            "blockers": [{"reason": str(error)}],
        }
    assets: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(pinned)))) as executor:
        futures = {
            executor.submit(
                _resolve_python_bundle_asset,
                package,
                version,
                system=system,
                arch=arch,
                fetch_json=fetch_json,
            ): (package, version)
            for package, version in pinned
        }
        for future in as_completed(futures):
            package, version = futures[future]
            asset, reason = future.result()
            if asset:
                assets.append(asset)
            else:
                blockers.append(
                    {
                        "package": package,
                        "version": version,
                        "reason": reason,
                    }
                )
    assets.sort(key=lambda item: (item["package"].lower(), item["filename"]))
    blockers.sort(key=lambda item: (item.get("package", ""), item["reason"]))
    return {
        "status": "ready" if not blockers else "partial",
        "direct_requirements": direct_requirements,
        "requirements": lock_text,
        "requirements_sha256": sha256_bytes(lock_text.encode("utf-8")),
        "assets": assets,
        "blockers": blockers,
    }


def build_agent_adapter_section(sidecar_dir: str, agent_file: str) -> str:
    provider_note = (
        "- Claude-specific guidance remains subordinate to repository-wide `AGENTS.md` rules."
        if agent_file == "CLAUDE.md"
        else "- Provider-specific files may add rules but must not bypass this repository contract."
    )
    return "\n".join(
        [
            AGENT_MARKER_BEGIN,
            "## Moradin Forge",
            "",
            f"- Local sidecar: `{sidecar_dir}/`",
            f"- Start with `{sidecar_dir}/scripts/moradin_forge.sh context-primer --target .`.",
            f"- Use `{sidecar_dir}/scripts/moradin_forge.sh repo-brief --target .` before broad reads.",
            "- Prefer current summaries and repo-native deterministic commands before raw logs.",
            f"- Use `{sidecar_dir}/scripts/moradin_forge.sh rerun-advice --target . -- <command>` before repeating expensive checks.",
            "- Request tools only when they materially improve testing or diagnosis, and keep evidence intake compact.",
            "- Ask before installing tools or changing this repository; approved user-level installs may run through Forge.",
            "- Privileged tooling is delivered as a reviewable script for the user to execute.",
            "- Expand context when evidence is missing, contradictory, security-sensitive, or release-critical.",
            provider_note,
            AGENT_MARKER_END,
            "",
        ]
    )


def _read_guidance(path: Path) -> str:
    if path.is_symlink():
        raise WorkstationError(f"agent guidance symlinks are not patchable: {path.name}")
    if not path.exists():
        return ""
    if not path.is_file():
        raise WorkstationError(f"agent guidance path is not a file: {path.name}")
    if path.stat().st_size > MAX_GUIDANCE_BYTES:
        raise WorkstationError(f"agent guidance exceeds {MAX_GUIDANCE_BYTES} bytes: {path.name}")
    return path.read_text(encoding="utf-8")


def render_owned_agent_patch(existing: str, section: str) -> tuple[str, str]:
    begin_count = existing.count(AGENT_MARKER_BEGIN)
    end_count = existing.count(AGENT_MARKER_END)
    if begin_count != end_count or begin_count > 1:
        raise WorkstationError("agent guidance contains ambiguous Moradin marker blocks")
    if begin_count == 1:
        start = existing.index(AGENT_MARKER_BEGIN)
        end = existing.index(AGENT_MARKER_END, start) + len(AGENT_MARKER_END)
        if end < len(existing) and existing[end] == "\n":
            end += 1
        return existing[:start] + section + existing[end:], "update"
    if not existing:
        return section, "create"
    separator = "" if existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n"
    return existing + separator + section, "patch"


def agent_file_proposal(
    repo_root: Path,
    agent_file: str,
    *,
    sidecar_dir: str = ".moradins-harness",
) -> dict[str, Any]:
    if agent_file not in STANDARD_AGENT_FILES:
        raise WorkstationError(f"unsupported agent guidance file: {agent_file}")
    path = repo_root / agent_file
    existing = _read_guidance(path)
    section = build_agent_adapter_section(sidecar_dir, agent_file)
    rendered, action = render_owned_agent_patch(existing, section)
    existing_owned = ""
    if existing.count(AGENT_MARKER_BEGIN) == 1:
        start = existing.index(AGENT_MARKER_BEGIN)
        end = existing.index(AGENT_MARKER_END, start) + len(AGENT_MARKER_END)
        if end < len(existing) and existing[end] == "\n":
            end += 1
        existing_owned = existing[start:end]
    owned_diff = "\n".join(
        difflib.unified_diff(
            existing_owned.splitlines(),
            section.splitlines(),
            fromfile=f"{agent_file} (current Moradin block)",
            tofile=f"{agent_file} (proposed Moradin block)",
            lineterm="",
            n=0,
        )
    )
    return {
        "path": agent_file,
        "action": action,
        "present": path.is_file(),
        "before_sha256": sha256_bytes(existing.encode("utf-8")) if existing else "",
        "after_sha256": sha256_bytes(rendered.encode("utf-8")),
        "owned_block": section,
        "owned_block_sha256": sha256_bytes(section.encode("utf-8")),
        "patch_preview": owned_diff,
        "requires_explicit_approval": True,
    }


def build_tooling_plan(
    workspaces: Sequence[Path],
    *,
    forge_root: Path,
    profile: str = DEFAULT_PROFILE,
    refresh_versions: bool = False,
    sidecar_dir: str = ".moradins-harness",
    include_tools: Sequence[str] = (),
    exclude_tools: Sequence[str] = (),
    discovery_callback: Callable[[Sequence[Path]], None] | None = None,
) -> dict[str, Any]:
    if profile != DEFAULT_PROFILE:
        raise WorkstationError(f"unsupported tooling profile: {profile}")
    approved = sorted({ensure_approved_workspace(path) for path in workspaces})
    repos = discover_repositories(approved)
    if discovery_callback is not None:
        discovery_callback(repos)
    repository_rows: list[dict[str, Any]] = []
    capability_union: set[str] = set()
    for repo in repos:
        inspection = inspect_repository_capabilities(repo)
        capability_union.update(inspection["capabilities"])
        repository_rows.append(
            {
                "id": repository_id(repo),
                "path": repo.as_posix(),
                **inspection,
                "agent_file_proposals": [
                    agent_file_proposal(repo, name, sidecar_dir=sidecar_dir)
                    for name in STANDARD_AGENT_FILES
                ],
            }
        )

    system = normalized_platform()
    arch = normalized_arch()
    cache_path = (
        forge_root
        / "Harness"
        / "artifacts"
        / "control"
        / "tooling_plans"
        / "version_cache.json"
    )
    uv_present = command_present("uv")
    catalog_by_id = {spec.id: spec for spec in TOOL_CATALOG}
    unknown = sorted(
        (set(include_tools) | set(exclude_tools)) - set(catalog_by_id)
    )
    if unknown:
        raise WorkstationError("unknown tooling ids: " + ", ".join(unknown))
    selected_specs = {
        spec.id: spec
        for spec in recommended_tool_specs(capability_union)
    }
    selected_specs.update(
        {tool_id: catalog_by_id[tool_id] for tool_id in include_tools}
    )
    for tool_id in exclude_tools:
        selected_specs.pop(tool_id, None)
    tool_rows: list[dict[str, Any]] = []
    for spec in sorted(
        selected_specs.values(),
        key=lambda item: (item.category, item.id),
    ):
        present = command_present(spec.command)
        resolved = resolve_latest_version(
            spec,
            cache_path=cache_path,
            refresh=refresh_versions,
            system=system,
            arch=arch,
            prefer_python=uv_present,
        )
        action = _install_action(
            spec,
            system=system,
            resolved=resolved,
            uv_present=uv_present,
        )
        tool_rows.append(
            {
                "id": spec.id,
                "label": spec.label,
                "command": spec.command,
                "category": spec.category,
                "reason": spec.reason,
                "required": spec.required,
                "present": present,
                "status": "present" if present else "missing",
                "matched_capabilities": sorted(capability_union.intersection(spec.triggers)),
                "resolved": resolved,
                "install_action": action,
                "verification_command": (
                    [spec.command, "--version"] if spec.command else []
                ),
            }
        )

    missing_required = [
        row["id"] for row in tool_rows if row["required"] and not row["present"]
    ]
    missing_recommended = [
        row["id"] for row in tool_rows if not row["required"] and not row["present"]
    ]
    python_tool_lock = build_python_tool_lock(
        tool_rows,
        system=system,
        arch=arch,
    )
    payload: dict[str, Any] = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": utc_now(),
        "profile": profile,
        "explicitly_included_tools": sorted(set(include_tools)),
        "explicitly_excluded_tools": sorted(set(exclude_tools)),
        "platform": {"system": system, "arch": arch},
        "approved_workspaces": [path.as_posix() for path in approved],
        "discovered_repository_count": len(repository_rows),
        "repositories": repository_rows,
        "capabilities": sorted(capability_union),
        "tools": tool_rows,
        "python_tool_lock": python_tool_lock,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "status": "blocked" if missing_required else "ready",
        "consent": {
            "workspace_scope": True,
            "user_level_installs": True,
            "agent_files": True,
            "user_configuration": True,
            "privileged_scripts": True,
        },
        "safety": [
            "Only approved workspace roots were scanned.",
            "Project source contents were not inspected.",
            "No tools, agent files, shell profiles, or repositories were changed.",
            "The plan digest binds the exact approved actions.",
            "Privileged actions are generated for user execution.",
        ],
    }
    payload["plan_sha256"] = plan_digest(payload)
    return payload


def tooling_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Moradin Forge Workstation Plan",
        "",
        f"- generated_at: `{plan['generated_at']}`",
        f"- profile: `{plan['profile']}`",
        f"- platform: `{plan['platform']['system']}/{plan['platform']['arch']}`",
        f"- repositories: `{plan['discovered_repository_count']}`",
        f"- status: `{plan['status']}`",
        f"- plan_sha256: `{plan['plan_sha256']}`",
        "",
        "## Approved Workspaces",
        "",
    ]
    lines.extend(f"- `{path}`" for path in plan["approved_workspaces"])
    lines.extend(["", "## Discovered Repositories", ""])
    for repo in plan["repositories"]:
        lines.append(
            f"- `{repo['path']}`: "
            f"{', '.join(repo.get('capabilities', [])) or 'no project markers'}"
        )
        if repo.get("lowercase_agent_file_warnings"):
            lines.append(
                "  - non-canonical agent files: "
                + ", ".join(f"`{name}`" for name in repo["lowercase_agent_file_warnings"])
            )
    lines.extend(["", "## Tool Recommendations", ""])
    for row in plan["tools"]:
        lines.append(
            f"- `{row['id']}` [{row.get('status', 'unknown')}] "
            f"({row.get('category', 'manual')}): {row.get('reason', 'review required')}"
        )
        if row.get("status") == "missing":
            action = row["install_action"]
            lines.append(
                f"  - action: `{action['kind']}`; approval required; {action['reason']}"
            )
    python_lock = plan.get("python_tool_lock", {})
    if isinstance(python_lock, dict) and python_lock.get("status") != "not-required":
        lines.extend(
            [
                "",
                "## Offline Python Dependency Closure",
                "",
                f"- status: `{python_lock.get('status', 'unavailable')}`",
                f"- frozen requirements: `{len(python_lock.get('assets', []))}`",
                f"- blockers: `{len(python_lock.get('blockers', []))}`",
            ]
        )
    lines.extend(["", "## Agent File Proposals", ""])
    for repo in plan["repositories"]:
        lines.append(f"- `{repo['path']}`")
        for proposal in repo.get("agent_file_proposals", []):
            lines.append(
                f"  - `{proposal['path']}`: `{proposal['action']}`, explicit approval required"
            )
    lines.extend(["", "## Required User Decisions", ""])
    lines.extend(
        [
            "- Confirm the approved workspace list.",
            "- Select recommended tooling modules and approve user-level execution.",
            "- Approve each `AGENTS.md` or `CLAUDE.md` patch independently.",
            "- Approve PATH or shell-profile changes separately.",
            "- Review and run any privileged script, then ask the agent to verify.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tooling_plan_artifacts(
    forge_root: Path,
    plan: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, str]:
    run_id = run_id or datetime.now(tz=UTC).strftime("tooling_%Y%m%dT%H%M%S%fZ")
    root = (
        forge_root
        / "Harness"
        / "artifacts"
        / "control"
        / "tooling_plans"
        / run_id
    )
    json_path = root / "tooling_plan.json"
    markdown_path = root / "tooling_plan.md"
    write_json(json_path, plan)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(tooling_plan_markdown(plan), encoding="utf-8")
    privileged = write_privileged_scripts(root / "privileged", plan)
    return {
        "run_id": run_id,
        "json": json_path.as_posix(),
        "markdown": markdown_path.as_posix(),
        "privileged_bash": privileged["bash"],
        "privileged_bash_sha256": sha256_file(Path(privileged["bash"])),
        "privileged_powershell": privileged["powershell"],
        "privileged_powershell_sha256": sha256_file(
            Path(privileged["powershell"])
        ),
    }


def build_onboard_plan(
    workspaces: Sequence[Path],
    *,
    forge_root: Path,
    profile: str = DEFAULT_PROFILE,
    refresh_versions: bool = False,
    include_tools: Sequence[str] = (),
    exclude_tools: Sequence[str] = (),
    discovery_callback: Callable[[Sequence[Path]], None] | None = None,
) -> dict[str, Any]:
    tooling = build_tooling_plan(
        workspaces,
        forge_root=forge_root,
        profile=profile,
        refresh_versions=refresh_versions,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
        discovery_callback=discovery_callback,
    )
    payload: dict[str, Any] = {
        "version": ONBOARD_PLAN_VERSION,
        "generated_at": utc_now(),
        "tooling_plan": tooling,
        "questions": [
            "Are these the complete workspace roots Forge may inspect?",
            "Which recommended tooling modules may Forge install at user level?",
            "Which AGENTS.md and CLAUDE.md proposals may Forge apply?",
            "May Forge change user PATH or shell configuration?",
            "Will you review and run the generated privileged script if needed?",
        ],
        "next_commands": {
            "tooling_apply": (
                "scripts/moradin_forge.sh tooling-apply --plan <tooling-plan.json> "
                f"--approve-plan-sha256 {tooling['plan_sha256']}"
            ),
            "integration": (
                "scripts/moradin_forge.sh apply --target <target-repo> --approve "
                "--approve-agent-file AGENTS.md"
            ),
        },
    }
    payload["plan_sha256"] = plan_digest(payload)
    return payload


def load_bound_plan(path: Path, expected_version: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise WorkstationError(f"plan must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkstationError(f"plan is not valid JSON: {path}") from error
    if not isinstance(payload, dict) or payload.get("version") != expected_version:
        raise WorkstationError(f"plan version must be {expected_version}")
    recorded = str(payload.get("plan_sha256", ""))
    actual = plan_digest(payload)
    if not recorded or recorded != actual:
        raise WorkstationError("plan digest is missing or does not match its contents")
    return payload


def validate_tooling_plan(
    plan: dict[str, Any],
    *,
    require_current_platform: bool,
) -> None:
    if plan.get("profile") != DEFAULT_PROFILE:
        raise WorkstationError("tooling plan profile is not supported")
    plan_platform = plan.get("platform", {})
    system = str(plan_platform.get("system", ""))
    if system not in {"linux", "macos", "windows"}:
        raise WorkstationError("tooling plan platform is not supported")
    if require_current_platform and system != normalized_platform():
        raise WorkstationError(
            f"tooling plan targets {system}, not the current {normalized_platform()} host"
        )
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    seen: set[str] = set()
    for row in plan.get("tools", []):
        if not isinstance(row, dict):
            raise WorkstationError("tooling plan contains a malformed tool row")
        tool_id = str(row.get("id", ""))
        if tool_id in seen or tool_id not in catalog:
            raise WorkstationError(f"tooling plan contains an invalid tool id: {tool_id}")
        seen.add(tool_id)
        spec = catalog[tool_id]
        expected_verification = (
            [spec.command, "--version"] if spec.command else []
        )
        if (
            row.get("label") != spec.label
            or row.get("command") != spec.command
            or row.get("category") != spec.category
            or row.get("reason") != spec.reason
            or row.get("required") is not spec.required
            or row.get("verification_command", expected_verification)
            != expected_verification
            or not isinstance(row.get("present"), bool)
        ):
            raise WorkstationError(
                f"tooling plan row does not match the verified catalog: {tool_id}"
            )
        if row.get("present"):
            continue
        resolved = row.get("resolved", {})
        action = row.get("install_action", {})
        if not isinstance(resolved, dict) or not isinstance(action, dict):
            raise WorkstationError(f"tooling plan action is malformed for {tool_id}")
        if action.get("tool_id") not in {None, "", tool_id}:
            raise WorkstationError(f"tooling plan action id mismatch for {tool_id}")
        kind = str(action.get("kind", ""))
        argv = action.get("argv", [])
        if kind == "manual":
            if argv:
                raise WorkstationError(f"manual tooling action must not contain argv: {tool_id}")
            continue
        version = str(resolved.get("version", ""))
        if not version or version == "latest-stable":
            raise WorkstationError(f"automatic tooling action is not version-frozen: {tool_id}")
        if kind == "user-local":
            expected = [
                "uv",
                "tool",
                "install",
                "--force",
                f"{spec.python_package}=={version}",
            ]
            if (
                system not in {"linux", "macos", "windows"}
                or not spec.python_package
                or argv != expected
                or resolved.get("cache") not in {"fresh", "refreshed"}
                or resolved.get("source") != "pypi"
                or resolved.get("trust") != "pypi-hash-verified"
                or not (
                    resolved.get("artifact_sha256s")
                    or resolved.get("sha256")
                )
                or action.get("auto_execute") is not True
            ):
                raise WorkstationError(
                    f"user-local tooling action does not match the verified catalog: {tool_id}"
                )
            continue
        if kind == "user-package-manager":
            expected = ["brew", "install", spec.brew_formula]
            if (
                system != "macos"
                or not spec.brew_formula
                or argv != expected
                or resolved.get("cache") not in {"fresh", "refreshed"}
                or resolved.get("source") != "homebrew"
                or resolved.get("trust") != "signed-package-manager"
                or action.get("auto_execute") is not True
            ):
                raise WorkstationError(
                    f"package-manager action does not match the verified catalog: {tool_id}"
                )
            continue
        if kind == "privileged-script":
            expected_package = (
                spec.apt_package if system == "linux" else spec.winget_id
            )
            expected_source = "apt" if system == "linux" else "winget"
            if (
                system not in {"linux", "windows"}
                or not expected_package
                or action.get("package") != expected_package
                or action.get("version") != version
                or action.get("requires_elevation") is not True
                or action.get("auto_execute") is not False
                or argv
                or resolved.get("cache") not in {"fresh", "refreshed"}
                or resolved.get("source") != expected_source
                or resolved.get("trust") != "signed-package-manager"
            ):
                raise WorkstationError(
                    f"privileged tooling action does not match the verified catalog: {tool_id}"
                )
            continue
        raise WorkstationError(f"unsupported tooling action kind for {tool_id}: {kind}")
    python_lock = plan.get("python_tool_lock")
    if python_lock is not None:
        if not isinstance(python_lock, dict):
            raise WorkstationError("Python tool lock is malformed")
        requirements = str(python_lock.get("requirements", ""))
        recorded_hash = str(python_lock.get("requirements_sha256", ""))
        if requirements:
            if sha256_bytes(requirements.encode("utf-8")) != recorded_hash:
                raise WorkstationError("Python tool lock digest does not match")
            pinned = parse_hashed_requirements(requirements)
        else:
            pinned = []
        pinned_pairs = {
            (normalized_package_name(package), version)
            for package, version in pinned
        }
        if len(pinned_pairs) != len(pinned):
            raise WorkstationError("Python tool lock contains duplicate packages")
        direct_expected = sorted(
            {
                str(row["install_action"]["package"])
                for row in plan.get("tools", [])
                if isinstance(row, dict)
                and not row.get("present")
                and isinstance(row.get("install_action"), dict)
                and row["install_action"].get("kind") == "user-local"
                and row["install_action"].get("auto_execute")
            }
        )
        if sorted(python_lock.get("direct_requirements", [])) != direct_expected:
            raise WorkstationError(
                "Python tool lock does not match selected user-local tools"
            )
        asset_pairs: set[tuple[str, str]] = set()
        asset_filenames: set[str] = set()
        for asset in python_lock.get("assets", []):
            if not isinstance(asset, dict):
                raise WorkstationError("Python bundle asset is malformed")
            url = str(asset.get("url", ""))
            digest = str(asset.get("sha256", ""))
            filename = str(asset.get("filename", ""))
            package = normalized_package_name(str(asset.get("package", "")))
            version = str(asset.get("version", ""))
            _assert_official_asset(url)
            if (
                not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not filename
                or Path(filename).name != filename
                or not filename.lower().endswith(".whl")
                or not package
                or not version
                or asset.get("source") != "pypi"
                or (package, version) not in pinned_pairs
                or digest not in requirements
                or filename in asset_filenames
            ):
                raise WorkstationError("Python bundle asset integrity is malformed")
            asset_pairs.add((package, version))
            asset_filenames.add(filename)
        if python_lock.get("status") == "ready" and (
            asset_pairs != pinned_pairs or python_lock.get("blockers")
        ):
            raise WorkstationError(
                "ready Python tool lock does not include its complete dependency closure"
            )
        if not asset_pairs.issubset(pinned_pairs):
            raise WorkstationError(
                "Python bundle assets do not match the frozen dependency closure"
            )


def _safe_action_argv(action: dict[str, Any]) -> list[str]:
    argv = action.get("argv")
    if not isinstance(argv, list) or not argv or not all(
        isinstance(item, str) and item and "\x00" not in item for item in argv
    ):
        raise WorkstationError("approved user-level install action has invalid argv")
    executable = argv[0]
    if executable not in {"uv", "brew", "winget"}:
        raise WorkstationError(f"approved installer executable is not allowlisted: {executable}")
    return argv


def render_privileged_bash(plan: dict[str, Any]) -> str:
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    plan_system = str(plan.get("platform", {}).get("system", ""))
    package_versions = {
        str(row["install_action"]["package"]): str(
            row["install_action"].get("version", "")
        )
        for row in plan["tools"]
        if plan_system in {"", "linux"}
        if not row["present"]
        and row["install_action"]["kind"] == "privileged-script"
        and row["install_action"]["package"]
    }
    packages = sorted(
        f"{package}={version}" if version else package
        for package, version in package_versions.items()
    )
    reversal_packages = sorted(package_versions)
    quoted = " ".join("'" + package.replace("'", "'\"'\"'") + "'" for package in packages)
    reversal_quoted = " ".join(
        "'" + package.replace("'", "'\"'\"'") + "'"
        for package in reversal_packages
    )
    verify_commands = sorted(
        {
            catalog[str(row["id"])].command
            for row in plan["tools"]
            if plan_system in {"", "linux"}
            if str(row.get("id", "")) in catalog
            if row["id"] in {
                item["tool_id"]
                for item in (
                    candidate["install_action"]
                    for candidate in plan["tools"]
                    if candidate["install_action"]["kind"] == "privileged-script"
                )
            }
            and catalog[str(row["id"])].command
        }
    )
    checks = "\n".join(f"command -v {command!s} >/dev/null" for command in verify_commands)
    return f"""#!/usr/bin/env bash
set -euo pipefail

packages=({quoted})
reversal_packages=({reversal_quoted})
if [[ "${{#packages[@]}}" -eq 0 ]]; then
  printf '%s\\n' "No privileged packages were selected."
  exit 0
fi
if [[ "${{1:-}}" != "--apply" ]]; then
  printf 'dry-run packages:'
  printf ' %q' "${{packages[@]}}"
  printf '\\n'
  exit 0
fi
if [[ "${{EUID}}" -ne 0 ]]; then
  printf '%s\\n' "Run this reviewed script explicitly with sudo." >&2
  exit 2
fi

apt-get update
apt-get install -y -- "${{packages[@]}}"
{checks}
printf '%s\\n' "Moradin privileged tooling verification passed."
printf '%s\\n' "reversal: apt-get remove -- ${{reversal_packages[*]}}"
"""


def render_privileged_powershell(plan: dict[str, Any]) -> str:
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    plan_system = str(plan.get("platform", {}).get("system", ""))
    packages = sorted(
        (
            str(row["install_action"]["package"]),
            str(row["install_action"].get("version", "")),
        )
        for row in plan["tools"]
        if plan_system in {"", "windows"}
        if not row["present"]
        and row["install_action"]["kind"] == "privileged-script"
        and row["install_action"]["package"]
    )
    rendered = ", ".join(
        (
            "@{ Id = '"
            + package.replace("'", "''")
            + "'; Version = '"
            + version.replace("'", "''")
            + "' }"
        )
        for package, version in packages
    )
    commands = sorted(
        {
            catalog[str(row["id"])].command
            for row in plan["tools"]
            if plan_system in {"", "windows"}
            if str(row.get("id", "")) in catalog
            if not row["present"]
            and row["install_action"]["kind"] == "privileged-script"
            and catalog[str(row["id"])].command
        }
    )
    rendered_commands = ", ".join(
        "'" + item.replace("'", "''") + "'" for item in commands
    )
    return f"""param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$packages = @({rendered})
$commands = @({rendered_commands})
if ($packages.Count -eq 0) {{
  Write-Output 'No privileged packages were selected.'
  exit 0
}}
if (-not $Apply) {{
  Write-Output ('dry-run packages: ' + (($packages | ForEach-Object {{ $_.Id + '@' + $_.Version }}) -join ', '))
  exit 0
}}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
  throw 'Run this reviewed script from an elevated PowerShell session.'
}}
foreach ($package in $packages) {{
  $versionArgs = @()
  if ($package.Version) {{ $versionArgs = @('--version', $package.Version) }}
  winget install --exact --id $package.Id @versionArgs --accept-package-agreements --accept-source-agreements
}}
foreach ($command in $commands) {{
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {{
    throw "Verification failed for $command"
  }}
}}
Write-Output 'Moradin privileged tooling verification passed.'
Write-Output ('reversal: winget uninstall --exact --id ' + (($packages | ForEach-Object {{ $_.Id }}) -join '; winget uninstall --exact --id '))
"""


def write_privileged_scripts(output_root: Path, plan: dict[str, Any]) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    bash_path = output_root / "install-privileged.sh"
    powershell_path = output_root / "install-privileged.ps1"
    bash_path.write_text(render_privileged_bash(plan), encoding="utf-8")
    bash_path.chmod(0o755)
    powershell_path.write_text(render_privileged_powershell(plan), encoding="utf-8")
    return {
        "bash": bash_path.as_posix(),
        "powershell": powershell_path.as_posix(),
    }


def apply_user_path_config(bin_root: Path) -> dict[str, Any]:
    if normalized_platform() == "windows":
        return {
            "status": "manual",
            "path": "<user-environment>",
            "reason": (
                "Windows PATH updates remain a separately reviewed user action; "
                f"add {bin_root.as_posix()} to the user PATH."
            ),
        }
    profile_path = Path.home() / ".profile"
    if profile_path.is_symlink():
        raise WorkstationError("refusing to edit a symlinked user profile")
    if profile_path.exists() and not profile_path.is_file():
        raise WorkstationError("user profile must be a regular file")
    existing = (
        profile_path.read_text(encoding="utf-8")
        if profile_path.is_file()
        else ""
    )
    if PATH_MARKER_BEGIN in existing or PATH_MARKER_END in existing:
        if existing.count(PATH_MARKER_BEGIN) != 1 or existing.count(PATH_MARKER_END) != 1:
            raise WorkstationError("user profile contains ambiguous Moradin PATH markers")
        return {
            "status": "already_present",
            "path": "<user-home>/.profile",
        }
    block = "\n".join(
        [
            PATH_MARKER_BEGIN,
            'export PATH="$HOME/.local/bin:$PATH"',
            PATH_MARKER_END,
            "",
        ]
    )
    separator = "" if not existing or existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n"
    rendered = existing + separator + block
    atomic_write_text(profile_path, rendered)
    return {
        "status": "patched" if existing else "created",
        "path": "<user-home>/.profile",
        "before_sha256": sha256_bytes(existing.encode("utf-8")) if existing else "",
        "after_sha256": sha256_file(profile_path),
        "owned_block_sha256": sha256_bytes(block.encode("utf-8")),
    }


def shim_identity(bin_root: Path, command: str) -> tuple[str, str]:
    if not command:
        return "", ""
    names = [command]
    if normalized_platform() == "windows":
        names.extend(f"{command}{suffix}" for suffix in (".exe", ".cmd", ".bat"))
    for name in names:
        path = bin_root / name
        if path.is_symlink():
            identity = "symlink:" + os.readlink(path)
        elif path.is_file():
            identity = "file:" + sha256_file(path)
        else:
            continue
        return sha256_bytes(identity.encode("utf-8")), name
    return "", ""


def apply_tooling_plan(
    plan_path: Path,
    *,
    approved_sha256: str,
    forge_root: Path,
    user_config_approved: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    plan = load_bound_plan(plan_path, WORKSTATION_PLAN_VERSION)
    if approved_sha256 != plan["plan_sha256"]:
        raise WorkstationError("approved plan digest does not match the tooling plan")
    validate_tooling_plan(plan, require_current_platform=True)
    install_base = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        / "moradins-forge"
        / "tools"
    )
    generation = str(plan["plan_sha256"])[:16]
    install_root = install_base / generation
    bin_root = Path.home() / ".local" / "bin"
    install_root.mkdir(parents=True, exist_ok=True)
    bin_root.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "UV_TOOL_DIR": install_root.as_posix(),
            "UV_TOOL_BIN_DIR": bin_root.as_posix(),
            "HOMEBREW_NO_AUTO_UPDATE": "1",
            "PATH": (
                bin_root.as_posix()
                + os.pathsep
                + environment.get("PATH", "")
            ),
        }
    )
    receipt_root = (
        forge_root
        / "Harness"
        / "artifacts"
        / "control"
        / "tooling_receipts"
        / datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    executed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None
    for row in plan["tools"]:
        if row["present"]:
            continue
        action = row["install_action"]
        if action["kind"] not in {"user-local", "user-package-manager"}:
            skipped.append({"tool_id": row["id"], "reason": action["reason"]})
            continue
        if not action.get("auto_execute"):
            skipped.append(
                {
                    "tool_id": row["id"],
                    "reason": "installer lacks verified automatic execution evidence",
                }
            )
            continue
        argv = _safe_action_argv(action)
        try:
            result = runner(
                argv,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=900,
            )
            install_exit_code = int(result.returncode)
            install_reason = ""
        except (OSError, subprocess.TimeoutExpired) as error:
            install_exit_code = (
                124 if isinstance(error, subprocess.TimeoutExpired) else 127
            )
            install_reason = "installer could not be executed safely"
        executed_item = {
            "tool_id": row["id"],
            "action_kind": action["kind"],
            "version": row["resolved"]["version"],
            "argv_sha256": sha256_bytes(canonical_json_bytes(argv)),
            "exit_code": install_exit_code,
            "status": "pass" if install_exit_code == 0 else "fail",
            "verification_exit_code": None,
            "verification_status": "not_run",
        }
        executed.append(executed_item)
        if install_exit_code != 0:
            failure = {
                "tool_id": row["id"],
                "exit_code": install_exit_code,
                "reason": (
                    install_reason
                    or "approved user-level installer returned a failure"
                ),
            }
            break
        verification_argv = list(row["verification_command"])
        try:
            verification = runner(
                verification_argv,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )
            verification_exit_code = int(verification.returncode)
            verification_reason = ""
        except (OSError, subprocess.TimeoutExpired) as error:
            verification_exit_code = (
                124 if isinstance(error, subprocess.TimeoutExpired) else 127
            )
            verification_reason = "installed tool could not be rechecked safely"
        executed_item["verification_exit_code"] = verification_exit_code
        executed_item["verification_status"] = (
            "pass" if verification_exit_code == 0 else "fail"
        )
        shim_sha256, shim_name = shim_identity(
            bin_root,
            str(row.get("command", "")),
        )
        executed_item["shim_identity_sha256"] = shim_sha256
        executed_item["shim_name"] = shim_name
        if verification_exit_code != 0:
            executed_item["status"] = "fail"
            failure = {
                "tool_id": row["id"],
                "exit_code": verification_exit_code,
                "reason": (
                    verification_reason
                    or "installed tool failed its catalog verification command"
                ),
            }
            break

    user_config = (
        apply_user_path_config(bin_root)
        if user_config_approved and failure is None
        else {
            "status": (
                "not_approved"
                if not user_config_approved
                else "not_applied_after_install_failure"
            ),
            "path": "<user-home>/.local/bin",
        }
    )
    recheck = []
    for row in plan["tools"]:
        command = str(row.get("command", ""))
        candidates = [command]
        if command == "python3":
            candidates.extend(["python", "py"])
        if command == "fd":
            candidates.append("fdfind")
        recheck.append(
            {
                "tool_id": row["id"],
                "present": bool(command)
                and any(
                    shutil.which(candidate, path=environment["PATH"]) is not None
                    for candidate in candidates
                    if candidate
                ),
            }
        )
    receipt: dict[str, Any] = {
        "version": TOOLING_RECEIPT_VERSION,
        "generated_at": utc_now(),
        "status": "fail" if failure else "pass",
        "failure": failure,
        "plan_sha256": plan["plan_sha256"],
        "install_root": f"<user-data>/moradins-forge/tools/{generation}",
        "install_generation": generation,
        "bin_root": "<user-home>/.local/bin",
        "user_config_approved": user_config_approved,
        "user_config": user_config,
        "executed": executed,
        "skipped": skipped,
        "recheck": recheck,
        "missing_required_after": sorted(
            row["tool_id"]
            for row in recheck
            if not row["present"]
            and next(
                item["required"]
                for item in plan["tools"]
                if item["id"] == row["tool_id"]
            )
        ),
        "privileged_scripts": {},
        "safety": (
            "No privileged command was executed. "
            + (
                "The separately approved Forge PATH marker was applied."
                if user_config.get("status") in {"created", "patched"}
                else "No shell-profile edit was executed."
            )
        ),
    }
    receipt["privileged_scripts"] = write_privileged_scripts(receipt_root, plan)
    write_json(receipt_root / "receipt.json", receipt)
    receipt["receipt"] = (receipt_root / "receipt.json").as_posix()
    if failure:
        raise WorkstationError(
            f"approved tooling action failed for {failure['tool_id']} "
            f"with exit code {failure['exit_code']} ({failure['reason']}); "
            "rollback receipt: "
            f"{receipt['receipt']}"
        )
    return receipt


def rollback_tooling_receipt(
    receipt_path: Path,
    *,
    approve: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not approve:
        raise WorkstationError("tooling rollback requires --approve")
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise WorkstationError(f"tooling receipt must be a regular file: {receipt_path}")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkstationError("tooling receipt is not valid JSON") from error
    if not isinstance(receipt, dict) or receipt.get("version") != TOOLING_RECEIPT_VERSION:
        raise WorkstationError(f"receipt version must be {TOOLING_RECEIPT_VERSION}")
    install_base = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        / "moradins-forge"
        / "tools"
    )
    generation = str(receipt.get("install_generation", ""))
    if generation and not re.fullmatch(r"[0-9a-f]{16}", generation):
        raise WorkstationError("tooling receipt install generation is invalid")
    install_root = install_base / generation if generation else install_base
    bin_root = Path.home() / ".local" / "bin"
    environment = os.environ.copy()
    environment.update(
        {
            "UV_TOOL_DIR": install_root.as_posix(),
            "UV_TOOL_BIN_DIR": bin_root.as_posix(),
        }
    )
    removed: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []
    for item in reversed(receipt.get("executed", [])):
        if not isinstance(item, dict):
            continue
        tool_id = str(item.get("tool_id", ""))
        spec = next((candidate for candidate in TOOL_CATALOG if candidate.id == tool_id), None)
        action_kind = str(item.get("action_kind", ""))
        if spec and spec.python_package and action_kind in {"", "user-local"}:
            expected_shim = str(item.get("shim_identity_sha256", ""))
            if expected_shim:
                current_shim, _name = shim_identity(bin_root, spec.command)
                if current_shim != expected_shim:
                    manual.append(
                        {
                            "tool_id": tool_id,
                            "reason": (
                                "the shared shim changed after this receipt; "
                                "the newer generation was preserved"
                            ),
                        }
                    )
                    continue
            argv = ["uv", "tool", "uninstall", spec.python_package]
            result = runner(
                argv,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            removed.append(
                {
                    "tool_id": tool_id,
                    "exit_code": int(result.returncode),
                    "status": "pass" if result.returncode == 0 else "fail",
                }
            )
        else:
            manual.append(
                {
                    "tool_id": tool_id,
                    "reason": "shared package-manager installs require explicit native removal",
                }
            )
    user_config = receipt.get("user_config", {})
    config_rollback: dict[str, Any] = {"status": "not_owned"}
    if isinstance(user_config, dict) and user_config.get("status") in {
        "created",
        "patched",
        "already_present",
    }:
        if normalized_platform() == "windows":
            config_rollback = {
                "status": "manual",
                "reason": "Windows PATH changes are user-managed.",
            }
        else:
            profile_path = Path.home() / ".profile"
            if not profile_path.is_file() or profile_path.is_symlink():
                config_rollback = {
                    "status": "manual",
                    "reason": "The recorded profile is missing or not a regular file.",
                }
            else:
                current = profile_path.read_text(encoding="utf-8")
                if (
                    current.count(PATH_MARKER_BEGIN) != 1
                    or current.count(PATH_MARKER_END) != 1
                ):
                    config_rollback = {
                        "status": "manual",
                        "reason": "The Forge PATH marker is missing or ambiguous.",
                    }
                else:
                    start = current.index(PATH_MARKER_BEGIN)
                    end = current.index(PATH_MARKER_END, start) + len(PATH_MARKER_END)
                    if end < len(current) and current[end] == "\n":
                        end += 1
                    block = current[start:end]
                    expected = str(user_config.get("owned_block_sha256", ""))
                    if not expected or sha256_bytes(block.encode("utf-8")) != expected:
                        config_rollback = {
                            "status": "manual",
                            "reason": "The owned PATH marker was modified.",
                        }
                    else:
                        prefix = current[:start]
                        suffix = current[end:]
                        candidates = [prefix + suffix]
                        if prefix.endswith("\n"):
                            candidates.append(prefix[:-1] + suffix)
                        if prefix.endswith("\n\n"):
                            candidates.append(prefix[:-2] + suffix)
                        expected_before = str(user_config.get("before_sha256", ""))
                        restored = next(
                            (
                                candidate
                                for candidate in candidates
                                if expected_before
                                and sha256_bytes(candidate.encode("utf-8"))
                                == expected_before
                            ),
                            candidates[0],
                        )
                        if user_config.get("status") == "created" and not restored:
                            profile_path.unlink()
                            config_rollback = {"status": "removed_created_profile"}
                        else:
                            atomic_write_text(profile_path, restored)
                            config_rollback = {"status": "restored"}
    return {
        "version": TOOLING_ROLLBACK_VERSION,
        "generated_at": utc_now(),
        "status": (
            "pass"
            if all(item["status"] == "pass" for item in removed)
            else "fail"
        ),
        "removed": removed,
        "manual": manual,
        "user_config": config_rollback,
        "safety": (
            "Only Forge-recorded user-local uv tools and an unmodified owned "
            "PATH marker were automatically removed."
        ),
    }


def _assert_official_asset(url: str) -> None:
    _assert_official_https_url(url, purpose="offline bundle asset")


def _download_asset(url: str, destination: Path) -> None:
    _assert_official_asset(url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "moradins-forge-offline-bundle/0.2.0-beta.3"},
    )
    with _open_official_url(request, timeout=30) as response:
        destination.write_bytes(response.read())


def portable_bundle_plan(plan: dict[str, Any]) -> dict[str, Any]:
    portable = json.loads(json.dumps(plan))
    source_sha = str(portable.pop("plan_sha256", ""))
    portable.pop("artifacts", None)
    portable["approved_workspaces"] = [
        f"<workspace-{index}>"
        for index, _path in enumerate(portable.get("approved_workspaces", []), start=1)
    ]
    for index, repository in enumerate(portable.get("repositories", []), start=1):
        if isinstance(repository, dict):
            repository["path"] = f"<repo-{index}>"
            repository.pop("patch_preview", None)
    portable["source_plan_sha256"] = source_sha
    portable["portable"] = True
    portable["plan_sha256"] = plan_digest(portable)
    return portable


def offline_user_verification_commands(plan: dict[str, Any]) -> list[str]:
    catalog = {spec.id: spec for spec in TOOL_CATALOG}
    return sorted(
        {
            catalog[str(row["id"])].command
            for row in plan.get("tools", [])
            if isinstance(row, dict)
            and str(row.get("id", "")) in catalog
            and not row.get("present")
            and isinstance(row.get("install_action"), dict)
            and row["install_action"].get("kind") == "user-local"
            and row["install_action"].get("auto_execute")
            and catalog[str(row["id"])].command
        }
    )


def render_offline_user_bash(plan: dict[str, Any]) -> str:
    python_lock = plan.get("python_tool_lock", {})
    requirements = (
        sorted(python_lock.get("direct_requirements", []))
        if isinstance(python_lock, dict) and python_lock.get("status") == "ready"
        else []
    )
    quoted = " ".join(
        "'" + requirement.replace("'", "'\"'\"'") + "'"
        for requirement in requirements
    )
    commands = " ".join(
        "'" + command.replace("'", "'\"'\"'") + "'"
        for command in offline_user_verification_commands(plan)
    )
    generation = str(plan.get("plan_sha256", ""))[:16]
    return f"""#!/usr/bin/env bash
set -euo pipefail

bundle_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if find "$bundle_root" -type l -print -quit | grep -q .; then
  printf '%s\\n' "Offline bundle must not contain symbolic links." >&2
  exit 2
fi
while IFS= read -r checksum_line; do
  expected=${{checksum_line%%  *}}
  relative=${{checksum_line#*  }}
  if [[ "${{#expected}}" -ne 64 || "$expected" == *[!0-9a-f]* ||
        "$relative" == "$checksum_line" || -z "$relative" ||
        "$relative" == /* || "$relative" == ../* ||
        "$relative" == */../* || "$relative" == */.. ||
        "$relative" == *\\\\* ]]; then
    printf '%s\\n' "Unsafe SHA256SUMS entry." >&2
    exit 2
  fi
done < "$bundle_root/SHA256SUMS"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$bundle_root" && sha256sum -c SHA256SUMS)
else
  (cd "$bundle_root" && shasum -a 256 -c SHA256SUMS)
fi
if ! command -v uv >/dev/null 2>&1; then
  printf '%s\\n' "uv is required before offline user-tool installation." >&2
  exit 2
fi
requirements=({quoted})
commands=({commands})
if [[ "${{#requirements[@]}}" -eq 0 ]]; then
  printf '%s\\n' "No complete offline user-tool set is available in this bundle."
  exit 0
fi
export UV_TOOL_DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/moradins-forge/tools/{generation}"
export UV_TOOL_BIN_DIR="$HOME/.local/bin"
for requirement in "${{requirements[@]}}"; do
  uv tool install --force --offline --no-index --no-config --no-python-downloads \\
    --find-links "$bundle_root/assets" \\
    --constraints "$bundle_root/constraints.txt" \\
    "$requirement"
done
for command_name in "${{commands[@]}}"; do
  command -v "$command_name" >/dev/null
done
printf '%s\\n' "Moradin offline user-tool installation passed."
"""


def render_offline_user_powershell(plan: dict[str, Any]) -> str:
    python_lock = plan.get("python_tool_lock", {})
    requirements = (
        sorted(python_lock.get("direct_requirements", []))
        if isinstance(python_lock, dict) and python_lock.get("status") == "ready"
        else []
    )
    rendered = ", ".join(
        "'" + requirement.replace("'", "''") + "'"
        for requirement in requirements
    )
    commands = ", ".join(
        "'" + command.replace("'", "''") + "'"
        for command in offline_user_verification_commands(plan)
    )
    generation = str(plan.get("plan_sha256", ""))[:16]
    return f"""$ErrorActionPreference = 'Stop'
$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Get-ChildItem -LiteralPath $bundleRoot -Recurse -Force |
    Where-Object {{ $_.Attributes -band [IO.FileAttributes]::ReparsePoint }} |
    Select-Object -First 1) {{
  throw 'Offline bundle must not contain reparse points.'
}}
$bundleFull = [IO.Path]::GetFullPath($bundleRoot) + [IO.Path]::DirectorySeparatorChar
Get-Content (Join-Path $bundleRoot 'SHA256SUMS') | ForEach-Object {{
  if ($_ -notmatch '^([0-9a-f]{{64}})  (.+)$') {{ throw 'Malformed SHA256SUMS entry.' }}
  $expected = $Matches[1]
  $relativeText = $Matches[2]
  if ([IO.Path]::IsPathRooted($relativeText) -or
      $relativeText -match '(^|[\\\\/])\\.\\.([\\\\/]|$)') {{
    throw 'Unsafe SHA256SUMS entry.'
  }}
  $relative = $relativeText -replace '/', [IO.Path]::DirectorySeparatorChar
  $candidate = [IO.Path]::GetFullPath((Join-Path $bundleRoot $relative))
  if (-not $candidate.StartsWith($bundleFull, [StringComparison]::OrdinalIgnoreCase)) {{
    throw 'Unsafe SHA256SUMS entry.'
  }}
  $actual = (Get-FileHash -Algorithm SHA256 $candidate).Hash.ToLowerInvariant()
  if ($actual -ne $expected) {{ throw "Checksum mismatch: $relative" }}
}}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {{
  throw 'uv is required before offline user-tool installation.'
}}
$requirements = @({rendered})
$commands = @({commands})
if ($requirements.Count -eq 0) {{
  Write-Output 'No complete offline user-tool set is available in this bundle.'
  exit 0
}}
$dataRoot = if ($env:LOCALAPPDATA) {{ $env:LOCALAPPDATA }} else {{ Join-Path $HOME '.local/share' }}
$env:UV_TOOL_DIR = Join-Path $dataRoot 'moradins-forge/tools/{generation}'
$env:UV_TOOL_BIN_DIR = Join-Path $HOME '.local/bin'
foreach ($requirement in $requirements) {{
  uv tool install --force --offline --no-index --no-config --no-python-downloads `
    --find-links (Join-Path $bundleRoot 'assets') `
    --constraints (Join-Path $bundleRoot 'constraints.txt') `
    $requirement
}}
foreach ($command in $commands) {{
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {{
    throw "Verification failed for $command"
  }}
}}
Write-Output 'Moradin offline user-tool installation passed.'
"""


def write_offline_user_scripts(output_root: Path, plan: dict[str, Any]) -> dict[str, str]:
    bash_path = output_root / "install-user-tools-offline.sh"
    powershell_path = output_root / "install-user-tools-offline.ps1"
    bash_path.write_text(render_offline_user_bash(plan), encoding="utf-8")
    bash_path.chmod(0o755)
    powershell_path.write_text(
        render_offline_user_powershell(plan),
        encoding="utf-8",
    )
    return {
        "bash": bash_path.name,
        "powershell": powershell_path.name,
    }


def build_offline_bundle(
    plan_path: Path,
    *,
    output: Path,
    downloader: Callable[[str, Path], None] = _download_asset,
) -> dict[str, Any]:
    plan = load_bound_plan(plan_path, WORKSTATION_PLAN_VERSION)
    validate_tooling_plan(plan, require_current_platform=False)
    if output.exists() or output.is_symlink():
        raise WorkstationError(f"offline bundle output already exists: {output}")
    staging_parent = output.parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="moradin-bundle-", dir=staging_parent) as temporary:
        root = Path(temporary) / "bundle"
        assets_root = root / "assets"
        assets_root.mkdir(parents=True)
        bundled_plan = portable_bundle_plan(plan)
        write_json(root / "tooling_plan.json", bundled_plan)
        (root / "tooling_plan.md").write_text(
            tooling_plan_markdown(bundled_plan),
            encoding="utf-8",
        )
        privileged_scripts = {
            key: Path(value).name
            for key, value in write_privileged_scripts(root, plan).items()
        }
        offline_user_scripts = write_offline_user_scripts(root, plan)
        included: list[dict[str, str]] = []
        blockers: list[dict[str, str]] = []
        downloaded_urls: set[str] = set()
        python_lock = plan.get("python_tool_lock", {})
        if isinstance(python_lock, dict) and python_lock.get("requirements"):
            (root / "requirements.lock").write_text(
                str(python_lock["requirements"]),
                encoding="utf-8",
            )
        constraints = sorted(
            {
                f"{asset['package']}=={asset['version']}"
                for asset in (
                    python_lock.get("assets", [])
                    if isinstance(python_lock, dict)
                    else []
                )
            }
        )
        (root / "constraints.txt").write_text(
            "\n".join(constraints) + ("\n" if constraints else ""),
            encoding="utf-8",
        )
        if isinstance(python_lock, dict):
            for blocker in python_lock.get("blockers", []):
                blockers.append(
                    {
                        "tool_id": "python-tool-closure",
                        "reason": str(blocker.get("reason", "unresolved Python wheel")),
                    }
                )
            for asset in python_lock.get("assets", []):
                asset_url = str(asset["url"])
                expected = str(asset["sha256"])
                filename = str(asset["filename"])
                destination = assets_root / filename
                if destination.exists():
                    raise WorkstationError(
                        f"offline bundle asset filename collision: {filename}"
                    )
                _assert_official_asset(asset_url)
                downloader(asset_url, destination)
                actual = sha256_file(destination)
                if actual != expected:
                    raise WorkstationError(
                        f"offline asset digest mismatch for {asset['package']}: {actual}"
                    )
                downloaded_urls.add(asset_url)
                included.append(
                    {
                        "tool_id": f"python:{asset['package']}",
                        "path": destination.relative_to(root).as_posix(),
                        "sha256": actual,
                    }
                )
        for row in plan["tools"]:
            if row["present"]:
                continue
            action = row["install_action"]
            if action["kind"] == "user-local":
                if not (
                    isinstance(python_lock, dict)
                    and python_lock.get("status") == "ready"
                ):
                    blockers.append(
                        {
                            "tool_id": row["id"],
                            "reason": "complete frozen Python dependency closure is unavailable",
                        }
                    )
                continue
            resolved = row["resolved"]
            asset_url = str(resolved.get("asset_url", ""))
            expected = str(resolved.get("sha256", ""))
            if not asset_url or not expected:
                blockers.append(
                    {
                        "tool_id": row["id"],
                        "reason": "no verified downloadable asset was resolved",
                    }
                )
                continue
            filename = str(resolved.get("asset_filename", "")) or Path(
                urllib.parse.urlparse(asset_url).path
            ).name
            if not filename or Path(filename).name != filename:
                raise WorkstationError(
                    f"offline bundle asset filename is unsafe for {row['id']}"
                )
            if asset_url in downloaded_urls:
                continue
            destination = assets_root / f"{row['id']}-{filename}"
            _assert_official_asset(asset_url)
            downloader(asset_url, destination)
            actual = sha256_file(destination)
            if actual != expected:
                raise WorkstationError(
                    f"offline asset digest mismatch for {row['id']}: {actual}"
                )
            included.append(
                {
                    "tool_id": row["id"],
                    "path": destination.relative_to(root).as_posix(),
                    "sha256": actual,
                }
            )
            blockers.append(
                {
                    "tool_id": row["id"],
                    "reason": (
                        "verified asset is bundled but environment-specific "
                        "installation remains manual"
                    ),
                }
            )
        manifest = {
            "version": TOOLING_BUNDLE_VERSION,
            "generated_at": utc_now(),
            "plan_sha256": plan["plan_sha256"],
            "included": included,
            "blockers": blockers,
            "install_scripts": {
                "user": offline_user_scripts,
                "privileged": privileged_scripts,
            },
            "status": "pass" if not blockers else "partial",
            "privacy": (
                "Bundle contains tool metadata and verified assets only; "
                "it contains no project content, credentials, prompts, or host paths."
            ),
        }
        write_json(root / "bundle-manifest.json", manifest)
        checksum_lines = []
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            checksum_lines.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
        (root / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        os.replace(root, output)
    return {
        **manifest,
        "output": output.as_posix(),
        "manifest": (output / "bundle-manifest.json").as_posix(),
        "checksums": (output / "SHA256SUMS").as_posix(),
    }


def _run_compact_git(repo_root: Path, args: Sequence[str]) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", repo_root.as_posix(), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode, result.stdout.strip()


def compact_repo_state(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    if not root.is_dir():
        raise WorkstationError(f"target must be an existing directory: {repo_root}")
    branch_code, branch = _run_compact_git(root, ["branch", "--show-current"])
    head_code, head = _run_compact_git(root, ["rev-parse", "--short=12", "HEAD"])
    status_code, status = _run_compact_git(root, ["status", "--short"])
    changed_count = len(status.splitlines()) if status_code == 0 and status else 0
    inspection = inspect_repository_capabilities(root)
    return {
        "version": "MoradinForgeStateV1",
        "generated_at": utc_now(),
        "repository_id": repository_id(root),
        "git": {
            "available": branch_code == 0 and head_code == 0,
            "branch": branch if branch_code == 0 else "",
            "head": head if head_code == 0 else "",
            "changed_path_count": changed_count,
            "worktree_sha256": (
                sha256_bytes(status.encode("utf-8"))
                if status_code == 0
                else ""
            ),
        },
        "capabilities": inspection["capabilities"],
        "agent_files": inspection["agent_files"],
    }


def _read_bounded_text(path: Path, limit: int = 256 * 1024) -> str:
    if not path.is_file() or path.is_symlink():
        return ""
    with path.open("rb") as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        return ""
    return payload.decode("utf-8", errors="replace")


def detected_repo_commands(repo_root: Path) -> list[str]:
    commands: list[str] = []
    makefile = repo_root / "Makefile"
    if makefile.is_file() and not makefile.is_symlink():
        text = _read_bounded_text(makefile, 128_000)
        targets = set(re.findall(r"(?m)^([A-Za-z0-9_.-]+):(?:\\s|$)", text))
        for target in (
            "repo-brief",
            "doctor",
            "verify-fast",
            "verify",
            "review-ready",
            "verify-security",
            "test",
        ):
            if target in targets:
                commands.append(f"make {target}")
    package = repo_root / "package.json"
    if package.is_file() and not package.is_symlink():
        try:
            payload = json.loads(_read_bounded_text(package))
        except json.JSONDecodeError:
            payload = {}
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        if isinstance(scripts, dict):
            for name in ("test", "lint", "build"):
                if name in scripts:
                    commands.append(f"npm run {name}")
    if (repo_root / "pyproject.toml").is_file():
        commands.append("uv run pytest" if (repo_root / "uv.lock").is_file() else "python -m pytest")
    if (repo_root / "Cargo.toml").is_file():
        commands.append("cargo test")
    if (repo_root / "go.mod").is_file():
        commands.append("go test ./...")
    return list(dict.fromkeys(commands))


def repo_brief(repo_root: Path) -> dict[str, Any]:
    state = compact_repo_state(repo_root)
    commands = detected_repo_commands(repo_root)
    return {
        "version": "MoradinForgeRepoBriefV1",
        "generated_at": utc_now(),
        "state": state,
        "preferred_commands": commands,
        "next_action": commands[0] if commands else "Inspect the repository README and guidance files.",
    }


def _metrics_path(runtime_root: Path) -> Path:
    return (
        runtime_root
        / "Harness"
        / "artifacts"
        / "control"
        / "efficiency"
        / "local_counters.json"
    )


def load_efficiency_metrics(runtime_root: Path) -> dict[str, Any]:
    path = _metrics_path(runtime_root)
    if path.is_file() and not path.is_symlink():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("version") == EFFICIENCY_METRICS_VERSION:
            return payload
    return {
        "version": EFFICIENCY_METRICS_VERSION,
        "updated_at": utc_now(),
        "counters": {
            "primer_runs": 0,
            "summarized_bytes": 0,
            "rerun_checks": 0,
            "reruns_avoided": 0,
            "evidence_reuse": 0,
            "command_pass": 0,
            "command_fail": 0,
        },
        "command_fingerprints": {},
    }


def save_efficiency_metrics(runtime_root: Path, metrics: dict[str, Any]) -> None:
    metrics["updated_at"] = utc_now()
    write_json(_metrics_path(runtime_root), metrics)


def context_primer(repo_root: Path, *, runtime_root: Path) -> str:
    brief = repo_brief(repo_root)
    state = brief["state"]
    lines = [
        "# Moradin Forge Context Primer",
        "",
        f"- repository_id: `{state['repository_id']}`",
        f"- branch: `{state['git']['branch'] or 'unavailable'}`",
        f"- head: `{state['git']['head'] or 'unavailable'}`",
        f"- changed_paths: `{state['git']['changed_path_count']}`",
        f"- capabilities: `{', '.join(state['capabilities']) or 'none detected'}`",
        "",
        "## Preferred Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in brief["preferred_commands"][:8])
    lines.extend(
        [
            "",
            "## Expansion Rule",
            "",
            "- Read current summaries first. Expand to source or full logs when evidence is missing, stale, contradictory, security-sensitive, or release-critical.",
            "",
            "## Next Action",
            "",
            f"- {brief['next_action']}",
            "",
        ]
    )
    rendered = "\n".join(lines)
    encoded = rendered.encode("utf-8")
    if len(encoded) > CONTEXT_PRIMER_LIMIT:
        rendered = encoded[: CONTEXT_PRIMER_LIMIT - 1].decode("utf-8", errors="ignore") + "\n"
    metrics = load_efficiency_metrics(runtime_root)
    metrics["counters"]["primer_runs"] += 1
    metrics["counters"]["summarized_bytes"] += len(rendered.encode("utf-8"))
    save_efficiency_metrics(runtime_root, metrics)
    return rendered


def _repo_state_fingerprint(repo_root: Path) -> str:
    state = compact_repo_state(repo_root)
    stable = {
        "repository_id": state["repository_id"],
        "head": state["git"]["head"],
        "changed_path_count": state["git"]["changed_path_count"],
        "worktree_sha256": state["git"]["worktree_sha256"],
        "capabilities": state["capabilities"],
    }
    return sha256_bytes(canonical_json_bytes(stable))


def rerun_advice(
    repo_root: Path,
    command: Sequence[str],
    *,
    runtime_root: Path,
) -> dict[str, Any]:
    if not command or any("\x00" in item for item in command):
        raise WorkstationError("rerun-advice requires a non-empty command")
    command_sha = sha256_bytes(canonical_json_bytes(list(command)))
    state_sha = _repo_state_fingerprint(repo_root)
    metrics = load_efficiency_metrics(runtime_root)
    metrics["counters"]["rerun_checks"] += 1
    prior = metrics["command_fingerprints"].get(command_sha, {})
    if prior.get("state_sha256") == state_sha and prior.get("outcome") == "pass":
        action = "reuse"
        reason = "the same command passed for the current repository state"
        metrics["counters"]["reruns_avoided"] += 1
        metrics["counters"]["evidence_reuse"] += 1
    elif prior.get("state_sha256") == state_sha and prior.get("outcome") == "fail":
        action = "investigate"
        reason = "the same failure was recorded for the current repository state"
        metrics["counters"]["reruns_avoided"] += 1
    else:
        action = "run"
        reason = "no current-state evidence exists for this command"
    save_efficiency_metrics(runtime_root, metrics)
    return {
        "version": "MoradinForgeRerunAdviceV1",
        "generated_at": utc_now(),
        "repository_id": repository_id(repo_root),
        "command_sha256": command_sha,
        "state_sha256": state_sha,
        "action": action,
        "reason": reason,
    }


def session_checkpoint(
    repo_root: Path,
    command: Sequence[str],
    outcome: str,
    *,
    runtime_root: Path,
) -> dict[str, Any]:
    if outcome not in {"pass", "fail", "skipped"}:
        raise WorkstationError("checkpoint outcome must be pass, fail, or skipped")
    if not command or any("\x00" in item for item in command):
        raise WorkstationError("session-checkpoint requires a non-empty command")
    command_sha = sha256_bytes(canonical_json_bytes(list(command)))
    state_sha = _repo_state_fingerprint(repo_root)
    metrics = load_efficiency_metrics(runtime_root)
    metrics["command_fingerprints"][command_sha] = {
        "state_sha256": state_sha,
        "outcome": outcome,
        "updated_at": utc_now(),
    }
    if outcome == "pass":
        metrics["counters"]["command_pass"] += 1
    elif outcome == "fail":
        metrics["counters"]["command_fail"] += 1
    save_efficiency_metrics(runtime_root, metrics)
    return {
        "version": "MoradinForgeSessionCheckpointV1",
        "generated_at": utc_now(),
        "repository_id": repository_id(repo_root),
        "command_sha256": command_sha,
        "state_sha256": state_sha,
        "outcome": outcome,
    }


def diagnostic_brief(*, runtime_root: Path) -> dict[str, Any]:
    metrics = load_efficiency_metrics(runtime_root)
    counters = metrics["counters"]
    failed = sum(
        1
        for item in metrics["command_fingerprints"].values()
        if item.get("outcome") == "fail"
    )
    if failed:
        next_action = "Inspect the latest distinct failure before another rerun."
    elif counters["reruns_avoided"]:
        next_action = "Reuse current evidence and continue with the next unresolved task."
    else:
        next_action = "Run the shortest repository-native validation command."
    return {
        "version": "MoradinForgeDiagnosticBriefV1",
        "generated_at": utc_now(),
        "counters": counters,
        "recorded_failed_fingerprints": failed,
        "next_action": next_action,
        "privacy": "No prompts, source, raw commands, raw paths, or logs are stored.",
    }
