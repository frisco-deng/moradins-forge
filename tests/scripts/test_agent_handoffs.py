"""First-read contract coverage for generic, Codex, and Claude handoffs."""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_readme_starts_with_self_contained_agent_intercept() -> None:
    readme = read("README.md")
    first_read = readme[:9000]
    first_read_lower = " ".join(first_read.lower().split())

    assert readme.startswith("# Moradin's Forge\n\n## Agent: Start Here")
    assert (
        "show the discovered repository list before inspecting deeper"
        in first_read_lower
    )
    assert "workspace scope" in first_read_lower
    assert "selected tooling modules" in first_read_lower
    assert "each agents.md or claude.md file" in first_read_lower
    assert "path or shell-profile configuration" in first_read_lower
    assert "never execute sudo or an elevated powershell action" in first_read_lower
    assert "verified checksum/signature" in first_read_lower


@pytest.mark.parametrize(
    "relative",
    [
        "Harness/entrypoints/agent.md",
        "Harness/entrypoints/codex.md",
        "Harness/entrypoints/claude.md",
    ],
)
def test_agent_entrypoints_preserve_scope_consent_and_privilege_rules(
    relative: str,
) -> None:
    text = read(relative).lower()

    assert "workspace" in text
    assert "approv" in text or "consent" in text
    assert "user-level" in text
    assert "privileged" in text
    assert "agent" in text
    assert "primer" in text
    assert "rerun" in text
    assert "material" in text


def test_first_read_surfaces_do_not_teach_request_only_install_model() -> None:
    surfaces = [
        read("README.md"),
        read("FORGE.md"),
        read("Harness/entrypoints/agent.md"),
        read("Harness/entrypoints/codex.md"),
        read("Harness/entrypoints/claude.md"),
        read("Harness/entrypoints/forge.md"),
    ]

    assert all("host tool installation request-only" not in text for text in surfaces)
