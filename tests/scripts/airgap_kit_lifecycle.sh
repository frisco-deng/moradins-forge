#!/usr/bin/env bash
set -euo pipefail

umask 077
SAFE_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PATH=$SAFE_PATH:${HOME:?}/.local/bin
export PATH

forge_root=${FORGE_ROOT:-$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd -P)}
target_image=${TARGET_IMAGE:?TARGET_IMAGE is required}
target_platform=${TARGET_PLATFORM:?TARGET_PLATFORM is required}
target_kind=${TARGET_KIND:?TARGET_KIND is required}
scratch_root=$(mktemp -d "${RUNNER_TEMP:-/tmp}/moradin-airgap-qualification.XXXXXXXX")
container_name=moradin-airgap-${target_kind}-${target_platform##*/}-$$

cleanup() {
	podman rm --force "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

podman run --detach --name "$container_name" --platform "$target_platform" \
	--volume "$forge_root:/forge:ro" \
	"$target_image" /bin/sh -c 'while :; do sleep 3600; done' >/dev/null

case $target_kind in
ubuntu | debian)
	podman exec "$container_name" /bin/sh -eu -c \
		'export DEBIAN_FRONTEND=noninteractive; apt-get update; apt-get install -y --no-install-recommends ca-certificates coreutils curl findutils git gzip python3 sudo tar'
	;;
fedora)
	podman exec "$container_name" /bin/sh -eu -c \
		'dnf install -y --setopt=install_weak_deps=False ca-certificates coreutils curl findutils git gzip python3 shadow-utils sudo tar'
	;;
rocky)
	podman exec "$container_name" /bin/sh -eu -c \
		'dnf install -y --setopt=install_weak_deps=False ca-certificates coreutils-single findutils git gzip python3 shadow-utils sudo tar'
	;;
arch)
	podman exec "$container_name" /bin/sh -eu -c \
		'pacman -Syu --needed --noconfirm ca-certificates coreutils curl findutils git gzip python sudo tar'
	;;
*)
	printf 'Unsupported qualification target: %s\n' "$target_kind" >&2
	exit 2
	;;
esac

podman exec "$container_name" /bin/sh -eu -c \
	'useradd --create-home --shell /bin/bash forge; printf "forge ALL=(ALL) NOPASSWD: ALL\n" >/etc/sudoers.d/forge; chmod 0440 /etc/sudoers.d/forge'

mapfile -t exclusions < <(
	cd "$forge_root"
	uv run python - <<'PY'
from scripts.moradin_workstation import TOOL_CATALOG
for spec in TOOL_CATALOG:
    if "practical" in spec.profiles and spec.id != "make":
        print(spec.id)
PY
)
request_arguments=(
	airgap-request --profile practical --output /home/forge/REQUEST.json
)
for tool_id in "${exclusions[@]}"; do
	request_arguments+=(--exclude "$tool_id")
done
if [[ $target_kind == arch ]]; then
	request_arguments+=(
		--arch-snapshot 2026/07/01
		--approve-arch-package-inventory
	)
fi
podman exec --user forge --env HOME=/home/forge "$container_name" \
	/forge/install/tooling-suite.sh "${request_arguments[@]}" >/dev/null
podman cp "$container_name:/home/forge/REQUEST.json" "$scratch_root/REQUEST.json"

(
	cd "$forge_root"
	uv run python scripts/moradin_tooling_suite.py --forge-root "$forge_root" \
		airgap-build --request "$scratch_root/REQUEST.json" \
		--output "$scratch_root/KIT.tar.gz" >"$scratch_root/build.json"
)
bundle_digest=$(sha256sum "$scratch_root/KIT.tar.gz" | cut -d ' ' -f 1)
test "$bundle_digest" = "$(jq -r .bundle_sha256 "$scratch_root/build.json")"
podman cp "$scratch_root/KIT.tar.gz" "$container_name:/home/forge/KIT.tar.gz"
podman exec "$container_name" chown forge:forge /home/forge/KIT.tar.gz

mapfile -t networks < <(
	podman inspect --format '{{range $name, $network := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$container_name"
)
for network in "${networks[@]}"; do
	[[ -n $network ]] || continue
	podman network disconnect --force "$network" "$container_name"
done
test "$(podman inspect --format '{{len .NetworkSettings.Networks}}' "$container_name")" = 0

podman exec --user forge --env HOME=/home/forge "$container_name" \
	/forge/install/tooling-suite.sh airgap-verify \
	--bundle /home/forge/KIT.tar.gz --expected-sha256 "$bundle_digest" >/dev/null

set +e
podman exec --user forge --env HOME=/home/forge "$container_name" \
	/forge/install/tooling-suite.sh --json airgap-apply \
	--bundle /home/forge/KIT.tar.gz \
	--approve-bundle-sha256 "$bundle_digest" >"$scratch_root/preview.json"
preview_status=$?
set -e
test "$preview_status" -eq 2
plan_digest=$(jq -r .plan_sha256 "$scratch_root/preview.json")
[[ $plan_digest =~ ^[0-9a-f]{64}$ ]]

podman exec --user forge --env HOME=/home/forge "$container_name" \
	/forge/install/tooling-suite.sh airgap-apply \
	--bundle /home/forge/KIT.tar.gz \
	--approve-bundle-sha256 "$bundle_digest" \
	--approve-offline-plan-sha256 "$plan_digest" >/dev/null
podman exec --user forge --env HOME=/home/forge "$container_name" \
	/forge/install/tooling-suite.sh verify --latest >/dev/null

podman exec --user forge --env HOME=/home/forge "$container_name" /bin/bash -eu -c '
mkdir -p /home/forge/extracted /home/forge/workspace/repository
tar -xzf /home/forge/KIT.tar.gz -C /home/forge/extracted
git clone /home/forge/extracted/forge/moradins-forge-public.bundle /home/forge/offline-forge
test "$(git -C /home/forge/offline-forge rev-list --count HEAD)" = 1
git -C /home/forge/workspace/repository init
runtime=$(find /home/forge/.local/share/moradins-forge/bootstrap/python \
  -mindepth 4 -maxdepth 4 -type f -path "*/bin/python3.12" -print -quit)
test -x "$runtime"
"$runtime" /home/forge/offline-forge/scripts/moradin_forge.py explain >/dev/null
"$runtime" /home/forge/offline-forge/scripts/moradin_forge.py onboard \
  --workspace /home/forge/workspace --offline >/dev/null
receipt=$(find /home/forge/.local/state/moradins-forge/receipts \
  -mindepth 2 -maxdepth 2 -type f -name receipt.json -print | sort | tail -n 1)
test -n "$receipt"
receipt_id=$(basename "$(dirname "$receipt")")
receipt_digest=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1], encoding=\"utf-8\"))[\"receipt_sha256\"])" "$receipt")
/forge/install/tooling-suite.sh rollback --receipt "$receipt_id" \
  --approve-receipt-sha256 "$receipt_digest" >/dev/null
'

printf 'Air-gap qualification passed: %s %s\n' "$target_kind" "$target_platform"
