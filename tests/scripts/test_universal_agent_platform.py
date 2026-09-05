"""Cross-platform contract tests for the beta.3 universal agent baseline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import moradin_workstation
from scripts.moradin_workstation import (
    build_tooling_plan,
    plan_digest,
    render_privileged_bash,
    render_privileged_powershell,
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fixed_resolution(*_args: object, **kwargs: object) -> dict[str, object]:
    sources = {
        "linux": "apt",
        "macos": "homebrew",
        "windows": "winget",
    }
    system = str(kwargs.get("system", "linux"))
    return {
        "version": "1.2.3",
        "source": sources[system],
        "source_url": "https://github.com/example/tool/releases/tag/v1.2.3",
        "asset_url": "",
        "sha256": "",
        "trust": "signed-package-manager",
        "checked_at": "2026-07-28T00:00:00+00:00",
        "cache": "fresh",
    }


@pytest.mark.parametrize(
    ("system", "expected_kind"),
    [
        ("linux", "privileged-script"),
        ("macos", "user-package-manager"),
        ("windows", "privileged-script"),
    ],
)
def test_platform_plan_is_digest_bound_and_uses_equivalent_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    expected_kind: str,
) -> None:
    workspace = tmp_path / "workspace"
    repo = workspace / "example"
    write(repo / ".git/HEAD", "ref: refs/heads/main\n")
    write(repo / "pyproject.toml", "[project]\nname='example'\n")
    write(repo / ".github/workflows/ci.yml", "name: ci\n")
    monkeypatch.setattr(moradin_workstation, "normalized_platform", lambda: system)
    monkeypatch.setattr(
        moradin_workstation,
        "resolve_latest_version",
        fixed_resolution,
    )
    monkeypatch.setattr(moradin_workstation, "command_present", lambda _command: False)
    if system == "macos":
        monkeypatch.setattr(
            moradin_workstation.shutil,
            "which",
            lambda command: "/opt/homebrew/bin/brew" if command == "brew" else None,
        )

    plan = build_tooling_plan(
        [workspace],
        forge_root=tmp_path / "forge",
        include_tools=("gh",),
    )

    git_row = next(row for row in plan["tools"] if row["id"] == "git")
    assert git_row["install_action"]["kind"] == expected_kind
    assert {"python", "github-actions"}.issubset(plan["capabilities"])
    assert plan["plan_sha256"] == plan_digest(plan)
    bash = render_privileged_bash(plan)
    powershell = render_privileged_powershell(plan)
    if system == "linux":
        assert "$packages = @()" in powershell
    elif system == "windows":
        assert "packages=()" in bash
    else:
        assert "packages=()" in bash
        assert "$packages = @()" in powershell


def test_generated_privileged_scripts_are_dry_run_first_and_reversible() -> None:
    plan = {
        "tools": [
            {
                "id": "git",
                "command": "git; touch should-not-run",
                "present": False,
                "install_action": {
                    "tool_id": "git",
                    "kind": "privileged-script",
                    "package": "git",
                },
            }
        ]
    }

    bash = render_privileged_bash(plan)
    powershell = render_privileged_powershell(plan)

    assert "--apply" in bash
    assert "dry-run packages:" in bash
    assert "apt-get install -y --" in bash
    assert "reversal:" in bash
    assert "should-not-run" not in bash
    assert "command -v git" in bash
    assert "-not $Apply" in powershell
    assert "dry-run packages:" in powershell
    assert "& $manager install --exact" in powershell
    assert "$manager = 'winget'" in powershell
    assert "reversal:" in powershell
    assert "should-not-run" not in powershell


def test_generated_fedora_script_uses_dnf5_compatible_package_arguments() -> None:
    plan = {
        "platform": {"system": "linux", "package_manager": "dnf"},
        "tools": [
            {
                "id": "git",
                "command": "git",
                "present": False,
                "install_action": {
                    "tool_id": "git",
                    "kind": "privileged-script",
                    "package": "git",
                    "version": "2.55.0-1.fc44",
                },
            }
        ],
    }

    bash = render_privileged_bash(plan)
    bootstrap = Path("install/tooling-suite.sh").read_text(encoding="utf-8")

    assert 'dnf install -y --setopt=install_weak_deps=False "${packages[@]}"' in bash
    assert 'reversal="dnf remove ${reversal_packages[*]}"' in bash
    assert '-- "${packages[@]}"' not in bash.split("  dnf)", maxsplit=1)[1].split(
        ";;", maxsplit=1
    )[0]
    bootstrap_dnf = bootstrap.split("\tdnf)", maxsplit=1)[1].split(
        "\t\t;;", maxsplit=1
    )[0]
    assert '-- "${bootstrap_packages[@]}"' not in bootstrap_dnf


@pytest.mark.parametrize(
    ("relative_path", "reversal"),
    [
        ("install/bootstrap-linux.sh", "apt-get remove --"),
        ("install/bootstrap-macos.sh", "brew uninstall"),
        ("install/bootstrap-windows.ps1", "winget uninstall --exact"),
    ],
)
def test_native_prerequisite_bridges_are_dry_run_first_and_reversible(
    relative_path: str,
    reversal: str,
) -> None:
    source = Path(relative_path).read_text(encoding="utf-8")

    assert "dry-run" in source
    assert reversal in source
    assert "install-prerequisites" in source


def test_plan_json_contains_no_raw_command_string(tmp_path: Path) -> None:
    payload = {
        "version": "MoradinForgeToolingPlanV1",
        "tools": [{"install_action": {"argv": ["uv", "tool", "install", "example"]}}],
    }

    rendered = json.dumps(payload)

    assert "uv tool install example" not in rendered
