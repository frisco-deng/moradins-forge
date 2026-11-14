"""Native browser/Vitest acceptance and bounded entity-free JUnit reading."""

from pathlib import Path
from xml.parsers import expat
import json
from dev_tools_catalog import inputs, save, sha
from dev_tools_runtime import environment, run


def junit_count(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise ValueError("junit_over_read_bound")
    parser = expat.ParserCreate(namespace_separator="}")
    cases, stack = [], []
    current = None
    failed = False

    def forbidden(*args):
        raise ValueError("junit_dtd_or_entity_forbidden")

    def start(name, attrs):
        nonlocal current, failed
        name = name.rsplit("}", 1)[-1]
        if not stack and name not in ("testsuite", "testsuites"):
            raise ValueError("junit_invalid_root")
        if name == "testcase":
            if current is not None or "testsuite" not in stack:
                raise ValueError("junit_invalid_testcase")
            current = {"skipped": False}
        elif name == "skipped" and current is not None:
            current["skipped"] = True
        elif name in ("failure", "error"):
            failed = True
        stack.append(name)

    def end(name):
        nonlocal current
        name = name.rsplit("}", 1)[-1]
        if name == "testcase":
            cases.append(current)
            current = None
        stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    try:
        parser.Parse(raw, True)
    except expat.ExpatError as error:
        raise ValueError("junit_invalid_xml") from error
    executed = sum(not c["skipped"] for c in cases)
    if not executed or failed:
        raise ValueError("vitest_empty_skipped_or_failed")
    return executed


def smoke(root, ui_root, node, output, *, env=None):
    ui_root, output = Path(ui_root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    env = env or environment(node, ui_root / "browsers")
    result = run(
        [node, Path(root) / "scripts/lib/dev_tools_smoke.cjs", ui_root, output],
        ui_root,
        env,
        log=output / "browser-smoke.log",
    )
    browser = json.loads(result.stdout)
    # Native Vitest reports must contain executed passing cases.
    workspace = output / "vitest-workspace"
    workspace.mkdir(exist_ok=True)
    modules = workspace / "node_modules"
    if modules.exists() or modules.is_symlink():
        if (
            not modules.is_symlink()
            or modules.resolve() != (ui_root / "node_modules").resolve()
        ):
            raise ValueError("vitest_workspace_conflict")
    else:
        modules.symlink_to(ui_root / "node_modules", target_is_directory=True)
    tests = workspace / "tooling-smoke"
    tests.mkdir(exist_ok=True)
    (tests / "smoke.browser.test.js").write_text(
        "import {it,expect} from 'vitest'; it('real browser click',()=>{document.body.innerHTML='<button>Go</button><output>waiting</output>';document.querySelector('button').onclick=()=>document.querySelector('output').textContent='clicked';document.querySelector('button').click();expect(document.querySelector('output').textContent).toBe('clicked')});\n"
    )
    config = (
        "import {defineConfig} from 'vitest/config';import {playwright} from '@vitest/browser-playwright';export default defineConfig({server:{host:'127.0.0.1'},test:{include:['tooling-smoke/*.test.js'],reporters:['default','junit'],outputFile:{junit:"
        + json.dumps(str(output / "vitest.xml"))
        + "},browser:{enabled:true,provider:playwright(),headless:true,api:{host:'127.0.0.1'},instances:[{browser:'chromium'}]}}});"
    )
    config = config.replace(
        "defineConfig({server:",
        "defineConfig({cacheDir:" + json.dumps(str(workspace / ".vite")) + ",server:",
    )
    (workspace / "tooling-smoke.config.mjs").write_text(config)
    run(
        [
            node,
            ui_root / "node_modules/vitest/vitest.mjs",
            "run",
            "--configLoader",
            "native",
            "--config",
            "tooling-smoke.config.mjs",
        ],
        workspace,
        env,
        log=output / "vitest.log",
    )
    executed = junit_count(output / "vitest.xml")
    complete = not (
        browser["status"] != "pass"
        or len(browser["stages"]) != 7
        or any(s["status"] != "pass" for s in browser["stages"])
    )
    save(
        output / "execution.json",
        {
            "status": "pass" if complete else "partial",
            "browser": browser,
            "vitest_executed_cases": executed,
            "source_sha256": inputs(root),
            "config_sha256": sha(workspace / "tooling-smoke.config.mjs"),
        },
    )
    if not complete:
        raise ValueError("ui_browser_execution_incomplete")
    return {"status": "pass", "receipt": str(output / "execution.json")}
