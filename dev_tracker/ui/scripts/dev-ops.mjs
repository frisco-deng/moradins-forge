import { spawn } from "node:child_process";
import path from "node:path";

import {
  buildExistingHarnessMessage,
  buildForeignPortConflictMessage,
  createSupervisorRuntimeState,
  detectWslIpv4,
  FIXED_API_PORT,
  inspectHarnessRuntime,
  isLoopbackBindHost,
  isWslRuntime,
  removeRuntimeState,
  resolveRuntimeFilePath,
  resolveUiHost,
  stopHarnessProcesses,
  uiRoot,
  waitForPortsToClear,
  writeRuntimeState,
} from "./devops-runtime.mjs";

const uiPort = Number.parseInt(String(process.env.TRACKER_UI_PORT ?? "5273"), 10);
const apiPort = Number.parseInt(String(process.env.TRACKER_API_PORT ?? FIXED_API_PORT), 10);
const uiHost = resolveUiHost(process.env.TRACKER_UI_HOST ?? "");
const wslIpv4 = detectWslIpv4();
const runtimeFilePath = resolveRuntimeFilePath();
const startupLines = [
  "[dev:ops] starting Moradin Forge Workbench",
  `[dev:ops] UI bind host: ${uiHost}`,
  `[dev:ops] UI primary: http://localhost:${uiPort}/`,
  `[dev:ops] UI secondary: http://127.0.0.1:${uiPort}/`,
];

if (wslIpv4) {
  startupLines.push(`[dev:ops] UI WSL IPv4: http://${wslIpv4}:${uiPort}/`);
}
if (isWslRuntime()) {
  startupLines.push("[dev:ops] WSL browser access: use localhost or the WSL IPv4 address from Windows.");
  startupLines.push("[dev:ops] note: 10.255.255.254 is a WSL loopback alias and not a primary browser target.");
} else {
  startupLines.push(`[dev:ops] remote SSH tunnel: ssh -L ${uiPort}:127.0.0.1:${uiPort} <linux-host>`);
  startupLines.push("[dev:ops] release policy: keep remote hosts loopback-only and use SSH local port forwarding.");
  if (!isLoopbackBindHost(uiHost)) {
    startupLines.push(`[dev:ops] warning: UI bind host '${uiHost}' is outside current-scope release support for remote Linux usage.`);
  }
}
startupLines.push(`[dev:ops] Control API: http://127.0.0.1:${apiPort}/`);
process.stdout.write(`${startupLines.join("\n")}\n`);

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
  process.stderr.write("[dev:ops] stop the other service on 127.0.0.1:8787 before launching dev:ops.\n");
  process.exit(1);
}

if (inspection.foreignUiConflict) {
  process.stderr.write(`${buildForeignPortConflictMessage("UI", inspection.uiProcess)}\n`);
  process.stderr.write(`[dev:ops] choose a different TRACKER_UI_PORT than ${uiPort} before launching dev:ops.\n`);
  process.exit(1);
}

if (inspection.sameHarnessInstance) {
  process.stderr.write(`${buildExistingHarnessMessage(inspection, uiPort, apiPort)}\n`);
  process.stderr.write("[dev:ops] rerun via ./harness_devops.sh --restart-existing to replace the existing instance.\n");
  process.exit(1);
}

const childSpecs = [
  { name: "control-api", command: process.execPath, args: [path.join(uiRoot, "scripts", "control-api.mjs")] },
  { name: "watch-docs", command: process.execPath, args: [path.join(uiRoot, "scripts", "watch-docs.mjs")] },
  { name: "vite", command: process.platform === "win32" ? "npm.cmd" : "npm", args: ["run", "dev"] },
];

const children = [];
let shutdownPromise = null;
let exitCode = 0;

for (const childSpec of childSpecs) {
  const child = spawn(childSpec.command, childSpec.args, {
    cwd: uiRoot,
    stdio: "inherit",
    env: process.env,
  });

  child.on("exit", (code, signal) => {
    process.stdout.write(
      `[dev:ops] ${childSpec.name} exited with code ${code === null ? "null" : code}${signal ? ` (signal ${signal})` : ""}\n`,
    );
    if (shutdownPromise) {
      return;
    }
    const intentionalShutdown = signal === "SIGTERM" || signal === "SIGINT";
    if (intentionalShutdown) {
      void shutdownAll(`${childSpec.name} stopped`, code ?? 0);
      return;
    }
    if (code === 0) {
      void shutdownAll(`${childSpec.name} exited unexpectedly`, 1);
      return;
    }
    void shutdownAll(`${childSpec.name} failure`, code ?? 1);
  });

  child.on("error", (error) => {
    if (shutdownPromise) {
      return;
    }
    process.stderr.write(`[dev:ops] ${childSpec.name} error: ${String(error)}\n`);
    void shutdownAll(`${childSpec.name} error`, 1);
  });

  children.push({ ...childSpec, handle: child });
}

await removeRuntimeState(runtimeFilePath);
await writeRuntimeState(
  createSupervisorRuntimeState({
    supervisorPid: process.pid,
    controlApiPid: children.find((child) => child.name === "control-api")?.handle.pid ?? null,
    watchDocsPid: children.find((child) => child.name === "watch-docs")?.handle.pid ?? null,
    vitePid: children.find((child) => child.name === "vite")?.handle.pid ?? null,
    uiPort,
    apiPort,
    bindHost: uiHost,
  }),
  runtimeFilePath,
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    void shutdownAll(signal, 0);
  });
}

function shutdownAll(reason, code) {
  if (shutdownPromise) {
    return shutdownPromise;
  }

  exitCode = code;
  process.stdout.write(`[dev:ops] shutting down after ${reason}\n`);

  shutdownPromise = (async () => {
    const pids = children.map((child) => child.handle.pid).filter((pid) => Number.isInteger(pid));
    const survivors = await stopHarnessProcesses(pids, 4000);
    const busyPorts = await waitForPortsToClear([uiPort, apiPort], 3000);
    await removeRuntimeState(runtimeFilePath);

    if (survivors.length > 0) {
      process.stderr.write(`[dev:ops] warning: managed child pids still alive: ${survivors.join(", ")}\n`);
    }
    if (busyPorts.length > 0) {
      process.stderr.write(`[dev:ops] warning: ports still busy after shutdown: ${busyPorts.join(", ")}\n`);
    }

    process.exit(exitCode);
  })();

  return shutdownPromise;
}
