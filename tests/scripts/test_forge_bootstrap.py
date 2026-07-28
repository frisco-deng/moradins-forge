"""Coverage for the safe Moradin Forge bootstrap installer."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import forge_bootstrap
from scripts.forge_bootstrap import BootstrapOptions, bootstrap, detect_tools


def test_bootstrap_core_dry_run_plans_clone_without_writing_paths(tmp_path: Path) -> None:
    dest = tmp_path / "forge"

    payload = bootstrap(
        BootstrapOptions(
            repo_url=forge_bootstrap.DEFAULT_REPO_URL,
            ref="main",
            dest=dest,
            target=tmp_path / "target",
            deps="none",
            dry_run=True,
        )
    )

    rendered = json.dumps(payload, sort_keys=True)
    assert payload["version"] == "MoradinForgeBootstrapV1"
    assert payload["dry_run"] is True
    assert payload["status"] == "cloned"
    assert payload["agent_start"]["dry_run"] == "true"
    assert not dest.exists()
    assert str(tmp_path) not in rendered
    assert "/tmp/" not in rendered
    assert "apply --target" not in rendered


def test_bootstrap_reuses_current_checkout_without_git_checkout(tmp_path: Path) -> None:
    payload = bootstrap(
        BootstrapOptions(
            repo_url=forge_bootstrap.DEFAULT_REPO_URL,
            ref="main",
            dest=forge_bootstrap.SCRIPT_ROOT,
            target=None,
            deps="none",
            dry_run=True,
        )
    )

    assert payload["status"] == "in_place"
    commands = [action["command"] for action in payload["actions"]]
    assert ["reuse-current-checkout"] in commands
    assert not any(command[:1] == ["git"] and "checkout" in command for command in commands)


def test_missing_required_tools_are_request_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(forge_bootstrap.shutil, "which", lambda _command: None)

    readiness = detect_tools("full")
    payload = bootstrap(
        BootstrapOptions(
            repo_url="git" + "@github.com:" + "private/example.git",
            ref="main",
            dest=Path("/tmp/forge"),
            target=None,
            deps="full",
            dry_run=True,
        )
    )
    rendered = json.dumps(payload, sort_keys=True)

    assert readiness["status"] == "blocked"
    assert payload["status"] == "blocked"
    assert payload["agent_start"]["dry_run"] == "true"
    assert payload["agent_start"]["write_suppressed"] == "true"
    assert "request_only" in rendered
    assert "sudo " not in rendered
    assert "brew " not in rendered
    assert "winget " not in rendered
    assert "git@github.com" not in rendered


def test_blocked_bootstrap_does_not_write_start_card_to_non_forge_dest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = tmp_path / "non-forge"
    dest.mkdir()
    (dest / "README.md").write_text("not Forge\n", encoding="utf-8")
    monkeypatch.setattr(forge_bootstrap.shutil, "which", lambda _command: None)

    payload = bootstrap(
        BootstrapOptions(
            repo_url=forge_bootstrap.DEFAULT_REPO_URL,
            ref="main",
            dest=dest,
            target=None,
            deps="minimal",
            dry_run=False,
        )
    )

    assert payload["status"] == "blocked"
    assert payload["agent_start"]["write_suppressed"] == "true"
    assert not (dest / "artifacts").exists()


def test_error_output_sanitizes_destination(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dest = tmp_path / "nonempty"
    dest.mkdir()
    (dest / "README.md").write_text("not forge\n", encoding="utf-8")

    exit_code = forge_bootstrap.main(["--dest", str(dest), "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)
    rendered = json.dumps(payload, sort_keys=True)

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert "<forge-root>" in payload["error"]
    assert str(tmp_path) not in rendered
    assert "/tmp/" not in rendered


def run_wrapper(command: list[str], repo_root: Path, dest: Path) -> dict[str, object]:
    result = subprocess.run(
        [*command, "--dest", dest.as_posix(), "--deps", "none", "--dry-run", "--json"],
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def test_linux_bootstrap_wrapper_dry_run(tmp_path: Path) -> None:
    repo_root = forge_bootstrap.SCRIPT_ROOT
    payload = run_wrapper(["install/bootstrap-linux.sh"], repo_root, tmp_path / "linux-forge")

    assert payload["version"] == "MoradinForgeBootstrapV1"
    assert payload["dry_run"] is True
    assert payload["agent_start"]["markdown"] == "<forge-root>/artifacts/bootstrap/latest/agent_start.md"


def test_macos_bootstrap_wrapper_dry_run(tmp_path: Path) -> None:
    repo_root = forge_bootstrap.SCRIPT_ROOT
    payload = run_wrapper(["install/bootstrap-macos.sh"], repo_root, tmp_path / "macos-forge")

    assert payload["version"] == "MoradinForgeBootstrapV1"
    assert payload["dry_run"] is True


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell is not installed")
def test_windows_bootstrap_wrapper_dry_run(tmp_path: Path) -> None:
    repo_root = forge_bootstrap.SCRIPT_ROOT
    result = subprocess.run(
        [
            "pwsh",
            "-File",
            "install/bootstrap-windows.ps1",
            "-Dest",
            (tmp_path / "windows-forge").as_posix(),
            "-Deps",
            "none",
            "-DryRun",
            "-Json",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)

    assert payload["version"] == "MoradinForgeBootstrapV1"
    assert payload["dry_run"] is True
