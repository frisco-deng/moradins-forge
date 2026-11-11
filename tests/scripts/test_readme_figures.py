"""Accessible, deterministic README figure contracts."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import generate_readme_figures


REPO_ROOT = Path(__file__).resolve().parents[2]
FIGURES = {
    "three-step-setup.svg": "Illustrative",
    "trust-architecture.svg": "Qualitative",
    "airgap-round-trip.svg": "Qualitative",
    "measured-benefits.svg": "Measured",
}


def test_readme_figures_are_accessible_local_svg() -> None:
    for filename, classification in FIGURES.items():
        text = (REPO_ROOT / "docs/assets/readme" / filename).read_text(
            encoding="utf-8"
        )
        lowered = text.lower()
        assert 'role="img"' in lowered
        assert "<title" in lowered
        assert "<desc" in lowered
        assert classification in text
        assert "<script" not in lowered
        assert "<foreignobject" not in lowered
        assert "href=" not in lowered
        without_namespace = lowered.replace(
            'xmlns="http://www.w3.org/2000/svg"', ""
        )
        assert "http://" not in without_namespace
        assert "https://" not in without_namespace


def test_measured_figure_and_text_are_current() -> None:
    evidence, svg, readme = generate_readme_figures.render()
    assert generate_readme_figures.EVIDENCE_PATH.read_text(encoding="utf-8") == evidence
    assert generate_readme_figures.SVG_PATH.read_text(encoding="utf-8") == svg
    assert generate_readme_figures.README_PATH.read_text(encoding="utf-8") == readme


def test_measured_evidence_is_public_fixture_bound() -> None:
    payload = json.loads(
        generate_readme_figures.EVIDENCE_PATH.read_text(encoding="utf-8")
    )
    assert payload["classification"] == "Measured"
    assert payload["scope"] == "release-dogfood-fixtures"
    assert payload["metrics"]["startup_context"]["avoided_bytes"] > 0
    assert payload["metrics"]["repeated_output"]["avoided_bytes"] > 0
    assert all(not row["path"].startswith("/") for row in payload["inputs"])
    assert all(len(row["sha256"]) == 64 for row in payload["inputs"])


def test_readme_has_visible_text_equivalent_for_each_figure() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for classification in ("Illustrative", "Qualitative", "Measured"):
        assert f"Text equivalent — **{classification}" in readme
    assert "not a universal token-reduction guarantee" in readme
