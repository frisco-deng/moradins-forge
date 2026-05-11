import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(__dirname, "..", "..", "..");
const generatedRoot = path.join(uiRoot, "public", "generated");
const logDir = path.join(generatedRoot, "qa_logs");

const checks = [
  { check_id: "engineer_entry_guard", command: ["node", "./scripts/check-engineer-entry-frontmatter.mjs"], cwd: uiRoot },
  { check_id: "branch_hygiene", command: ["make", "branch-hygiene"], cwd: repoRoot },
  { check_id: "lint_py", command: ["make", "lint-py"], cwd: repoRoot },
  { check_id: "lint_md", command: ["make", "lint-md"], cwd: repoRoot },
  { check_id: "ui_test", command: ["npm", "test"], cwd: uiRoot },
  { check_id: "ui_build", command: ["npm", "run", "build"], cwd: uiRoot },
];

async function main() {
  await fs.mkdir(logDir, { recursive: true });

  const runResults = [];
  for (const check of checks) {
    const result = await runCheck(check);
    runResults.push(result);
  }

  const report = {
    version: "QaPassReportV1",
    generated_at: new Date().toISOString(),
    overall_status: runResults.every((result) => result.status === "pass") ? "pass" : "fail",
    checks: runResults,
  };

  await fs.writeFile(path.join(generatedRoot, "qa_pass_report_v1.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  process.stdout.write(`[qa-pass] completed with status ${report.overall_status}\n`);
}

function runCheck({ check_id, command, cwd }) {
  return new Promise((resolve) => {
    const started = Date.now();
    const [bin, ...args] = command;
    const child = spawn(bin, args, {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });

    child.on("error", async (error) => {
      const duration = Date.now() - started;
      const logPath = await writeCheckLog(check_id, stdout, `${stderr}\n${String(error)}`);
      resolve({
        check_id,
        status: "fail",
        duration_ms: duration,
        command: command.join(" "),
        log_path: normalizePath(logPath),
      });
    });

    child.on("close", async (code) => {
      const duration = Date.now() - started;
      const logPath = await writeCheckLog(check_id, stdout, stderr);
      resolve({
        check_id,
        status: code === 0 ? "pass" : "fail",
        duration_ms: duration,
        command: command.join(" "),
        log_path: normalizePath(logPath),
      });
    });
  });
}

async function writeCheckLog(checkId, stdout, stderr) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const logPath = path.join(logDir, `${timestamp}_${checkId}.log`);
  const content = [`# ${checkId}`, "", "## stdout", stdout || "(empty)", "", "## stderr", stderr || "(empty)", ""].join("\n");
  await fs.writeFile(logPath, content, "utf8");
  return logPath;
}

function normalizePath(inputPath) {
  return inputPath.split(path.sep).join("/");
}

main().catch((error) => {
  process.stderr.write(`[qa-pass] failed: ${String(error.stack || error)}\n`);
  process.exitCode = 1;
});
