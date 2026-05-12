/* @vitest-environment node */

import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

import { afterEach, describe, expect, it } from "vitest";

import { buildEngineerEntryIndexMarkdown } from "../scripts/generate-engineer-entry-index.mjs";
import { runEngineerEntryGuard, validateEngineerEntry } from "../scripts/check-engineer-entry-frontmatter.mjs";

const execFileAsync = promisify(execFile);
const tempRoots: string[] = [];
const uiRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function createTempEngineerEntryFixture({
  owner = "person:test-owner",
  indexDate = "2026-03-07",
  staleIndex = false,
} = {}) {
  const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "mh-engineer-entry-"));
  tempRoots.push(repoRoot);

  const engineerEntryRoot = path.join(repoRoot, "docs", "engineer_entry");
  await fs.mkdir(engineerEntryRoot, { recursive: true });

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
  await fs.writeFile(path.join(engineerEntryRoot, "policy.md"), `${policyMarkdown}\n`, "utf8");

  let indexMarkdown = await buildEngineerEntryIndexMarkdown({
    repoRootPath: repoRoot,
    engineerEntryPath: engineerEntryRoot,
    lastReviewedDate: indexDate,
  });
  if (staleIndex) {
    indexMarkdown = indexMarkdown.replace("## Generation Notes", "## Outdated Generation Notes");
  }
  await fs.writeFile(path.join(engineerEntryRoot, "index.md"), `${indexMarkdown}\n`, "utf8");

  return { repoRoot, engineerEntryRoot };
}

async function createCapabilityGapRegister(repoRoot: string) {
  const capabilityGapPath = path.join(repoRoot, "Harness", "artifacts", "control", "capability_gap_register.md");
  const originalContent = [
    "---",
    'title: "Public Workbench Capability Gap Register"',
    "status: public-placeholder",
    "owner: moradin-forge",
    "---",
    "",
    "# Public Workbench Capability Gap Register",
    "",
    "## Register Table",
    "",
    "| gap_id | opened_on | status | class | owner | enforcement_target | evidence_link |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    "",
  ].join("\n");

  await fs.mkdir(path.dirname(capabilityGapPath), { recursive: true });
  await fs.writeFile(capabilityGapPath, originalContent, "utf8");
  return { capabilityGapPath, originalContent };
}

function captureStream() {
  const chunks: string[] = [];
  return {
    chunks,
    stream: {
      write(chunk: string) {
        chunks.push(String(chunk));
        return true;
      },
    },
  };
}

describe("engineer entry guard", () => {
  afterEach(async () => {
    await Promise.all(tempRoots.splice(0).map((root) => fs.rm(root, { recursive: true, force: true })));
  });

  it("does not execute the CLI when imported as a module", async () => {
    const guardScriptPath = path.join(uiRoot, "scripts", "check-engineer-entry-frontmatter.mjs");

    const { stdout, stderr } = await execFileAsync(
      process.execPath,
      ["-e", `import(${JSON.stringify(pathToFileURL(guardScriptPath).href)})`],
      {
        cwd: uiRoot,
        encoding: "utf8",
        env: { ...process.env, ENGINEER_ENTRY_AUTOGAP: "1" },
      },
    );

    expect(stdout).toBe("");
    expect(stderr).toBe("");
  });

  it("passes when index is generated and human-owned docs use person owners", async () => {
    const fixture = await createTempEngineerEntryFixture();

    const errors = await validateEngineerEntry({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      changedPaths: [],
    });

    expect(errors).toEqual([]);
  });

  it("does not fail only because the generated index date differs from today", async () => {
    const fixture = await createTempEngineerEntryFixture({ indexDate: "2026-03-07" });

    const errors = await validateEngineerEntry({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      changedPaths: [],
    });

    expect(errors).toEqual([]);
  });

  it("still fails when the generated index body is stale", async () => {
    const fixture = await createTempEngineerEntryFixture({ staleIndex: true });

    const errors = await validateEngineerEntry({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      changedPaths: [],
    });

    expect(errors).toContain("docs/engineer_entry/index.md: stale generated index; run `npm --prefix dev_tracker/ui run sync:engineer-entry`");
  });

  it("fails when a non-index engineer-entry doc does not use a person owner", async () => {
    const fixture = await createTempEngineerEntryFixture({ owner: "platform-operations" });

    const errors = await validateEngineerEntry({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      changedPaths: [],
    });

    expect(errors).toContain("docs/engineer_entry/policy.md: human-owned engineer-entry docs must use `owner: person:<slug>`");
  });

  it("does not modify the capability gap register by default", async () => {
    const fixture = await createTempEngineerEntryFixture({ owner: "platform-operations" });
    const { capabilityGapPath, originalContent } = await createCapabilityGapRegister(fixture.repoRoot);
    const stdout = captureStream();
    const stderr = captureStream();

    const exitCode = await runEngineerEntryGuard({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      env: {},
      stdout: stdout.stream,
      stderr: stderr.stream,
    });

    expect(exitCode).toBe(1);
    expect(stderr.chunks.join("")).toContain("human-owned engineer-entry docs must use `owner: person:<slug>`");
    expect(await fs.readFile(capabilityGapPath, "utf8")).toBe(originalContent);
  });

  it("opens one deduplicated capability gap when requested", async () => {
    const fixture = await createTempEngineerEntryFixture({ owner: "platform-operations" });
    const { capabilityGapPath } = await createCapabilityGapRegister(fixture.repoRoot);
    const stdout = captureStream();
    const stderr = captureStream();

    await runEngineerEntryGuard({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      args: ["--open-gap"],
      env: {},
      stdout: stdout.stream,
      stderr: stderr.stream,
    });
    await runEngineerEntryGuard({
      repoRootPath: fixture.repoRoot,
      engineerEntryPath: fixture.engineerEntryRoot,
      args: ["--open-gap"],
      env: {},
      stdout: stdout.stream,
      stderr: stderr.stream,
    });

    const markdown = await fs.readFile(capabilityGapPath, "utf8");
    expect(markdown).toContain("engineer-entry guard automation");
    expect(markdown.match(/\|\s*GAP-\d+\s*\|/g) ?? []).toHaveLength(1);
  });
});
