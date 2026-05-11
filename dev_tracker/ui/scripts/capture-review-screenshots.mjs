#!/usr/bin/env node

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";
import { createServer } from "vite";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(uiRoot, "..", "..");
const defaultOutputDir = path.join(
  uiRoot,
  ".review_evidence",
  new Date().toISOString().replaceAll(":", "-").replaceAll(".", "-"),
);
const host = "127.0.0.1";
const port = Number(process.env.UI_REVIEW_PORT || 4373);
const fullPageCapture = process.env.UI_REVIEW_FULL_PAGE === "1";
const outputDir = process.env.UI_REVIEW_OUTPUT_DIR
  ? path.resolve(process.env.UI_REVIEW_OUTPUT_DIR)
  : defaultOutputDir;
const trackerSnapshotPath = path.join(uiRoot, "public", "generated", "tracker_snapshot_v1.json");

const screenshotTargets = [
  {
    fileName: "01-home-no-project.png",
    path: "/home",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) => page.getByText("No project pinned").waitFor(),
  },
  {
    fileName: "02-deploy-quick-start.png",
    path: "/deploy/quick-start",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) => page.getByRole("button", { name: "Dismiss tutorial" }).waitFor(),
  },
  {
    fileName: "03-deploy-map.png",
    path: "/deploy/map",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) => page.getByRole("heading", { name: "Baseline Harness Tree" }).waitFor(),
  },
  {
    fileName: "04-deploy-builder-demo.png",
    path: "/deploy/builder?demo=seeded",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) => page.getByText("Preview mode is read-only.").waitFor(),
  },
  {
    fileName: "05-deploy-verify-demo.png",
    path: "/deploy/status?demo=seeded",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) =>
      page
        .getByText("Preview mode is read-only. Use it to understand the Verify layout and alignment summary before you load a real project report.")
        .waitFor(),
  },
  {
    fileName: "06-docs-explorer.png",
    path: "/docs",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) => page.getByPlaceholder("Search title/path/headings/content").waitFor(),
  },
  {
    fileName: "07-reviews-queue.png",
    path: "/reviews/queue",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) => page.getByText("Review Artifacts").waitFor(),
  },
  {
    fileName: "08-activity-feed.png",
    path: "/reviews/exchange",
    localState: {
      pinnedProject: null,
    },
    waitFor: async (page) => page.getByText("Rolling change feed for the work that actually moved.").waitFor(),
  },
];

function buildMockStatus(uiPort) {
  return {
    api: "TrackerControlStatusV1",
    runtime_state: {
      last_sync_at: "",
      last_sync_result: "success",
      last_sync_duration_ms: 42,
      sync_count: 1,
      syncing: false,
      last_error: "",
    },
    runtime_snapshot: {},
    tracker_snapshot: {
      version: "TrackerSnapshotV6",
      generated_at: new Date().toISOString(),
      summary: {},
    },
    ui_access: {
      runtime_mode: "linux",
      bind_host: host,
      ui_port: uiPort,
      preferred_urls: [`http://${host}:${uiPort}/`],
      browser_access_summary: "Use localhost, WSL browser access, or SSH local port forwarding.",
      remote_ssh_tunnel_example: `ssh -L ${uiPort}:127.0.0.1:${uiPort} <linux-host>`,
      execution_host_summary: "Assistant commands run on the Linux host that launched the harness.",
      public_bind_supported: false,
    },
    assistant_runtimes: {
      codex_cli: {
        assistant: "codex_cli",
        label: "Codex CLI",
        command: "codex",
        args: [],
        terminal_command_template:
          "printf '%s\\n' '<paste prompt here>' | codex exec --color never --sandbox read-only",
        availability_status: "available",
        detail: "ready",
      },
      claude_code: {
        assistant: "claude_code",
        label: "Claude Code",
        command: "claude",
        args: [],
        terminal_command_template: "claude",
        availability_status: "available",
        detail: "ready",
      },
    },
  };
}

function buildMockBuilderStatus() {
  return {
    version: "BuilderStatusV1",
    allowlisted_root: path.join(repoRoot, "..", "moradin_tmp_runs"),
    existing_project_mode_enabled: true,
    known_repos: [
      {
        name: "seeded-analytics-portal",
        path: path.join(repoRoot, "..", "moradin_tmp_runs", "seeded-analytics-portal"),
        git_initialized: true,
      },
    ],
    recent_operations: [],
  };
}

const mockBuilderProviders = {
  version: "BuilderProviderListV1",
  providers: [
    {
      provider_id: "none",
      label: "Deterministic Local",
      capabilities: ["deterministic_fallback"],
      availability_status: "available",
      detail: "ok",
      default_model: "deterministic-v1",
    },
  ],
};

const mockAssistantRuns = {
  version: "AssistantRunsListV1",
  runs: [],
};

async function ensureBrowserReady() {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
  } catch (error) {
    throw new Error(
      `Playwright Chromium is not ready. Run 'make ui-playwright-mcp-doctor' first. ${error instanceof Error ? error.message : String(error)}`,
    );
  } finally {
    await browser?.close();
  }
}

function asJson(body) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  };
}

async function main() {
  await ensureBrowserReady();
  await fs.mkdir(outputDir, { recursive: true });

  const snapshot = JSON.parse(await fs.readFile(trackerSnapshotPath, "utf8"));
  const mockStatus = buildMockStatus(port);
  const mockBuilderStatus = buildMockBuilderStatus();

  const server = await createServer({
    root: uiRoot,
    configFile: path.join(uiRoot, "vite.config.ts"),
    logLevel: "error",
    server: {
      host,
      port,
      strictPort: true,
    },
  });

  await server.listen();
  const baseUrl = `http://${host}:${port}`;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    colorScheme: "dark",
    viewport: { width: 1440, height: 960 },
  });

  await context.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes("tracker_snapshot_v1.json")) {
      await route.fulfill(asJson(snapshot));
      return;
    }
    if (url.includes("/api/status")) {
      await route.fulfill(asJson(mockStatus));
      return;
    }
    if (url.includes("/api/git")) {
      await route.fulfill(asJson(snapshot.git ?? {}));
      return;
    }
    if (url.includes("/api/builder/status")) {
      await route.fulfill(asJson(mockBuilderStatus));
      return;
    }
    if (url.includes("/api/builder/providers")) {
      await route.fulfill(asJson(mockBuilderProviders));
      return;
    }
    if (url.includes("/api/assistant/runs")) {
      await route.fulfill(asJson(mockAssistantRuns));
      return;
    }
    await route.continue();
  });

  const captured = [];
  try {
    for (const target of screenshotTargets) {
      const page = await context.newPage();
      await page.addInitScript((state) => {
        localStorage.clear();
        if (state.pinnedProject) {
          localStorage.setItem("mh_overview_active_project_v1", state.pinnedProject);
        }
      }, target.localState);
      await page.goto(`${baseUrl}${target.path}`, { waitUntil: "networkidle" });
      await target.waitFor(page);
      const filePath = path.join(outputDir, target.fileName);
      await page.screenshot({ path: filePath, fullPage: fullPageCapture });
      captured.push({
        route: target.path,
        file_name: target.fileName,
        absolute_path: filePath,
      });
      await page.close();
    }
  } finally {
    await context.close();
    await browser.close();
    await server.close();
  }

  const summary = {
    generated_at: new Date().toISOString(),
    host,
    port,
    output_dir: outputDir,
    screenshots: captured,
  };

  const summaryMarkdown = [
    "# Cycle 041 UI Review Screenshots",
    "",
    `- Generated: ${summary.generated_at}`,
    `- Host: ${host}`,
    `- Port: ${port}`,
    `- Output directory: ${outputDir}`,
    "",
    "## Captured Routes",
    "",
    ...captured.map((item) => `- ${item.route}: ${item.absolute_path}`),
    "",
    "## Notes",
    "",
    "- This capture is deterministic and mock-backed.",
    "- It is intended for local evaluator review, not CI truth or downstream artifacts.",
  ].join("\n");

  await fs.writeFile(path.join(outputDir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`, "utf8");
  await fs.writeFile(path.join(outputDir, "summary.md"), `${summaryMarkdown}\n`, "utf8");

  process.stdout.write(`${outputDir}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
