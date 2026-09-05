#!/usr/bin/env bash
set -euo pipefail

umask 077
uv_command=$(command -v uv || true)
if [[ -z $uv_command ]]; then
	printf '%s\n' 'Air-gap qualification requires the workflow-provided uv binary.' >&2
	exit 2
fi
uv_command=$(readlink -f -- "$uv_command")
if [[ ! -f $uv_command || ! -x $uv_command ]]; then
	printf '%s\n' 'Air-gap qualification resolved an unsafe uv binary.' >&2
	exit 2
fi
SAFE_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PATH=$SAFE_PATH:${HOME:?}/.local/bin
export PATH

forge_root=${FORGE_ROOT:-$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd -P)}
target_image=${TARGET_IMAGE:?TARGET_IMAGE is required}
target_platform=${TARGET_PLATFORM:?TARGET_PLATFORM is required}
target_kind=${TARGET_KIND:?TARGET_KIND is required}
arch_snapshot=2026/07/31
scratch_root=$(mktemp -d "${RUNNER_TEMP:-/tmp}/moradin-airgap-qualification.XXXXXXXX")
container_name=moradin-airgap-${target_kind}-${target_platform##*/}-$$
consumer_home=/var/lib/moradin-consumer

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
		'export DEBIAN_FRONTEND=noninteractive; apt-get update -qq; apt-get install -qq -y --no-install-recommends ca-certificates coreutils curl findutils git gzip python3 sudo tar >/dev/null'
	;;
fedora)
	podman exec "$container_name" /bin/sh -eu -c \
		'dnf -q install -y --setopt=install_weak_deps=False ca-certificates coreutils curl findutils git gzip python3 shadow-utils sudo tar >/dev/null'
	;;
rocky)
	podman exec "$container_name" /bin/sh -eu -c \
		'dnf -q install -y --setopt=install_weak_deps=False ca-certificates coreutils-single findutils git gzip python3 shadow-utils sudo tar >/dev/null'
	;;
arch)
	podman exec --env ARCH_SNAPSHOT="$arch_snapshot" "$container_name" /bin/sh -eu -c \
		'printf "Server = https://archive.archlinux.org/repos/%s/\$repo/os/\$arch\n" "$ARCH_SNAPSHOT" >/etc/pacman.d/mirrorlist; pacman -Syyuu --needed --noconfirm --quiet ca-certificates coreutils curl findutils git gzip python sudo tar >/dev/null'
	;;
*)
	printf 'Unsupported qualification target: %s\n' "$target_kind" >&2
	exit 2
	;;
esac

podman exec "$container_name" useradd --create-home --home-dir "$consumer_home" \
	--shell /bin/bash forge
# Some rootless CI runners cannot expose shadow metadata to setuid sudo. This
# disposable PAM service represents the test operator's explicit acceptance.
podman exec "$container_name" /bin/sh -eu -c \
	'printf "%s\n" "#%PAM-1.0" "auth required pam_permit.so" "account required pam_permit.so" "password required pam_permit.so" "session required pam_permit.so" >/etc/pam.d/moradin-forge-ci; chmod 0644 /etc/pam.d/moradin-forge-ci; printf "%s\n" "Defaults:forge pam_service=moradin-forge-ci" "forge ALL=(ALL) NOPASSWD: ALL" >/etc/sudoers.d/forge; chmod 0440 /etc/sudoers.d/forge'
podman exec "$container_name" /bin/sh -eu -c \
	'visudo -cf /etc/sudoers >/dev/null'
podman exec --user forge --env HOME="$consumer_home" "$container_name" \
	sudo -n -v

mapfile -t exclusions < <(
	cd "$forge_root"
	"$uv_command" run python - <<'PY'
from scripts.moradin_workstation import TOOL_CATALOG
for spec in TOOL_CATALOG:
    if "practical" in spec.profiles and spec.id != "make":
        print(spec.id)
PY
)
request_arguments=(
	airgap-request --profile practical --output "$consumer_home/REQUEST.json"
)
for tool_id in "${exclusions[@]}"; do
	request_arguments+=(--exclude "$tool_id")
done
if [[ $target_kind == arch ]]; then
	request_arguments+=(
		--arch-snapshot "$arch_snapshot"
		--approve-arch-package-inventory
	)
fi
podman exec --user forge --env HOME="$consumer_home" "$container_name" \
	/forge/install/tooling-suite.sh "${request_arguments[@]}" >/dev/null
podman cp "$container_name:$consumer_home/REQUEST.json" "$scratch_root/REQUEST.json"

(
	cd "$forge_root"
	"$uv_command" run python scripts/moradin_tooling_suite.py --forge-root "$forge_root" \
		airgap-build --request "$scratch_root/REQUEST.json" \
		--output "$scratch_root/KIT.tar.gz" >"$scratch_root/build.json"
)
bundle_digest=$(sha256sum "$scratch_root/KIT.tar.gz" | cut -d ' ' -f 1)
test "$bundle_digest" = "$(jq -r .bundle_sha256 "$scratch_root/build.json")"
podman cp "$scratch_root/KIT.tar.gz" "$container_name:$consumer_home/KIT.tar.gz"
podman exec "$container_name" chown forge:forge "$consumer_home/KIT.tar.gz"

mapfile -t networks < <(
	podman inspect --format '{{range $name, $network := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$container_name"
)
for network in "${networks[@]}"; do
	[[ -n $network ]] || continue
	podman network disconnect --force "$network" "$container_name"
done
test "$(podman inspect --format '{{len .NetworkSettings.Networks}}' "$container_name")" = 0

podman exec --user forge --env HOME="$consumer_home" "$container_name" \
	/forge/install/tooling-suite.sh airgap-verify \
	--bundle "$consumer_home/KIT.tar.gz" --expected-sha256 "$bundle_digest" >/dev/null

set +e
podman exec --user forge --env HOME="$consumer_home" "$container_name" \
	/forge/install/tooling-suite.sh --json airgap-apply \
	--bundle "$consumer_home/KIT.tar.gz" \
	--approve-bundle-sha256 "$bundle_digest" >"$scratch_root/preview.json"
preview_status=$?
set -e
test "$preview_status" -eq 2
plan_digest=$(jq -r .plan_sha256 "$scratch_root/preview.json")
[[ $plan_digest =~ ^[0-9a-f]{64}$ ]]

# Keep the CI stand-in for explicit human sudo acceptance and the sealed apply
# in one exec session so distributions with ppid-scoped timestamps behave alike.
podman exec --user forge --env HOME="$consumer_home" "$container_name" \
	/bin/bash -eu -c '
sudo -n -v
exec /forge/install/tooling-suite.sh airgap-apply \
  --bundle "$1" \
  --approve-bundle-sha256 "$2" \
  --approve-offline-plan-sha256 "$3"
' bash "$consumer_home/KIT.tar.gz" "$bundle_digest" "$plan_digest" >/dev/null
podman exec --user forge --env HOME="$consumer_home" "$container_name" \
	/forge/install/tooling-suite.sh verify --latest >/dev/null

podman exec --user forge --env HOME="$consumer_home" "$container_name" /bin/bash -eu -c '
mkdir -p "$HOME/extracted" "$HOME/workspace/repository"
tar -xzf "$HOME/KIT.tar.gz" -C "$HOME/extracted"
git clone --quiet "$HOME/extracted/forge/moradins-forge-public.bundle" "$HOME/offline-forge"
test "$(git -C "$HOME/offline-forge" rev-list --count HEAD)" = 1
git -C "$HOME/workspace/repository" init --quiet --initial-branch=main
runtime=$(find "$HOME/.local/share/moradins-forge/bootstrap/python" \
  -mindepth 4 -maxdepth 4 -type f -path "*/bin/python3.12" -print -quit)
test -x "$runtime"
"$runtime" "$HOME/offline-forge/scripts/moradin_forge.py" explain >/dev/null
"$runtime" "$HOME/offline-forge/scripts/moradin_forge.py" onboard \
  --workspace "$HOME/workspace" --offline >/dev/null
receipt=$(find "$HOME/.local/state/moradins-forge/receipts" \
  -mindepth 2 -maxdepth 2 -type f -name receipt.json -print | sort | tail -n 1)
test -n "$receipt"
receipt_id=$(basename "$(dirname "$receipt")")
receipt_digest=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1], encoding=\"utf-8\"))[\"receipt_sha256\"])" "$receipt")
/forge/install/tooling-suite.sh rollback --receipt "$receipt_id" \
  --approve-receipt-sha256 "$receipt_digest" >/dev/null
'

printf 'Air-gap qualification passed: %s %s\n' "$target_kind" "$target_platform"
