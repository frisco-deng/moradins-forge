"""First-read contract coverage for every supported provider handoff."""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_readme_starts_with_self_contained_agent_intercept() -> None:
    readme = read("README.md")
    first_read = readme[:12000]
    first_read_lower = " ".join(first_read.lower().split())

    assert readme.startswith("# Moradin's Forge\n\n## Three-Step Setup")
    assert "## agent: start here" in first_read_lower
    assert (
        "show the discovered repository list before inspecting deeper"
        in first_read_lower
    )
    assert "workspace scope" in first_read_lower
    assert "selected tooling modules" in first_read_lower
    assert (
        "each allowlisted codex, claude, gemini, copilot, or cursor"
        in first_read_lower
    )
    assert "path or shell-profile configuration" in first_read_lower
    assert "agents never enter credentials, run sudo" in first_read_lower
    assert "install/tooling-suite.sh" in first_read_lower
    assert "digest-binding the exact root transaction" in first_read_lower
    assert "verified checksum/signature" in first_read_lower
    assert "air-gapped alternative" in first_read_lower
    assert "asset-only" in first_read_lower
    assert "measured release-dogfood" in first_read_lower


@pytest.mark.parametrize(
    "relative",
    [
        "Harness/entrypoints/agent.md",
        "Harness/entrypoints/codex.md",
        "Harness/entrypoints/claude.md",
        "Harness/entrypoints/copilot.md",
        "Harness/entrypoints/gemini.md",
        "Harness/entrypoints/cursor.md",
        "Harness/entrypoints/forge.md",
    ],
)
def test_agent_entrypoints_preserve_scope_consent_and_privilege_rules(
    relative: str,
) -> None:
    text = read(relative).lower()

    assert "workspace" in text
    assert "approv" in text or "consent" in text
    assert "tooling-suite.sh" in text
    assert "sudo" in text
    assert "provider" in text
    assert "offline" in text or "air-gap" in text
    assert "rerun" in text


def test_first_read_surfaces_do_not_teach_request_only_install_model() -> None:
    surfaces = [
        read("README.md"),
        read("FORGE.md"),
        read("Harness/entrypoints/agent.md"),
        read("Harness/entrypoints/codex.md"),
        read("Harness/entrypoints/claude.md"),
        read("Harness/entrypoints/copilot.md"),
        read("Harness/entrypoints/gemini.md"),
        read("Harness/entrypoints/cursor.md"),
        read("Harness/entrypoints/forge.md"),
    ]

    assert all("host tool installation request-only" not in text for text in surfaces)
    assert all("tooling-suite.sh" in text for text in surfaces[2:])
    assert all("sudo" in text and "user" in text for text in surfaces[2:])
