#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(scriptDir, "..");
const codexConfigPath = path.join(os.homedir(), ".codex", "config.toml");
const requireMcp = process.argv.includes("--require-mcp");

function pass(label, detail) {
  process.stdout.write(`PASS ${label}: ${detail}\n`);
}

function warn(label, detail) {
  process.stdout.write(`WARN ${label}: ${detail}\n`);
}

function fail(label, detail) {
  process.stderr.write(`FAIL ${label}: ${detail}\n`);
}

function commandAvailable(command, args = ["--version"]) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  return result.status === 0;
}

async function browserReady() {
  const browser = await chromium.launch({ headless: true });
  await browser.close();
}

async function main() {
  let failed = false;

  if (commandAvailable("codex")) {
    pass("codex_cli", "codex is available on PATH");
  } else {
    warn("codex_cli", "codex is not available; Playwright MCP bootstrap cannot run on this host");
  }

  if (commandAvailable("npx")) {
    pass("npx", "npx is available for @playwright/mcp bootstrap");
  } else {
    failed = true;
    fail("npx", "npx is required for browser tooling and Playwright MCP bootstrap");
  }

  if (fs.existsSync(path.join(uiRoot, "node_modules", "playwright"))) {
    pass("repo_playwright_package", "playwright is installed in dev_tracker/ui/node_modules");
  } else {
    failed = true;
    fail("repo_playwright_package", "install UI dependencies before running browser tooling");
  }

  try {
    await browserReady();
    pass("browser_readiness", "chromium launches successfully for repo-local browser checks");
  } catch (error) {
    failed = true;
    fail(
      "browser_readiness",
      `chromium launch failed. Run 'npx playwright install chromium' in dev_tracker/ui. ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
  }

  let mcpConfigured = false;
  if (commandAvailable("codex", ["mcp", "get", "playwright"])) {
    mcpConfigured = true;
  } else if (fs.existsSync(codexConfigPath)) {
    const config = fs.readFileSync(codexConfigPath, "utf8");
    mcpConfigured = config.includes("[mcp_servers.playwright]");
  }

  if (mcpConfigured) {
    pass("mcp_readiness", "playwright MCP entry is present");
  } else if (requireMcp) {
    failed = true;
    fail(
      "mcp_readiness",
      "playwright MCP is not configured. Run dev_tracker/ui/scripts/bootstrap-playwright-mcp.sh first.",
    );
  } else {
    warn(
      "mcp_readiness",
      "playwright MCP is optional and not configured. Ordinary browser tests still work without it.",
    );
  }

  pass("repo_native_browser_checks", "use 'make ui-test-browser' and 'make ui-review-screenshots' for deterministic repo-local UI validation");

  if (failed) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
