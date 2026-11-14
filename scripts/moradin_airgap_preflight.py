"""Cheap source/runtime checks before disposable qualification provisioning."""


def qualification_preflight(root, image, platform, *, images, source_check, engine_check, run):
    source = source_check(root)
    aliases = {}
    for pinned in images.values():
        name = pinned.partition("@")[0]
        first, slash, _ = name.partition("/")
        qualified = bool(slash) and ("." in first or ":" in first or first == "localhost")
        canonical = pinned if qualified else "docker.io/" + (pinned if slash else "library/" + pinned)
        aliases[pinned] = canonical
        aliases[canonical] = canonical
        if not qualified:
            aliases["docker.io/" + pinned] = canonical
    if image not in aliases:
        raise ValueError("qualification image must match an exact registered digest")
    if platform not in {"linux/amd64", "linux/arm64"}:
        raise ValueError("qualification platform is unsupported")
    selected = aliases[image]
    if selected.startswith("docker.io/archlinux/") and platform != "linux/amd64":
        raise ValueError("official Arch qualification supports amd64 only")
    if engine_check() != "podman":
        raise ValueError("native qualification requires existing rootless Podman")
    canonical = selected
    check = run(["podman", "image", "exists", canonical])
    if check.returncode not in {0, 1}:
        raise ValueError("qualification image-store inspection failed; reconcile the existing runtime")
    return {"schema_version": "airgap-qualification-preflight-v1", "status": "ready",
            "source_sha": source, "target_image": canonical, "target_platform": platform,
            "engine": "podman", "rootless": True, "image_present": check.returncode == 0,
            "image_pull_required": check.returncode == 1,
            "image_pull_authority": "Existing explicitly invoked qualification workflow; preflight performs no pull",
            "qualification_accepted": False, "containers_started": 0, "host_configuration_changes": 0}
