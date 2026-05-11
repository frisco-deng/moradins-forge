"""Launcher script argument and environment checks."""

from __future__ import annotations

import subprocess
import os
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "harness_devops.sh"


def run_script(*args: str, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(dict(env) if env else {})},
    )


def test_harness_devops_help() -> None:
    result = run_script("--help")

    assert result.returncode == 0
    assert "Usage: ./harness_devops.sh" in result.stdout
    assert "--port <1-65535>" in result.stdout
    assert "--restart-existing" in result.stdout


def test_harness_devops_dry_run_uses_custom_ui_port() -> None:
    result = run_script("--port", "6123", "--dry-run")

    assert result.returncode == 0
    assert "[harness_devops] UI port: 6123" in result.stdout
    assert "[harness_devops] UI URL: http://localhost:6123/" in result.stdout
    assert "[harness_devops] API URL: http://127.0.0.1:8787/" in result.stdout
    assert (
        "ssh -L 6123:127.0.0.1:6123 <linux-host>" in result.stdout
        or "WSL browser access: use http://localhost:6123/ or the WSL IPv4 address." in result.stdout
    )
    assert "npm --prefix dev_tracker/ui run dev:ops" in result.stdout


def test_harness_devops_rejects_invalid_port() -> None:
    result = run_script("--port", "99999", "--dry-run")

    assert result.returncode == 1
    assert "invalid port" in result.stderr


def test_harness_devops_reads_port_from_config_dry_run() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "harness_devops.toml"
        config_path.write_text(
            '[launcher]\nui_port = 6124\nui_host = "auto"\napi_port = 8787\n',
            encoding="utf-8",
        )

        result = run_script("--dry-run", env={"HARNESS_DEVOPS_CONFIG_PATH": str(config_path)})

    assert result.returncode == 0
    assert "[harness_devops] UI port: 6124" in result.stdout
    assert f"[harness_devops] Config: {config_path}" in result.stdout


def test_harness_devops_rejects_non_release_api_port_in_config() -> None:
    with TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "harness_devops.toml"
        config_path.write_text(
            '[launcher]\nui_port = 6124\nui_host = "auto"\napi_port = 9000\n',
            encoding="utf-8",
        )

        result = run_script("--dry-run", env={"HARNESS_DEVOPS_CONFIG_PATH": str(config_path)})

    assert result.returncode == 1
    assert "launcher.api_port must remain 8787 for the current-scope release" in result.stderr


def test_harness_devops_rejects_non_release_api_port_in_environment() -> None:
    result = run_script("--dry-run", env={"TRACKER_API_PORT": "9000"})

    assert result.returncode == 1
    assert "TRACKER_API_PORT must remain 8787 for the current-scope release" in result.stderr
