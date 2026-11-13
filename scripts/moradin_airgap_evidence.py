"""Private, bounded failure evidence outside disposable air-gap build trees."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import uuid
import shutil
import tempfile
from contextlib import contextmanager

try:
    from scripts.moradin_workstation import atomic_write_text, write_json
except ModuleNotFoundError:  # direct script import
    from moradin_workstation import atomic_write_text, write_json


def redact(value: str) -> str:
    value = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
    for name, secret in os.environ.items():
        if len(secret) >= 4 and any(word in name.upper() for word in ("TOKEN", "PASSWORD", "SECRET")):
            value = value.replace(secret, "<redacted>")
    value = re.sub(r"(?i)(token|password|secret|authorization)(\s*[=:]\s*)(\S+)", r"\1\2<redacted>", value)
    value = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://<redacted>@", value)
    value = re.sub(r"/(?:home|Users)/[^/\s]+", "<home>", value)
    return value


def create_failure(forge_root: Path, request: dict, image: str, engine: str, *, result=None, error=None) -> tuple[Path, dict]:
    parent = forge_root / "artifacts" / "airgap-failures"
    if any(p.is_symlink() for p in (parent, *parent.parents)):
        raise ValueError("airgap_failure_evidence_symlink_conflict")
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / uuid.uuid4().hex
    destination.mkdir(mode=0o700)
    receipt = {
        "version": "AirgapFailureEvidenceV1", "status": "failed", "accepted_payload": False,
        "request_sha256": request["request_sha256"], "target": request["target"],
        "image": image, "engine": engine, "returncode": getattr(result, "returncode", None),
        "engine_binary_sha256": hashlib.sha256(Path(shutil.which(engine)).resolve().read_bytes()).hexdigest() if shutil.which(engine) else None,
        "execution_error": type(error).__name__ if error else None,
        "cleanup": {"status": "pending"}, "logs": {},
        "limit": "Bounded redacted diagnostic excerpts; partial files are not accepted payloads. Root cause requires investigation.",
    }
    for label in ("stdout", "stderr"):
        raw = getattr(result if result is not None else error, label, "") or ""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        original = raw.encode("utf-8", errors="replace")
        text = redact(raw)
        encoded = text.encode()
        truncated = len(encoded) > 65536
        if truncated:
            text = encoded[:32768].decode("utf-8", errors="replace") + "\n<diagnostic excerpt truncated>\n" + encoded[-32768:].decode("utf-8", errors="replace")
        path = destination / (label + ".log")
        atomic_write_text(path, text)
        path.chmod(0o600)
        receipt["logs"][label] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                    "original_sha256": hashlib.sha256(original).hexdigest(),
                                    "original_bytes": len(original), "truncated": truncated}
    write_json(destination / "receipt.json", receipt)
    return destination, receipt


def finish_cleanup(destination: Path, receipt: dict, error=None):
    receipt["cleanup"] = {"status": "failed" if error else "complete",
                          "error_type": type(error).__name__ if error else None}
    write_json(destination / "receipt.json", receipt)


@contextmanager
def build_workspace(parent: Path):
    temporary = Path(tempfile.mkdtemp(prefix="moradin-airgap-build-", dir=parent))
    try:
        yield str(temporary)
    except BaseException as primary:
        if getattr(primary, "preserve_workspace", False):
            primary.add_note(f"uncertain air-gap build workspace retained for reconciliation: {temporary}")
            raise
        try:
            shutil.rmtree(temporary)
        except OSError as cleanup:
            primary.add_note(f"air-gap workspace cleanup also failed: {type(cleanup).__name__}")
        raise
    else:
        # A successful build still reports a real cleanup failure.
        shutil.rmtree(temporary)
