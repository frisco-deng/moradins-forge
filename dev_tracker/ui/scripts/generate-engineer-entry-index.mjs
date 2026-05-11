import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..", "..");
const engineerEntryRoot = path.join(repoRoot, "docs", "engineer_entry");
const engineerEntrypointPath = path.join(repoRoot, "docs", "00_overview", "engineer_entrypoint.md");
const indexPath = path.join(engineerEntryRoot, "index.md");

export async function listEngineerEntryDocs(baseDir = engineerEntryRoot) {
  const entries = await fs.readdir(baseDir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(baseDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listEngineerEntryDocs(fullPath)));
      continue;
    }
    if (entry.isFile() && entry.name.endsWith(".md")) {
      files.push(fullPath);
    }
  }

  return files
    .map((filePath) => path.relative(repoRoot, filePath).split(path.sep).join("/"))
    .sort((left, right) => left.localeCompare(right));
}

function parseFrontmatter(raw) {
  if (!raw.startsWith("---\n")) {
    return { frontMatter: {}, body: raw };
  }

  const end = raw.indexOf("\n---\n", 4);
  if (end === -1) {
    return { frontMatter: {}, body: raw };
  }

  const frontMatter = {};
  for (const line of raw.slice(4, end).split("\n")) {
    const match = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (!match) {
      continue;
    }
    frontMatter[match[1]] = match[2];
  }

  return {
    frontMatter,
    body: raw.slice(end + 5),
  };
}

function firstHeading(body, fallback) {
  const match = body.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : fallback;
}

export async function buildEngineerEntryIndexMarkdown() {
  const docs = (await listEngineerEntryDocs()).filter((relativePath) => relativePath !== "docs/engineer_entry/index.md");
  const rows = [];

  for (const relativePath of docs) {
    const raw = await fs.readFile(path.join(repoRoot, relativePath), "utf8");
    const { frontMatter, body } = parseFrontmatter(raw);
    rows.push({
      title: String(frontMatter.title ?? firstHeading(body, path.basename(relativePath, ".md"))),
      owner: String(frontMatter.owner ?? "--"),
      status: String(frontMatter.status ?? "--"),
      path: relativePath,
    });
  }

  rows.sort((left, right) => left.path.localeCompare(right.path));

  const relatedDocs = ["../00_overview/engineer_entrypoint.md", "../11_ops/engineer_entry_authoring_runbook.md", "../11_ops/tooling_pipeline.md"];
  if (rows.length > 0) {
    relatedDocs.push(...rows.map((row) => row.path.replace(/^docs\/engineer_entry\//, "")));
  }

  return [
    "---",
    'title: "Engineer Entry Index"',
    "status: generated-reference",
    "owner: docs-build-pipeline",
    `last_reviewed: ${new Date().toISOString().slice(0, 10)}`,
    "source_refs: []",
    "related_docs:",
    ...Array.from(new Set(relatedDocs)).map((entry) => `  - ${entry}`),
    "generated: true",
    "generation_source: engineer-entry-index-generator",
    "generation_owner: docs-build-pipeline",
    "---",
    "",
    "# Engineer Entry Index",
    "",
    "## Purpose",
    "",
    "- Provide the generated directory index for engineer-entry context.",
    "- Separate generated navigation from human-owned operator instructions.",
    "",
    "## Human-Owned Context Contract",
    "",
    "- `docs/00_overview/engineer_entrypoint.md` is treated as human-owned context for the tracker classification model.",
    "- Any markdown file under `docs/engineer_entry/` except this index is human-owned context.",
    "- Human-owned engineer-entry docs must use `owner: person:<slug>` and are blocked from agent-side writes.",
    "",
    "## Current Human-Owned Files",
    "",
    rows.length > 0 ? rows.map((row) => `- [${row.title}](${row.path.replace(/^docs\//, "../")}) | owner: \`${row.owner}\` | status: \`${row.status}\``).join("\n") : "- No human-owned files under `docs/engineer_entry/` yet.",
    "",
    "## Required First Reads",
    "",
    "1. [Engineer Entrypoint](../00_overview/engineer_entrypoint.md)",
    "2. [Engineer Entry Authoring Runbook](../11_ops/engineer_entry_authoring_runbook.md)",
    "3. [Tooling Pipeline](../11_ops/tooling_pipeline.md)",
    "",
    "## Generation Notes",
    "",
    "- Regenerate this index after changing any human-owned engineer-entry file.",
    "- Canonical generator: `npm --prefix dev_tracker/ui run sync:engineer-entry`.",
    "",
  ].join("\n");
}

export async function writeEngineerEntryIndex() {
  const markdown = await buildEngineerEntryIndexMarkdown();
  await fs.writeFile(indexPath, `${markdown}\n`, "utf8");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await writeEngineerEntryIndex();
}
