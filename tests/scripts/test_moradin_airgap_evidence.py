"""Diagnostic retention cannot turn a failed or uncertain build into acceptance."""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import moradin_airgap as airgap
from scripts import moradin_airgap_evidence as evidence


REQUEST = {"request_sha256": "a" * 64, "target": {"os_id": "arch", "version_id": "rolling", "arch": "amd64"}}


def run_failure(tmp_path, result=None, error=None):
    key = next(k for k in airgap.TARGET_IMAGES if k[0] == "arch")
    request = {**REQUEST, "target": {**REQUEST["target"], "version_id": key[1]}}
    with patch.object(airgap, "load_airgap_request", return_value=request), patch.object(airgap, "_rootless_engine", return_value="podman"):
        def runner(*args, **kwargs):
            (tmp_path / "output" / "partial").write_text("unaccepted")
            if error:
                raise error
            return result
        airgap.run_target_builder(tmp_path / "request.json", output=tmp_path / "output", forge_root=tmp_path, runner=runner)


def test_primary_build_error_and_bounded_redacted_logs_survive_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("FIXTURE_TOKEN", "opaque-example-credential")
    result = SimpleNamespace(returncode=125, stdout="package hook failed\n", stderr="password=hidden opaque-example-credential\ncleanup permission denied\n")
    with pytest.raises(airgap.AirgapError, match="exit 125"):
        run_failure(tmp_path, result)
    root = next((tmp_path / "artifacts/airgap-failures").iterdir())
    receipt = json.loads((root / "receipt.json").read_text())
    assert receipt["status"] == "failed" and receipt["accepted_payload"] is False
    assert receipt["cleanup"]["status"] == "complete"
    assert "package hook failed" in (root / "stdout.log").read_text()
    assert "hidden" not in (root / "stderr.log").read_text()
    assert "opaque-example-credential" not in (root / "stderr.log").read_text()
    assert not (tmp_path / "output").exists()


def test_cleanup_error_does_not_replace_original_status(tmp_path):
    result = SimpleNamespace(returncode=7, stdout="original failure", stderr="second error")
    with patch.object(airgap.shutil, "rmtree", side_effect=PermissionError("cleanup")):
        with pytest.raises(airgap.AirgapError, match="exit 7"):
            run_failure(tmp_path, result)
    receipt = json.loads(next((tmp_path / "artifacts/airgap-failures").glob("*/receipt.json")).read_text())
    assert receipt["cleanup"] == {"status": "failed", "error_type": "PermissionError"}


def test_uncertain_timeout_preserves_output_and_names_reconciliation(tmp_path):
    with pytest.raises(airgap.AirgapError, match="outcome uncertain"):
        run_failure(tmp_path, error=subprocess.TimeoutExpired(["podman"], 1, output="partial diagnostic"))
    receipt = json.loads(next((tmp_path / "artifacts/airgap-failures").glob("*/receipt.json")).read_text())
    assert receipt["cleanup"]["status"] == "not_attempted"
    assert (tmp_path / "output/partial").exists()
    assert receipt["accepted_payload"] is False


def test_long_logs_are_bounded_with_original_hash(tmp_path):
    destination, receipt = evidence.create_failure(tmp_path, REQUEST, "pinned", "fixture", result=SimpleNamespace(returncode=1, stdout="x" * 200000, stderr=""))
    assert receipt["logs"]["stdout"]["truncated"] is True
    assert receipt["logs"]["stdout"]["original_bytes"] == 200000
    assert (destination / "stdout.log").stat().st_size < 66000
    assert destination.stat().st_mode & 0o777 == 0o700


def test_evidence_write_failure_is_not_success(tmp_path):
    with patch.object(evidence, "write_json", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            evidence.create_failure(tmp_path, REQUEST, "pinned", "fixture")


def test_failed_workspace_cleanup_keeps_primary_exception(tmp_path):
    with patch.object(evidence.shutil, "rmtree", side_effect=PermissionError("secondary")):
        with pytest.raises(ValueError, match="primary") as raised:
            with evidence.build_workspace(tmp_path):
                raise ValueError("primary")
    # The exception propagates without being replaced by cleanup reporting.
    assert str(raised.value) == "primary"
    assert "PermissionError" in raised.value.__notes__[0]


def test_outer_bundle_workspace_retains_uncertain_builder_output(tmp_path):
    with pytest.raises(airgap.AirgapError, match="outcome uncertain"):
        with evidence.build_workspace(tmp_path) as workspace:
            root = Path(workspace)
            (root / "active-output").write_text("unreconciled")
            error = airgap.AirgapError("outcome uncertain")
            error.preserve_workspace = True
            raise error
    assert (root / "active-output").read_text() == "unreconciled"
