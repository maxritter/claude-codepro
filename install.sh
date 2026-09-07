#!/bin/bash

set -e

case "${HOME:-}" in
/*) ;;
*)
	echo "  [!!] HOME must be an absolute path, got: '${HOME:-}'" >&2
	exit 1
	;;
esac
if [ ! -d "$HOME" ]; then
	echo "  [!!] HOME must name an existing user directory, got: '$HOME'" >&2
	exit 1
fi
HOME_CANONICAL=$(cd -- "$HOME" && pwd -P) || {
	echo "  [!!] Could not resolve HOME safely: '$HOME'" >&2
	exit 1
}
if [ "$HOME_CANONICAL" = "/" ]; then
	echo "  [!!] HOME resolves to the filesystem root; refusing to install." >&2
	exit 1
fi
HOME="$HOME_CANONICAL"
export HOME
if [ -L "$HOME/.pilot" ]; then
	echo "  [!!] ~/.pilot is a symlink; refusing installation through an untrusted root." >&2
	exit 1
fi
for override_name in CLAUDE_CONFIG_DIR CODEX_HOME; do
	eval "override_value=\${$override_name-}"
	if [ -z "$override_value" ]; then
		continue
	fi
	case "$override_value" in
	/*) ;;
	*)
		echo "  [!!] $override_name must be an absolute path, got: '$override_value'" >&2
		exit 1
		;;
	esac
	override_normalized="${override_value%/}"
	case "${override_normalized}/" in
	*"/../"* | *"/./"*)
		echo "  [!!] $override_name contains unsafe path segments: '$override_value'" >&2
		exit 1
		;;
	esac
	case "$override_normalized" in
	*"//"*)
		echo "  [!!] $override_name contains duplicate path separators: '$override_value'" >&2
		exit 1
		;;
	esac
	if [ "$override_value" = "/" ]; then
		echo "  [!!] $override_name must not be the filesystem root" >&2
		exit 1
	fi
	if [ -d "$override_value" ]; then
		override_canonical=$(cd -- "$override_value" && pwd -P) || {
			echo "  [!!] Could not resolve $override_name safely: '$override_value'" >&2
			exit 1
		}
		if [ "$override_canonical" = "/" ]; then
			echo "  [!!] $override_name resolves to the filesystem root" >&2
			exit 1
		fi
	fi
done

# Ambient uv config (e.g. ~/.config/uv/uv.toml with authenticated corporate
# indexes) must not break nested uv invocations: the downloaded wrapper's
# verification and the installer's `uv tool install` calls all inherit this.
export UV_NO_CONFIG=1

REPO="maxritter/pilot-shell"

VERSION="${VERSION:-}"
VERSION="${VERSION#v}"

INSTALLER_ARGS=""
RESTART_PILOT=false
AUTO_UPDATE=false
SKIP_VERSION_CHECK=false
USE_LOCAL_INSTALLER=false
PILOT_BIN_LIVE_DIR=""
PILOT_BIN_STAGE_DIR=""
PILOT_BIN_BACKUP_DIR=""
PILOT_BIN_LOCK_DIR=""
PILOT_BIN_ACTIVATED=false
PILOT_BIN_COMMITTED=false
PILOT_BIN_COMMIT_MARKER=""

while [ $# -gt 0 ]; do
	case "$1" in
	--restart-pilot)
		# Legacy flag from v8.x and early v9.0.x — implies auto-update and
		# auto-restart. Newer launchers pass --auto-update instead so we no
		# longer inherit a raw-mode terminal from the Rich installer.
		RESTART_PILOT=true
		AUTO_UPDATE=true
		shift
		;;
	--auto-update)
		# Skip the local-install confirm prompt without auto-restarting Pilot.
		# Called by `pilot update` in v9.0.x post-fix.
		AUTO_UPDATE=true
		shift
		;;
	--skip-version-check)
		SKIP_VERSION_CHECK=true
		shift
		;;
	--local)
		USE_LOCAL_INSTALLER=true
		SKIP_VERSION_CHECK=true
		shift
		;;
	*)
		if [ -z "$INSTALLER_ARGS" ]; then
			INSTALLER_ARGS="$1"
		else
			INSTALLER_ARGS="$INSTALLER_ARGS $1"
		fi
		shift
		;;
	esac
done

is_native_windows() {
	case "$(uname -s)" in
	MINGW* | MSYS* | CYGWIN*) return 0 ;;
	*) return 1 ;;
	esac
}

if is_native_windows; then
	echo ""
	echo "======================================================================"
	echo "  Pilot Shell — Windows Detected"
	echo "======================================================================"
	echo ""
	echo "  Pilot Shell requires a Unix environment (macOS, Linux, or WSL2)."
	echo ""
	echo "  Install WSL2 first (PowerShell as admin):"
	echo "    wsl --install -d Ubuntu"
	echo ""
	echo "  Then open Ubuntu and re-run this installer."
	echo ""
	exit 1
fi

get_latest_release() {
	local redirect_url="https://github.com/${REPO}/releases/latest"
	local api_url="https://api.github.com/repos/${REPO}/releases/latest"
	local version=""

	if command -v curl >/dev/null 2>&1; then
		local redirect_location
		redirect_location=$(curl -sIo /dev/null -w '%{redirect_url}' "$redirect_url" 2>/dev/null | tr -d '\r') || true
		if [ -n "$redirect_location" ] && [ "$redirect_location" != "%{redirect_url}" ]; then
			version=$(echo "$redirect_location" | sed -n 's|.*/releases/tag/v\([^/]*\).*|\1|p') || true
		fi
	elif command -v wget >/dev/null 2>&1; then
		local redirect_location
		redirect_location=$(wget --spider -S "$redirect_url" 2>&1 | grep -i 'location:' | tail -1 | sed 's/.*location: *//I' | tr -d '\r') || true
		if [ -n "$redirect_location" ]; then
			version=$(echo "$redirect_location" | sed -n 's|.*/releases/tag/v\([^/]*\).*|\1|p') || true
		fi
	fi

	if [ -n "$version" ]; then
		echo "$version"
		return 0
	fi

	if command -v curl >/dev/null 2>&1; then
		version=$(curl -fsSL "$api_url" 2>/dev/null | grep -m1 '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/') || true
	elif command -v wget >/dev/null 2>&1; then
		version=$(wget -qO- "$api_url" 2>/dev/null | grep -m1 '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/') || true
	fi

	if [ -n "$version" ]; then
		echo "$version"
		return 0
	fi
	return 1
}

if [ -z "$VERSION" ]; then
	echo "  [..] Fetching latest version..."
	VERSION=$(get_latest_release) || true
	if [ -z "$VERSION" ]; then
		echo "  [!!] Failed to fetch latest version from GitHub."
		echo "  [!!] Please specify a version: VERSION=6.0.0 curl ... | bash"
		exit 1
	fi
	echo "  [OK] Latest version: $VERSION"
else
	echo "  Using specified version: $VERSION"
	if [ "$SKIP_VERSION_CHECK" = true ]; then
		echo "  [..] Skipping version check (--skip-version-check)"
	fi
fi

case "$VERSION" in
dev-*)
	REPO_RAW="https://raw.githubusercontent.com/${REPO}/${VERSION}"
	;;
*)
	REPO_RAW="https://raw.githubusercontent.com/${REPO}/v${VERSION}"
	;;
esac

is_in_container() {
	[ -f "/.dockerenv" ] || [ -f "/run/.containerenv" ]
}

download_file() {
	local path="$1"
	local dest="$2"
	local url="${REPO_RAW}/${path}"

	mkdir -p "$(dirname "$dest")"
	if command -v curl >/dev/null 2>&1; then
		curl -fsSL "$url" -o "$dest"
	elif command -v wget >/dev/null 2>&1; then
		wget -q "$url" -O "$dest"
	else
		echo "Error: Neither curl nor wget found."
		exit 1
	fi
}

check_uv() {
	command -v uv >/dev/null 2>&1
}

install_uv() {
	# Vendor-managed floating endpoint - always installs the latest uv.
	# Deliberately unpinned (soft_pin): astral.sh rewrites this script on
	# every uv release, so a hard sha256 pin breaks each release (GH #147).
	# URL MUST match the uv-installer entry in installer/upstreams.yaml;
	# scripts/check_manifest_drift.py gates this in CI.
	local UV_INSTALL_URL="https://astral.sh/uv/install.sh"
	local tmp_uv
	tmp_uv="$(mktemp -t pilot-uv-install.XXXXXX.sh)" || {
		echo "  [!!] Failed to create a temporary uv installer file"
		return 1
	}
	chmod 600 "$tmp_uv" 2>/dev/null || true

	echo "  [..] Installing uv..."
	if command -v curl >/dev/null 2>&1; then
		curl -fsSL "$UV_INSTALL_URL" -o "$tmp_uv" || {
			echo "  [!!] curl failed"
			rm -f "$tmp_uv"
			return 1
		}
	elif command -v wget >/dev/null 2>&1; then
		wget -qO "$tmp_uv" "$UV_INSTALL_URL" || {
			echo "  [!!] wget failed"
			rm -f "$tmp_uv"
			return 1
		}
	else
		echo "  [!!] Need curl or wget"
		rm -f "$tmp_uv"
		return 1
	fi
	if ! sh "$tmp_uv"; then
		echo "  [!!] uv installer failed"
		rm -f "$tmp_uv"
		return 1
	fi
	rm -f "$tmp_uv"

	export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

	if ! check_uv; then
		echo "  [!!] Failed to install uv"
		return 1
	fi
	echo "  [OK] uv installed"
}

is_macos_gatekeeper_block() {
	local output="$1"
	local wrapper_path="$2"
	local so_path="$3"

	case "$output" in
	*"cannot be opened because the developer cannot be verified"* | *"is damaged and can't be opened"* | *"Killed: 9"* | *"killed: 9"*)
		return 0
		;;
	esac

	xattr -p com.apple.quarantine "$wrapper_path" >/dev/null 2>&1 ||
		xattr -p com.apple.quarantine "$so_path" >/dev/null 2>&1
}

show_macos_gatekeeper_warning() {
	echo ""
	echo "  ⚠️  macOS Gatekeeper is blocking the pilot binary"
	echo ""
	echo "  macOS still rejected the staged binary after the installer removed"
	echo "  its quarantine attributes. Your Mac may enforce an organisation profile."
	echo "  Please follow these steps to unblock it:"
	echo ""
	echo "    1. Open System Settings → Privacy & Security"
	echo "    2. Scroll down to find a message about 'pilot' being blocked"
	echo "    3. Click 'Allow Anyway'"
	echo "    4. Re-run this installer"
	echo ""
}

recover_abandoned_pilot_binary_install() {
	local pilot_home="$1"
	local bin_dir="$2"
	local backup_count=0
	local backup_dir=""
	local candidate

	for candidate in "$pilot_home"/.bin-backup.*; do
		if [ -d "$candidate" ]; then
			if [ -f "${candidate}.committed" ]; then
				if rm -rf "$candidate"; then
					rm -f "${candidate}.committed"
				fi
				continue
			fi
			backup_count=$((backup_count + 1))
			backup_dir="$candidate"
		fi
	done
	if [ "$backup_count" -gt 1 ]; then
		echo "  [!!] Multiple interrupted Pilot backups need manual recovery in $pilot_home"
		return 1
	fi
	if [ "$backup_count" -eq 1 ]; then
		PILOT_BIN_BACKUP_DIR="$backup_dir"
		PILOT_BIN_ACTIVATED=true
		if [ -e "$bin_dir" ] && ! rm -rf "$bin_dir"; then
			echo "  [!!] Failed to remove the interrupted Pilot binary"
			return 1
		fi
		PILOT_BIN_ACTIVATED=false
		if ! mv "$backup_dir" "$bin_dir"; then
			echo "  [!!] Failed to restore interrupted Pilot backup: $backup_dir"
			return 1
		fi
		PILOT_BIN_BACKUP_DIR=""
		echo "  [OK] Restored Pilot binary from an interrupted update"
	fi

	for candidate in "$pilot_home"/.bin-stage.*; do
		if [ -d "$candidate" ]; then
			rm -rf "$candidate"
		fi
	done
	for candidate in "$pilot_home"/.bin-committed-backup.*; do
		if [ -d "$candidate" ]; then
			rm -rf "$candidate" || true
		fi
	done
}

acquire_pilot_install_lock() {
	local pilot_home="$HOME/.pilot"
	local bin_dir="$pilot_home/bin"
	local lock_dir="$pilot_home/.bin-install.lock"
	local lock_pid=""

	mkdir -p "$pilot_home"
	if ! mkdir "$lock_dir" 2>/dev/null; then
		if [ -f "$lock_dir/pid" ]; then
			lock_pid=$(sed -n '1p' "$lock_dir/pid") || true
		fi
		if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
			echo "  [!!] Another Pilot install or update is already running"
			return 1
		fi
		echo "  [!!] A previous Pilot install left a stale lock: $lock_dir"
		echo "  [!!] If no installer is running, remove that directory and re-run this installer"
		return 1
	fi
	if ! printf "%s\n" "$$" >"$lock_dir/pid"; then
		echo "  [!!] Failed to initialise the Pilot install lock"
		rm -rf "$lock_dir"
		return 1
	fi

	PILOT_BIN_LIVE_DIR="$bin_dir"
	PILOT_BIN_STAGE_DIR=""
	PILOT_BIN_BACKUP_DIR=""
	PILOT_BIN_LOCK_DIR="$lock_dir"
	PILOT_BIN_ACTIVATED=false
	PILOT_BIN_COMMITTED=false
	PILOT_BIN_COMMIT_MARKER=""
	trap rollback_pilot_binary_install EXIT
	trap 'rollback_pilot_binary_install; exit 1' HUP INT TERM
	if ! recover_abandoned_pilot_binary_install "$pilot_home" "$bin_dir"; then
		rollback_pilot_binary_install
		return 1
	fi
}

rollback_pilot_binary_install() {
	trap - EXIT HUP INT TERM

	if [ "$PILOT_BIN_COMMITTED" = true ]; then
		if [ -n "$PILOT_BIN_BACKUP_DIR" ]; then
			rm -rf "$PILOT_BIN_BACKUP_DIR" || true
		fi
	else
		if [ "$PILOT_BIN_ACTIVATED" = true ] && [ -n "$PILOT_BIN_LIVE_DIR" ]; then
			rm -rf "$PILOT_BIN_LIVE_DIR"
		fi
		if [ -n "$PILOT_BIN_BACKUP_DIR" ] && [ -d "$PILOT_BIN_BACKUP_DIR" ]; then
			mv "$PILOT_BIN_BACKUP_DIR" "$PILOT_BIN_LIVE_DIR" || true
		fi
	fi
	if [ -n "$PILOT_BIN_STAGE_DIR" ] && [ -d "$PILOT_BIN_STAGE_DIR" ]; then
		rm -rf "$PILOT_BIN_STAGE_DIR"
	fi
	if [ -n "$PILOT_BIN_LOCK_DIR" ]; then
		rm -rf "$PILOT_BIN_LOCK_DIR"
	fi
	if [ -n "$PILOT_BIN_COMMIT_MARKER" ]; then
		rm -f "$PILOT_BIN_COMMIT_MARKER"
	fi

	PILOT_BIN_LIVE_DIR=""
	PILOT_BIN_STAGE_DIR=""
	PILOT_BIN_BACKUP_DIR=""
	PILOT_BIN_LOCK_DIR=""
	PILOT_BIN_ACTIVATED=false
	PILOT_BIN_COMMITTED=false
	PILOT_BIN_COMMIT_MARKER=""
}

commit_pilot_binary_install() {
	if [ -n "$PILOT_BIN_BACKUP_DIR" ]; then
		if ! touch "$PILOT_BIN_COMMIT_MARKER"; then
			echo "  [!!] Failed to mark the Pilot binary transaction as committed"
			return 1
		fi
	fi

	PILOT_BIN_COMMITTED=true
	trap - EXIT HUP INT TERM
	local backup_removed=true
	if [ -n "$PILOT_BIN_BACKUP_DIR" ] && ! rm -rf "$PILOT_BIN_BACKUP_DIR"; then
		echo "  [!!] Warning: could not remove old binary backup: $PILOT_BIN_BACKUP_DIR"
		backup_removed=false
	fi
	if [ "$backup_removed" = true ] && [ -n "$PILOT_BIN_COMMIT_MARKER" ]; then
		rm -f "$PILOT_BIN_COMMIT_MARKER"
	fi
	if [ -n "$PILOT_BIN_LOCK_DIR" ]; then
		rm -rf "$PILOT_BIN_LOCK_DIR" || true
	fi

	PILOT_BIN_LIVE_DIR=""
	PILOT_BIN_STAGE_DIR=""
	PILOT_BIN_BACKUP_DIR=""
	PILOT_BIN_LOCK_DIR=""
	PILOT_BIN_ACTIVATED=false
	PILOT_BIN_COMMITTED=false
	PILOT_BIN_COMMIT_MARKER=""
}

confirm_local_install() {
	# Name the paths this install will actually touch. With CLAUDE_CONFIG_DIR set,
	# a hardcoded "~/.claude" here would tell the user we are about to modify
	# their personal profile at the exact moment they decide whether to proceed.
	_claude_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
	_claude_app_config="${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json"
	_codex_dir="${CODEX_HOME:-$HOME/.codex}"

	echo ""
	echo "  Local installation will:"
	echo "    • Add 'pilot' and 'ccp' command to your favorite shell config (~/.bashrc, ~/.zshrc, fish)"
	echo "    • Configure Claude Code (${_claude_app_config}, ${_claude_dir}/settings.json) and Codex CLI (${_codex_dir}/config.toml) to Pilot best-practices"
	echo "    • Install additional tool dependencies via Homebrew or NPM on your system"
	if [ -n "${CLAUDE_CONFIG_DIR+x}" ]; then
		echo "    • Use CLAUDE_CONFIG_DIR: your default $HOME/.claude will NOT be modified"
	fi
	echo ""
	confirm=""
	if [ -t 0 ]; then
		printf "  Continue? [Y/n]: "
		read -r confirm
	elif [ -e /dev/tty ]; then
		printf "  Continue? [Y/n]: "
		read -r confirm </dev/tty
	else
		echo "  No interactive terminal available, continuing with defaults."
		confirm="y"
	fi
	case "$confirm" in
	[Nn] | [Nn][Oo])
		echo "  Cancelled."
		exit 0
		;;
	esac
}

download_installer() {
	local installer_dir="$HOME/.pilot/installer"

	echo "  [..] Downloading installer..."

	rm -rf "$installer_dir"
	mkdir -p "$installer_dir/installer"

	local base_url=""
	case "$VERSION" in
	dev-*) base_url="https://github.com/${REPO}/releases/download/${VERSION}" ;;
	*) base_url="https://github.com/${REPO}/releases/download/v${VERSION}" ;;
	esac
	local tree_url="${base_url}/tree.json"

	local tag_ref=""
	case "$VERSION" in
	dev-*) tag_ref="$VERSION" ;;
	*) tag_ref="v${VERSION}" ;;
	esac
	local api_url="https://api.github.com/repos/${REPO}/git/trees/${tag_ref}?recursive=true"
	local tree_json=""

	if command -v curl >/dev/null 2>&1; then
		tree_json=$(curl -fsSL "$tree_url" 2>/dev/null) || true
	elif command -v wget >/dev/null 2>&1; then
		tree_json=$(wget -qO- "$tree_url" 2>/dev/null) || true
	fi

	if [ -z "$tree_json" ]; then
		if command -v curl >/dev/null 2>&1; then
			tree_json=$(curl -fsSL "$api_url" 2>/dev/null) || true
		elif command -v wget >/dev/null 2>&1; then
			tree_json=$(wget -qO- "$api_url" 2>/dev/null) || true
		fi
	fi

	if [ -z "$tree_json" ]; then
		echo "  [!!] Failed to fetch file list from GitHub API"
		exit 1
	fi

	echo "$tree_json" | grep -oE '"path": ?"installer/[^"]*\.(py|yaml)"' | sed 's/"path": *"//g; s/"$//g' | while IFS= read -r file_path; do
		case "$file_path" in
		*__pycache__* | *dist/* | *build/* | *tests/*) continue ;;
		esac

		local dest_file="$installer_dir/$file_path"
		mkdir -p "$(dirname "$dest_file")"
		download_file "$file_path" "$dest_file"
	done

	download_file "pyproject.toml" "$installer_dir/pyproject.toml"

	echo "  [OK] Installer downloaded"
}

get_platform_suffix() {
	local os_name=""
	local arch=""

	case "$(uname -s)" in
	Linux) os_name="linux" ;;
	Darwin) os_name="darwin" ;;
	*) return 1 ;;
	esac

	case "$(uname -m)" in
	x86_64 | amd64) arch="x86_64" ;;
	arm64 | aarch64) arch="arm64" ;;
	*) return 1 ;;
	esac

	echo "${os_name}-${arch}"
}

get_local_so_name() {
	local platform_tag=""
	case "$(uname -s)" in
	Linux)
		case "$(uname -m)" in
		x86_64 | amd64) platform_tag="x86_64-linux-gnu" ;;
		arm64 | aarch64) platform_tag="aarch64-linux-gnu" ;;
		esac
		;;
	Darwin) platform_tag="darwin" ;;
	esac

	echo "pilot.cpython-312-${platform_tag}.so"
}

download_pilot_binary() {
	local pilot_home="$HOME/.pilot"
	local bin_dir="${pilot_home}/bin"
	local platform_suffix
	local so_name
	local base_url
	local stage_dir=""

	platform_suffix=$(get_platform_suffix) || {
		echo "  [!!] Unsupported platform for Pilot binary"
		return 1
	}

	so_name=$(get_local_so_name)

	case "$VERSION" in
	dev-*) base_url="https://github.com/${REPO}/releases/download/${VERSION}" ;;
	*) base_url="https://github.com/${REPO}/releases/download/v${VERSION}" ;;
	esac

	stage_dir=$(mktemp -d "${pilot_home}/.bin-stage.XXXXXX") || {
		echo "  [!!] Failed to create staging directory"
		rollback_pilot_binary_install
		return 1
	}
	PILOT_BIN_STAGE_DIR="$stage_dir"
	if ! chmod 755 "$stage_dir"; then
		echo "  [!!] Failed to prepare the staging directory"
		rollback_pilot_binary_install
		return 1
	fi

	# Preserve Pilot-managed sidecars and tool symlinks while replacing only the
	# launcher. The live bin directory is untouched until the staged CLI starts.
	if [ -d "$bin_dir" ] && ! cp -R "$bin_dir/." "$stage_dir/"; then
		echo "  [!!] Failed to stage the existing Pilot installation"
		rollback_pilot_binary_install
		return 1
	fi
	rm -f "$stage_dir/pilot" "$stage_dir"/pilot.cpython-*.so

	echo "  [..] Downloading Pilot binary (${platform_suffix})..."

	local so_url="${base_url}/pilot-${platform_suffix}.so"
	local so_path="${stage_dir}/${so_name}"

	if command -v curl >/dev/null 2>&1; then
		if ! curl -fsSL "$so_url" -o "$so_path" 2>/dev/null; then
			echo "  [!!] Failed to download pilot module"
			rollback_pilot_binary_install
			return 1
		fi
	elif command -v wget >/dev/null 2>&1; then
		if ! wget -q "$so_url" -O "$so_path" 2>/dev/null; then
			echo "  [!!] Failed to download pilot module"
			rollback_pilot_binary_install
			return 1
		fi
	else
		echo "  [!!] Neither curl nor wget is available to download the pilot module"
		rollback_pilot_binary_install
		return 1
	fi

	chmod +x "$so_path"

	local wrapper_url="${base_url}/pilot"
	local wrapper_path="${stage_dir}/pilot"

	if command -v curl >/dev/null 2>&1; then
		if ! curl -fsSL "$wrapper_url" -o "$wrapper_path" 2>/dev/null; then
			echo "  [!!] Failed to download pilot wrapper"
			rollback_pilot_binary_install
			return 1
		fi
	elif command -v wget >/dev/null 2>&1; then
		if ! wget -q "$wrapper_url" -O "$wrapper_path" 2>/dev/null; then
			echo "  [!!] Failed to download pilot wrapper"
			rollback_pilot_binary_install
			return 1
		fi
	else
		echo "  [!!] Neither curl nor wget is available to download the pilot wrapper"
		rollback_pilot_binary_install
		return 1
	fi

	chmod +x "$wrapper_path"

	echo "  [..] Verifying pilot binary..."
	local pilot_output=""
	local pilot_version=""
	if pilot_output=$("$wrapper_path" --version 2>&1); then
		pilot_version="$pilot_output"
	fi

	if [ -z "$pilot_version" ] && [ "$(uname -s)" = "Darwin" ]; then
		echo "  [..] Removing macOS quarantine attributes..."
		xattr -c "$wrapper_path" 2>/dev/null || true
		xattr -c "$so_path" 2>/dev/null || true
		spctl --add "$wrapper_path" 2>/dev/null || true
		spctl --add "$so_path" 2>/dev/null || true
		if pilot_output=$("$wrapper_path" --version 2>&1); then
			pilot_version="$pilot_output"
		fi
	fi

	if [ -z "$pilot_version" ]; then
		if [ "$(uname -s)" = "Darwin" ] && is_macos_gatekeeper_block "$pilot_output" "$wrapper_path" "$so_path"; then
			show_macos_gatekeeper_warning
		else
			echo "  [!!] Pilot binary failed to execute:"
			printf "%s\n" "$pilot_output"
		fi
		if [ -d "$bin_dir" ]; then
			echo "  [OK] Existing Pilot installation left unchanged"
		fi
		rollback_pilot_binary_install
		return 1
	fi

	local installed_version
	installed_version=$(echo "$pilot_version" | sed -n 's/.* v\([^ ]*\).*/\1/p')

	if [ -z "$installed_version" ]; then
		echo "  [!!] Could not determine pilot version"
		if [ -d "$bin_dir" ]; then
			echo "  [OK] Existing Pilot installation left unchanged"
		fi
		rollback_pilot_binary_install
		return 1
	fi
	if [ "$installed_version" != "$VERSION" ]; then
		echo "  [!!] Downloaded Pilot v${installed_version}, expected v${VERSION}"
		if [ -d "$bin_dir" ]; then
			echo "  [OK] Existing Pilot installation left unchanged"
		fi
		rollback_pilot_binary_install
		return 1
	fi

	local backup_dir=""
	if [ -d "$bin_dir" ]; then
		backup_dir=$(mktemp -d "${pilot_home}/.bin-backup.XXXXXX") || {
			echo "  [!!] Failed to prepare binary rollback"
			rollback_pilot_binary_install
			return 1
		}
		if ! rmdir "$backup_dir"; then
			echo "  [!!] Failed to prepare binary rollback"
			rollback_pilot_binary_install
			return 1
		fi
		PILOT_BIN_BACKUP_DIR="$backup_dir"
		PILOT_BIN_COMMIT_MARKER="${backup_dir}.committed"
		if ! mv "$bin_dir" "$backup_dir"; then
			echo "  [!!] Failed to preserve the current Pilot installation"
			rollback_pilot_binary_install
			return 1
		fi
	fi

	PILOT_BIN_ACTIVATED=true
	if ! mv "$stage_dir" "$bin_dir"; then
		echo "  [!!] Failed to activate the verified Pilot binary"
		rollback_pilot_binary_install
		return 1
	fi
	PILOT_BIN_STAGE_DIR=""

	echo "  [OK] Pilot binary ready (v${installed_version})"
}

run_installer() {
	local installer_dir="$HOME/.pilot/installer"

	echo ""

	export PYTHONPATH="$installer_dir:${PYTHONPATH:-}"

	local version_arg="--target-version $VERSION"
	local local_arg=""
	if [ "$USE_LOCAL_INSTALLER" = true ]; then
		local_arg="--local --local-repo-dir $(pwd)"
	fi

	local system_arg=""
	if ! is_in_container; then
		system_arg="--local-system"
	fi

	# shellcheck disable=SC2086 # These optional strings intentionally expand to multiple CLI arguments.
	uv run --python 3.12 --no-project --no-config \
		--with rich==15.0.0 --with certifi==2026.7.22 --with PyYAML==6.0.3 \
		python -m installer install $system_arg $version_arg $local_arg "$@"
}

echo ""
echo "======================================================================"
echo "  Pilot Shell Installer (v${VERSION})"
echo "======================================================================"
echo ""

if is_in_container; then
	echo "  Running inside container — skipping system dependencies"
	echo ""
elif [ "$AUTO_UPDATE" = true ]; then
	echo "  Updating local installation..."
	echo ""
elif [ "$USE_LOCAL_INSTALLER" = true ]; then
	echo "  Local installation selected (--local)"
	echo ""
	confirm_local_install
else
	confirm_local_install
fi

acquire_pilot_install_lock

echo ""
echo "Downloading Pilot Shell (v${VERSION})..."
echo ""

if check_uv; then
	echo "  [OK] uv already installed"
else
	install_uv
fi

if ! command -v git >/dev/null 2>&1; then
	case "$(uname -s)" in
	Linux)
		if command -v dnf >/dev/null 2>&1; then
			echo "  [..] Installing git (required by Homebrew)..."
			sudo dnf install -y git && echo "  [OK] git installed" ||
				echo "  [!!] Failed to install git via dnf"
		elif command -v yum >/dev/null 2>&1; then
			echo "  [..] Installing git (required by Homebrew)..."
			sudo yum install -y git && echo "  [OK] git installed" ||
				echo "  [!!] Failed to install git via yum"
		elif command -v apt-get >/dev/null 2>&1; then
			echo "  [..] Installing git (required by Homebrew)..."
			sudo apt-get update -qq && sudo apt-get install -y git &&
				echo "  [OK] git installed" ||
				echo "  [!!] Failed to install git via apt"
		fi
		;;
	esac
fi

if [ "$USE_LOCAL_INSTALLER" = true ]; then
	if [ -d "installer" ] && [ -f "pyproject.toml" ]; then
		echo "  [OK] Using local installer from current directory"
		rm -rf "$HOME/.pilot/installer"
		mkdir -p "$HOME/.pilot/installer"
		ln -sf "$(pwd)/installer" "$HOME/.pilot/installer/installer"
		ln -sf "$(pwd)/pyproject.toml" "$HOME/.pilot/installer/pyproject.toml"
	else
		echo "  [!!] --local requires running from pilot-shell repo root"
		echo "  [!!] Missing: installer/ directory or pyproject.toml"
		exit 1
	fi
else
	download_installer
fi
download_pilot_binary

# shellcheck disable=SC2086 # Preserve the legacy pass-through of multiple installer arguments.
if run_installer $INSTALLER_ARGS; then
	commit_pilot_binary_install
else
	echo "  [!!] Installer failed; restoring the previous Pilot binary"
	rollback_pilot_binary_install
	exit 1
fi

if [ "$RESTART_PILOT" = true ]; then
	PILOT_BIN="$HOME/.pilot/bin/pilot"
	if [ -x "$PILOT_BIN" ]; then
		echo ""
		echo "  Restarting Pilot Shell..."
		echo ""
		exec "$PILOT_BIN" --skip-update-check
	fi
fi
