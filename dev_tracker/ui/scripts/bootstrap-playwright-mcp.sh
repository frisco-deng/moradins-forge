#!/usr/bin/env bash
set -euo pipefail

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI is not installed or not on PATH." >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required to launch @playwright/mcp@latest." >&2
  exit 1
fi

echo "Configuring Playwright MCP for Moradins Harness."
echo "This is an opt-in, human-run setup for Codex-driven browser evaluator loops."
echo "Ordinary repo checks should stay on make ui-test-browser and make ui-review-screenshots."

if codex mcp get playwright >/dev/null 2>&1; then
  echo "Playwright MCP is already configured in ~/.codex/config.toml"
else
  codex mcp add playwright -- npx @playwright/mcp@latest
  echo "Added Playwright MCP to ~/.codex/config.toml"
fi

echo "Next steps:"
echo "  1. Run: make ui-playwright-mcp-doctor"
echo "  2. Install Chromium if the doctor reports browser_readiness failure:"
echo "     cd dev_tracker/ui && npx playwright install chromium"
echo "  3. Keep ordinary repo validation on make ui-test-browser and make ui-review-screenshots"
