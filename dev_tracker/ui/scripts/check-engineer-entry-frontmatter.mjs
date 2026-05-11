import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { buildEngineerEntryIndexMarkdown } from "./generate-engineer-entry-index.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..", "..");
const engineerEntryRoot = path.join(repoRoot, "docs", "engineer_entry");
const capabilityGapReportPaths = [path.join(repoRoot, "Harness", "artifacts", "control", "capability_gap_register.md")];
const allowedBootstrapWrites = new Set(["docs/engineer_entry/index.md"]);
const requiredFrontmatterKeys = ["title", "status", "owner", "last_reviewed", "source_refs", "related_docs"];
const engineerEntryGapTarget = "engineer-entry guard automation";
const generatedIndexPath = "docs/engineer_entry/index.md";
const humanOwnerPattern = /^person:[a-z0-9][a-z0-9_-]*$/;

async function main() {
  const files = await listMarkdownFiles(engineerEntryRoot);
  const errors = await validateEngineerEntry();

  if (errors.length > 0) {
    await ensureEngineerEntryGapOpened();
    process.stderr.write("[engineer-entry] guard failed\n");
    for (const error of errors) {
      process.stderr.write(`- ${error}\n`);
    }
    process.exitCode = 1;
    return;
  }

  process.stdout.write(`[engineer-entry] guard pass (${files.length} files validated)\n`);
}

export async function validateEngineerEntry({
  repoRootPath = repoRoot,
  engineerEntryPath = engineerEntryRoot,
  changedPaths = null,
  expectedIndexMarkdown = null,
} = {}) {
  const files = await listMarkdownFiles(engineerEntryPath);
  const errors = [];

  if (files.length === 0) {
    errors.push("docs/engineer_entry must contain at least one markdown file");
    return errors;
  }

  const normalizedRepoRoot = path.resolve(repoRootPath);
  const expectedIndex = expectedIndexMarkdown ?? (await buildEngineerEntryIndexMarkdown());

  for (const filePath of files) {
    const relativePath = normalizePath(path.relative(normalizedRepoRoot, filePath));
    const raw = await fs.readFile(filePath, "utf8");
    const parsed = parseFrontmatter(raw);

    if (!parsed) {
      errors.push(`${relativePath}: missing valid frontmatter block`);
      continue;
    }

    for (const key of requiredFrontmatterKeys) {
      if (!parsed.keys.has(key)) {
        errors.push(`${relativePath}: missing frontmatter key \`${key}\``);
      }
    }

    if (relativePath === generatedIndexPath) {
      if (!parsed.keys.has("generated")) {
        errors.push(`${relativePath}: generated index must include \`generated: true\``);
      }
      const generatedValue = parsed.values.get("generated") ?? "";
      if (String(generatedValue).trim() !== "true") {
        errors.push(`${relativePath}: generated index must set \`generated: true\``);
      }

      if (normalizeLineEndings(raw).trim() !== normalizeLineEndings(expectedIndex).trim()) {
        errors.push(`${relativePath}: stale generated index; run \`npm --prefix dev_tracker/ui run sync:engineer-entry\``);
      }
      continue;
    }

    const ownerValue = parsed.values.get("owner") ?? "";
    if (!humanOwnerPattern.test(String(ownerValue).trim())) {
      errors.push(`${relativePath}: human-owned engineer-entry docs must use \`owner: person:<slug>\``);
    }

    if (!hasTopLevelHeading(parsed.body)) {
      errors.push(`${relativePath}: missing top-level markdown heading`);
    }
  }

  const changedEngineerEntryPaths = changedPaths ?? readChangedEngineerEntryPaths(normalizedRepoRoot);
  const disallowedWrites = changedEngineerEntryPaths.filter((filePath) => !allowedBootstrapWrites.has(filePath));
  if (disallowedWrites.length > 0) {
    errors.push(`disallowed writes detected in engineer_entry: ${disallowedWrites.join(", ")}`);
  }

  return errors;
}

async function listMarkdownFiles(baseDir) {
  try {
    const entries = await fs.readdir(baseDir, { withFileTypes: true });
    const files = [];

    for (const entry of entries) {
      const fullPath = path.join(baseDir, entry.name);
      if (entry.isDirectory()) {
        const nestedFiles = await listMarkdownFiles(fullPath);
        files.push(...nestedFiles);
        continue;
      }
      if (entry.isFile() && entry.name.endsWith(".md")) {
        files.push(fullPath);
      }
    }

    return files.sort((a, b) => normalizePath(a).localeCompare(normalizePath(b)));
  } catch {
    return [];
  }
}

async function ensureEngineerEntryGapOpened() {
  if (process.env.ENGINEER_ENTRY_AUTOGAP === "0") {
    return;
  }

  const capabilityGapReportPath = await resolveCapabilityGapReportPath();
  if (!capabilityGapReportPath) {
    return;
  }

  let markdown = "";
  try {
    markdown = await fs.readFile(capabilityGapReportPath, "utf8");
  } catch {
    return;
  }

  const openRowPattern = new RegExp(`\\|\\s*GAP-\\d+\\s*\\|[^\\n]*\\|\\s*open\\s*\\|[^\\n]*${escapeRegex(engineerEntryGapTarget)}`, "i");
  if (openRowPattern.test(markdown)) {
    return;
  }

  const matches = [...markdown.matchAll(/\|\s*GAP-(\d+)\s*\|/g)];
  const maxGapNumber = matches.reduce((max, match) => Math.max(max, Number(match[1] || 0)), 0);
  const nextGapId = `GAP-${String(maxGapNumber + 1).padStart(4, "0")}`;
  const today = new Date().toISOString().slice(0, 10);
  const row = `| ${nextGapId} | ${today} | open | tooling | platform-operations | ${engineerEntryGapTarget} | ../../11_ops/tooling_pipeline.md |`;

  if (markdown.includes("## Status Values")) {
    markdown = markdown.replace("\n## Status Values", `\n${row}\n\n## Status Values`);
  } else {
    markdown = `${markdown.trim()}\n\n${row}\n`;
  }

  await fs.writeFile(capabilityGapReportPath, markdown, "utf8");
}

async function resolveCapabilityGapReportPath() {
  for (const candidatePath of capabilityGapReportPaths) {
    try {
      const stat = await fs.stat(candidatePath);
      if (stat.isFile()) {
        return candidatePath;
      }
    } catch {
      continue;
    }
  }
  return null;
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parseFrontmatter(markdown) {
  if (!markdown.startsWith("---\n")) {
    return null;
  }

  const end = markdown.indexOf("\n---\n", 4);
  if (end === -1) {
    return null;
  }

  const header = markdown.slice(4, end);
  const body = markdown.slice(end + 5);
  const keys = new Set();
  const values = new Map();

  for (const line of header.split("\n")) {
    const match = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (!match) {
      continue;
    }
    keys.add(match[1]);
    values.set(match[1], match[2]);
  }

  return { keys, values, body };
}

function hasTopLevelHeading(body) {
  return body
    .split("\n")
    .some((line) => line.trim().startsWith("# "));
}

function readChangedEngineerEntryPaths(repoRoot) {
  try {
    const output = execFileSync("git", ["-C", repoRoot, "status", "--porcelain=v1", "--", "docs/engineer_entry"], {
      encoding: "utf8",
    });

    const rawPaths = output
      .split("\n")
      .map((line) => line.replace(/\r$/, ""))
      .filter((line) => line.trim().length > 0)
      .map((line) => {
        const pathPart = line.length >= 3 ? line.slice(3).trim() : line.trim();
        if (pathPart.includes(" -> ")) {
          return normalizePath(pathPart.split(" -> ").at(-1) ?? "");
        }
        return normalizePath(pathPart);
      })
      .filter(Boolean);

    const expanded = [];
    for (const rawPath of rawPaths) {
      if (rawPath.endsWith("/")) {
        const fullPath = path.join(repoRoot, rawPath);
        try {
          const entries = execFileSync("find", [fullPath, "-type", "f", "-name", "*.md"], { encoding: "utf8" })
            .split("\n")
            .map((entry) => entry.trim())
            .filter(Boolean)
            .map((entry) => normalizePath(path.relative(repoRoot, entry)));
          expanded.push(...entries);
        } catch {
          continue;
        }
        continue;
      }
      expanded.push(rawPath);
    }

    return Array.from(new Set(expanded)).sort((a, b) => a.localeCompare(b));
  } catch {
    return [];
  }
}

function normalizePath(inputPath) {
  return inputPath.split(path.sep).join("/");
}

function normalizeLineEndings(input) {
  return String(input).replace(/\r\n/g, "\n");
}

main().catch((error) => {
  process.stderr.write(`[engineer-entry] guard failed: ${String(error.stack || error)}\n`);
  process.exitCode = 1;
});
