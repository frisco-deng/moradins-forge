"""Execution-boundary controls for the shared developer setup payload."""

from pathlib import Path
import copy
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(
    p
    for p in Path(__file__).resolve().parents
    if (p / "catalog/workstation-tools.toml").is_file()
)
sys.path.insert(0, str(ROOT / "scripts/lib"))
import dev_tools_catalog as catalog  # noqa: E402 - portable checkout bootstrap
import dev_tools_doctor as doctor  # noqa: E402 - portable checkout bootstrap
import dev_tools_ui as ui  # noqa: E402 - portable checkout bootstrap


class Catalog(unittest.TestCase):
    def test_complete_inventory_and_paired_vitest(self):
        data = catalog.load(ROOT)
        self.assertEqual(len(data["tools"]), 78)
        for p in data["ui_profiles"].values():
            self.assertEqual(p["vitest"], p["provider"])
        self.assertEqual(data["ui_profiles"]["laneweaver"]["playwright"], "1.62.0")
        self.assertEqual(data["ui_profiles"]["moradin_legacy"]["vitest"], "4.1.12")

    def test_real_materialization_and_drift_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            (target / "scripts").mkdir()
            (target / "scripts/moradin_tooling_suite.py").touch()
            catalog.materialize(ROOT, target, apply=True)
            self.assertEqual(catalog.materialize(ROOT, target)["status"], "match")
            p = target / "scripts/setup-dev-tools"
            p.write_text("external drift")
            with self.assertRaisesRegex(ValueError, "drift"):
                catalog.materialize(ROOT, target, apply=True)
            self.assertEqual(p.read_text(), "external drift")

    def test_atomic_private_checkpoint(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name) / "receipt.json"
            catalog.save(p, {"a": 1})
            catalog.save(p, {"a": 2})
            self.assertEqual(json.loads(p.read_text()), {"a": 2})
            if os.name == "posix":
                self.assertEqual(p.stat().st_mode & 0o777, 0o600)


@unittest.skipUnless(
    os.name == "posix", "Linux/WSL runtime probes; other hosts unverified"
)
class Probes(unittest.TestCase):
    def spec(self):
        return {"id": "test", "command": "test-tool", "category": "fixture"}

    def test_exact_version_not_substring(self):
        with (
            patch.object(doctor.shutil, "which", return_value=sys.executable),
            patch.object(
                doctor.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], 0, "test-tool 1.7.110", ""
                ),
            ),
        ):
            self.assertEqual(
                doctor.command_check(self.spec(), {"test": "1.7.11"})["status"],
                "version_mismatch",
            )

    def test_empty_success_is_not_version_match(self):
        with (
            patch.object(doctor.shutil, "which", return_value=sys.executable),
            patch.object(
                doctor.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "", ""),
            ),
        ):
            self.assertEqual(
                doctor.command_check(self.spec(), {"test": "1.7.11"})["status"],
                "version_mismatch",
            )

    def test_catalog_owned_probe_executable_is_preserved(self):
        spec = {
            **self.spec(),
            "verification_argv": ["/usr/bin/test", "-x", sys.executable],
        }
        with patch.object(doctor.shutil, "which", return_value=sys.executable):
            self.assertEqual(
                doctor.command_check(spec, {})["status"], "presence_probe_passed"
            )

    def test_missing_timeout_and_failure_distinguished(self):
        with patch.object(doctor.shutil, "which", return_value=None):
            self.assertEqual(doctor.command_check(self.spec(), {})["status"], "missing")
        with (
            patch.object(doctor.shutil, "which", return_value=sys.executable),
            patch.object(
                doctor.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("test", 1),
            ),
        ):
            self.assertEqual(
                doctor.command_check(self.spec(), {})["status"], "unverified"
            )

    def test_repo_versions_and_locks_remain_reference(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name)
            (p / "package.json").write_text(
                json.dumps({"devDependencies": {"vitest": "4.1.12"}})
            )
            (p / "package-lock.json").write_text("{}")
            before = catalog.sha(p / "package.json")
            with patch.object(
                doctor, "command_check", return_value={"status": "missing"}
            ):
                result = doctor.doctor(ROOT, repo_root=p)
            self.assertEqual(result["repository"]["versions"]["vitest"], "4.1.12")
            self.assertEqual(catalog.sha(p / "package.json"), before)

    def test_ui_absent_is_not_ready(self):
        self.assertEqual(
            doctor.ui_check(ROOT, "laneweaver", None, None)["status"],
            "missing_runtime_or_profile",
        )


@unittest.skipUnless(
    os.name == "posix", "Linux/WSL UI transactions; other hosts unverified"
)
class Locks(unittest.TestCase):
    def lock(self):
        return {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"playwright": "1.62.0"}},
                "node_modules/playwright": {
                    "resolved": "https://registry.npmjs.org/playwright/-/playwright-1.62.0.tgz",
                    "integrity": "sha512-" + base64.b64encode(bytes(64)).decode(),
                },
            },
        }

    def test_untrusted_missing_or_wrong_lock_rejected(self):
        good = self.lock()
        ui.validate_lock(good, {"playwright": "1.62.0"})
        for field, value in [
            ("resolved", "https://example.invalid/a.tgz"),
            ("integrity", ""),
            ("link", True),
        ]:
            bad = copy.deepcopy(good)
            bad["packages"]["node_modules/playwright"][field] = value
            with self.assertRaises(ValueError):
                ui.validate_lock(bad, {"playwright": "1.62.0"})
        with self.assertRaises(ValueError):
            ui.validate_lock(good, {"playwright": "1.58.2"})

    def test_failed_nested_command_not_wrapper_success(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(ValueError, "ui_command_failed"):
                ui.run(
                    [sys.executable, "-c", "raise SystemExit(7)"],
                    Path(name),
                    dict(os.environ),
                )

    def test_safe_environment_has_no_inherited_credentials_or_loader(self):
        with patch.dict(
            os.environ,
            {
                "GH_TOKEN": "private",
                "NODE_OPTIONS": "--require malicious",
                "NPM_TOKEN": "private",
            },
        ):
            env = ui.environment("/tmp/node/bin/node", "/tmp/cache")
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("NODE_OPTIONS", env)
        self.assertNotIn("NPM_TOKEN", env)
        self.assertEqual(env["NPM_CONFIG_IGNORE_SCRIPTS"], "true")

    def test_prepared_and_drifted_receipts_never_verify(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "receipt.json"
            catalog.save(
                path,
                {
                    "schema_version": "forge-ui-tooling-receipt-v1",
                    "uid": os.getuid(),
                    "state": "prepared",
                    "generation": str(
                        Path(
                            os.environ.get(
                                "XDG_DATA_HOME", Path.home() / ".local/share"
                            )
                        )
                        / "moradins-forge/ui"
                        / ("a" * 16)
                    ),
                    "pointer": str(
                        Path(
                            os.environ.get(
                                "XDG_DATA_HOME", Path.home() / ".local/share"
                            )
                        )
                        / "moradins-forge/ui/laneweaver"
                    ),
                    "plan_sha256": "a" * 64,
                    "profile": "laneweaver",
                },
            )
            with self.assertRaisesRegex(ValueError, "not_verified"):
                ui.verify(path)
            with self.assertRaisesRegex(ValueError, "hash_mismatch"):
                ui.verify(path, "0" * 64)

    def test_tree_hashes_detect_external_changes_and_links(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "a").write_text("before")
            before = ui.tree_hashes(root)
            (root / "a").chmod(0o600)
            self.assertNotEqual(ui.tree_hashes(root), before)
            (root / "a").write_text("after")
            self.assertNotEqual(ui.tree_hashes(root), before)
            (root / "outside").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(ValueError, "external_symlink"):
                ui.tree_hashes(root)

    def test_empty_skipped_and_failed_nested_junit_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name) / "junit.xml"
            for xml in [
                "<testsuite/>",
                "<testsuite><testcase><skipped/></testcase></testsuite>",
                "<testsuite><testcase><failure/></testcase></testsuite>",
            ]:
                p.write_text(xml)
                with self.assertRaisesRegex(ValueError, "vitest_empty"):
                    ui.junit_count(p)
            p.write_text("<testsuites><testsuite><testcase/></testsuite></testsuites>")
            self.assertEqual(ui.junit_count(p), 1)

    def test_existing_plan_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name) / "plan.json"
            p.write_text("original bytes")
            with self.assertRaisesRegex(ValueError, "output_exists"):
                ui.plan(ROOT, "laneweaver", p)
            self.assertEqual(p.read_text(), "original bytes")

    def test_changed_staged_asset_never_reused(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name) / "archive.tar.xz"
            p.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "asset_drift"):
                ui.node_archive({"sha256": "0" * 64}, p)

    def test_wrong_approval_rejected_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name) / "plan.json"
            p.write_text(json.dumps({"plan_sha256": "not-approved"}))
            with self.assertRaisesRegex(ValueError, "digest_mismatch"):
                ui.checked_plan(ROOT, p, "different")


@unittest.skipUnless(
    os.name == "posix"
    and hasattr(os, "getuid")
    and os.getuid() != 0
    and (ROOT / "scripts/moradin_tooling_suite.py").exists(),
    "Native Forge target-user integration; other hosts remain unverified",
)
class LauncherNative(unittest.TestCase):
    def setUp(self):
        import importlib

        sys.path.insert(0, str(ROOT / "scripts"))
        self.native = importlib.import_module("moradin_tooling_suite")
        self.launcher = importlib.import_module("dev_tools_launcher")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "XDG_DATA_HOME": str(self.home / "data"),
                "XDG_STATE_HOME": str(self.home / "state"),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.primary = self.home / "dev/tooling/scripts/setup-dev-tools"

    def test_actual_snapshot_launch_and_unchanged_rerun(self):
        r = self.launcher.install(ROOT, self.native)
        self.assertEqual(r["status"], "verified")
        self.assertTrue(self.primary.is_symlink())
        proc = subprocess.run(
            [sys.executable, str(self.primary), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            self.launcher.install(ROOT, self.native)["status"], "verified_unchanged"
        )

    def test_existing_path_command_blocks_before_primary_mutation(self):
        binary = self.home / ".local/bin/setup-dev-tools"
        binary.parent.mkdir(parents=True)
        binary.write_text("operator command")
        with self.assertRaises(self.native.ToolingSuiteError):
            self.launcher.install(ROOT, self.native)
        self.assertEqual(binary.read_text(), "operator command")
        self.assertFalse(self.primary.exists())

    def test_receipt_bound_rollback_retains_snapshot(self):
        r = self.launcher.install(ROOT, self.native)
        receipt = Path(r["receipt"])
        generation = Path(json.loads(receipt.read_text())["generation"])
        result = self.launcher.rollback(receipt, catalog.sha(receipt), self.native)
        self.assertEqual(result["status"], "rolled_back_evidence_retained")
        self.assertFalse(self.primary.exists())
        self.assertTrue(generation.is_dir())

    def test_external_destination_drift_is_preserved(self):
        r = self.launcher.install(ROOT, self.native)
        receipt = Path(r["receipt"])
        self.primary.unlink()
        self.primary.write_text("new operator work")
        with self.assertRaises(self.native.ToolingSuiteError):
            self.launcher.rollback(receipt, catalog.sha(receipt), self.native)
        self.assertEqual(self.primary.read_text(), "new operator work")

    def test_interrupted_pointer_checkpoint_is_truthful_and_recoverable(self):
        original = self.launcher.save
        injected = []

        def write(path, value):
            if (
                isinstance(value, dict)
                and value.get("state") == "pointer_1_activated"
                and not injected
            ):
                injected.append(True)
                raise OSError("fixture receipt write interrupted")
            return original(path, value)

        with patch.object(self.launcher, "save", side_effect=write):
            with self.assertRaisesRegex(OSError, "interrupted"):
                self.launcher.install(ROOT, self.native)
        receipt = next((self.home / "state/moradins-forge/dev-tools").glob("*.json"))
        self.assertNotEqual(json.loads(receipt.read_text())["state"], "verified")
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            self.launcher.install(ROOT, self.native)
        self.launcher.rollback(receipt, catalog.sha(receipt), self.native)
        self.assertFalse(self.primary.exists())

    def test_corrupt_staging_never_activates(self):
        original = self.launcher.shutil.copy2

        def corrupt(source, target):
            result = original(source, target)
            if str(target).endswith("dev_tools_probe.cjs"):
                Path(target).write_text("corrupt staged bytes")
            return result

        with patch.object(self.launcher.shutil, "copy2", side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, "source_changed"):
                self.launcher.install(ROOT, self.native)
        self.assertFalse(self.primary.exists())


if __name__ == "__main__":
    unittest.main()
