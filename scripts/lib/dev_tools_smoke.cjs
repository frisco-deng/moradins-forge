// Executed local controls: real clicks, positive/negative axe, FFmpeg and JUnit.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const root = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
const pw = require(require.resolve('playwright', { paths: [root] }));
const axeModule = require(require.resolve('@axe-core/playwright', { paths: [root] }));
const AxeBuilder = axeModule.default || axeModule.AxeBuilder || axeModule;
const stages = [];
const html = '<html lang="en"><head><title>Tooling fixture</title></head><body><main><h1>Tooling</h1><button>Run</button><output>waiting</output></main></body></html>';
async function stage(id, fn) {
  try { await fn(); stages.push({ id, status: 'pass' }); }
  catch (e) { stages.push({ id, status: 'fail', error: e.message.slice(0, 1800) }); }
}
(async () => {
  for (const [id, type, options] of [['headless-chromium', pw.chromium, {}], ['chromium', pw.chromium, { channel: 'chromium' }], ['firefox', pw.firefox, {}], ['webkit', pw.webkit, {}]]) {
    await stage(id, async () => {
      const browser = await type.launch({ headless: true, ...options });
      try {
        const page = await browser.newPage(); await page.setContent(html);
        await page.locator('button').evaluate(el => { el.onclick = () => document.querySelector('output').textContent = 'clicked'; });
        await page.getByRole('button', { name: 'Run', exact: true }).click();
        assert.equal(await page.locator('output').textContent(), 'clicked');
        await page.screenshot({ path: path.join(out, id + '.png') });
      } finally { await browser.close(); }
    });
  }
  for (const bad of [true, false]) {
    await stage(bad ? 'axe-negative-control' : 'axe-positive-control', async () => {
      const browser = await pw.chromium.launch({ headless: true });
      try {
        const context = await browser.newContext(); const page = await context.newPage(); await page.setContent(bad ? html.replace('<h1>', '<img src="data:image/png;base64,AA=="><h1>') : html);
        const result = await new AxeBuilder({ page }).analyze();
        if (bad) assert.ok(result.violations.some(v => v.id === 'image-alt'), 'seeded inaccessible image must fail');
        else assert.equal(result.violations.length, 0, JSON.stringify(result.violations.map(v => v.id)));
        fs.writeFileSync(path.join(out, bad ? 'axe-negative.json' : 'axe-positive.json'), JSON.stringify(result, null, 2));
      } finally { await browser.close(); }
    });
  }
  await stage('ffmpeg', async () => {
    const core = require.resolve('playwright-core/package.json', { paths: [path.dirname(require.resolve('playwright/package.json', { paths: [root] }))] });
    const v = JSON.parse(fs.readFileSync(core)).version;
    let registry;
    if (v === '1.58.2') ({ registry } = require(path.join(path.dirname(core), 'lib/server/registry/index.js')));
    else if (v === '1.62.0') ({ registry } = require(path.join(path.dirname(core), 'lib/coreBundle.js')).registry);
    else throw new Error('unverified browser registry adapter for ' + v);
    const r = spawnSync(registry.findExecutable('ffmpeg').executablePath(), ['-version'], { encoding: 'utf8' });
    assert.equal(r.status, 0); assert.match(r.stdout + r.stderr, /ffmpeg version/i);
  });
  const escape = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
  fs.writeFileSync(path.join(out, 'browsers.xml'), '<testsuite name="native-ui" tests="7" failures="' + stages.filter(s => s.status !== 'pass').length + '">' + stages.map(s => '<testcase name="' + s.id + '">' + (s.status === 'pass' ? '' : '<failure message="' + escape(s.error) + '"/>') + '</testcase>').join('') + '</testsuite>');
  console.log(JSON.stringify({ status: stages.every(s => s.status === 'pass') ? 'pass' : 'fail', stages }));
})().catch(e => { console.error(e.message); process.exitCode = 1; });
