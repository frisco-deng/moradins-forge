"""Coverage for universal workstation planning and portable agent controls."""

from __future__ import annotations

import json
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import moradin_workstation
from scripts.moradin_workstation import (
    CONTEXT_PRIMER_LIMIT,
    TOOL_CATALOG,
    WORKSTATION_PLAN_VERSION,
    WorkstationError,
    agent_file_proposal,
    apply_tooling_plan,
    build_offline_bundle,
    build_python_tool_lock,
    build_tooling_plan,
    context_primer,
    diagnostic_brief,
    discover_repositories,
    inspect_repository_capabilities,
    plan_digest,
    portable_bundle_plan,
    rerun_advice,
    resolve_latest_version,
    rollback_tooling_receipt,
    session_checkpoint,
)


def write(path: Path, content: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_repo(root: Path, name: str = "repo") -> Path:
    repo = root / name
    write(repo / ".git/HEAD", "ref: refs/heads/main\n")
    write(repo / "README.md", "# Example\n")
    return repo


def fixed_resolution(*_args: object, **_kwargs: object) -> dict[str, str]:
    return {
        "version": "1.2.3",
        "source": "test",
        "source_url": "https://pypi.org/project/example/",
        "asset_url": "",
        "sha256": "",
        "trust": "pypi-release-metadata",
        "checked_at": "2026-07-28T00:00:00+00:00",
        "cache": "fresh",
    }


def catalog_fields(tool_id: str) -> dict[str, object]:
    spec = next(item for item in TOOL_CATALOG if item.id == tool_id)
    return {
        "label": spec.label,
        "command": spec.command,
        "category": spec.category,
        "reason": spec.reason,
        "required": spec.required,
        "verification_command": ([spec.command, "--version"] if spec.command else []),
    }


def test_discovery_stays_within_approved_workspaces(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    outside = tmp_path / "outside"
    inside_repo = make_repo(approved, "inside")
    make_repo(outside, "outside")
    (approved / "outside-link").symlink_to(outside, target_is_directory=True)

    repositories = discover_repositories([approved])

    assert repositories == [inside_repo.resolve()]
    assert all(path.is_relative_to(approved.resolve()) for path in repositories)


def test_filesystem_root_cannot_be_approved() -> None:
    with pytest.raises(WorkstationError, match="filesystem roots"):
        discover_repositories([Path("/")])


def test_full_home_directory_cannot_be_approved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    with pytest.raises(WorkstationError, match="too broad"):
        discover_repositories([home])


def test_capability_inspection_uses_standard_manifests(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo / "pyproject.toml", "[project]\nname='example'\n")
    write(repo / "Dockerfile", "FROM scratch\n")
    write(repo / ".github/workflows/ci.yml", "name: ci\n")
    write(repo / "claude.md", "# noncanonical\n")
    write(repo / "src/secret_algorithm.py", "DO_NOT_READ = True\n")

    inspection = inspect_repository_capabilities(repo)

    assert {"git", "python", "container", "github-actions"}.issubset(
        inspection["capabilities"]
    )
    assert inspection["lowercase_agent_file_warnings"] == ["claude.md"]
    assert "secret_algorithm" not in json.dumps(inspection)


def test_tooling_plan_is_adaptive_and_digest_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    repo = make_repo(workspace)
    write(repo / "pyproject.toml", "[project]\nname='example'\n")
    write(repo / ".github/workflows/ci.yml", "name: ci\n")
    monkeypatch.setattr(
        moradin_workstation,
        "resolve_latest_version",
        fixed_resolution,
    )
    events: list[tuple[str, list[Path] | Path]] = []
    inspect = moradin_workstation.inspect_repository_capabilities

    def record_inspection(path: Path) -> dict[str, object]:
        events.append(("inspect", path))
        return inspect(path)

    monkeypatch.setattr(
        moradin_workstation,
        "inspect_repository_capabilities",
        record_inspection,
    )

    plan = build_tooling_plan(
        [workspace],
        forge_root=tmp_path / "forge",
        exclude_tools=("docker",),
        discovery_callback=lambda repositories: events.append(
            ("discovery", list(repositories))
        ),
    )

    tool_ids = {row["id"] for row in plan["tools"]}
    assert plan["version"] == WORKSTATION_PLAN_VERSION
    assert "pip_audit" in tool_ids
    assert "actionlint" in tool_ids
    assert "zizmor" in tool_ids
    assert "cad" not in tool_ids
    assert events[0] == ("discovery", [repo.resolve()])
    assert events[1] == ("inspect", repo.resolve())
    assert plan["plan_sha256"] == plan_digest(plan)
    plan["profile"] = "tampered"
    assert plan["plan_sha256"] != plan_digest(plan)


def test_agent_proposal_contains_only_owned_added_lines(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo / "AGENTS.md", "# Private Project\n\nNever expose internal phrase.\n")

    proposal = agent_file_proposal(repo, "AGENTS.md")

    assert proposal["action"] == "patch"
    assert "Never expose internal phrase" not in proposal["patch_preview"]
    assert "context-primer" in proposal["owned_block"]
    assert "materially improve testing or diagnosis" in proposal["owned_block"]
    assert proposal["requires_explicit_approval"] is True


def test_agent_proposal_shows_exact_owned_block_update_only(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(
        repo / "AGENTS.md",
        "\n".join(
            [
                "# Private Project",
                "",
                "Do not expose unrelated private guidance.",
                "",
                "<!-- moradin-forge:start -->",
                "legacy owned instruction",
                "<!-- moradin-forge:end -->",
                "",
            ]
        ),
    )

    proposal = agent_file_proposal(repo, "AGENTS.md")

    assert proposal["action"] == "update"
    assert "-legacy owned instruction" in proposal["patch_preview"]
    assert "+## Moradin Forge" in proposal["patch_preview"]
    assert "unrelated private guidance" not in proposal["patch_preview"]


def test_tooling_apply_requires_exact_digest_and_uses_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    plan = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": "2026-07-28T00:00:00+00:00",
        "profile": "practical-full",
        "platform": {"system": "linux", "arch": "amd64"},
        "approved_workspaces": [str(tmp_path / "workspace")],
        "discovered_repository_count": 0,
        "repositories": [],
        "capabilities": [],
        "tools": [
            {
                "id": "semgrep",
                **catalog_fields("semgrep"),
                "present": False,
                "status": "missing",
                "matched_capabilities": ["python"],
                "resolved": {
                    "version": "1.2.3",
                    "source": "pypi",
                    "cache": "fresh",
                    "trust": "pypi-hash-verified",
                    "artifact_sha256s": ["a" * 64],
                },
                "install_action": {
                    "tool_id": "semgrep",
                    "kind": "user-local",
                    "argv": [
                        "uv",
                        "tool",
                        "install",
                        "--force",
                        "semgrep==1.2.3",
                    ],
                    "requires_elevation": False,
                    "auto_execute": True,
                    "package": "semgrep==1.2.3",
                    "reason": "test",
                },
                "verification_command": ["semgrep", "--version"],
            }
        ],
        "missing_required": [],
        "missing_recommended": ["semgrep"],
        "status": "ready",
        "consent": {},
        "safety": [],
    }
    plan["plan_sha256"] = plan_digest(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    calls: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(WorkstationError, match="approved plan digest"):
        apply_tooling_plan(
            plan_path,
            approved_sha256="0" * 64,
            forge_root=tmp_path / "forge",
            runner=runner,
        )

    receipt = apply_tooling_plan(
        plan_path,
        approved_sha256=plan["plan_sha256"],
        forge_root=tmp_path / "forge",
        runner=runner,
    )

    assert calls == [
        ["uv", "tool", "install", "--force", "semgrep==1.2.3"],
        ["semgrep", "--version"],
    ]
    assert receipt["executed"][0]["tool_id"] == "semgrep"
    assert receipt["status"] == "pass"
    assert receipt["executed"][0]["verification_status"] == "pass"
    assert receipt["install_generation"] == plan["plan_sha256"][:16]
    assert "semgrep==1.2.3" not in json.dumps(receipt["executed"])

    def failing_runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=17, stdout="", stderr="")

    with pytest.raises(WorkstationError, match="rollback receipt"):
        apply_tooling_plan(
            plan_path,
            approved_sha256=plan["plan_sha256"],
            forge_root=tmp_path / "failed-forge",
            runner=failing_runner,
        )
    failed_receipts = sorted(
        (tmp_path / "failed-forge").glob(
            "Harness/artifacts/control/tooling_receipts/*/receipt.json"
        )
    )
    failed_receipt = json.loads(failed_receipts[-1].read_text(encoding="utf-8"))
    assert failed_receipt["status"] == "fail"
    assert failed_receipt["failure"] == {
        "tool_id": "semgrep",
        "exit_code": 17,
        "reason": "approved user-level installer returned a failure",
    }

    verification_calls = 0

    def verification_fails(
        argv: list[str],
        **_kwargs: object,
    ) -> SimpleNamespace:
        nonlocal verification_calls
        verification_calls += 1
        return SimpleNamespace(
            returncode=0 if verification_calls == 1 else 9,
            stdout="",
            stderr="",
        )

    with pytest.raises(WorkstationError, match="verification command"):
        apply_tooling_plan(
            plan_path,
            approved_sha256=plan["plan_sha256"],
            forge_root=tmp_path / "verify-failed-forge",
            runner=verification_fails,
        )
    verification_receipt_path = next(
        (tmp_path / "verify-failed-forge").glob(
            "Harness/artifacts/control/tooling_receipts/*/receipt.json"
        )
    )
    verification_receipt = json.loads(
        verification_receipt_path.read_text(encoding="utf-8")
    )
    assert verification_receipt["status"] == "fail"
    assert verification_receipt["executed"][0]["verification_status"] == "fail"


def test_tooling_rollback_only_removes_recorded_uv_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    receipt = {
        "version": "MoradinForgeToolingReceiptV1",
        "executed": [
            {"tool_id": "semgrep", "status": "pass"},
            {"tool_id": "gh", "status": "pass"},
            {
                "tool_id": "yamllint",
                "action_kind": "user-package-manager",
                "status": "pass",
            },
        ],
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    calls: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = rollback_tooling_receipt(
        receipt_path,
        approve=True,
        runner=runner,
    )

    assert calls == [["uv", "tool", "uninstall", "semgrep"]]
    assert result["manual"] == [
        {
            "tool_id": "yamllint",
            "reason": "shared package-manager installs require explicit native removal",
        },
        {
            "tool_id": "gh",
            "reason": "shared package-manager installs require explicit native removal",
        },
    ]


def test_tooling_rollback_preserves_a_newer_shared_shim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    write(home / ".local/bin/semgrep", "newer generation\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    receipt = {
        "version": "MoradinForgeToolingReceiptV1",
        "install_generation": "a" * 16,
        "executed": [
            {
                "tool_id": "semgrep",
                "status": "pass",
                "shim_identity_sha256": "b" * 64,
            }
        ],
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    calls: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = rollback_tooling_receipt(
        receipt_path,
        approve=True,
        runner=runner,
    )

    assert calls == []
    assert result["manual"] == [
        {
            "tool_id": "semgrep",
            "reason": (
                "the shared shim changed after this receipt; "
                "the newer generation was preserved"
            ),
        }
    ]


def test_offline_bundle_plan_removes_host_paths(tmp_path: Path) -> None:
    plan = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": "2026-07-28T00:00:00+00:00",
        "profile": "practical-full",
        "platform": {"system": "linux", "arch": "amd64"},
        "approved_workspaces": ["/private/workspace"],
        "discovered_repository_count": 1,
        "repositories": [{"path": "/private/workspace/repo"}],
        "capabilities": [],
        "tools": [],
        "missing_required": [],
        "missing_recommended": [],
        "status": "ready",
        "consent": {},
        "safety": [],
    }
    plan["plan_sha256"] = plan_digest(plan)

    portable = portable_bundle_plan(plan)

    rendered = json.dumps(portable)
    assert "/private/workspace" not in rendered
    assert portable["approved_workspaces"] == ["<workspace-1>"]
    assert portable["repositories"][0]["path"] == "<repo-1>"
    assert portable["plan_sha256"] == plan_digest(portable)


def test_offline_bundle_reports_unresolved_assets_without_leaking_paths(
    tmp_path: Path,
) -> None:
    plan = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": "2026-07-28T00:00:00+00:00",
        "profile": "practical-full",
        "platform": {"system": "linux", "arch": "amd64"},
        "approved_workspaces": ["/private/workspace"],
        "discovered_repository_count": 0,
        "repositories": [],
        "capabilities": [],
        "tools": [
            {
                "id": "ripgrep",
                **catalog_fields("ripgrep"),
                "present": False,
                "resolved": {"asset_url": "", "sha256": ""},
                "install_action": {
                    "kind": "manual",
                    "package": "",
                },
            }
        ],
        "missing_required": [],
        "missing_recommended": ["ripgrep"],
        "status": "ready",
        "consent": {},
        "safety": [],
    }
    plan["plan_sha256"] = plan_digest(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = build_offline_bundle(
        plan_path,
        output=tmp_path / "bundle",
    )

    assert result["status"] == "partial"
    assert "/private/workspace" not in (
        tmp_path / "bundle/tooling_plan.json"
    ).read_text(encoding="utf-8")
    assert (tmp_path / "bundle/SHA256SUMS").is_file()


def test_rehashed_plan_cannot_change_allowlisted_installer_arguments(
    tmp_path: Path,
) -> None:
    plan = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": "2026-07-28T00:00:00+00:00",
        "profile": "practical-full",
        "platform": {"system": "linux", "arch": "amd64"},
        "approved_workspaces": [str(tmp_path / "workspace")],
        "discovered_repository_count": 0,
        "repositories": [],
        "capabilities": [],
        "tools": [
            {
                "id": "semgrep",
                **catalog_fields("semgrep"),
                "present": False,
                "resolved": {
                    "version": "1.2.3",
                    "source": "pypi",
                    "cache": "fresh",
                    "trust": "pypi-hash-verified",
                    "artifact_sha256s": ["a" * 64],
                },
                "install_action": {
                    "tool_id": "semgrep",
                    "kind": "user-local",
                    "argv": ["uv", "tool", "install", "--force", "attacker==9.9.9"],
                    "requires_elevation": False,
                    "auto_execute": True,
                    "package": "attacker==9.9.9",
                },
            }
        ],
        "missing_required": [],
        "missing_recommended": ["semgrep"],
        "status": "ready",
        "consent": {},
        "safety": [],
    }
    plan["plan_sha256"] = plan_digest(plan)
    plan_path = tmp_path / "tampered-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(WorkstationError, match="verified catalog"):
        apply_tooling_plan(
            plan_path,
            approved_sha256=plan["plan_sha256"],
            forge_root=tmp_path / "forge",
        )

    plan["tools"][0]["install_action"] = {
        "tool_id": "semgrep",
        "kind": "user-local",
        "argv": ["uv", "tool", "install", "--force", "semgrep==1.2.3"],
        "requires_elevation": False,
        "auto_execute": True,
        "package": "semgrep==1.2.3",
    }
    plan["tools"][0]["command"] = "semgrep; touch should-not-run"
    plan["plan_sha256"] = plan_digest(plan)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(WorkstationError, match="verified catalog"):
        apply_tooling_plan(
            plan_path,
            approved_sha256=plan["plan_sha256"],
            forge_root=tmp_path / "forge",
        )


def test_offline_bundle_rejects_nonofficial_asset_before_download(
    tmp_path: Path,
) -> None:
    plan = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": "2026-07-28T00:00:00+00:00",
        "profile": "practical-full",
        "platform": {"system": "linux", "arch": "amd64"},
        "approved_workspaces": [str(tmp_path / "workspace")],
        "discovered_repository_count": 0,
        "repositories": [],
        "capabilities": [],
        "tools": [
            {
                "id": "ripgrep",
                **catalog_fields("ripgrep"),
                "present": False,
                "resolved": {
                    "version": "1.2.3",
                    "asset_url": "https://malicious.invalid/tool",
                    "sha256": "a" * 64,
                },
                "install_action": {"kind": "manual", "argv": [], "package": ""},
            }
        ],
        "missing_required": [],
        "missing_recommended": ["ripgrep"],
        "status": "ready",
        "consent": {},
        "safety": [],
    }
    plan["plan_sha256"] = plan_digest(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    downloaded = False

    def downloader(_url: str, _destination: Path) -> None:
        nonlocal downloaded
        downloaded = True

    with pytest.raises(WorkstationError, match="official host"):
        build_offline_bundle(
            plan_path,
            output=tmp_path / "bundle",
            downloader=downloader,
        )

    assert downloaded is False


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://pypi.org:444/simple/tool",
        "https://user@pypi.org/simple/tool",
        "https://pypi.org/simple/tool#fragment",
        "https://pypi.org/simple/\nmalicious",
    ],
)
def test_network_boundary_rejects_unsafe_sources_and_redirects(url: str) -> None:
    with pytest.raises(WorkstationError):
        moradin_workstation._assert_official_https_url(
            url,
            purpose="test source",
        )
    handler = moradin_workstation._OfficialSourceRedirectHandler()
    with pytest.raises(WorkstationError):
        handler.redirect_request(
            moradin_workstation.urllib.request.Request("https://pypi.org/simple/tool"),
            None,
            302,
            "redirect",
            {},
            url,
        )

    assert (
        moradin_workstation._assert_official_https_url(
            "https://pypi.org/simple/tool",
            purpose="test source",
        )
        == "https://pypi.org/simple/tool"
    )


def test_python_dependency_closure_builds_installable_offline_bundle(
    tmp_path: Path,
) -> None:
    contents = {
        "semgrep": b"semgrep wheel",
        "dependency": b"dependency wheel",
    }
    lock_text = "\n".join(
        [
            "dependency==4.5.6 \\",
            f"    --hash=sha256:{hashlib.sha256(contents['dependency']).hexdigest()}",
            "semgrep==1.2.3 \\",
            f"    --hash=sha256:{hashlib.sha256(contents['semgrep']).hexdigest()}",
            "",
        ]
    )
    compiler_argv: list[str] = []

    def compiler(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        compiler_argv.extend(argv)
        return SimpleNamespace(returncode=0, stdout=lock_text, stderr="")

    def fetch_json(url: str) -> dict[str, object]:
        package = "semgrep" if "/semgrep/" in url else "dependency"
        version = "1.2.3" if package == "semgrep" else "4.5.6"
        payload = contents[package]
        return {
            "urls": [
                {
                    "filename": f"{package}-{version}-py3-none-any.whl",
                    "url": (
                        "https://files.pythonhosted.org/packages/"
                        f"{package}-{version}-py3-none-any.whl"
                    ),
                    "digests": {"sha256": hashlib.sha256(payload).hexdigest()},
                    "yanked": False,
                }
            ]
        }

    rows = [
        {
            "id": "semgrep",
            "present": False,
            "install_action": {
                "kind": "user-local",
                "package": "semgrep==1.2.3",
                "auto_execute": True,
            },
        }
    ]
    closure = build_python_tool_lock(
        rows,
        system="linux",
        arch="amd64",
        runner=compiler,
        fetch_json=fetch_json,
    )
    assert closure["status"] == "ready"
    assert len(closure["assets"]) == 2
    assert compiler_argv[compiler_argv.index("--python-platform") + 1] == (
        "x86_64-unknown-linux-gnu"
    )

    plan = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": "2026-07-28T00:00:00+00:00",
        "profile": "practical-full",
        "platform": {"system": "linux", "arch": "amd64"},
        "approved_workspaces": [str(tmp_path / "workspace")],
        "discovered_repository_count": 0,
        "repositories": [],
        "capabilities": ["python"],
        "tools": [
            {
                "id": "semgrep",
                **catalog_fields("semgrep"),
                "present": False,
                "resolved": {
                    "version": "1.2.3",
                    "source": "pypi",
                    "cache": "fresh",
                    "trust": "pypi-hash-verified",
                    "artifact_sha256s": [
                        hashlib.sha256(contents["semgrep"]).hexdigest()
                    ],
                },
                "install_action": {
                    "tool_id": "semgrep",
                    "kind": "user-local",
                    "argv": [
                        "uv",
                        "tool",
                        "install",
                        "--force",
                        "semgrep==1.2.3",
                    ],
                    "requires_elevation": False,
                    "auto_execute": True,
                    "package": "semgrep==1.2.3",
                },
            }
        ],
        "python_tool_lock": closure,
        "missing_required": [],
        "missing_recommended": ["semgrep"],
        "status": "ready",
        "consent": {},
        "safety": [],
    }
    plan["plan_sha256"] = plan_digest(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    def downloader(url: str, destination: Path) -> None:
        package = "semgrep" if "semgrep-" in url else "dependency"
        destination.write_bytes(contents[package])

    bundle = build_offline_bundle(
        plan_path,
        output=tmp_path / "bundle",
        downloader=downloader,
    )

    assert bundle["status"] == "pass"
    assert len(bundle["included"]) == 2
    assert (tmp_path / "bundle/requirements.lock").is_file()
    assert (tmp_path / "bundle/constraints.txt").read_text(
        encoding="utf-8"
    ) == "dependency==4.5.6\nsemgrep==1.2.3\n"
    assert (tmp_path / "bundle/install-user-tools-offline.sh").is_file()
    assert (tmp_path / "bundle/install-user-tools-offline.ps1").is_file()
    offline_bash = (tmp_path / "bundle/install-user-tools-offline.sh").read_text(
        encoding="utf-8"
    )
    assert "--offline --no-index --no-config --no-python-downloads" in offline_bash
    assert '--constraints "$bundle_root/constraints.txt"' in offline_bash
    assert 'command -v "$command_name"' in offline_bash
    assert "commands=('semgrep')" in offline_bash
    assert "Unsafe SHA256SUMS entry." in offline_bash
    offline_powershell = (tmp_path / "bundle/install-user-tools-offline.ps1").read_text(
        encoding="utf-8"
    )
    assert "$commands = @('semgrep')" in offline_powershell
    assert "Get-Command $command" in offline_powershell
    assert "Unsafe SHA256SUMS entry." in offline_powershell


def test_version_resolution_uses_24_hour_cache(tmp_path: Path) -> None:
    spec = next(item for item in TOOL_CATALOG if item.id == "semgrep")
    cache = tmp_path / "versions.json"
    calls = 0

    def fetch_json(_url: str) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "info": {"version": "1.2.3"},
            "releases": {
                "1.2.3": [{"digests": {"sha256": "a" * 64}}],
            },
        }

    start = datetime(2026, 7, 28, tzinfo=UTC)
    first = resolve_latest_version(
        spec,
        cache_path=cache,
        refresh=False,
        system="linux",
        prefer_python=True,
        now=start,
        fetch_json=fetch_json,
    )
    second = resolve_latest_version(
        spec,
        cache_path=cache,
        refresh=False,
        system="linux",
        prefer_python=True,
        now=start + timedelta(hours=23),
        fetch_json=fetch_json,
    )
    third = resolve_latest_version(
        spec,
        cache_path=cache,
        refresh=False,
        system="linux",
        prefer_python=True,
        now=start + timedelta(hours=25),
        fetch_json=fetch_json,
    )

    assert first["version"] == second["version"] == third["version"] == "1.2.3"
    assert second["cache"] == "fresh"
    assert calls == 2


def test_stale_version_metadata_cannot_auto_execute() -> None:
    spec = next(item for item in TOOL_CATALOG if item.id == "semgrep")
    resolved = {
        "version": "1.2.3",
        "source": "pypi",
        "trust": "pypi-hash-verified",
        "artifact_sha256s": ["a" * 64],
        "cache": "stale",
    }

    action = moradin_workstation._install_action(
        spec,
        system="linux",
        resolved=resolved,
        uv_present=True,
    )

    assert action["kind"] == "manual"
    assert action["auto_execute"] is False
    assert "stale" in action["reason"]


def test_github_asset_selector_rejects_distro_packages_for_standalone_linux() -> None:
    digest = "a" * 64
    selected = moradin_workstation.select_github_asset(
        [
            {
                "name": "tool_1.0_linux_amd64.deb",
                "browser_download_url": (
                    "https://github.com/example/tool/releases/download/v1/tool.deb"
                ),
                "digest": f"sha256:{digest}",
                "size": 10,
            },
            {
                "name": "tool_1.0_linux_amd64.deb.b3",
                "browser_download_url": (
                    "https://github.com/example/tool/releases/download/v1/tool.deb.b3"
                ),
                "digest": f"sha256:{digest}",
                "size": 10,
            },
            {
                "name": "tool_1.0_linux_amd64.deb.sha512",
                "browser_download_url": (
                    "https://github.com/example/tool/releases/download/v1/tool.deb.sha512"
                ),
                "digest": f"sha256:{digest}",
                "size": 10,
            },
            {
                "name": "tool_1.0_linux_amd64.tar.gz",
                "browser_download_url": (
                    "https://github.com/example/tool/releases/download/v1/tool.tar.gz"
                ),
                "digest": f"sha256:{digest}",
                "size": 20,
            },
        ],
        system="linux",
        arch="amd64",
    )

    assert selected is not None
    assert selected["filename"].endswith(".tar.gz")

    deb_only = moradin_workstation.select_github_asset(
        [
            {
                "name": "tool_1.0_linux_amd64.deb",
                "browser_download_url": (
                    "https://github.com/example/tool/releases/download/v1/tool.deb"
                ),
                "digest": f"sha256:{digest}",
                "size": 10,
            }
        ],
        system="linux",
        arch="amd64",
    )
    assert deb_only is not None
    assert deb_only["filename"].endswith(".deb")


def test_tooling_rollback_restores_owned_path_block_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    profile = home / ".profile"
    write(profile, "# existing\nexport KEEP=1\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    plan = {
        "version": WORKSTATION_PLAN_VERSION,
        "generated_at": "2026-07-28T00:00:00+00:00",
        "profile": "practical-full",
        "platform": {
            "system": moradin_workstation.normalized_platform(),
            "arch": "amd64",
        },
        "approved_workspaces": [str(tmp_path / "workspace")],
        "discovered_repository_count": 0,
        "repositories": [],
        "capabilities": [],
        "tools": [],
        "missing_required": [],
        "missing_recommended": [],
        "status": "ready",
        "consent": {},
        "safety": [],
    }
    plan["plan_sha256"] = plan_digest(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    receipt = apply_tooling_plan(
        plan_path,
        approved_sha256=plan["plan_sha256"],
        forge_root=tmp_path / "forge",
        user_config_approved=True,
    )
    assert "moradin-forge:path:start" in profile.read_text(encoding="utf-8")

    result = rollback_tooling_receipt(
        Path(receipt["receipt"]),
        approve=True,
    )

    assert result["user_config"]["status"] == "restored"
    assert profile.read_text(encoding="utf-8") == "# existing\nexport KEEP=1\n"


def test_context_primer_and_metrics_are_compact_and_sanitized(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo / "Makefile", "repo-brief:\n\t@true\nverify-fast:\n\t@true\n")
    runtime = tmp_path / "runtime"

    primer = context_primer(repo, runtime_root=runtime)
    checkpoint = session_checkpoint(
        repo,
        ["make", "verify-fast"],
        "pass",
        runtime_root=runtime,
    )
    advice = rerun_advice(
        repo,
        ["make", "verify-fast"],
        runtime_root=runtime,
    )
    brief = diagnostic_brief(runtime_root=runtime)

    assert len(primer.encode("utf-8")) <= CONTEXT_PRIMER_LIMIT
    assert primer.count("## Next Action") == 1
    assert advice["action"] == "reuse"
    assert checkpoint["command_sha256"] == advice["command_sha256"]
    metrics_text = (
        runtime / "Harness/artifacts/control/efficiency/local_counters.json"
    ).read_text(encoding="utf-8")
    assert repo.as_posix() not in metrics_text
    assert "make verify-fast" not in metrics_text
    assert brief["counters"]["reruns_avoided"] == 1
