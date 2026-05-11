import { spawn } from "node:child_process";

import {
  buildExistingHarnessMessage,
  buildForeignPortConflictMessage,
  DEFAULT_UI_PORT,
  FIXED_API_PORT,
  inspectHarnessRuntime,
  isInteractiveTerminal,
  isValidPort,
  isWslRuntime,
  promptYesNo,
  readLauncherConfig,
  removeRuntimeState,
  repoRoot,
  resolveLauncherConfigPath,
  resolveRuntimeFilePath,
  resolveUiHost,
  stopHarnessProcesses,
  waitForPortsToClear,
} from "./devops-runtime.mjs";

const args = process.argv.slice(2);

const options = parseArgs(args);
if (options.help) {
  printHelp();
  process.exit(0);
}

const configPath = resolveLauncherConfigPath();
const runtimeFilePath = resolveRuntimeFilePath();
const config = await readLauncherConfig(configPath);
if (config.errors.length > 0) {
  for (const error of config.errors) {
    process.stderr.write(`error: ${error}\n`);
  }
  process.exit(1);
}

const envUiPort = Number.parseInt(String(process.env.TRACKER_UI_PORT ?? "").trim(), 10);
const uiPort = [options.uiPort, isValidPort(envUiPort) ? envUiPort : null, config.launcher.ui_port, DEFAULT_UI_PORT].find(
  (value) => isValidPort(value),
);
const envApiPortRaw = String(process.env.TRACKER_API_PORT ?? "").trim();
const envApiPort = envApiPortRaw ? Number.parseInt(envApiPortRaw, 10) : FIXED_API_PORT;
const apiPort = isValidPort(envApiPort) ? envApiPort : FIXED_API_PORT;
if (apiPort !== FIXED_API_PORT) {
  process.stderr.write(`error: TRACKER_API_PORT must remain ${FIXED_API_PORT} for the current-scope release\n`);
  process.exit(1);
}

const uiHost = resolveUiHost(process.env.TRACKER_UI_HOST ?? config.launcher.ui_host);
process.env.TRACKER_UI_PORT = String(uiPort);
process.env.TRACKER_API_PORT = String(apiPort);
process.env.TRACKER_UI_HOST = uiHost;
process.env.HARNESS_DEVOPS_CONFIG_PATH = configPath;
process.env.HARNESS_DEVOPS_RUNTIME_PATH = runtimeFilePath;

printSummary({
  uiPort,
  apiPort,
  config,
});

if (options.dryRun) {
  process.exit(0);
}

const inspection = await inspectHarnessRuntime({
  uiPort,
  apiPort,
  runtimeFilePath,
});

if (inspection.staleRuntime) {
  await removeRuntimeState(runtimeFilePath);
}

if (inspection.foreignApiConflict) {
  process.stderr.write(`${buildForeignPortConflictMessage("API", inspection.apiProcess)}\n`);
  process.stderr.write("Free port 8787 or stop the other service before launching Moradins Harness.\n");
  process.exit(1);
}

if (inspection.foreignUiConflict) {
  process.stderr.write(`${buildForeignPortConflictMessage("UI", inspection.uiProcess)}\n`);
  process.stderr.write(`Choose a different --port or stop the other process before launching Moradins Harness.\n`);
  process.exit(1);
}

if (inspection.sameHarnessInstance) {
  process.stdout.write(`${buildExistingHarnessMessage(inspection, uiPort, apiPort)}\n`);

  let shouldRestart = options.restartExisting;
  if (!shouldRestart) {
    if (!isInteractiveTerminal()) {
      process.stderr.write("Existing Moradins Harness instance detected. Rerun with --restart-existing.\n");
      process.exit(1);
    }
    shouldRestart = await promptYesNo("Existing Moradins Harness instance detected on UI/API ports. Restart it now? [y/N]");
  }

  if (!shouldRestart) {
    process.stderr.write("Launch cancelled. Rerun with --restart-existing when you are ready to replace the existing instance.\n");
    process.exit(1);
  }

  const survivors = await stopHarnessProcesses(inspection.managedPids);
  const busyPorts = await waitForPortsToClear([uiPort, apiPort]);
  await removeRuntimeState(runtimeFilePath);

  if (survivors.length > 0 || busyPorts.length > 0) {
    process.stderr.write("Failed to stop the existing Moradins Harness instance cleanly.\n");
    if (survivors.length > 0) {
      process.stderr.write(`- remaining pids: ${survivors.join(", ")}\n`);
    }
    if (busyPorts.length > 0) {
      process.stderr.write(`- busy ports: ${busyPorts.join(", ")}\n`);
    }
    process.exit(1);
  }
}

const child = spawn(process.platform === "win32" ? "npm.cmd" : "npm", ["--prefix", "dev_tracker/ui", "run", "dev:ops"], {
  cwd: repoRoot,
  env: process.env,
  stdio: "inherit",
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});

child.on("error", (error) => {
  process.stderr.write(`error: failed to start dev:ops: ${String(error)}\n`);
  process.exit(1);
});

function printHelp() {
  process.stdout.write(
    [
      "Usage: ./harness_devops.sh [--port <1-65535>] [--dry-run] [--restart-existing] [--help]",
      "",
      "Options:",
      "  --port <n>           Set TRACKER_UI_PORT for the local tracker UI.",
      "  --dry-run            Print resolved environment and command without launching.",
      "  --restart-existing   Restart an already-running Moradins Harness instance.",
      "  --help               Show this help text.",
      "",
      "Config:",
      "  Root config file: harness_devops.toml",
      `  Control API port is fixed at ${FIXED_API_PORT} for the current-scope release.`,
      "",
    ].join("\n"),
  );
}

function parseArgs(rawArgs) {
  const result = {
    help: false,
    dryRun: false,
    restartExisting: false,
    uiPort: null,
  };

  for (let index = 0; index < rawArgs.length; index += 1) {
    const value = rawArgs[index];
    if (value === "--help" || value === "-h") {
      result.help = true;
      continue;
    }
    if (value === "--dry-run") {
      result.dryRun = true;
      continue;
    }
    if (value === "--restart-existing") {
      result.restartExisting = true;
      continue;
    }
    if (value === "--port") {
      const next = rawArgs[index + 1];
      if (!next) {
        process.stderr.write("error: --port requires a value\n");
        process.exit(1);
      }
      const parsed = Number.parseInt(String(next).trim(), 10);
      if (!isValidPort(parsed)) {
        process.stderr.write(`error: invalid port '${next}' (expected integer 1-65535)\n`);
        process.exit(1);
      }
      result.uiPort = parsed;
      index += 1;
      continue;
    }

    process.stderr.write(`error: unknown argument '${value}'\n`);
    printHelp();
    process.exit(1);
  }

  return result;
}

function printSummary({ uiPort, apiPort, config }) {
  process.stdout.write(`[harness_devops] UI port: ${uiPort}\n`);
  process.stdout.write(`[harness_devops] UI URL: http://localhost:${uiPort}/\n`);
  process.stdout.write(`[harness_devops] API URL: http://127.0.0.1:${apiPort}/\n`);
  if (config.exists) {
    process.stdout.write(`[harness_devops] Config: ${config.configPath}\n`);
  }
  if (isWslRuntime()) {
    process.stdout.write(
      `[harness_devops] WSL browser access: use http://localhost:${uiPort}/ or the WSL IPv4 address.\n`,
    );
  } else {
    process.stdout.write(`[harness_devops] Remote SSH tunnel: ssh -L ${uiPort}:127.0.0.1:${uiPort} <linux-host>\n`);
    process.stdout.write("[harness_devops] Release policy: keep remote hosts loopback-only and use SSH local port forwarding.\n");
  }
  process.stdout.write("[harness_devops] Command: npm --prefix dev_tracker/ui run dev:ops\n");
}
