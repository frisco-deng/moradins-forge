// Resolve the selected package cohort and its actual browser registry, not PATH guesses.
const fs = require('node:fs');
const path = require('node:path');
const root = fs.realpathSync(process.argv[2]);
const packages = {};
for (const name of ['playwright', 'vitest', '@vitest/browser-playwright', '@axe-core/playwright']) {
  try { let p = path.dirname(require.resolve(name, { paths: [root] }));
    while (p.startsWith(root + path.sep)) {
      const manifest = path.join(p, 'package.json');
      if (fs.existsSync(manifest)) { const data = JSON.parse(fs.readFileSync(manifest));
        if (data.name === name) { packages[name] = data.version; break; }
      }
      p = path.dirname(p);
    }
    if (!packages[name]) throw new Error('package outside selected cohort');
  } catch { packages[name] = null; }
}
const browsers = {};
try {
  const base = require.resolve('playwright/package.json', { paths: [root] });
  const core = require.resolve('playwright-core/package.json', { paths: [path.dirname(base)] });
  const v = JSON.parse(fs.readFileSync(core)).version;
  let registry;
  if (v === '1.58.2') ({ registry } = require(path.join(path.dirname(core), 'lib/server/registry/index.js')));
  else if (v === '1.62.0') ({ registry } = require(path.join(path.dirname(core), 'lib/coreBundle.js')).registry);
  else throw new Error('unverified browser registry adapter for ' + v);
  for (const name of ['chromium', 'chromium-headless-shell', 'firefox', 'webkit', 'ffmpeg']) {
    const item = registry.findExecutable(name); const executable = item?.executablePath();
    browsers[name] = { path: executable || null, present: !!executable && fs.existsSync(executable) };
  }
} catch (e) { browsers.registry_error = e.message; }
console.log(JSON.stringify({ node: process.versions.node, packages, browsers,
  browser_cache: process.env.PLAYWRIGHT_BROWSERS_PATH || 'Playwright native default' }));
