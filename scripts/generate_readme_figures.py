#!/usr/bin/env python3
"""Generate deterministic public README measurement evidence and its SVG."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = REPO_ROOT / "docs/assets/readme/measured-benefits.json"
SVG_PATH = REPO_ROOT / "docs/assets/readme/measured-benefits.svg"
README_PATH = REPO_ROOT / "README.md"
TEXT_BEGIN = "<!-- measured-benefits-text:start -->"
TEXT_END = "<!-- measured-benefits-text:end -->"
STARTUP_RAW = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "FORGE.md",
    REPO_ROOT / "Harness/entrypoints/forge.md",
)
STARTUP_SUMMARY = REPO_ROOT / "tests/fixtures/readme_metrics/context-primer.md"
REPEATED_RAW = REPO_ROOT / "tests/fixtures/readme_metrics/repeated-command-output.txt"
REPEATED_SUMMARY = REPO_ROOT / "tests/fixtures/readme_metrics/rerun-advice.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence() -> dict[str, object]:
    startup_raw = sum(path.stat().st_size for path in STARTUP_RAW)
    startup_summary = STARTUP_SUMMARY.stat().st_size
    repeated_raw = REPEATED_RAW.stat().st_size
    repeated_summary = REPEATED_SUMMARY.stat().st_size
    return {
        "version": "MoradinForgeReadmeEvidenceV1",
        "classification": "Measured",
        "scope": "release-dogfood-fixtures",
        "method": (
            "UTF-8 byte counts over checked-in public first-hop guidance and "
            "deterministic summary fixtures"
        ),
        "inputs": [
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (*STARTUP_RAW, STARTUP_SUMMARY, REPEATED_RAW, REPEATED_SUMMARY)
        ],
        "metrics": {
            "startup_context": {
                "without_summary_bytes": startup_raw,
                "with_summary_bytes": startup_summary,
                "avoided_bytes": startup_raw - startup_summary,
            },
            "repeated_output": {
                "without_reuse_bytes": repeated_raw,
                "with_rerun_advice_bytes": repeated_summary,
                "avoided_bytes": repeated_raw - repeated_summary,
            },
        },
        "disclaimer": (
            "Release-dogfood fixture evidence only; results are not a universal "
            "token-reduction or performance guarantee."
        ),
    }


def svg(payload: dict[str, object]) -> str:
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    startup = metrics["startup_context"]
    repeated = metrics["repeated_output"]
    assert isinstance(startup, dict) and isinstance(repeated, dict)
    startup_raw = int(startup["without_summary_bytes"])
    startup_summary = int(startup["with_summary_bytes"])
    repeated_raw = int(repeated["without_reuse_bytes"])
    repeated_summary = int(repeated["with_rerun_advice_bytes"])
    startup_width = max(8, round(520 * startup_summary / startup_raw))
    repeated_width = max(8, round(520 * repeated_summary / repeated_raw))
    return f'''<svg width="920" height="390" viewBox="0 0 920 390" role="img" aria-labelledby="title desc" xmlns="http://www.w3.org/2000/svg">
  <title id="title">Measured release-dogfood summary byte comparison</title>
  <desc id="desc">Checked-in fixture byte counts compare raw first-hop guidance with a compact primer, and repeated command output with rerun advice.</desc>
  <rect width="920" height="390" rx="18" fill="#f8fafc"/>
  <rect x="32" y="28" width="856" height="334" rx="14" fill="#ffffff" stroke="#64748b" stroke-width="2"/>
  <rect x="60" y="50" width="118" height="34" rx="17" fill="#14532d"/>
  <text x="119" y="73" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#ffffff">Measured</text>
  <text x="198" y="73" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#0f172a">Release-dogfood fixture bytes</text>
  <g font-family="Arial, sans-serif" fill="#0f172a">
    <text x="60" y="125" font-size="18" font-weight="700">Startup context</text>
    <text x="60" y="154" font-size="14">Raw guidance: {startup_raw:,} bytes</text>
    <rect x="260" y="138" width="520" height="22" rx="5" fill="#1d4ed8"/>
    <text x="60" y="186" font-size="14">Compact primer: {startup_summary:,} bytes</text>
    <rect x="260" y="170" width="{startup_width}" height="22" rx="5" fill="#16a34a"/>
    <text x="60" y="239" font-size="18" font-weight="700">Repeated output</text>
    <text x="60" y="268" font-size="14">Repeated log: {repeated_raw:,} bytes</text>
    <rect x="260" y="252" width="520" height="22" rx="5" fill="#1d4ed8"/>
    <text x="60" y="300" font-size="14">Rerun advice: {repeated_summary:,} bytes</text>
    <rect x="260" y="284" width="{repeated_width}" height="22" rx="5" fill="#16a34a"/>
    <text x="60" y="340" font-size="13" fill="#334155">Fixture evidence, not a universal token-reduction guarantee.</text>
  </g>
</svg>
'''


def text_equivalent(payload: dict[str, object]) -> str:
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    startup = metrics["startup_context"]
    repeated = metrics["repeated_output"]
    assert isinstance(startup, dict) and isinstance(repeated, dict)
    return "\n".join(
        [
            TEXT_BEGIN,
            "Text equivalent — **Measured release-dogfood fixtures:** startup context was "
            f"{startup['without_summary_bytes']:,} raw bytes versus "
            f"{startup['with_summary_bytes']:,} primer bytes; repeated output was "
            f"{repeated['without_reuse_bytes']:,} raw bytes versus "
            f"{repeated['with_rerun_advice_bytes']:,} rerun-advice bytes. These "
            "checked-in fixture results are not a universal token-reduction guarantee.",
            TEXT_END,
        ]
    )


def replace_readme_block(readme: str, block: str) -> str:
    if readme.count(TEXT_BEGIN) != 1 or readme.count(TEXT_END) != 1:
        raise RuntimeError("README measured-benefits marker block is missing or ambiguous")
    start = readme.index(TEXT_BEGIN)
    end = readme.index(TEXT_END, start) + len(TEXT_END)
    return readme[:start] + block + readme[end:]


def render() -> tuple[str, str, str]:
    payload = evidence()
    evidence_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    svg_text = svg(payload)
    readme_text = replace_readme_block(
        README_PATH.read_text(encoding="utf-8"),
        text_equivalent(payload),
    )
    return evidence_text, svg_text, readme_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    evidence_text, svg_text, readme_text = render()
    expected = {
        EVIDENCE_PATH: evidence_text,
        SVG_PATH: svg_text,
        README_PATH: readme_text,
    }
    if args.check:
        stale = [
            path.relative_to(REPO_ROOT).as_posix()
            for path, content in expected.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            print("stale README evidence: " + ", ".join(stale), file=sys.stderr)
            return 1
        return 0
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
