/* @vitest-environment node */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { validateEngineerEntry } from "../scripts/check-engineer-entry-frontmatter.mjs";

const tempRoots: string[] = [];

async function createTempEngineerEntryFixture(owner: string) {
  const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "mh-engineer-entry-"));
  tempRoots.push(repoRoot);

  const engineerEntryRoot = path.join(repoRoot, "docs", "engineer_entry");
  await fs.mkdir(engineerEntryRoot, { recursive: true });

  const indexMarkdown = [
    "---",
    'title: "Engineer Entry Index"',
    "status: generated-reference",
    "owner: docs-build-pipeline",
    "last_reviewed: 2026-03-07",
    "source_refs: []",
    "related_docs:",
    "  - ../00_overview/engineer_entrypoint.md",
    "generated: true",
    "generation_source: engineer-entry-index-generator",
    "generation_owner: docs-build-pipeline",
    "---",
    "",
    "# Engineer Entry Index",
    "",
    "## Current Human-Owned Files",
    "",
    "- [Runbook](policy.md) | owner: `person:test-owner` | status: `approved`",
    "",
  ].join("\n");

  const policyMarkdown = [
    "---",
    'title: "Runbook"',
    "status: approved",
    `owner: ${owner}`,
    "last_reviewed: 2026-03-07",
    "source_refs: []",
    "related_docs:",
    "  - index.md",
    "---",
    "",
    "# Runbook",
    "",
    "Operator guidance.",
    "",
  ].join("\n");

  await fs.writeFile(path.join(engineerEntryRoot, "index.md"), `${indexMarkdown}\n`, "utf8");
  await fs.writeFile(path.join(engineerEntryRoot, "policy.md"), `${policyMarkdown}\n`, "utf8");

  return { repoRoot, engineerEntryRoot, indexMarkdown };
}

describe("engineer entry guard", () => {
  afterEach(async () => {
    await Promise.all(tempRoots.splice(0).map((root) => fs.rm(root, { recursive: true, force: true })));
  });

  it("passes when index is generated and human-owned docs use person owners", async () => {
    const fixture = await createTempEngineerEntryFixture("person:test-owner");

    const errors = await validateEngineerEntry({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      changedPaths: [],
      expectedIndexMarkdown: fixture.indexMarkdown,
    });

    expect(errors).toEqual([]);
  });

  it("fails when a non-index engineer-entry doc does not use a person owner", async () => {
    const fixture = await createTempEngineerEntryFixture("platform-operations");

    const errors = await validateEngineerEntry({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      changedPaths: [],
      expectedIndexMarkdown: fixture.indexMarkdown,
    });

    expect(errors).toContain("docs/engineer_entry/policy.md: human-owned engineer-entry docs must use `owner: person:<slug>`");
  });
});
