import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const uiRoot = path.resolve(__dirname, "..");
export const repoRoot = path.resolve(uiRoot, "..", "..");
export const DEFAULT_UI_PORT = 5273;
export const FIXED_API_PORT = 8787;
export const DEFAULT_CONFIG_PATH = path.join(repoRoot, "harness_devops.toml");
export const DEFAULT_RUNTIME_FILE = path.join(repoRoot, ".harness_devops", "runtime.json");

export function resolveLauncherConfigPath(env = process.env) {
  return path.resolve(env.HARNESS_DEVOPS_CONFIG_PATH ?? DEFAULT_CONFIG_PATH);
}

export function resolveRuntimeFilePath(env = process.env) {
  return path.resolve(env.HARNESS_DEVOPS_RUNTIME_PATH ?? DEFAULT_RUNTIME_FILE);
}

export function isWslRuntime(
  env = process.env,
  platform = process.platform,
  release = os.release(),
) {
  if (platform !== "linux") {
    return false;
  }
  if (env.WSL_DISTRO_NAME || env.WSL_INTEROP) {
    return true;
  }
  return release.toLowerCase().includes("microsoft");
}

export function detectWslIpv4(
  env = process.env,
  platform = process.platform,
  release = os.release(),
  interfaces = os.networkInterfaces(),
) {
  if (!isWslRuntime(env, platform, release)) {
    return "";
  }

  for (const networkEntries of Object.values(interfaces)) {
    for (const entry of networkEntries ?? []) {
      const family = typeof entry.family === "string" ? entry.family : entry.family === 4 ? "IPv4" : "";
      if (family !== "IPv4" || entry.internal || entry.address === "127.0.0.1") {
        continue;
      }
      return entry.address;
    }
  }

  return "";
}

export function resolveUiHost(
  configuredHost = "",
  env = process.env,
  platform = process.platform,
  release = os.release(),
) {
  const normalized = String(configuredHost ?? "").trim();
  if (normalized && normalized.toLowerCase() !== "auto") {
    return normalized;
  }
  return isWslRuntime(env, platform, release) ? "0.0.0.0" : "127.0.0.1";
}

export function isLoopbackBindHost(host) {
  const normalized = String(host ?? "").trim().toLowerCase();
  return normalized === "127.0.0.1" || normalized === "localhost" || normalized === "::1" || normalized === "[::1]";
}

export function isValidPort(value) {
  return Number.isInteger(value) && value >= 1 && value <= 65535;
}

export function parsePort(value, fallback = null) {
  const normalized = Number.parseInt(String(value ?? "").trim(), 10);
  return isValidPort(normalized) ? normalized : fallback;
}

export async function readLauncherConfig(configPath = resolveLauncherConfigPath()) {
  const result = {
    configPath,
    exists: false,
    launcher: {
      ui_port: null,
      ui_host: "auto",
      api_port: FIXED_API_PORT,
    },
    errors: [],
  };

  let raw;
  try {
    raw = await fs.readFile(configPath, "utf8");
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return result;
    }
    throw error;
  }

  result.exists = true;

  let section = "";
  for (const rawLine of raw.split(/\r?\n/u)) {
    const trimmed = rawLine.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const sectionMatch = trimmed.match(/^\[([A-Za-z0-9_-]+)\]$/u);
    if (sectionMatch) {
      section = sectionMatch[1];
      continue;
    }

    if (section !== "launcher") {
      continue;
    }

    const entryMatch = trimmed.match(/^([A-Za-z0-9_]+)\s*=\s*(.+)$/u);
    if (!entryMatch) {
      result.errors.push(`invalid launcher entry: ${trimmed}`);
      continue;
    }

    const [, key, rawValue] = entryMatch;
    if (key === "ui_port" || key === "api_port") {
      const parsed = parsePort(rawValue, null);
      if (parsed === null) {
        result.errors.push(`launcher.${key} must be an integer 1-65535`);
        continue;
      }
      result.launcher[key] = parsed;
      continue;
    }

    if (key === "ui_host") {
      const stringMatch = rawValue.match(/^"(.*)"$/u);
      if (!stringMatch) {
        result.errors.push('launcher.ui_host must be a quoted string, for example "auto"');
        continue;
      }
      result.launcher.ui_host = stringMatch[1].trim() || "auto";
      continue;
    }

    result.errors.push(`unsupported launcher key: ${key}`);
  }

  if (result.launcher.api_port !== FIXED_API_PORT) {
    result.errors.push(
      `launcher.api_port must remain ${FIXED_API_PORT} for the current-scope release; use the fixed control API port policy`,
    );
  }

  return result;
}

export async function ensureRuntimeDir(runtimeFilePath = resolveRuntimeFilePath()) {
  await fs.mkdir(path.dirname(runtimeFilePath), { recursive: true });
}

export async function readRuntimeState(runtimeFilePath = resolveRuntimeFilePath()) {
  try {
    const raw = await fs.readFile(runtimeFilePath, "utf8");
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? parsed : null;
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return null;
    }
    return null;
  }
}

export async function writeRuntimeState(runtimeState, runtimeFilePath = resolveRuntimeFilePath()) {
  await ensureRuntimeDir(runtimeFilePath);
  await fs.writeFile(runtimeFilePath, `${JSON.stringify(runtimeState, null, 2)}\n`, "utf8");
}

export async function removeRuntimeState(runtimeFilePath = resolveRuntimeFilePath()) {
  await fs.rm(runtimeFilePath, { force: true });
}

export function isPidAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) {
    return false;
  }

  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (error && typeof error === "object" && "code" in error) {
      return error.code === "EPERM";
    }
    return false;
  }
}

export function commandLineForPid(pid) {
  if (!Number.isInteger(pid) || pid <= 0) {
    return "";
  }

  try {
    return execFileSync("ps", ["-p", String(pid), "-o", "args="], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

export function lookupListeningProcess(port) {
  const fromSs = lookupWithSs(port);
  if (fromSs.inUse) {
    return fromSs;
  }
  return lookupWithLsof(port);
}

function lookupWithSs(port) {
  try {
    const output = execFileSync("ss", ["-ltnpH"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });

    for (const line of output.split(/\r?\n/u)) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      const parts = trimmed.split(/\s+/u);
      const localAddress = parts[3] ?? "";
      if (!matchesPort(localAddress, port)) {
        continue;
      }
      const processInfo = parts.slice(5).join(" ");
      const pidMatch = processInfo.match(/pid=(\d+)/u);
      const commandMatch = processInfo.match(/users:\(\("([^"]+)"/u);
      const pid = pidMatch ? Number.parseInt(pidMatch[1], 10) : null;
      const command = commandMatch?.[1] ?? (pid ? commandLineForPid(pid) : "");

      return {
        port,
        inUse: true,
        pid,
        command,
        address: localAddress,
        source: "ss",
      };
    }
  } catch {
    return {
      port,
      inUse: false,
      pid: null,
      command: "",
      address: "",
      source: "ss",
    };
  }

  return {
    port,
    inUse: false,
    pid: null,
    command: "",
    address: "",
    source: "ss",
  };
}

function lookupWithLsof(port) {
  try {
    const output = execFileSync("lsof", ["-nP", `-iTCP:${port}`, "-sTCP:LISTEN"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    const lines = output.split(/\r?\n/u).filter(Boolean);
    if (lines.length < 2) {
      throw new Error("no listener");
    }

    const parts = lines[1].trim().split(/\s+/u);
    const command = parts[0] ?? "";
    const pid = parts[1] ? Number.parseInt(parts[1], 10) : null;
    const address = parts.at(-2) ?? "";

    return {
      port,
      inUse: true,
      pid,
      command,
      address,
      source: "lsof",
    };
  } catch {
    return {
      port,
      inUse: false,
      pid: null,
      command: "",
      address: "",
      source: "lsof",
    };
  }
}

function matchesPort(localAddress, port) {
  const normalized = String(localAddress ?? "").trim();
  return normalized.endsWith(`:${port}`) || normalized === `*:${port}` || normalized === `[::]:${port}`;
}

export async function probeHarnessApi(apiPort, timeoutMs = 800) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`http://127.0.0.1:${apiPort}/api/status`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return {
        reachable: true,
        sameHarness: false,
        payload: null,
      };
    }
    const payload = await response.json();
    return {
      reachable: true,
      sameHarness: payload?.api === "TrackerControlStatusV1",
      payload,
    };
  } catch {
    return {
      reachable: false,
      sameHarness: false,
      payload: null,
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function inspectHarnessRuntime({
  uiPort,
  apiPort = FIXED_API_PORT,
  runtimeFilePath = resolveRuntimeFilePath(),
}) {
  const runtimeState = await readRuntimeState(runtimeFilePath);
  const runtimePids = collectRuntimePids(runtimeState);
  const liveRuntimePids = runtimePids.filter((pid) => isPidAlive(pid));
  const runtimeManaged = liveRuntimePids.length > 0 && runtimeState?.repo_root === repoRoot;
  const staleRuntime = Boolean(runtimeState) && !runtimeManaged;
  const apiProcess = lookupListeningProcess(apiPort);
  const uiProcess = lookupListeningProcess(uiPort);
  const apiProbe = await probeHarnessApi(apiPort);
  const managedUiPort = runtimeManaged
    ? Number.parseInt(String(runtimeState?.ui_port ?? ""), 10)
    : Number.parseInt(String(apiProbe.payload?.ui_access?.ui_port ?? ""), 10);
  const normalizedManagedUiPort = Number.isInteger(managedUiPort) ? managedUiPort : null;
  const sameHarnessApi = apiProcess.inUse && (runtimeManaged || apiProbe.sameHarness);
  const sameHarnessUi = uiProcess.inUse && normalizedManagedUiPort === uiPort && (runtimeManaged || sameHarnessApi);
  const sameHarnessInstance = sameHarnessApi || sameHarnessUi || runtimeManaged;
  const foreignApiConflict = apiProcess.inUse && !sameHarnessApi;
  const foreignUiConflict = uiProcess.inUse && !sameHarnessUi;
  const candidatePids = new Set(liveRuntimePids);

  if (sameHarnessApi && Number.isInteger(apiProcess.pid) && apiProcess.pid > 0) {
    candidatePids.add(apiProcess.pid);
  }
  if (sameHarnessUi && Number.isInteger(uiProcess.pid) && uiProcess.pid > 0) {
    candidatePids.add(uiProcess.pid);
  }

  return {
    runtimeFilePath,
    runtimeState,
    runtimeManaged,
    staleRuntime,
    sameHarnessInstance,
    sameHarnessApi,
    sameHarnessUi,
    foreignApiConflict,
    foreignUiConflict,
    apiProcess,
    uiProcess,
    apiProbe,
    managedUiPort: normalizedManagedUiPort,
    managedPids: Array.from(candidatePids.values()).sort((left, right) => left - right),
  };
}

function collectRuntimePids(runtimeState) {
  if (!runtimeState || typeof runtimeState !== "object") {
    return [];
  }
  return [
    runtimeState.supervisor_pid,
    runtimeState.control_api_pid,
    runtimeState.watch_docs_pid,
    runtimeState.vite_pid,
  ]
    .map((value) => Number.parseInt(String(value ?? ""), 10))
    .filter((value) => Number.isInteger(value) && value > 0);
}

export async function stopHarnessProcesses(pids, timeoutMs = 5000) {
  const uniquePids = Array.from(
    new Set(
      pids
        .map((value) => Number.parseInt(String(value ?? ""), 10))
        .filter((value) => Number.isInteger(value) && value > 0),
    ),
  );

  if (uniquePids.length === 0) {
    return [];
  }

  for (const pid of uniquePids) {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // Ignore dead or inaccessible processes here; exit polling handles the rest.
    }
  }

  const stillAliveAfterTerm = await waitForPidsToExit(uniquePids, timeoutMs);
  for (const pid of stillAliveAfterTerm) {
    try {
      process.kill(pid, "SIGKILL");
    } catch {
      // Ignore dead or inaccessible processes here.
    }
  }

  return waitForPidsToExit(stillAliveAfterTerm, 1500);
}

async function waitForPidsToExit(pids, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const survivors = pids.filter((pid) => isPidAlive(pid));
    if (survivors.length === 0) {
      return [];
    }
    await delay(100);
  }
  return pids.filter((pid) => isPidAlive(pid));
}

export async function waitForPortsToClear(ports, timeoutMs = 4000) {
  const uniquePorts = Array.from(new Set(ports.filter((port) => isValidPort(port))));
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const busyPorts = uniquePorts.filter((port) => lookupListeningProcess(port).inUse);
    if (busyPorts.length === 0) {
      return [];
    }
    await delay(100);
  }
  return uniquePorts.filter((port) => lookupListeningProcess(port).inUse);
}

export function buildExistingHarnessMessage(inspection, uiPort, apiPort = FIXED_API_PORT) {
  const currentUiPort = inspection.managedUiPort ?? uiPort;
  const lines = [`Existing Moradins Harness instance detected on UI/API ports.`];
  if (inspection.sameHarnessApi) {
    lines.push(`- control API: http://127.0.0.1:${apiPort}/`);
  }
  lines.push(`- requested UI port: ${uiPort}`);
  if (currentUiPort !== uiPort) {
    lines.push(`- existing harness UI port: ${currentUiPort}`);
  }
  lines.push(`- managed instance: ${inspection.runtimeManaged ? "yes" : "no"}`);
  return lines.join("\n");
}

export function buildForeignPortConflictMessage(label, inspectionResult) {
  const processLabel = inspectionResult.command ? `${inspectionResult.command}` : "unknown process";
  const pidLabel = Number.isInteger(inspectionResult.pid) ? `pid ${inspectionResult.pid}` : "pid unavailable";
  return [
    `${label} port ${inspectionResult.port} is already in use.`,
    `- owner: ${processLabel} (${pidLabel})`,
    inspectionResult.address ? `- listener: ${inspectionResult.address}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export function createSupervisorRuntimeState({
  supervisorPid,
  controlApiPid,
  watchDocsPid,
  vitePid,
  uiPort,
  apiPort = FIXED_API_PORT,
  bindHost,
}) {
  return {
    version: "HarnessDevopsRuntimeV1",
    supervisor_pid: supervisorPid,
    control_api_pid: controlApiPid,
    watch_docs_pid: watchDocsPid,
    vite_pid: vitePid,
    ui_port: uiPort,
    api_port: apiPort,
    bind_host: bindHost,
    started_at: new Date().toISOString(),
    repo_root: repoRoot,
  };
}

export function isInteractiveTerminal(stdin = process.stdin, stdout = process.stdout) {
  return Boolean(stdin?.isTTY && stdout?.isTTY);
}

export async function promptYesNo(message, stdin = process.stdin, stdout = process.stdout) {
  stdout.write(`${message} `);
  stdin.setEncoding("utf8");
  stdin.resume();

  return new Promise((resolve) => {
    stdin.once("data", (chunk) => {
      stdin.pause();
      const normalized = String(chunk ?? "").trim().toLowerCase();
      resolve(normalized === "y" || normalized === "yes");
    });
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function waitForHttpOk(url, timeoutMs = 8000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await httpGet(url, 800);
      if (response.statusCode === 200) {
        return true;
      }
    } catch {
      // Retry until timeout.
    }
    await delay(150);
  }
  return false;
}

function httpGet(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, { timeout: timeoutMs }, (response) => {
      response.resume();
      resolve(response);
    });
    request.on("timeout", () => {
      request.destroy(new Error(`timeout after ${timeoutMs}ms`));
    });
    request.on("error", reject);
  });
}
