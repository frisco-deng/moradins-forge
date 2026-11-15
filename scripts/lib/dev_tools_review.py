"""Compact ownership-aware version review using existing native resolvers."""

from pathlib import Path
import re
import shutil
import subprocess
import sys

from dev_tools_catalog import load, sha
from dev_tools_environments import discover


def owner(native, spec, facts):
    options = native._suite_verification_options(spec)
    executable = next(
        (shutil.which(argv[0]) for argv in options if shutil.which(argv[0])), None
    )
    if executable and native._command_is_forge_owned(spec):
        return "forge", executable
    if executable and facts["package_manager"] == "apt":
        actual = Path(executable).resolve()
        result = native._run(["dpkg-query", "-S", executable, str(actual)], timeout=10)
        if result.returncode in {0, 1}:
            paths = [
                line.rsplit(": ", 1)[-1]
                for line in result.stdout.splitlines()
                if ": " in line
            ]
            if any(
                Path(p).is_absolute() and Path(p).resolve() == actual for p in paths
            ):
                return "apt", executable
    return ("external" if executable else "package/unknown"), executable


def stable_relation(installed, available):
    """Compare fully recognized stable numeric versions; other formats stay unknown."""
    pattern = r"v?((?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){1,3})"
    a, b = (
        re.fullmatch(pattern, installed or ""),
        re.fullmatch(pattern, available or ""),
    )
    if not a or not b:
        return None
    left, right = tuple(map(int, a[1].split("."))), tuple(map(int, b[1].split(".")))
    width = max(len(left), len(right))
    left, right = left + (0,) * (width - len(left)), right + (0,) * (width - len(right))
    return (left > right) - (left < right)


def review(root, native, *, progress=True):
    root = Path(root)
    facts = native.host_facts()
    cache = root / "Harness/artifacts/control/tooling_plans/version_cache.json"
    rows = []
    for index, spec in enumerate(native.TOOL_CATALOG):
        if progress and index % 10 == 0:
            print(
                f"Checking tool versions {index}/{len(native.TOOL_CATALOG)}…",
                file=sys.stderr,
                flush=True,
            )
        try:
            item = native._tool_row(
                spec,
                facts=facts,
                cache_path=cache,
                refresh_versions=True,
                runner=subprocess.run,
                resolver=native.resolve_latest_version,
                epel_available=facts.get("os_id") == "fedora",
            )
            ownership, executable = owner(native, spec, facts)
            resolved = item["resolved"]
            available = (
                resolved.get("version")
                if resolved.get("source") not in {"installed", "unresolved"}
                else None
            )
            if available in {"unknown", "latest-stable", ""}:
                available = None
            installed = item.get("installed_version") or None
            status = item["status"]
            if not executable and item["present"] and resolved.get("source") == "apt":
                ownership = "apt"
            action = (
                "optional/missing"
                if not item["present"] and not spec.profiles
                else status
            )
            if status == "preserved":
                relation = stable_relation(installed, available)
                action = (
                    "external/other channel"
                    if resolved.get("source") == "apt"
                    else "external/update available"
                    if relation == -1
                    else "external/unchanged"
                    if relation == 0
                    else "external/newer"
                    if relation == 1
                    else "external/unknown"
                )
            if ownership == "external" and resolved.get("source") == "apt":
                action = "external/other channel"
            if not item["present"] and "practical" not in spec.profiles:
                action = "optional/missing"
            if status == "current" and available is None:
                action = "installed/freshness unknown"
            if ownership == "forge" and status == "upgrade":
                relation = stable_relation(installed, available)
                if relation is None or relation >= 0:
                    action = (
                        "version comparison unknown"
                        if relation is None
                        else "downgrade blocked"
                        if relation > 0
                        else "current"
                    )
            rows.append(
                {
                    "id": spec.id,
                    "installed": installed,
                    "available": available,
                    "channel": resolved.get("source", "unknown"),
                    "freshness": resolved.get("cache", "unavailable")
                    if available
                    else "unavailable",
                    "owner": ownership,
                    "executable": executable,
                    "action": action,
                    "selected": "practical" in spec.profiles or ownership == "forge",
                    "reason": item["install_action"]["reason"],
                }
            )
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
            rows.append(
                {
                    "id": spec.id,
                    "installed": None,
                    "available": None,
                    "channel": "unavailable",
                    "owner": "unknown",
                    "action": "unavailable",
                    "selected": "practical" in spec.profiles,
                    "reason": str(error),
                }
            )
    environments = discover(root, native)
    profiles = load(root)["ui_profiles"]
    for environment in environments["environments"]:
        profile = environment["profile"]
        observed = environment["observed"].get("observed", {}).get("packages", {})
        package_rows = [
            ("playwright", "playwright"),
            ("vitest", "vitest"),
            ("@vitest/browser-playwright", "provider"),
            ("@axe-core/playwright", "axe"),
        ]
        package_rows.append(("node", "node"))
        for name, key in package_rows:
            rows.append(
                {
                    "id": profile + "/" + key,
                    "installed": environment["observed"].get("observed", {}).get("node")
                    if key == "node"
                    else observed.get(name),
                    "available": profiles[profile][key],
                    "channel": "validated pin",
                    "owner": "forge-ui",
                    "selected": True,
                    "action": "verify/repair"
                    if environment["state"] != "verified"
                    else "current",
                }
            )
    return {
        "schema_version": "dev-tools-review-v1",
        "rows": rows,
        "ui": environments,
        "platform": facts,
        "catalog_sha256": sha(root / "catalog/workstation-tools.toml"),
        "scope": "Practical baseline plus installed Forge tools and registered UI environments.",
        "apt_metadata": "Configured local APT index; root refresh and exact candidate checks occur before package installation.",
        "status": "partial"
        if environments["conflicts"] or any(x["action"] == "unavailable" for x in rows)
        else "reviewed",
    }


def cell(value, width):
    value = "—" if value is None else str(value)
    value = "".join(c if c.isprintable() else " " for c in value)
    return value if len(value) <= width else value[: width - 1] + "…"


def table(rows):
    columns = [
        ("Tool", "id", 30),
        ("Installed", "installed", 24),
        ("Available / channel", "target", 32),
        ("Owner", "owner", 15),
        ("Action", "action", 27),
    ]
    print("  ".join(title.ljust(width) for title, _, width in columns))
    for row in rows:
        values = dict(row)
        values["target"] = (
            (str(row["available"]) + " (" + row.get("channel", "") + ")")
            if row.get("available")
            else None
        )
        print(
            "  ".join(
                cell(values.get(key), width).ljust(width) for _, key, width in columns
            ).rstrip()
        )


def display(report):
    table(report["rows"])
    print("\n" + report["scope"])
    print("Unknown means unavailable evidence; external tools are not overwritten.")
    print(report["apt_metadata"])
    for conflict in report["ui"]["conflicts"]:
        print("UI conflict: " + conflict["reason"])
