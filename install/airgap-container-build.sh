#!/usr/bin/env bash
set -euo pipefail

umask 077
SAFE_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PATH=$SAFE_PATH
export PATH
unset CDPATH ENV BASH_ENV PYTHONHOME PYTHONPATH LD_LIBRARY_PATH LD_PRELOAD

request=${1:?request path is required}
output=${2:?output path is required}
forge_root=/forge

if [[ $EUID -ne 0 ]]; then
	printf '%s\n' 'The disposable rootless builder container must initialize as container root.' >&2
	exit 2
fi
if [[ ! -f $request || -L $request || -e $output ]]; then
	printf '%s\n' 'The air-gap builder request or output path is unsafe.' >&2
	exit 2
fi

os_id=$(sed -n 's/^ID=//p' /etc/os-release | head -n 1 | tr -d '"')
case $os_id in
ubuntu | debian)
	export DEBIAN_FRONTEND=noninteractive
	apt-get update
	apt-get install -y --no-install-recommends \
		apt-rdepends ca-certificates coreutils curl dpkg-dev findutils git \
		gnupg lz4 python3 tar xz-utils
	;;
fedora)
	dnf install -y --setopt=install_weak_deps=False \
		ca-certificates coreutils curl dnf-plugins-core findutils git gnupg2 \
		python3 rpm-sign tar xz
	;;
rocky | almalinux | rhel)
	dnf install -y --setopt=install_weak_deps=False \
		ca-certificates coreutils-single curl-minimal dnf-plugins-core findutils \
		git gnupg2 python3.11 rpm-sign tar xz
	if python3.11 -c 'import json,sys; p=json.load(open(sys.argv[1], encoding="utf-8")); raise SystemExit("epel" not in p.get("approved_repositories", []))' "$request"; then
		dnf install -y --setopt=install_weak_deps=False epel-release
	fi
	;;
arch)
	snapshot=${AIRGAP_ARCH_SNAPSHOT:-}
	if [[ ! $snapshot =~ ^[0-9]{4}/[0-9]{2}/[0-9]{2}$ ]]; then
		printf '%s\n' 'A frozen YYYY/MM/DD Arch snapshot is required.' >&2
		exit 2
	fi
	printf "Server = https://archive.archlinux.org/repos/%s/\$repo/os/\$arch\n" "$snapshot" \
		>/etc/pacman.d/mirrorlist
	pacman -Syu --needed --noconfirm \
		ca-certificates coreutils curl findutils git gnupg pacman-contrib python tar xz
	;;
*)
	printf 'Unsupported target builder image: %s\n' "${os_id:-unknown}" >&2
	exit 2
	;;
esac

python_path=$(command -v python3 || command -v python3.11 || true)
if [[ -z $python_path ]]; then
	printf '%s\n' 'The disposable builder could not provision Python.' >&2
	exit 2
fi

arch=$(uname -m)
case $arch in
x86_64 | amd64)
	uv_target=x86_64-unknown-linux-gnu
	uv_archive_sha=ec72570c9d1f33021aa80b176d7baba390de2cfeb1abcbefca346d563bf17484
	uv_binary_sha=56ad65c85aa2c92013807d89d2ff55579dfed03255363e6180c1cc8ca2c4ac59
	;;
aarch64 | arm64)
	uv_target=aarch64-unknown-linux-gnu
	uv_archive_sha=0ed7d20f49f6b9b60d45fdfcac28f3ac01a671a6ef08672401ed2833423fea2a
	uv_binary_sha=7191fcbd3cbdea7b24e27d9941b22149bce70f925799c4ceb16a98490df5804d
	;;
*)
	printf 'Unsupported air-gap builder architecture: %s\n' "$arch" >&2
	exit 2
	;;
esac

scratch=$(mktemp -d /tmp/moradin-airgap-builder.XXXXXXXX)
cleanup() {
	find "$scratch" -depth -delete 2>/dev/null || true
}
trap cleanup EXIT
uv_archive=$scratch/uv.tar.gz
curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
	--output "$uv_archive" \
	"https://github.com/astral-sh/uv/releases/download/0.10.12/uv-$uv_target.tar.gz"
printf '%s  %s\n' "$uv_archive_sha" "$uv_archive" | sha256sum -c - >/dev/null
mkdir -p "$scratch/uv"
tar -xzf "$uv_archive" -C "$scratch/uv" --no-same-owner --no-same-permissions
if find "$scratch/uv" -type l -print -quit | grep -q .; then
	printf '%s\n' 'The pinned uv archive unexpectedly contains symbolic links.' >&2
	exit 2
fi
mapfile -t uv_candidates < <(find "$scratch/uv" -type f -name uv -print)
if [[ ${#uv_candidates[@]} -ne 1 ]]; then
	printf '%s\n' 'The pinned uv archive has an unexpected layout.' >&2
	exit 2
fi
extracted_uv=${uv_candidates[0]}
printf '%s  %s\n' "$uv_binary_sha" "$extracted_uv" | sha256sum -c - >/dev/null
XDG_DATA_HOME=$scratch/data
export XDG_DATA_HOME
uv_root=$XDG_DATA_HOME/moradins-forge/bootstrap/uv/0.10.12
mkdir -p -- "$uv_root"
uv_path=$uv_root/uv
install -m 0755 -- "$extracted_uv" "$uv_path"

python_install=$scratch/python
UV_PYTHON_INSTALL_DIR=$python_install
export UV_PYTHON_INSTALL_DIR
"$uv_path" python install --managed-python --no-config --install-dir "$python_install" 3.12.8
managed_python=$("$uv_path" python find --no-config --no-python-downloads --python-preference only-managed 3.12.8)
if [[ ! -x $managed_python ]]; then
	printf '%s\n' 'The pinned managed Python could not be resolved.' >&2
	exit 2
fi

MORADIN_FORGE_BOOTSTRAP_UV=$uv_path
export MORADIN_FORGE_BOOTSTRAP_UV
PATH=$(dirname -- "$managed_python"):$(dirname -- "$uv_path"):$SAFE_PATH
export PATH
mkdir -p -- "$(dirname -- "$output")"

"$managed_python" "$forge_root/scripts/moradin_airgap.py" \
	_container-build --request "$request" --output "$output" --forge-root "$forge_root"

printf 'Moradin air-gap target payload complete: %s\n' "$os_id"
