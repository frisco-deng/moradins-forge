---
title: "Message Catalog"
status: generated-contract
owner: docs-build-pipeline
last_reviewed: 2026-02-23
source_refs: []
related_docs:
  - ../../02_contracts/message_catalog.md
  - contracts.bundle.json
  - ../../12_pipelines/job_contracts.md
generated: true
generation_source: topic-contract-generator
generation_owner: docs-build-pipeline
---

# Message Catalog

## Topic Snapshot

| topic | key | payload_schema | retries | dlq |
| --- | --- | --- | --- | --- |
| ingestion.document.received.v1 | document_id | DocumentEnvelopeV1 | yes | yes |
| ingestion.chunk.ready.v1 | document_id | ChunkEnvelopeV1 | yes | yes |
| index.update.completed.v1 | index_name | ReindexJobEventV1 | yes | yes |
| retrieval.audit.event.v1 | request_id | AuditEventV1 | yes | yes |
| governance.capability_gap.v1 | gap_id | AuditEventV1 | yes | yes |

## Regeneration

- Regenerate from contract source after topic or schema updates.
- Keep topic names and key strategy synchronized with pipeline docs.

## Related Docs

- ../../02_contracts/message_catalog.md
- contracts.bundle.json
- ../../12_pipelines/job_contracts.md
