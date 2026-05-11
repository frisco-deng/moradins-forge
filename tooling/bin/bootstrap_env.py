#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
CONFIG_PATH = REPO_ROOT / "tooling" / "configs" / "tooling-targets.json"
LOCAL_BIN = Path.home() / ".local" / "bin"
TRIVY_SAFE_VERSION = "0.69.3"
TRIVY_DENIED_VERSIONS = {"0.69.4", "v0.69.4"}
DENIED_WORKFLOW_REFERENCES = (
    re.compile(r"aquasecurity/(?:trivy-action|setup-trivy)"),
    re.compile(r"aquasec/trivy:0\.69\.(?:4|5|6)(?:\b|[^0-9])"),
)
PYTHON_TOOL_SPECS = {
    "zizmor": "zizmor==1.23.1",
    "semgrep": "semgrep==1.156.0",
    "pip-audit": "pip-audit==2.10.0",
    "yamllint": "yamllint==1.37.1",
}
BINARY_TOOL_SPECS = {
    "actionlint": {
        "url": "https://github.com/rhysd/actionlint/releases/download/v1.7.11/actionlint_1.7.11_linux_amd64.tar.gz",
        "archive_member": "actionlint",
        "sha256": "900919a84f2229bac68ca9cd4103ea297abc35e9689ebb842c6e34a3d1b01b0a",
    },
    "hadolint": {
        "url": "https://github.com/hadolint/hadolint/releases/download/v2.14.0/hadolint-linux-x86_64",
        "binary_name": "hadolint",
        "sha256": "6bf226944684f56c84dd014e8b979d27425c0148f61b3bd99bcc6f39e9dc5a47",
    },
    "conftest": {
        "url": "https://github.com/open-policy-agent/conftest/releases/download/v0.66.0/conftest_0.66.0_Linux_x86_64.tar.gz",
        "archive_member": "conftest",
        "sha256": "7e717adada4ca64e600bdb86b789cbcc279215b3296e238bc291acbb81361d6f",
    },
    "syft": {
        "url": "https://github.com/anchore/syft/releases/download/v1.42.3/syft_1.42.3_linux_amd64.tar.gz",
        "archive_member": "syft",
        "sha256": "0d6be741479eddd2c8644a288990c04f3df0d609bbc1599a005532a9dff63509",
    },
    "grype": {
        "url": "https://github.com/anchore/grype/releases/download/v0.110.0/grype_0.110.0_linux_amd64.tar.gz",
        "archive_member": "grype",
        "sha256": "aaa98d27d2d7efd9317c6a1ad6d9b15f3e65bab320e7d03bde41e251387bb71c",
    },
    "trivy": {
        "url": "https://github.com/aquasecurity/trivy/releases/download/v0.69.3/trivy_0.69.3_Linux-64bit.tar.gz",
        "archive_member": "trivy",
        "sha256": "1816b632dfe529869c740c0913e36bd1629cb7688bd5634f4a858c1d57c88b75",
    },
    "gitleaks": {
        "url": "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz",
        "archive_member": "gitleaks",
        "sha256": "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
    },
    "osv-scanner": {
        "url": "https://github.com/google/osv-scanner/releases/download/v2.3.3/osv-scanner_linux_amd64",
        "binary_name": "osv-scanner",
        "sha256": "777b4bb7ddd10bdcc8a1aa398d37d05e91e866e7586f9cff3fca2f72b8153033",
    },
}
INITIAL_DOWNLOAD_HOSTS = frozenset({"github.com"})
REDIRECT_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "github-releases.githubusercontent.com",
    }
)
ALLOWED_DOWNLOAD_URLS = frozenset(str(spec["url"]) for spec in BINARY_TOOL_SPECS.values())


def tooling_log(message: str) -> None:
    print(f"[bootstrap] {message}")


def read_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_has(path: str) -> bool:
    return (REPO_ROOT / path).exists()


def install_node_dependencies(npm_directories: list[str]) -> None:
    visited: list[str] = []
    install_order = ["."]
    install_order.extend(npm_directories)
    for raw_dir in install_order:
        if raw_dir in visited:
            continue
        visited.append(raw_dir)
        package_dir = REPO_ROOT / raw_dir
        package_json = package_dir / "package.json"
        if not package_json.exists():
            continue
        command = ["npm", "ci", "--prefix", raw_dir] if (package_dir / "package-lock.json").exists() else ["npm", "install", "--prefix", raw_dir]
        tooling_log(f"installing node dependencies in {raw_dir}")
        run(command)


def run(command: list[str] | str) -> None:
    if isinstance(command, str):
        proc = subprocess.run(["/bin/bash", "-lc", command], cwd=REPO_ROOT, check=False)
    else:
        proc = subprocess.run(command, cwd=REPO_ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def have_tool(name: str) -> bool:
    if shutil.which(name):
        return True
    return (LOCAL_BIN / name).exists()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_download(path: Path, expected_sha256: str) -> None:
    observed_sha256 = _sha256(path)
    if observed_sha256.lower() != expected_sha256.lower():
        raise SystemExit(
            f"{path.name} sha256 mismatch: expected {expected_sha256}, observed {observed_sha256}"
        )


def _tool_version_output(tool: str) -> str:
    command = [tool, "--version"]
    try:
        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return "\n".join(part for part in (completed.stdout, completed.stderr) if part)


def _trivy_version() -> str:
    output = _tool_version_output("trivy")
    match = re.search(r"Version:\s*v?([0-9]+(?:\.[0-9]+){2})", output)
    if not match:
        return ""
    return match.group(1)


def _tool_is_acceptable(tool: str) -> bool:
    if tool != "trivy":
        return True
    version = _trivy_version()
    if not version:
        return False
    if version in {item.removeprefix("v") for item in TRIVY_DENIED_VERSIONS}:
        raise SystemExit(f"denied Trivy version on PATH: {version}")
    return version == TRIVY_SAFE_VERSION


def validate_installed_tool(tool: str) -> None:
    if not have_tool(tool):
        raise SystemExit(f"{tool} was not installed successfully")
    if tool == "trivy" and not _tool_is_acceptable(tool):
        version = _trivy_version() or "unknown"
        raise SystemExit(f"Trivy must resolve to safe pinned version {TRIVY_SAFE_VERSION}; observed {version}")


def validate_workflow_references() -> None:
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    if not workflow_dir.exists():
        return
    for workflow_path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        try:
            text = workflow_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in DENIED_WORKFLOW_REFERENCES:
            if pattern.search(text):
                raise SystemExit(f"denied Trivy workflow reference in {workflow_path.relative_to(REPO_ROOT)}")


def ensure_local_bin_on_path() -> None:
    LOCAL_BIN.mkdir(parents=True, exist_ok=True)
    current_path = os.environ.get("PATH", "")
    if str(LOCAL_BIN) not in current_path.split(os.pathsep):
        os.environ["PATH"] = f"{LOCAL_BIN}{os.pathsep}{current_path}" if current_path else str(LOCAL_BIN)
    github_path = os.environ.get("GITHUB_PATH")
    if github_path:
        github_path_file = Path(github_path)
        existing = github_path_file.read_text(encoding="utf-8") if github_path_file.exists() else ""
        if str(LOCAL_BIN) not in existing.splitlines():
            with github_path_file.open("a", encoding="utf-8") as handle:
                handle.write(f"{LOCAL_BIN}\n")


def install_python_tool(tool: str) -> None:
    spec = PYTHON_TOOL_SPECS[tool]
    tooling_log(f"installing python tool {spec}")
    run(["uv", "tool", "install", "--force", spec])


def _validate_download_url(url: str) -> str:
    if url not in ALLOWED_DOWNLOAD_URLS:
        raise SystemExit(f"download URL is not in the pinned tool allowlist: {url}")
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in INITIAL_DOWNLOAD_HOSTS:
        raise SystemExit(f"download URL must use an approved HTTPS host: {url}")
    if parsed.username or parsed.password:
        raise SystemExit(f"download URL must not include credentials: {url}")
    return url


def _validate_redirect_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in REDIRECT_DOWNLOAD_HOSTS:
        raise SystemExit(f"download redirected to an unapproved URL: {url}")
    if parsed.username or parsed.password:
        raise SystemExit(f"download redirect must not include credentials: {url}")


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(_validate_download_url(url), method="GET")
    # URL input is pinned above and final redirects are checked before bytes are trusted.
    with urllib.request.urlopen(request) as response, destination.open("wb") as handle:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        _validate_redirect_url(response.geturl())
        shutil.copyfileobj(response, handle)


def install_binary_tool(tool: str) -> None:
    spec = BINARY_TOOL_SPECS[tool]
    with tempfile.TemporaryDirectory(prefix=f"tool-{tool}-") as temp_dir_text:
        temp_dir = Path(temp_dir_text)
        download_path = temp_dir / Path(spec["url"]).name
        tooling_log(f"downloading {tool} from {spec['url']}")
        _download(spec["url"], download_path)
        _verify_download(download_path, str(spec["sha256"]))
        binary_target = LOCAL_BIN / tool
        if "archive_member" in spec:
            with tarfile.open(download_path, "r:*") as archive:
                members = [member for member in archive.getmembers() if member.isfile()]
                member = next((item for item in members if Path(item.name).name == spec["archive_member"]), None)
                if member is None:
                    raise SystemExit(f"unable to find {spec['archive_member']} in {download_path.name}")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise SystemExit(f"unable to extract {tool} from {download_path.name}")
                with binary_target.open("wb") as handle:
                    shutil.copyfileobj(extracted, handle)
        else:
            shutil.copyfile(download_path, binary_target)
        binary_target.chmod(0o755)


def install_tools(tools: list[str]) -> None:
    ensure_local_bin_on_path()
    for tool in tools:
        if have_tool(tool):
            if tool == "trivy" and not _tool_is_acceptable(tool):
                tooling_log(f"{tool} is available but not on the approved pin; installing pinned release")
            else:
                tooling_log(f"{tool} already available; reinstalling pinned release")
        if tool in PYTHON_TOOL_SPECS:
            install_python_tool(tool)
        elif tool in BINARY_TOOL_SPECS:
            install_binary_tool(tool)
        else:
            raise SystemExit(f"unsupported bootstrap tool: {tool}")
        validate_installed_tool(tool)


def run_bootstrap(mode: str, config: dict[str, Any]) -> None:
    validate_workflow_references()
    mode_key = mode.removeprefix("bootstrap-")
    repo_cfg = config["repo"]
    bootstrap_cfg = repo_cfg.get("bootstrap", {}).get(mode_key, {})
    if repo_has("pyproject.toml"):
        for command in bootstrap_cfg.get("commands", []):
            tooling_log(f"running {command}")
            run(command)
    if repo_has("package.json") or any(repo_has(f"{directory}/package.json") for directory in repo_cfg.get("npm_directories", [])):
        install_node_dependencies(list(repo_cfg.get("npm_directories", [])))
    install_tools(list(bootstrap_cfg.get("tools", [])))
    tooling_log(f"{mode} complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a rendered repo for verify targets in CI or scratch environments.")
    parser.add_argument("mode", choices=("bootstrap-ci", "bootstrap-security", "bootstrap-container"))
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    config = read_config(args.config)
    run_bootstrap(args.mode, config)


if __name__ == "__main__":
    main()
