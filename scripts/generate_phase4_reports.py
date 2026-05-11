#!/usr/bin/env python3
"""Generate deterministic phase 4 evaluation and observability report artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from rag_pipeline.evaluation import (
        build_online_eval_summary,
        execute_gold_set_pipeline,
        render_eval_summary_markdown,
        run_offline_evaluation,
    )
    from rag_pipeline.observability import (
        build_cost_summary,
        build_dashboard_snapshot,
        build_incident_routing_contract,
        evaluate_alert_rules,
        render_cost_summary_markdown,
    )
except ModuleNotFoundError:  # Harness-core seed mode.
    build_online_eval_summary = None
    execute_gold_set_pipeline = None
    render_eval_summary_markdown = None
    run_offline_evaluation = None
    build_cost_summary = None
    build_dashboard_snapshot = None
    build_incident_routing_contract = None
    evaluate_alert_rules = None
    render_cost_summary_markdown = None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_list(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = _load_json(path)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows", [])
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    raise ValueError(f"Expected list or {{rows: []}} JSON payload: {path}")


def _default_offline_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "gold_finance_policy",
            "query": "finance retention policy",
            "expected_doc_ids": ["doc_fin_policy"],
            "expected_answer_status": "grounded",
            "response": {
                "answer_status": "grounded",
                "citations": [
                    {
                        "document_id": "doc_fin_policy",
                        "content_uri": "file:///tmp/doc_fin_policy.md",
                    }
                ],
            },
        },
        {
            "case_id": "gold_denied_domain",
            "query": "finance retention policy with hr-only filter",
            "expected_doc_ids": [],
            "expected_answer_status": "low_confidence_fallback",
            "response": {
                "answer_status": "low_confidence_fallback",
                "citations": [],
            },
        },
    ]


def _default_request_events() -> list[dict[str, Any]]:
    return [
        {
            "request_id": "req_phase4_001",
            "status": "ok",
            "latency_ms": 420,
            "answer_status": "grounded",
            "confidence": 0.82,
            "feedback_score": 0.6,
            "candidate_count": 6,
            "evidence_count": 3,
        },
        {
            "request_id": "req_phase4_002",
            "status": "ok",
            "latency_ms": 710,
            "answer_status": "grounded",
            "confidence": 0.74,
            "feedback_score": 0.2,
            "candidate_count": 5,
            "evidence_count": 2,
        },
        {
            "request_id": "req_phase4_003",
            "status": "ok",
            "latency_ms": 860,
            "answer_status": "low_confidence_fallback",
            "confidence": 0.28,
            "feedback_score": -0.3,
            "candidate_count": 0,
            "evidence_count": 0,
        },
    ]


def _default_run_records() -> list[dict[str, Any]]:
    return [
        {
            "run_id": "run_phase4_001",
            "vector_writes": 24,
            "lexical_writes": 24,
            "metadata_writes": 24,
        },
        {
            "run_id": "run_phase4_002",
            "vector_writes": 12,
            "lexical_writes": 12,
            "metadata_writes": 12,
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("Harness/artifacts/reports"),
        help="Directory where eval_summary.md and cost_summary.md are written.",
    )
    parser.add_argument(
        "--offline-fixture",
        type=Path,
        default=None,
        help="Optional path to offline gold-set fixture JSON.",
    )
    parser.add_argument(
        "--request-events",
        type=Path,
        default=None,
        help="Optional path to JSON list of request events.",
    )
    parser.add_argument(
        "--run-records",
        type=Path,
        default=None,
        help="Optional path to JSON list of ingest run records.",
    )
    parser.add_argument(
        "--source-revision",
        type=str,
        default="working_tree",
        help="Source revision string written into generated reports.",
    )
    args = parser.parse_args(argv)

    if not all(
        [
            build_online_eval_summary,
            execute_gold_set_pipeline,
            render_eval_summary_markdown,
            run_offline_evaluation,
            build_cost_summary,
            build_dashboard_snapshot,
            build_incident_routing_contract,
            evaluate_alert_rules,
            render_cost_summary_markdown,
        ]
    ):
        reports_dir = args.reports_dir
        reports_dir.mkdir(parents=True, exist_ok=True)
        eval_summary_path = reports_dir / "eval_summary.md"
        cost_summary_path = reports_dir / "cost_summary.md"
        eval_summary_path.write_text(
            "# Eval Summary\n\n- Result: harness-core placeholder\n- Source: fallback mode without runtime evaluation package\n",
            encoding="utf-8",
        )
        cost_summary_path.write_text(
            "# Cost Summary\n\n- Result: harness-core placeholder\n- Source: fallback mode without runtime observability package\n",
            encoding="utf-8",
        )
        print(f"[phase4-reports] wrote {eval_summary_path}")
        print(f"[phase4-reports] wrote {cost_summary_path}")
        return 0

    if args.offline_fixture is not None:
        offline_summary = execute_gold_set_pipeline(fixture_path=args.offline_fixture)
    else:
        offline_summary = run_offline_evaluation(
            cases=_default_offline_cases(),
            workflow_id="offline_eval_harness_v1",
        )

    request_events = _load_list(args.request_events) if args.request_events else _default_request_events()
    run_records = _load_list(args.run_records) if args.run_records else _default_run_records()

    online_summary = build_online_eval_summary(events=request_events, sample_rate=1.0)
    dashboard = build_dashboard_snapshot(
        request_events=request_events,
        offline_eval_summary=offline_summary,
        online_eval_summary=online_summary,
    )
    alerts = evaluate_alert_rules(dashboard)
    incident_routing = build_incident_routing_contract(alerts["alerts"])
    cost_summary = build_cost_summary(run_records=run_records, request_events=request_events)

    combined_eval_summary = dict(offline_summary)
    combined_eval_summary["online_metrics"] = online_summary.get("metrics", {})
    combined_eval_summary["dashboard_reference"] = dashboard
    combined_eval_summary["incident_routing"] = incident_routing

    reports_dir = args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    eval_summary_path = reports_dir / "eval_summary.md"
    eval_summary_path.write_text(
        render_eval_summary_markdown(
            combined_eval_summary,
            source_revision=args.source_revision,
            workflow_id="phase4-evaluation-pipeline",
        ),
        encoding="utf-8",
    )

    cost_summary_path = reports_dir / "cost_summary.md"
    cost_summary_path.write_text(
        render_cost_summary_markdown(
            cost_summary,
            source_revision=args.source_revision,
            workflow_id="phase4-observability-pipeline",
        ),
        encoding="utf-8",
    )

    print(f"[phase4-reports] wrote {eval_summary_path}")
    print(f"[phase4-reports] wrote {cost_summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
