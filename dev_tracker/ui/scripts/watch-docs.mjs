import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(__dirname, "..", "..", "..");

const CHECK_PATHS = [
  path.join(repoRoot, "docs"),
  path.join(repoRoot, "skills"),
  path.join(repoRoot, "AGENTS.md"),
];
const POLL_MS = 2000;
const DEBOUNCE_MS = 1200;

let lastSignature = "";
let debounceTimer = null;
let syncInFlight = false;
let rerunRequested = false;
let pollHandle = null;
let shuttingDown = false;

async function main() {
  await runSync("startup");
  lastSignature = await computeSignature();

  process.stdout.write(`[watch-docs] watching markdown changes every ${POLL_MS}ms\n`);

  pollHandle = setInterval(async () => {
    if (shuttingDown) {
      return;
    }
    try {
      const nextSignature = await computeSignature();
      if (nextSignature !== lastSignature) {
        lastSignature = nextSignature;
        scheduleSync("detected filesystem update");
      }
    } catch (error) {
      process.stderr.write(`[watch-docs] poll error: ${String(error)}\n`);
    }
  }, POLL_MS);
}

function scheduleSync(reason) {
  if (shuttingDown) {
    return;
  }
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }

  debounceTimer = setTimeout(() => {
    runSync(reason).catch((error) => {
      process.stderr.write(`[watch-docs] sync error: ${String(error)}\n`);
    });
  }, DEBOUNCE_MS);
}

async function runSync(reason) {
  if (shuttingDown) {
    return;
  }
  if (syncInFlight) {
    rerunRequested = true;
    return;
  }

  syncInFlight = true;
  process.stdout.write(`[watch-docs] sync start (${reason})\n`);
  await runNodeScript(path.join(uiRoot, "scripts", "sync-docs.mjs"));
  syncInFlight = false;
  process.stdout.write("[watch-docs] sync complete\n");

  if (rerunRequested) {
    rerunRequested = false;
    await runSync("coalesced follow-up");
  }
}

function runNodeScript(scriptPath) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [scriptPath], {
      stdio: "inherit",
      env: process.env,
    });

    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`script failed with exit code ${code}`));
      }
    });

    child.on("error", reject);
  });
}

async function computeSignature() {
  const files = [];

  for (const target of CHECK_PATHS) {
    await walkFiles(target, files);
  }

  files.sort((a, b) => a.path.localeCompare(b.path));
  return files.map((item) => `${item.path}:${item.mtimeMs}:${item.size}`).join("|");
}

async function walkFiles(targetPath, files) {
  const stat = await fs.stat(targetPath);
  if (stat.isFile()) {
    if (targetPath.endsWith(".md")) {
      files.push({ path: targetPath, mtimeMs: stat.mtimeMs, size: stat.size });
    }
    return;
  }

  const entries = await fs.readdir(targetPath, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(targetPath, entry.name);
    if (entry.isDirectory()) {
      await walkFiles(fullPath, files);
      continue;
    }

    if (!entry.isFile() || !entry.name.endsWith(".md")) {
      continue;
    }

    const entryStat = await fs.stat(fullPath);
    files.push({ path: fullPath, mtimeMs: entryStat.mtimeMs, size: entryStat.size });
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    shuttingDown = true;
    if (pollHandle) {
      clearInterval(pollHandle);
    }
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    process.stdout.write(`[watch-docs] shutting down (${signal})\n`);
    process.exit(0);
  });
}

main().catch((error) => {
  process.stderr.write(`[watch-docs] fatal: ${String(error.stack || error)}\n`);
  process.exitCode = 1;
});
