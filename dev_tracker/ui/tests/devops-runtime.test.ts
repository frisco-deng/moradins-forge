/* @vitest-environment node */

import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { FIXED_API_PORT, inspectHarnessRuntime, readLauncherConfig, repoRoot } from "../scripts/devops-runtime.mjs";

const cleanupTasks: Array<() => Promise<void>> = [];

afterEach(async () => {
  while (cleanupTasks.length > 0) {
    const task = cleanupTasks.pop();
    if (task) {
      await task();
    }
  }
});

describe("devops runtime helpers", () => {
  it("parses the supported launcher config keys", async () => {
    const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "mh-devops-config-"));
    const configPath = path.join(tempDir, "harness_devops.toml");
    cleanupTasks.push(() => fs.rm(tempDir, { recursive: true, force: true }));
    await fs.writeFile(
      configPath,
      ['[launcher]', 'ui_port = 6124', 'ui_host = "0.0.0.0"', `api_port = ${FIXED_API_PORT}`, ""].join("\n"),
      "utf8",
    );

    const config = await readLauncherConfig(configPath);

    expect(config.exists).toBe(true);
    expect(config.errors).toEqual([]);
    expect(config.launcher.ui_port).toBe(6124);
    expect(config.launcher.ui_host).toBe("0.0.0.0");
    expect(config.launcher.api_port).toBe(FIXED_API_PORT);
  });

  it("rejects non-release API port values in the launcher config", async () => {
    const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "mh-devops-config-invalid-"));
    const configPath = path.join(tempDir, "harness_devops.toml");
    cleanupTasks.push(() => fs.rm(tempDir, { recursive: true, force: true }));
    await fs.writeFile(
      configPath,
      ['[launcher]', 'ui_port = 6124', 'ui_host = "auto"', "api_port = 9000", ""].join("\n"),
      "utf8",
    );

    const config = await readLauncherConfig(configPath);

    expect(config.errors).toContain(
      `launcher.api_port must remain ${FIXED_API_PORT} for the current-scope release; use the fixed control API port policy`,
    );
  });

  it("treats a foreign UI listener as a conflict even when the harness API is already running", async () => {
    const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "mh-devops-runtime-"));
    const runtimeFilePath = path.join(tempDir, "runtime.json");
    cleanupTasks.push(() => fs.rm(tempDir, { recursive: true, force: true }));

    const apiServer = await startServer((req, res) => {
      if (req.url === "/api/status") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            api: "TrackerControlStatusV1",
            ui_access: {
              ui_port: 6124,
            },
          }),
        );
        return;
      }
      res.writeHead(404);
      res.end();
    });
    cleanupTasks.push(() => closeServer(apiServer));

    const uiServer = await startServer((_, res) => {
      res.writeHead(200, { "Content-Type": "text/plain" });
      res.end("ui");
    });
    cleanupTasks.push(() => closeServer(uiServer));

    const apiPort = portForServer(apiServer);
    const uiPort = portForServer(uiServer);

    const inspection = await inspectHarnessRuntime({
      uiPort,
      apiPort,
      runtimeFilePath,
    });

    expect(inspection.sameHarnessApi).toBe(true);
    expect(inspection.sameHarnessUi).toBe(false);
    expect(inspection.sameHarnessInstance).toBe(true);
    expect(inspection.foreignApiConflict).toBe(false);
    expect(inspection.foreignUiConflict).toBe(true);
    expect(inspection.managedUiPort).toBe(6124);
  });

  it("marks runtime state as stale when the recorded pids are no longer alive", async () => {
    const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "mh-devops-runtime-stale-"));
    const runtimeFilePath = path.join(tempDir, "runtime.json");
    cleanupTasks.push(() => fs.rm(tempDir, { recursive: true, force: true }));
    const staleApiPort = await reserveUnusedPort();
    const staleUiPort = await reserveUnusedPort();

    await fs.writeFile(
      runtimeFilePath,
      JSON.stringify(
        {
          version: "HarnessDevopsRuntimeV1",
          supervisor_pid: 999_999,
          control_api_pid: 999_998,
          watch_docs_pid: 999_997,
          vite_pid: 999_996,
          ui_port: staleUiPort,
          api_port: staleApiPort,
          bind_host: "127.0.0.1",
          started_at: new Date().toISOString(),
          repo_root: repoRoot,
        },
        null,
        2,
      ),
      "utf8",
    );

    const inspection = await inspectHarnessRuntime({
      uiPort: staleUiPort,
      apiPort: staleApiPort,
      runtimeFilePath,
    });

    expect(inspection.runtimeManaged).toBe(false);
    expect(inspection.staleRuntime).toBe(true);
    expect(inspection.sameHarnessInstance).toBe(false);
  });
});

function startServer(handler: http.RequestListener): Promise<http.Server> {
  return new Promise((resolve, reject) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
    server.on("error", reject);
  });
}

function closeServer(server: http.Server): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}

function portForServer(server: http.Server): number {
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("server address unavailable");
  }
  return address.port;
}

async function reserveUnusedPort(): Promise<number> {
  const server = await startServer((_, res) => {
    res.writeHead(204);
    res.end();
  });
  const port = portForServer(server);
  await closeServer(server);
  return port;
}
