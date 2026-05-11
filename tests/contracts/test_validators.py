"""Harness-core schema bundle validator coverage."""

from __future__ import annotations

import json
from pathlib import Path


REQUIRED_SCHEMA_NAMES = {
    "DocumentEnvelopeV1",
    "RetrievalRequestV1",
    "RetrievalCandidateV1",
    "GroundedAnswerV1",
}


def test_contract_bundle_contains_required_schema_names() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    bundle_path = repo_root / "Harness" / "artifacts" / "schemas" / "contracts.bundle.json"
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    schemas = payload.get("schemas", [])
    names = {item.get("name") for item in schemas if isinstance(item, dict)}
    missing = REQUIRED_SCHEMA_NAMES.difference(names)
    assert not missing, f"missing required schemas: {sorted(missing)}"
