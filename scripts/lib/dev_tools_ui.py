"""Focused UI-cohort actions for Forge's existing tooling entrypoint.

Uses native npm/Playwright acquisition and Forge-owned generation pointers.
It never installs OS packages, edits project manifests, or changes global Node.
"""

from pathlib import Path
from urllib.request import urlopen
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import re
import base64

from dev_tools_catalog import load, save, sha, PAYLOAD, digest


def inputs(root):
    names = PAYLOAD + [
        n
        for n in ["scripts/moradin_tooling_suite.py", "scripts/moradin_workstation.py"]
        if (Path(root) / n).is_file()
    ]
    return {name: sha(Path(root) / name) for name in names}


def environment(node, cache):
    # No inherited credentials, npm config, loader options or browser sessions.
    return {
        "HOME": str(Path.home()),
        "PATH": str(Path(node).parent) + ":/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PLAYWRIGHT_BROWSERS_PATH": str(cache),
        "NPM_CONFIG_USERCONFIG": str(Path(cache).parent / "npm-userconfig"),
        "NPM_CONFIG_GLOBALCONFIG": str(Path(cache).parent / "npm-globalconfig"),
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/",
        "NPM_CONFIG_IGNORE_SCRIPTS": "true",
    }


def npm_configs(env):
    for key in ["NPM_CONFIG_USERCONFIG", "NPM_CONFIG_GLOBALCONFIG"]:
        path = Path(env[key])
        if path.is_symlink() or (path.exists() and path.read_bytes()):
            raise ValueError("npm_configuration_conflict")
        if not path.exists():
            with path.open("x") as stream:
                stream.write("")
            path.chmod(0o600)


def run(argv, cwd, env, *, timeout=900, log=None):
    result = subprocess.run(
        [str(x) for x in argv],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if log:
        Path(log).write_text((result.stdout + "\n" + result.stderr)[-100000:])
        Path(log).chmod(0o600)
    if result.returncode:
        raise ValueError(
            "ui_command_failed:"
            + Path(str(argv[0])).name
            + ":"
            + str(result.returncode)
        )
    return result


def validate_lock(lock, expected):
    if (
        lock.get("lockfileVersion") != 3
        or lock.get("packages", {}).get("", {}).get("dependencies") != expected
    ):
        raise ValueError("ui_lock_direct_requirements_mismatch")
    for name, row in lock["packages"].items():
        if not name:
            continue
        integrity = row.get("integrity", "")
        try:
            encoded = integrity.removeprefix("sha512-")
            decoded = base64.b64decode(encoded, validate=True)
            valid_integrity = (
                integrity.startswith("sha512-")
                and len(decoded) == 64
                and base64.b64encode(decoded).decode() == encoded
            )
        except (ValueError, TypeError):
            valid_integrity = False
        if (
            not row.get("resolved", "").startswith("https://registry.npmjs.org/")
            or not valid_integrity
            or row.get("link")
        ):
            raise ValueError("ui_lock_unverified_asset:" + name)


def node_archive(asset, destination):
    destination = Path(destination)
    if destination.exists():
        if destination.is_symlink() or sha(destination) != asset["sha256"]:
            raise ValueError("node_staged_asset_drift")
        return destination
    cached = Path(asset.get("cache_path", destination))
    if cached.exists() and cached != destination:
        if cached.is_symlink() or sha(cached) != asset["sha256"]:
            raise ValueError("node_staged_asset_drift")
        shutil.copyfile(cached, destination)
        return destination
    with urlopen(asset["url"], timeout=60) as response:
        if response.url != asset["url"]:
            raise ValueError("node_asset_redirect")
        with destination.open("xb") as stream:
            shutil.copyfileobj(response, stream)
    if sha(destination) != asset["sha256"]:
        raise ValueError("node_asset_hash_mismatch")
    return destination


def extract_node(archive, destination):
    with tarfile.open(archive) as bundle:
        prefix = Path(archive).name.removesuffix(".tar.xz")
        if any(m.name.split("/")[0] != prefix for m in bundle.getmembers()):
            raise ValueError("node_archive_root_mismatch")
        bundle.extractall(destination, filter="data")
    return Path(destination) / prefix


def plan(root, profile, output, *, reuse_receipt=None, prior_plan=None):
    root, output = Path(root), Path(output)
    if output.exists():
        raise ValueError("ui_plan_output_exists_choose_new_path")
    selected = load(root)["ui_profiles"][profile]
    arch = {"x86_64": "x64", "aarch64": "arm64"}.get(platform.machine())
    if platform.system() != "Linux" or not arch:
        raise ValueError("ui_runtime_platform_unverified")
    archive = f"node-v{selected['node']}-linux-{arch}.tar.xz"
    url = f"https://nodejs.org/dist/v{selected['node']}/"
    with urlopen(url + "SHASUMS256.txt", timeout=20) as response:
        if response.url != url + "SHASUMS256.txt":
            raise ValueError("node_checksum_redirect")
        checksums = response.read(1024 * 1024).decode()
    matches = [
        line.split()[0]
        for line in checksums.splitlines()
        if line.split()[-1:] == [archive]
    ]
    if len(matches) != 1 or not re.fullmatch("[a-f0-9]{64}", matches[0]):
        raise ValueError("node_exact_checksum_unavailable")
    dependencies = {
        "playwright": selected["playwright"],
        "vitest": selected["vitest"],
        "@vitest/browser-playwright": selected["provider"],
        "@axe-core/playwright": selected["axe"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    asset = {
        "url": url + archive,
        "sha256": matches[0],
        "archive": archive,
        "cache_path": str((output.parent / archive).resolve()),
    }
    staged = node_archive(asset, Path(asset["cache_path"]))
    reuse = None
    if reuse_receipt:
        if not prior_plan:
            raise ValueError("reuse_requires_original_plan")
        previous = json.loads(Path(prior_plan).read_text())
        previous_hash = previous.pop("plan_sha256")
        recorded = json.loads(Path(reuse_receipt).read_text())
        source = Path(recorded["generation"])
        owned = (
            Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
            / "moradins-forge/ui"
        )
        if (
            digest(previous) != previous_hash
            or recorded["plan_sha256"] != previous_hash
            or recorded["uid"] != os.getuid()
            or previous["selected"] != selected
            or source != owned / previous_hash[:16]
            or recorded["state"] == "verified"
        ):
            raise ValueError("reuse_prior_identity_or_scope_conflict")
        package, lock = previous["package"], previous["package_lock"]
        validate_lock(lock, dependencies)
        reuse = {
            "receipt": str(Path(reuse_receipt).resolve()),
            "receipt_sha256": sha(reuse_receipt),
            "generation": str(source),
            "files": tree_hashes(source),
            "classification": "reconciled acquisition snapshot; previous execution remains unverified",
        }
    else:
        package, lock = resolve_lock(staged, output, dependencies)
    value = {
        "schema_version": "forge-ui-tooling-plan-v1",
        "profile": profile,
        "selected": selected,
        "implementation": inputs(root),
        "uid": os.getuid(),
        "architecture": platform.machine(),
        "node_asset": asset,
        "package": package,
        "package_lock": lock,
        "reuse": reuse,
        "safety": "User-owned isolated cohort; no OS packages, global runtime, project manifests, services or credentials change.",
    }
    value["plan_sha256"] = digest(value)
    save(output, value)
    return {
        "status": "planned",
        "path": str(output),
        "plan_sha256": value["plan_sha256"],
        "profile": profile,
    }


def resolve_lock(staged, output, dependencies):
    with tempfile.TemporaryDirectory(prefix="ui-lock-", dir=output.parent) as temporary:
        work = Path(temporary)
        package = {
            "name": "forge-ui-toolchain",
            "version": "1.0.0",
            "private": True,
            "dependencies": dependencies,
        }
        runtime = extract_node(staged, work)
        node = runtime / "bin/node"
        (work / "package.json").write_text(json.dumps(package))
        env = environment(node, work / "unused")
        npm_configs(env)
        run(
            [
                node,
                runtime / "lib/node_modules/npm/bin/npm-cli.js",
                "install",
                "--package-lock-only",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ],
            work,
            env,
            log=output.with_suffix(".resolve.log"),
        )
        lock = json.loads((work / "package-lock.json").read_text())
    validate_lock(lock, dependencies)
    return package, lock


def checked_plan(root, path, approval):
    value = json.loads(Path(path).read_text())
    claimed = value.pop("plan_sha256")
    if (
        claimed != approval
        or digest(value) != approval
        or value.get("schema_version") != "forge-ui-tooling-plan-v1"
    ):
        raise ValueError("ui_plan_digest_mismatch")
    if (
        value["implementation"] != inputs(root)
        or value["uid"] != os.getuid()
        or value["architecture"] != platform.machine()
    ):
        raise ValueError("ui_plan_identity_or_source_changed")
    selected = load(root)["ui_profiles"][value["profile"]]
    if value["selected"] != selected:
        raise ValueError("ui_plan_profile_changed")
    expected = {
        "playwright": selected["playwright"],
        "vitest": selected["vitest"],
        "@vitest/browser-playwright": selected["provider"],
        "@axe-core/playwright": selected["axe"],
    }
    if value["package"]["dependencies"] != expected:
        raise ValueError("ui_plan_packages_changed")
    validate_lock(value["package_lock"], expected)
    arch = {"x86_64": "x64", "aarch64": "arm64"}[platform.machine()]
    archive = f"node-v{selected['node']}-linux-{arch}.tar.xz"
    if (
        value["node_asset"]["url"]
        != f"https://nodejs.org/dist/v{selected['node']}/{archive}"
        or value["node_asset"]["archive"] != archive
    ):
        raise ValueError("ui_plan_node_source_changed")
    value["plan_sha256"] = claimed
    return value


def tree_hashes(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("ui_generation_external_symlink")
            result[path.relative_to(root).as_posix()] = "link:" + os.readlink(path)
        elif path.is_file():
            result[path.relative_to(root).as_posix()] = {
                "sha256": sha(path),
                "mode": path.stat().st_mode & 0o777,
                "uid": path.stat().st_uid,
            }
    return result


def apply(root, path, approval, native):
    if os.geteuid() == 0:
        raise ValueError("ui_apply_requires_target_user_not_root")
    value = checked_plan(root, path, approval)
    data, state, _ = native._user_roots()
    owned = data / "ui"
    generation = owned / approval[:16]
    receipt = state / "ui" / (approval + ".json")
    if generation.exists() or generation.is_symlink() or receipt.exists():
        raise ValueError("ui_transaction_exists_verify_or_explicit_rollback")
    owned.mkdir(parents=True, exist_ok=True)
    if owned.is_symlink() or owned.stat().st_uid != os.getuid():
        raise ValueError("ui_owned_root_conflict")
    pointer = owned / value["profile"]
    previous = native._owned_symlink_target(pointer, owned)
    record = {
        "schema_version": "forge-ui-tooling-receipt-v1",
        "state": "prepared",
        "profile": value["profile"],
        "plan_sha256": approval,
        "implementation": value["implementation"],
        "generation": str(generation),
        "pointer": str(pointer),
        "previous_pointer": previous,
        "uid": os.getuid(),
        "stages": [],
    }
    save(receipt, record)  # Durable intent precedes all installation mutations.
    generation.mkdir(mode=0o700)
    try:
        reuse = value.get("reuse")
        if reuse:
            source = Path(reuse["generation"])
            if (
                sha(reuse["receipt"]) != reuse["receipt_sha256"]
                or tree_hashes(source) != reuse["files"]
            ):
                raise ValueError("ui_reuse_source_drift")
            shutil.copytree(source, generation, dirs_exist_ok=True, symlinks=True)
            if (
                tree_hashes(generation) != reuse["files"]
                or tree_hashes(source) != reuse["files"]
            ):
                raise ValueError("ui_reuse_copy_drift")
        archive = node_archive(
            value["node_asset"], generation / value["node_asset"]["archive"]
        )
        runtime = extract_node(archive, generation)
        node = runtime / "bin/node"
        (generation / "package.json").write_text(json.dumps(value["package"]))
        (generation / "package-lock.json").write_text(json.dumps(value["package_lock"]))
        cache = generation / "browsers"
        env = environment(node, cache)
        npm_configs(env)
        record["node"] = str(node)
        record["browser_cache"] = str(cache)
        record["state"] = "runtime_verified"
        save(receipt, record)
        run(
            [
                node,
                runtime / "lib/node_modules/npm/bin/npm-cli.js",
                "ci",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ],
            generation,
            env,
            log=generation / "npm-install.log",
        )
        record["state"] = "packages_installed"
        save(receipt, record)
        run(
            [
                node,
                generation / "node_modules/playwright/cli.js",
                "install",
                *value["selected"]["browsers"],
            ],
            generation,
            env,
            timeout=1800,
            log=generation / "browser-install.log",
        )
        record["state"] = "browsers_installed"
        save(receipt, record)
        # Probe with the exact selected cache, rather than global browser state.
        observed = json.loads(
            run(
                [node, Path(root) / "scripts/lib/dev_tools_probe.cjs", generation],
                generation,
                env,
            ).stdout
        )
        if (
            observed["packages"] != value["package"]["dependencies"]
            or observed["node"] != value["selected"]["node"]
            or not all(
                observed["browsers"].get(b, {}).get("present")
                for b in [
                    "chromium",
                    "chromium-headless-shell",
                    "firefox",
                    "webkit",
                    "ffmpeg",
                ]
            )
        ):
            raise ValueError("ui_install_verification_incomplete")
        record["observed"] = observed
        record["state"] = "installed_unverified"
        save(receipt, record)
        # Functional acceptance is mandatory before switching the active profile.
        acceptance = state / "ui/acceptance" / approval
        smoke(root, generation, node, acceptance, env=env)
        record["acceptance_receipt"] = str(acceptance / "execution.json")
        record["acceptance_sha256"] = sha(acceptance / "execution.json")
        record["files"] = tree_hashes(generation)
        if inputs(root) != value["implementation"]:
            raise ValueError("ui_source_changed_during_execution")
        record["state"] = "verified_before_activation"
        save(receipt, record)
        native._switch_owned_symlink(pointer, generation, owned)
        record["state"] = "verified"
        save(receipt, record)
        return {
            "status": "verified",
            "receipt": str(receipt),
            "receipt_sha256": sha(receipt),
            "profile": value["profile"],
        }
    except BaseException as error:
        record["state"] = "interrupted_or_failed"
        record["reason"] = str(error)
        acceptance = state / "ui/acceptance" / approval / "execution.json"
        if acceptance.exists():
            record["partial_acceptance"] = {
                "path": str(acceptance),
                "sha256": sha(acceptance),
            }
            record["native_dependency_remediation"] = (
                str(node)
                + " "
                + str(generation / "node_modules/playwright/cli.js")
                + " install-deps --dry-run webkit"
            )
        save(receipt, record)
        raise


def verify(path, expected=None):
    path = Path(path)
    if expected and sha(path) != expected:
        raise ValueError("ui_receipt_hash_mismatch")
    r = json.loads(path.read_text())
    if (
        r.get("schema_version") != "forge-ui-tooling-receipt-v1"
        or r["uid"] != os.getuid()
    ):
        raise ValueError("ui_receipt_identity_conflict")
    owned = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        / "moradins-forge/ui"
    )
    if (
        Path(r["generation"]) != owned / r["plan_sha256"][:16]
        or Path(r["pointer"]) != owned / r["profile"]
    ):
        raise ValueError("ui_receipt_scope_conflict")
    if r["state"] != "verified":
        raise ValueError("ui_receipt_not_verified:" + r["state"])
    if (
        Path(r["pointer"]).resolve() != Path(r["generation"]).resolve()
        or tree_hashes(r["generation"]) != r["files"]
    ):
        raise ValueError("ui_generation_drift")
    return {"status": "verified", "profile": r["profile"], "receipt_sha256": sha(path)}


def rollback(path, expected, native):
    path = Path(path)
    if sha(path) != expected:
        raise ValueError("ui_receipt_hash_mismatch")
    r = json.loads(path.read_text())
    data, _, _ = native._user_roots()
    owned = data / "ui"
    generation, pointer = Path(r["generation"]), Path(r["pointer"])
    if (
        r["uid"] != os.getuid()
        or generation.parent != owned
        or generation.name != r["plan_sha256"][:16]
        or pointer != owned / r["profile"]
    ):
        raise ValueError("ui_rollback_scope_conflict")
    if r.get("files") and tree_hashes(generation) != r["files"]:
        raise ValueError("ui_rollback_external_drift")
    if pointer.is_symlink() and pointer.resolve() == generation.resolve():
        if r["previous_pointer"]:
            previous = Path(r["previous_pointer"])
            if not previous.is_absolute():
                previous = pointer.parent / previous
            if not previous.resolve().is_relative_to(owned.resolve()):
                raise ValueError("ui_rollback_previous_conflict")
            native._switch_owned_symlink(pointer, previous, owned)
        else:
            pointer.unlink()
    elif pointer.exists() or pointer.is_symlink():
        raise ValueError("ui_rollback_pointer_conflict")
    # Preserve failed-generation evidence; rollback removes activation only.
    r["state"] = "rolled_back_evidence_retained"
    save(path, r)
    return {"status": r["state"], "receipt_sha256": sha(path)}


def junit_count(path):
    junit = ET.parse(path).getroot()
    cases = junit.findall(".//testcase")
    if (
        not cases
        or not any(c.find("skipped") is None for c in cases)
        or junit.findall(".//failure")
        or junit.findall(".//error")
    ):
        raise ValueError("vitest_empty_skipped_or_failed")
    return sum(c.find("skipped") is None for c in cases)


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
