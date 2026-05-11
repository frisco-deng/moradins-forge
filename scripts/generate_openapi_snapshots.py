#!/usr/bin/env python3
"""Generate OpenAPI snapshots from executable Flask service definitions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from flask import Flask
try:
    from apps.services.chunker_service.app import create_app as create_chunker_app
    from apps.services.gateway_api.app import create_app as create_gateway_app
    from apps.services.parser_service.app import create_app as create_parser_app
    from apps.services.query_service.app import create_app as create_query_app
except ModuleNotFoundError:  # Harness-core seed mode.
    create_chunker_app = None
    create_gateway_app = None
    create_parser_app = None
    create_query_app = None

METHODS_TO_INCLUDE = {"GET", "POST", "PUT", "PATCH", "DELETE"}

SERVICE_CONFIG: dict[str, dict[str, str]] = {
    "gateway_api": {
        "title": "Gateway API",
        "description": "Enterprise entrypoint for retrieval and ingestion orchestration.",
    },
    "query_service": {
        "title": "Query Service API",
        "description": "Internal retrieval planning and candidate fusion API.",
    },
    "parser_service": {
        "title": "Parser Service API",
        "description": "Parser service contract boundary for canonical parse outputs.",
    },
    "chunker_service": {
        "title": "Chunker Service API",
        "description": "Chunker service contract boundary for adaptive chunk output.",
    },
}


def _normalize_path(flask_rule: str) -> str:
    return re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", flask_rule)


def _responses_for(path: str, method: str) -> dict[str, dict[str, str]]:
    if method == "POST" and path == "/v1/ingestion/jobs":
        return {"202": {"description": "Accepted"}, "400": {"description": "Bad request"}}
    if method == "GET" and path == "/v1/ingestion/jobs/{job_id}":
        return {"200": {"description": "Job status"}, "404": {"description": "Not found"}}
    return {"200": {"description": "Success"}, "400": {"description": "Bad request"}}


def build_openapi_snapshot(service: str, app: Flask) -> dict[str, Any]:
    config = SERVICE_CONFIG[service]
    paths: dict[str, dict[str, Any]] = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = _normalize_path(rule.rule)
        for method in sorted(rule.methods.intersection(METHODS_TO_INCLUDE)):
            method_lower = method.lower()
            paths.setdefault(path, {})
            paths[path][method_lower] = {
                "summary": rule.endpoint.replace("_", " "),
                "responses": _responses_for(path, method),
            }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": config["title"],
            "version": "1.0.0",
            "description": config["description"],
        },
        "paths": paths,
        "components": {
            "schemas": {
                "ErrorResponse": {
                    "type": "object",
                    "required": [
                        "code",
                        "message",
                        "category",
                        "correlation_id",
                        "retryable",
                    ],
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "category": {"type": "string"},
                        "correlation_id": {"type": "string"},
                        "retryable": {"type": "boolean"},
                    },
                }
            }
        },
    }


def write_openapi_snapshots(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not all([create_gateway_app, create_query_app, create_parser_app, create_chunker_app]):
        written: list[Path] = []
        for service in SERVICE_CONFIG:
            output_path = output_dir / f"{service}.openapi.json"
            if output_path.exists():
                written.append(output_path)
                continue
            snapshot = {
                "openapi": "3.1.0",
                "info": {
                    "title": SERVICE_CONFIG[service]["title"],
                    "version": "1.0.0",
                    "description": f"{SERVICE_CONFIG[service]['description']} (harness-core placeholder)",
                },
                "paths": {},
                "components": {"schemas": {}},
            }
            output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=False), encoding="utf-8")
            written.append(output_path)
        return written

    service_apps: dict[str, Flask] = {
        "gateway_api": create_gateway_app(),
        "query_service": create_query_app(),
        "parser_service": create_parser_app(),
        "chunker_service": create_chunker_app(),
    }

    written: list[Path] = []
    for service, app in service_apps.items():
        snapshot = build_openapi_snapshot(service, app)
        output_path = output_dir / f"{service}.openapi.json"
        output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=False), encoding="utf-8")
        written.append(output_path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Harness/artifacts/openapi"),
        help="Directory to write service OpenAPI snapshot files.",
    )
    args = parser.parse_args(argv)
    written = write_openapi_snapshots(args.output_dir)
    for path in written:
        print(f"[openapi] wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
