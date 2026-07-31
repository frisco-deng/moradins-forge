#!/usr/bin/env bash
set -euo pipefail

umask 077
SAFE_SYSTEM_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
FORGE_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd -P)
USER_BIN=${HOME:?}/.local/bin
PATH=$SAFE_SYSTEM_PATH
export PATH
unset CDPATH ENV BASH_ENV PYTHONHOME PYTHONPATH MORADIN_FORGE_BOOTSTRAP_UV
unset CURL_CA_BUNDLE GIT_SSL_CAINFO LD_LIBRARY_PATH LD_PRELOAD REQUESTS_CA_BUNDLE
unset SSL_CERT_DIR SSL_CERT_FILE
unset UV_ARCHIVE_TEMP UV_SCRATCH_DIR

UV_BOOTSTRAP_VERSION=0.10.12
UV_AMD64_SHA256=ec72570c9d1f33021aa80b176d7baba390de2cfeb1abcbefca346d563bf17484
UV_ARM64_SHA256=0ed7d20f49f6b9b60d45fdfcac28f3ac01a671a6ef08672401ed2833423fea2a
UV_AMD64_BINARY_SHA256=56ad65c85aa2c92013807d89d2ff55579dfed03255363e6180c1cc8ca2c4ac59
UV_ARM64_BINARY_SHA256=7191fcbd3cbdea7b24e27d9941b22149bce70f925799c4ceb16a98490df5804d

if [[ $EUID -eq 0 ]]; then
	printf '%s\n' 'Run this installer as the target user, not as root.' >&2
	exit 2
fi

confirm() {
	local prompt=${1:?}
	local response
	if [[ ! -t 0 ]]; then
		return 1
	fi
	read -r -p "$prompt [y/N] " response || return 1
	[[ $response == y || $response == Y || $response == yes || $response == YES ]]
}

cleanup_uv_stage() {
	if [[ -n ${UV_ARCHIVE_TEMP:-} && -f $UV_ARCHIVE_TEMP && ! -L $UV_ARCHIVE_TEMP ]]; then
		find "$UV_ARCHIVE_TEMP" -maxdepth 0 -delete
	fi
	if [[ -n ${UV_SCRATCH_DIR:-} && -d $UV_SCRATCH_DIR && ! -L $UV_SCRATCH_DIR ]]; then
		find "$UV_SCRATCH_DIR" -depth -delete
	fi
}

find_python() {
	local candidate resolved owner permissions
	for candidate in /usr/bin/python3.12 /usr/bin/python3.11 /usr/bin/python3; do
		[[ -x $candidate ]] || continue
		resolved=$(readlink -f -- "$candidate")
		owner=$(stat -c '%u' -- "$resolved")
		permissions=$(stat -c '%a' -- "$resolved")
		permissions=${permissions: -3}
		if [[ $owner == 0 ]] && (((8#$permissions & 8#022) == 0)) &&
			"$resolved" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
			printf '%s\n' "$resolved"
			return 0
		fi
	done
	return 1
}

install_bootstrap_prerequisites() {
	local os_id id_like manager python_package
	local -a bootstrap_packages
	bootstrap_packages=()
	os_id=$(sed -n 's/^ID=//p' /etc/os-release | head -n 1 | tr -d '"')
	id_like=$(sed -n 's/^ID_LIKE=//p' /etc/os-release | head -n 1 | tr -d '"')
	manager=
	python_package=python3
	if [[ $os_id == ubuntu || $os_id == debian || $id_like == *debian* ]]; then
		manager=apt
	elif [[ $os_id == fedora || $os_id == rhel || $os_id == rocky ||
		$os_id == almalinux || $id_like == *rhel* || $id_like == *fedora* ]]; then
		manager=dnf
	elif [[ $os_id == arch || $id_like == *arch* ]]; then
		manager=pacman
		python_package=python
	fi
	if [[ -z $manager ]]; then
		printf '%s\n' 'Cannot bootstrap prerequisites on this Linux distribution.' >&2
		exit 2
	fi
	if ! find_python >/dev/null 2>&1; then
		case $manager in
		apt)
			if apt-cache policy python3.12 2>/dev/null | grep -q 'Candidate: [^(]'; then
				python_package=python3.12
			elif apt-cache policy python3.11 2>/dev/null | grep -q 'Candidate: [^(]'; then
				python_package=python3.11
			fi
			;;
		dnf)
			if dnf --quiet repoquery --latest-limit 1 python3.12 >/dev/null 2>&1; then
				python_package=python3.12
			elif dnf --quiet repoquery --latest-limit 1 python3.11 >/dev/null 2>&1; then
				python_package=python3.11
			fi
			;;
		esac
		bootstrap_packages+=("$python_package")
	fi
	command -v curl >/dev/null 2>&1 || bootstrap_packages+=(curl)
	command -v tar >/dev/null 2>&1 || bootstrap_packages+=(tar)
	command -v sha256sum >/dev/null 2>&1 || bootstrap_packages+=(coreutils)
	if [[ ! -r /etc/ssl/certs/ca-certificates.crt &&
		! -r /etc/pki/tls/certs/ca-bundle.crt ]]; then
		bootstrap_packages+=(ca-certificates)
	fi
	if [[ ${#bootstrap_packages[@]} -eq 0 ]]; then
		return 0
	fi
	printf 'Exact bootstrap packages:'
	printf ' %q' "${bootstrap_packages[@]}"
	printf '\n'
	printf 'Signed package-manager transaction: %s\n' "$manager"
	if ! confirm 'Allow this minimal prerequisite transaction through sudo?'; then
		printf '%s\n' 'Bootstrap prerequisite installation was not approved.' >&2
		exit 2
	fi
	case $manager in
	apt)
		sudo -- /usr/bin/env -i PATH="$SAFE_SYSTEM_PATH" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
			apt-get update
		sudo -- /usr/bin/env -i PATH="$SAFE_SYSTEM_PATH" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
			apt-get install -y --no-install-recommends -- "${bootstrap_packages[@]}"
		;;
	dnf)
		sudo -- /usr/bin/env -i PATH="$SAFE_SYSTEM_PATH" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
			dnf install -y --setopt=install_weak_deps=False -- "${bootstrap_packages[@]}"
		;;
	pacman)
		printf '%s\n' 'Arch requires a complete synchronized transaction; no partial upgrade is used.'
		if ! confirm 'Approve pacman -Syu for the bootstrap prerequisites?'; then
			printf '%s\n' 'Arch synchronization was not approved.' >&2
			exit 2
		fi
		sudo -- /usr/bin/env -i PATH="$SAFE_SYSTEM_PATH" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
			pacman -Syu --needed --noconfirm -- "${bootstrap_packages[@]}"
		;;
	esac
}

stage_uv() {
	local arch target sha256 binary_sha256 url scratch extracted install_root archive cached
	arch=$(uname -m)
	case $arch in
	x86_64 | amd64)
		target=x86_64-unknown-linux-gnu
		sha256=$UV_AMD64_SHA256
		binary_sha256=$UV_AMD64_BINARY_SHA256
		;;
	aarch64 | arm64)
		target=aarch64-unknown-linux-gnu
		sha256=$UV_ARM64_SHA256
		binary_sha256=$UV_ARM64_BINARY_SHA256
		;;
	*)
		printf 'Unsupported bootstrap architecture: %s\n' "$arch" >&2
		exit 2
		;;
	esac
	if ! command -v tar >/dev/null 2>&1 || ! command -v sha256sum >/dev/null 2>&1; then
		install_bootstrap_prerequisites
	fi
	url="https://github.com/astral-sh/uv/releases/download/$UV_BOOTSTRAP_VERSION/uv-$target.tar.gz"
	install_root=${XDG_DATA_HOME:-$HOME/.local/share}/moradins-forge/bootstrap/uv/$UV_BOOTSTRAP_VERSION
	mkdir -p -- "$install_root"
	archive=$install_root/uv-$target.tar.gz
	cached=false
	if [[ ! -L $archive && -f $archive ]] &&
		printf '%s  %s\n' "$sha256" "$archive" | sha256sum -c - >/dev/null 2>&1; then
		cached=true
	fi
	if [[ $cached != true ]]; then
		if ! command -v curl >/dev/null 2>&1; then
			install_bootstrap_prerequisites
		fi
		UV_ARCHIVE_TEMP=$(mktemp "$install_root/.uv-archive.XXXXXXXX")
		trap cleanup_uv_stage EXIT
		curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
			--output "$UV_ARCHIVE_TEMP" "$url"
		printf '%s  %s\n' "$sha256" "$UV_ARCHIVE_TEMP" | sha256sum -c - >/dev/null
		mv -f -- "$UV_ARCHIVE_TEMP" "$archive"
		UV_ARCHIVE_TEMP=
	fi
	scratch=$(mktemp -d "${TMPDIR:-/tmp}/moradin-uv.XXXXXXXX")
	UV_SCRATCH_DIR=$scratch
	trap cleanup_uv_stage EXIT
	mkdir -p -- "$scratch/extract"
	tar -xzf "$archive" -C "$scratch/extract" --no-same-owner --no-same-permissions
	if find "$scratch/extract" -type l -print -quit | grep -q .; then
		printf '%s\n' 'The verified uv archive unexpectedly contains symbolic links.' >&2
		exit 2
	fi
	mapfile -t uv_candidates < <(find "$scratch/extract" -type f -name uv -print)
	if [[ ${#uv_candidates[@]} -ne 1 ]]; then
		printf '%s\n' 'The verified uv archive has an unexpected layout.' >&2
		exit 2
	fi
	extracted=${uv_candidates[0]}
	printf '%s  %s\n' "$binary_sha256" "$extracted" | sha256sum -c - >/dev/null
	install -m 0755 -- "$extracted" "$install_root/uv.new"
	mv -f -- "$install_root/uv.new" "$install_root/uv"
	cleanup_uv_stage
	trap - EXIT
	printf '%s\n' "$install_root/uv"
}

run_suite() {
	local -a arguments
	local argument command_name help_requested skip_option_value uv_path python_path
	arguments=("$@")
	if [[ ${#arguments[@]} -eq 0 ]]; then
		arguments=(interactive)
	fi
	help_requested=false
	command_name=
	skip_option_value=false
	for argument in "${arguments[@]}"; do
		if [[ $skip_option_value == true ]]; then
			skip_option_value=false
			continue
		fi
		if [[ $argument == -h || $argument == --help ]]; then
			help_requested=true
			continue
		fi
		if [[ -n $command_name ]]; then
			continue
		fi
		case $argument in
		--forge-root)
			skip_option_value=true
			;;
		--forge-root=* | --json) ;;
		-*) ;;
		*)
			command_name=$argument
			;;
		esac
	done
	python_path=$(find_python || true)
	if [[ -z $python_path ]]; then
		if [[ ! -t 0 ]]; then
			printf '%s\n' 'Python 3.11+ is required; non-interactive mode will not install prerequisites.' >&2
			exit 2
		fi
		install_bootstrap_prerequisites
		python_path=$(find_python || true)
		if [[ -z $python_path ]]; then
			printf '%s\n' 'The signed system Python is older than 3.11; this host fails closed.' >&2
			exit 2
		fi
	fi
	uv_path=
	case $command_name in
	interactive | plan | apply)
		if [[ $help_requested != true ]]; then
			printf '%s\n' "Staging checksum-verified uv $UV_BOOTSTRAP_VERSION for Forge planning and user-tool isolation." >&2
			uv_path=$(stage_uv)
			MORADIN_FORGE_BOOTSTRAP_UV=$uv_path
			export MORADIN_FORGE_BOOTSTRAP_UV
			PATH=$USER_BIN:$(dirname -- "$uv_path"):$SAFE_SYSTEM_PATH
			export PATH
		fi
		;;
	*)
		PATH=$USER_BIN:$SAFE_SYSTEM_PATH
		export PATH
		;;
	esac
	exec "$python_path" "$FORGE_ROOT/scripts/moradin_tooling_suite.py" \
		--forge-root "$FORGE_ROOT" "${arguments[@]}"
}

run_suite "$@"
