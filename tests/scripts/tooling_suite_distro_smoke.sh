#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	printf '%s\n' 'tooling-suite distro smoke must initialize its disposable container as root.' >&2
	exit 2
fi

os_id=$(sed -n 's/^ID=//p' /etc/os-release | head -n 1 | tr -d '"')
os_version=$(sed -n 's/^VERSION_ID=//p' /etc/os-release | head -n 1 | tr -d '"')
case $os_id in
ubuntu | debian)
	export DEBIAN_FRONTEND=noninteractive
	apt-get update
	apt-get install -y --no-install-recommends \
		ca-certificates coreutils curl findutils git passwd python3 tar util-linux
	;;
fedora)
	dnf install -y --setopt=install_weak_deps=False \
		ca-certificates coreutils curl findutils git python3 shadow-utils tar util-linux
	;;
rocky | almalinux | rhel)
	# UBI-style minimal images provide the required commands through
	# coreutils-single and curl-minimal. Preserve those valid providers instead
	# of replacing them with their mutually exclusive full-package variants.
	dnf install -y --setopt=install_weak_deps=False \
		ca-certificates findutils git python3.11 shadow-utils tar util-linux
	;;
arch)
	pacman -Syu --needed --noconfirm \
		ca-certificates coreutils curl findutils git python shadow tar util-linux
	;;
*)
	printf 'unsupported disposable smoke distribution: %s\n' "${os_id:-unknown}" >&2
	exit 2
	;;
esac

smoke_user=moradin-smoke
smoke_home=/tmp/moradin-smoke-home
useradd --create-home --home-dir "$smoke_home" --shell /bin/bash "$smoke_user"
install -d -o "$smoke_user" -g "$smoke_user" -m 0700 /tmp/moradin-suite-smoke

run_as_smoke_user() {
	runuser -u "$smoke_user" -- env \
		HOME="$smoke_home" \
		XDG_CACHE_HOME="$smoke_home/.cache" \
		XDG_DATA_HOME="$smoke_home/.local/share" \
		XDG_STATE_HOME="$smoke_home/.local/state" \
		"$@"
}

plan=/tmp/moradin-suite-smoke/plan.json
run_as_smoke_user /forge/install/tooling-suite.sh plan \
	--custom --select git --output "$plan"

python_reader=/usr/bin/python3
if [[ ! -x $python_reader && -x /usr/bin/python3.11 ]]; then
	python_reader=/usr/bin/python3.11
fi
plan_digest=$(
	"$python_reader" -c \
		'import json,sys; p=json.load(open(sys.argv[1], encoding="utf-8")); assert p["status"] == "ready" and not p["root_actions"]; print(p["plan_sha256"])' \
		"$plan"
)
run_as_smoke_user /forge/install/tooling-suite.sh apply \
	--plan "$plan" --approve-plan-sha256 "$plan_digest"
run_as_smoke_user /forge/install/tooling-suite.sh verify --latest

receipt_digest=$(
	"$python_reader" -c \
		'import glob,json,sys; p=sorted(glob.glob(sys.argv[1]))[-1]; print(json.load(open(p, encoding="utf-8"))["receipt_sha256"])' \
		"$smoke_home/.local/state/moradins-forge/receipts/*/receipt.json"
)
run_as_smoke_user /forge/install/tooling-suite.sh rollback \
	--receipt latest --approve-receipt-sha256 "$receipt_digest"

printf 'tooling-suite distro smoke passed: %s %s\n' "${os_id:-unknown}" "${os_version:-rolling}"
