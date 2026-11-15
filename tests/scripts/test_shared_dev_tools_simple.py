"""Real CLI and filesystem controls for compact review and owned upgrades."""

from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import io
import json
import os

try:
    import pty
except ImportError:
    pty = None
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = next(
    p
    for p in Path(__file__).resolve().parents
    if (p / "catalog/workstation-tools.toml").is_file()
)
sys.path.insert(0, str(ROOT / "scripts/lib"))
import dev_tools_catalog as catalog  # noqa: E402 - portable checkout bootstrap
import dev_tools_dependencies as dependencies  # noqa: E402 - portable checkout bootstrap
import dev_tools_environments as environments  # noqa: E402 - portable checkout bootstrap
import dev_tools_review as review  # noqa: E402 - portable checkout bootstrap
import dev_tools_workflow as workflow  # noqa: E402 - portable checkout bootstrap


FIXTURE_NATIVE = """
from pathlib import Path
from types import SimpleNamespace
import json, os, sys
sys.path.insert(0, str(Path(__file__).parent / 'lib'))
from dev_tools_catalog import save, digest
TOOL_CATALOG = [SimpleNamespace(id='uv', profiles=('practical',))]
def host_facts():
    return dict(system='linux', arch='amd64', os_id='ubuntu', os_version='24.04', package_manager='apt')
def _user_roots():
    b=Path.home()
    return b/'data', b/'state', b/'bin'
def _suite_verification_options(spec): return [[sys.executable,'--version']]
def _command_is_forge_owned(spec): return True
def _version_matches(a,b): return a==b
def resolve_latest_version(*args,**kwargs): return {}
def _tool_row(spec,**kwargs):
    return dict(present=True, installed_version='1.0.0', status='upgrade', resolved=dict(version='2.0.0',source='github-release',cache='refreshed'), install_action=dict(kind='forge-user',reason='fixture upgrade'))
def build_suite_plan(**kwargs):
    v=dict(status='ready',blockers=[],tools=[dict(id='uv', installed_version='1.0.0',status='upgrade',resolved=dict(version='2.0.0',source='github-release'),install_action=dict(kind='forge-user'))])
    v['plan_sha256']=digest(v)
    return v
def write_suite_plan(v,path): save(path,v)
def apply_suite_plan(path,approved_sha256,**kwargs):
    v=json.loads(Path(path).read_text()); assert v.pop('plan_sha256')==approved_sha256==digest(v)
    marker=Path.home()/'installed-tool'; marker.write_text('2.0.0')
    receipt=Path.home()/'native-receipt.json';save(receipt,dict(status='pass',plan_sha256=approved_sha256))
    return dict(status='pass',receipt=str(receipt))
def verify_suite_receipt(path):
    return dict(status='pass' if (Path.home()/'installed-tool').read_text()=='2.0.0' else 'fail')
"""


@unittest.skipUnless(os.name == "posix", "Linux CLI execution boundary")
class SimpleCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "forge"
        for relative in catalog.PAYLOAD:
            destination = self.source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        (self.source / "scripts/moradin_tooling_suite.py").write_text(FIXTURE_NATIVE)
        self.home = self.base / "operator"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PYTHONPATH="")
        self.command = [sys.executable, str(self.source / "scripts/setup-dev-tools")]

    def terminal(self, args, answer):
        master, slave = pty.openpty()
        child = subprocess.Popen(
            self.command + args, stdin=slave, stdout=slave, stderr=slave, env=self.env
        )
        os.close(slave)
        output, sent = b"", False
        deadline = time.monotonic() + 25
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        block = os.read(master, 65536)
                    except OSError:
                        break
                    if not block:
                        break
                    output += block
                    if b"Apply these changes" in output and not sent:
                        os.write(master, answer.encode() + b"\n")
                        sent = True
                if child.poll() is not None and not ready:
                    break
            if child.poll() is None:
                child.kill()
                self.fail("CLI did not finish within its fixture bound")
            return child.wait(), output.decode(errors="replace")
        finally:
            os.close(master)
            if child.poll() is None:
                child.kill()
                child.wait()

    def test_bare_and_review_are_compact_no_install(self):
        for args in [[], ["--review"]]:
            result = subprocess.run(
                self.command + args,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for value in ["Installed", "Available", "1.0.0", "2.0.0"]:
                self.assertIn(value, result.stdout)
            self.assertNotIn('"schema_version"', result.stdout)
        self.assertFalse((self.home / "installed-tool").exists())

    def test_json_is_explicit_and_still_supported(self):
        result = subprocess.run(
            self.command + ["--review", "--json"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(
            json.loads(result.stdout)["schema_version"], "dev-tools-review-v1"
        )

    def test_one_confirmation_applies_and_verifies_without_paths(self):
        code, output = self.terminal(["--upgrade"], "yes")
        self.assertEqual(code, 0, output)
        self.assertEqual(output.count("Apply these changes and verify them?"), 1)
        self.assertIn("Upgrade complete and verified", output)
        self.assertEqual((self.home / "installed-tool").read_text(), "2.0.0")
        record = json.loads(
            next(
                (self.home / "state/dev-tools/runs").glob("*/execution.json")
            ).read_text()
        )
        self.assertEqual(record["status"], "pass")
        self.assertEqual(record["lanes"][0]["state"], "verified")

    def test_decline_leaves_installation_untouched(self):
        code, output = self.terminal(["--upgrade"], "")
        self.assertEqual(code, 0, output)
        self.assertIn("Cancelled", output)
        self.assertFalse((self.home / "installed-tool").exists())

    def test_noninteractive_upgrade_does_not_apply(self):
        result = subprocess.run(
            self.command + ["--upgrade"], env=self.env, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("one confirmation", result.stderr)
        self.assertFalse((self.home / "installed-tool").exists())

    def test_conflicting_simple_flags_rejected(self):
        result = subprocess.run(
            self.command + ["--review", "--upgrade"],
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)

    def test_simple_upgrade_never_silently_ignores_an_explicit_plan(self):
        result = subprocess.run(
            self.command + ["--upgrade", "--plan", "foreign.json"],
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("explicit action", result.stderr)
        self.assertFalse((self.home / "installed-tool").exists())


@unittest.skipUnless(os.name == "posix", "Linux native execution boundary")
class ExecutionBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "execution.json"

    def record(self, lanes):
        return {
            "implementation": catalog.inputs(ROOT),
            "lanes": lanes,
            "conflicts": [],
            "status": "approved",
        }

    def lane(self, **updates):
        result = {
            "id": "host",
            "kind": "native",
            "state": "prepared",
            "approval": "a" * 64,
            "plan": {"tools": [{"install_action": {"kind": "forge-user"}}]},
        }
        plan = self.path.parent / "plan.json"
        catalog.save(plan, {})
        result.update(path=str(plan), sha256=catalog.sha(plan))
        result.update(updates)
        return result

    def test_successful_outer_apply_with_failed_verification_is_partial(self):
        native = SimpleNamespace(
            apply_suite_plan=lambda *a, **k: {"status": "pass", "receipt": "fixture"},
            verify_suite_receipt=lambda *a: {"status": "fail"},
        )
        with redirect_stdout(io.StringIO()):
            result = workflow.execute(
                ROOT, native, self.record([self.lane()]), self.path
            )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["lanes"][0]["state"], "failed")

    def test_failed_prerequisite_blocks_ui_but_independent_work_runs(self):
        native = SimpleNamespace(
            apply_suite_plan=lambda *a, **k: {"status": "pass", "receipt": "fixture"},
            verify_suite_receipt=lambda *a: {"status": "pass"},
        )
        lanes = [
            {
                "id": "ui-dependencies",
                "kind": "native",
                "state": "blocked",
                "reason": "unavailable",
            },
            self.lane(id="ui:fixture", kind="ui", requires="ui-dependencies"),
            self.lane(),
        ]
        result = workflow.execute(ROOT, native, self.record(lanes), self.path)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(lanes[1]["state"], "failed")
        self.assertEqual(lanes[2]["state"], "verified")

    def test_plan_drift_never_invokes_apply(self):
        lane = self.lane()
        Path(lane["path"]).write_text("changed")
        native = SimpleNamespace(
            apply_suite_plan=lambda *a, **k: self.fail("drift was applied")
        )
        result = workflow.execute(ROOT, native, self.record([lane]), self.path)
        self.assertEqual(result["status"], "partial")
        self.assertIn("changed after confirmation", lane["reason"])

    def test_interrupt_retains_applying_checkpoint(self):
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt()

        native = SimpleNamespace(apply_suite_plan=interrupt)
        with self.assertRaises(KeyboardInterrupt):
            workflow.execute(ROOT, native, self.record([self.lane()]), self.path)
        self.assertEqual(
            json.loads(self.path.read_text())["lanes"][0]["state"], "applying"
        )

    def test_concurrent_apply_rejected(self):
        with workflow.exclusive(self.path.parent):
            with self.assertRaisesRegex(ValueError, "another"):
                with workflow.exclusive(self.path.parent):
                    self.fail("concurrent apply entered")

    def test_interruption_without_receipt_is_named_not_retried(self):
        state = self.path.parent
        run = state / "runs" / ("a" * 32)
        run.mkdir(parents=True)
        catalog.save(state / "current-upgrade.json", {"run_id": "a" * 32})
        catalog.save(
            run / "execution.json",
            {
                "uid": os.getuid(),
                "lanes": [
                    {
                        "id": "host",
                        "kind": "native",
                        "state": "applying",
                        "approval": "b" * 64,
                    }
                ],
            },
        )
        native = SimpleNamespace(
            _user_roots=lambda: (state / "data", state, state / "bin")
        )
        blocked = workflow.reconcile(ROOT, native, state)
        self.assertIn("no unique receipt", blocked["host"])

    def test_unknown_evidence_not_displayed_as_current(self):
        output = io.StringIO()
        with redirect_stdout(output):
            review.table(
                [
                    {
                        "id": "fixture",
                        "available": None,
                        "owner": "external",
                        "action": "external/unknown",
                    }
                ]
            )
        self.assertIn("external/unknown", output.getvalue())
        self.assertNotIn("current", output.getvalue())

    def test_strict_comparison_does_not_promote_downgrade_or_unknown(self):
        self.assertEqual(review.stable_relation("v2.1.0", "2.0.0"), 1)
        self.assertEqual(review.stable_relation("1.0", "1.0.0"), 0)
        self.assertIsNone(review.stable_relation("present-unverified", "2.0.0"))
        self.assertIsNone(review.stable_relation("1.0.0-rc1", "1.0.0"))

    def test_apt_package_current_does_not_certify_shadowing_external_command(self):
        item = {
            "present": True,
            "installed_version": "2.83.0",
            "status": "current",
            "resolved": {"source": "apt", "version": "2.45.0-1", "cache": "fresh"},
            "install_action": {"kind": "none", "reason": "APT package current"},
        }
        native = SimpleNamespace(
            TOOL_CATALOG=[SimpleNamespace(id="gh", profiles=("practical",))],
            host_facts=lambda: {"os_id": "ubuntu", "package_manager": "apt"},
            _tool_row=lambda *args, **kwargs: item,
            resolve_latest_version=lambda *args: None,
            _version_matches=lambda a, b: a == b,
        )
        with (
            patch.object(review, "owner", return_value=("external", "/external/gh")),
            patch.object(
                review, "discover", return_value={"environments": [], "conflicts": []}
            ),
        ):
            result = review.review(ROOT, native, progress=False)
        self.assertEqual(result["rows"][0]["action"], "external/other channel")

    def test_missing_extended_tool_is_optional_in_default_review(self):
        item = {
            "present": False,
            "installed_version": None,
            "status": "install",
            "resolved": {"source": "apt", "version": "1.0", "cache": "fresh"},
            "install_action": {"kind": "system-package", "reason": "available"},
        }
        native = SimpleNamespace(
            TOOL_CATALOG=[SimpleNamespace(id="optional", profiles=("extended",))],
            host_facts=lambda: {"os_id": "ubuntu", "package_manager": "apt"},
            _tool_row=lambda *args, **kwargs: item,
            resolve_latest_version=lambda *args: None,
        )
        with (
            patch.object(review, "owner", return_value=("package/unknown", None)),
            patch.object(
                review, "discover", return_value={"environments": [], "conflicts": []}
            ),
        ):
            result = review.review(ROOT, native, progress=False)
        self.assertFalse(result["rows"][0]["selected"])
        self.assertEqual(result["rows"][0]["action"], "optional/missing")

    def test_source_drift_before_execution_never_calls_installer(self):
        record = self.record([self.lane()])
        with patch.object(workflow, "inputs", return_value={"changed": True}):
            with self.assertRaisesRegex(ValueError, "source changed"):
                workflow.execute(ROOT, SimpleNamespace(), record, self.path)

    def test_equivalent_ui_receipts_are_not_selected_by_mtime(self):
        data, state = self.path.parent / "data", self.path.parent / "state"
        native = SimpleNamespace(
            _user_roots=lambda: (data, state, self.path.parent / "bin")
        )
        for value in ["a", "b"]:
            identity = value * 64
            generation = data / "ui" / identity[:16]
            node = generation / "node-v24.19.0-linux-x64/bin/node"
            node.parent.mkdir(parents=True)
            node.write_text("fixture runtime")
            (generation / "package.json").write_text("{}")
            (generation / "package-lock.json").write_text("{}")
            catalog.save(
                state / "ui" / (identity + ".json"),
                {
                    "schema_version": "forge-ui-tooling-receipt-v1",
                    "profile": "laneweaver",
                    "uid": os.getuid(),
                    "plan_sha256": identity,
                    "generation": str(generation),
                    "state": "interrupted_or_failed",
                },
            )
        observed = {
            "status": "installed_unverified",
            "observed": {"packages": {}, "browsers": {}},
        }
        with patch.object(environments, "ui_check", return_value=observed):
            first = environments.discover(ROOT, native)
            self.assertEqual(len(first["environments"]), 1)
            self.assertFalse(first["conflicts"])
            (data / "ui" / ("b" * 16) / "package-lock.json").write_text(
                '{"changed": true}'
            )
            second = environments.discover(ROOT, native)
            self.assertFalse(second["environments"])
            self.assertIn(
                "conflicting UI acquisitions", second["conflicts"][0]["reason"]
            )

    def test_profile_dependency_allowlist_and_platform(self):
        ids = dependencies.selected_ids(
            ROOT,
            {
                "os_id": "ubuntu",
                "os_version": "24.04",
                "package_manager": "apt",
                "arch": "amd64",
            },
            ["laneweaver"],
        )
        self.assertIn("ui_dep_libgtk_4_1", ids)
        with self.assertRaisesRegex(ValueError, "unverified"):
            dependencies.selected_ids(ROOT, {"os_id": "unknown"}, ["laneweaver"])


if __name__ == "__main__":
    unittest.main()
