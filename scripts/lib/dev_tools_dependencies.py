"""Catalog-owned UI system packages consumed by the native sealed installer."""

import re

from dev_tools_catalog import load


def definitions(root):
    data = load(root)
    result = {}
    for key, row in data.get("ui_system_dependencies", {}).items():
        if (
            key != "ubuntu_24_04"
            or row.get("os_id") != "ubuntu"
            or row.get("os_version") != "24.04"
            or row.get("manager") != "apt"
            or row.get("arches") != ["amd64", "arm64"]
        ):
            raise ValueError("unverified_ui_dependency_platform")
        for profile, selected in data["ui_profiles"].items():
            packages = row.get(profile, [])
            if (
                not packages
                or packages != sorted(set(packages))
                or any(not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", p) for p in packages)
                or row.get(profile + "_playwright") != selected["playwright"]
                or not re.fullmatch(
                    "[0-9a-f]{64}", row.get(profile + "_source_sha256", "")
                )
            ):
                raise ValueError("invalid_ui_dependency_catalog:" + profile)
        result[key] = row
    return result


def package_id(package):
    return "ui_dep_" + re.sub("[^a-z0-9]", "_", package)


def package_specs(root, spec_type):
    packages = set()
    for row in definitions(root).values():
        for profile in load(root)["ui_profiles"]:
            packages.update(row[profile])
    ids = [package_id(p) for p in packages]
    if len(set(ids)) != len(ids):
        raise ValueError("ui_dependency_identifier_conflict")
    return tuple(
        spec_type(
            id=package_id(package),
            label=package,
            command="",
            category="ui-runtime",
            reason="system library for a catalog-pinned UI environment",
            apt_package=package,
            required=True,
        )
        for package in sorted(packages)
    )


def selected_ids(root, facts, profiles):
    profiles = set(profiles)
    if not profiles:
        return []
    if not profiles.issubset(load(root)["ui_profiles"]):
        raise ValueError("unknown_ui_dependency_profile")
    for row in definitions(root).values():
        if (
            facts.get("os_id") == row["os_id"]
            and facts.get("os_version") == row["os_version"]
            and facts.get("package_manager") == row["manager"]
            and facts.get("arch") in row["arches"]
        ):
            return sorted({package_id(p) for profile in profiles for p in row[profile]})
    raise ValueError("UI system dependency installation is unverified on this platform")


def validate_platform(root, facts, tool_ids):
    requested = {x for x in tool_ids if x.startswith("ui_dep_")}
    if requested and not requested.issubset(
        selected_ids(root, facts, load(root)["ui_profiles"])
    ):
        raise ValueError("ui_dependency_platform_or_package_mismatch")
