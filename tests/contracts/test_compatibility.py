"""Harness-core compatibility script tests."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_compatibility_script_writes_report() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    bundle_path = repo_root / "Harness" / "artifacts" / "schemas" / "contracts.bundle.json"
    report_path = repo_root / "Harness" / "artifacts" / "schemas" / "compatibility_report.md"
    script_path = repo_root / "scripts" / "check_contract_compatibility.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--bundle",
            str(bundle_path),
            "--report",
            str(report_path),
            "--strict",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )

    assert completed.returncode == 0, completed.stderr
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Compatibility Report" in content
    assert "Result:" in content
