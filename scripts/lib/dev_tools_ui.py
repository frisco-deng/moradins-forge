"""Focused UI-cohort plans and Forge-owned transaction lifecycle."""

from pathlib import Path
import json
import os
import platform
import re
import shutil
from dev_tools_catalog import load, inputs, save, sha, digest
from dev_tools_runtime import (
    environment,
    npm_configs,
    run,
    validate_lock,
    node_archive,
    node_https,
    extract_node,
    resolve_lock,
)
from dev_tools_acceptance import smoke, junit_count as junit_count


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
    with node_https(selected["node"], "SHASUMS256.txt") as response:
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
