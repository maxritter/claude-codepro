#!/bin/bash

set -e

DEFAULT_VERSION="5.2.4"
VERSION="$DEFAULT_VERSION"

REPO="maxritter/claude-codepro"

INSTALL_DEV=false
INSTALL_VERSION=""
INSTALLER_ARGS=""

while [ $# -gt 0 ]; do
	case "$1" in
	--dev)
		INSTALL_DEV=true
		shift
		;;
	--version)
		INSTALL_VERSION="$2"
		shift 2
		;;
	--version=*)
		INSTALL_VERSION="${1#*=}"
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

get_latest_prerelease() {
	local api_url="https://api.github.com/repos/${REPO}/releases"
	local releases=""

	if command -v curl >/dev/null 2>&1; then
		releases=$(curl -fsSL "$api_url" 2>/dev/null) || true
	elif command -v wget >/dev/null 2>&1; then
		releases=$(wget -qO- "$api_url" 2>/dev/null) || true
	fi

	if [ -z "$releases" ]; then
		return 1
	fi

	echo "$releases" | tr ',' '\n' | grep -E '"(tag_name|created_at)"' | paste - - |
		grep 'dev-' | sed 's/.*"tag_name"[^"]*"\([^"]*\)".*"created_at"[^"]*"\([^"]*\)".*/\2|\1/' |
		sort -t'|' -k1 -r | head -1 | cut -d'|' -f2
}

if [ "$INSTALL_DEV" = true ]; then
	echo "  [..] Fetching latest dev pre-release..."
	VERSION=$(get_latest_prerelease)
	if [ -z "$VERSION" ]; then
		echo "  [!!] No dev pre-release found. Create a PR from dev to main first."
		exit 1
	fi
	echo "  [OK] Found dev version: $VERSION"
elif [ -n "$INSTALL_VERSION" ]; then
	VERSION="$INSTALL_VERSION"
	echo "  Using specified version: $VERSION"
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

get_saved_install_mode() {
	local config_file=".claude/config/ccp-config.json"
	if [ -f "$config_file" ]; then
		sed -n 's/.*"install_mode"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$config_file" 2>/dev/null
	fi
}

save_install_mode() {
	local mode="$1"
	local config_file=".claude/config/ccp-config.json"
	mkdir -p "$(dirname "$config_file")"
	if [ -f "$config_file" ]; then
		if grep -q '"install_mode"' "$config_file"; then
			sed -i.bak "s/\"install_mode\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"install_mode\": \"$mode\"/" "$config_file"
		else
			sed -i.bak 's/^{$/{\
  "install_mode": "'"$mode"'",/' "$config_file"
		fi
		rm -f "${config_file}.bak"
	else
		echo "{\"install_mode\": \"$mode\"}" >"$config_file"
	fi
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
	echo "  [..] Installing uv..."
	if command -v curl >/dev/null 2>&1; then
		curl -LsSf https://astral.sh/uv/install.sh | sh
	elif command -v wget >/dev/null 2>&1; then
		wget -qO- https://astral.sh/uv/install.sh | sh
	fi

	export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

	if ! check_uv; then
		echo "  [!!] Failed to install uv"
		exit 1
	fi
	echo "  [OK] uv installed"
}

show_macos_gatekeeper_warning() {
	echo ""
	echo "  ⚠️  macOS Gatekeeper is blocking the CCP binary"
	echo ""
	echo "  The installer requires CCP to verify your license."
	echo "  Please follow these steps to unblock it:"
	echo ""
	echo "    1. Open System Settings → Privacy & Security"
	echo "    2. Scroll down to find a message about 'ccp' being blocked"
	echo "    3. Click 'Allow Anyway'"
	echo "    4. Re-run this installer"
	echo ""
	echo "  Or run this command to remove the quarantine flag:"
	echo "    xattr -cr $PWD/.claude/bin"
	echo ""
}

confirm_local_install() {
	echo ""
	echo "  Local installation will:"
	echo "    • Install Homebrew packages: python, node, nvm, pnpm, bun, uv, go, gopls, git, gh"
	echo "    • Add 'ccp' command to your shell config (~/.bashrc, ~/.zshrc, fish)"
	echo "    • Configure Claude Code (~/.claude.json) according to CCP best-practices"
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
		echo "  Cancelled. Run again to choose Dev Container instead."
		exit 0
		;;
	esac
}

setup_devcontainer() {
	if [ -d ".devcontainer" ]; then
		echo "  [OK] .devcontainer already exists"
	else
		echo "  [..] Downloading dev container configuration..."
		download_file ".devcontainer/Dockerfile" ".devcontainer/Dockerfile"
		download_file ".devcontainer/devcontainer.json" ".devcontainer/devcontainer.json"

		PROJECT_NAME="$(basename "$(pwd)")"
		PROJECT_SLUG="$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | tr ' _' '-')"
		if [ -f ".devcontainer/devcontainer.json" ]; then
			sed -i.bak 's/"claude-codepro"/"'"${PROJECT_SLUG}"'"/g' ".devcontainer/devcontainer.json"
			sed -i.bak 's|/workspaces/claude-codepro|/workspaces/'"${PROJECT_SLUG}"'|g' ".devcontainer/devcontainer.json"
			rm -f ".devcontainer/devcontainer.json.bak"
		fi

		echo "  [OK] Dev container configuration installed"
	fi

	if [ ! -f ".vscode/extensions.json" ]; then
		echo "  [..] Downloading VS Code extensions recommendations..."
		download_file ".vscode/extensions.json" ".vscode/extensions.json"
		echo "  [OK] VS Code extensions recommendations installed"
	else
		echo "  [OK] .vscode/extensions.json already exists"
	fi

	echo ""
	echo "  Next steps:"
	echo "    1. Open this folder in VS Code"
	echo "    2. Install the 'Dev Containers' extension"
	echo "    3. Press Cmd+Shift+P (Mac) or Ctrl+Shift+P (Windows/Linux)"
	echo "    4. Run: 'Dev Containers: Reopen in Container'"
	echo "    5. Once inside the container, run this installer again"
	echo ""
	echo "======================================================================"
	echo ""
	exit 0
}

download_installer() {
	local installer_dir=".claude/installer"

	echo "  [..] Downloading installer..."

	rm -rf "$installer_dir"
	mkdir -p "$installer_dir/installer"

	local tag_ref=""
	case "$VERSION" in
	dev-*) tag_ref="$VERSION" ;;
	*) tag_ref="v${VERSION}" ;;
	esac
	local api_url="https://api.github.com/repos/${REPO}/git/trees/${tag_ref}?recursive=true"
	local tree_json=""

	if command -v curl >/dev/null 2>&1; then
		tree_json=$(curl -fsSL "$api_url" 2>/dev/null) || true
	elif command -v wget >/dev/null 2>&1; then
		tree_json=$(wget -qO- "$api_url" 2>/dev/null) || true
	fi

	if [ -z "$tree_json" ]; then
		echo "  [!!] Failed to fetch file list from GitHub API"
		exit 1
	fi

	echo "$tree_json" | grep -oE '"path": ?"installer/[^"]*\.py"' | sed 's/"path": *"//g; s/"$//g' | while IFS= read -r file_path; do
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

	echo "ccp.cpython-312-${platform_tag}.so"
}

download_ccp_binary() {
	local bin_dir=".claude/bin"
	local platform_suffix
	local so_name
	local base_url

	platform_suffix=$(get_platform_suffix) || {
		echo "  [!!] Unsupported platform for CCP binary"
		return 1
	}

	so_name=$(get_local_so_name)

	case "$VERSION" in
	dev-*) base_url="https://github.com/${REPO}/releases/download/${VERSION}" ;;
	*) base_url="https://github.com/${REPO}/releases/download/v${VERSION}" ;;
	esac

	if [ -d "$bin_dir" ]; then
		rm -rf "$bin_dir"
	fi
	mkdir -p "$bin_dir"

	echo "  [..] Downloading CCP binary (${platform_suffix})..."

	local so_url="${base_url}/ccp-${platform_suffix}.so"
	local so_path="${bin_dir}/${so_name}"

	if command -v curl >/dev/null 2>&1; then
		if ! curl -fsSL "$so_url" -o "$so_path" 2>/dev/null; then
			echo "  [!!] Failed to download CCP module"
			return 1
		fi
	elif command -v wget >/dev/null 2>&1; then
		if ! wget -q "$so_url" -O "$so_path" 2>/dev/null; then
			echo "  [!!] Failed to download CCP module"
			return 1
		fi
	fi

	chmod +x "$so_path"

	local wrapper_url="${base_url}/ccp"
	local wrapper_path="${bin_dir}/ccp"

	if command -v curl >/dev/null 2>&1; then
		if ! curl -fsSL "$wrapper_url" -o "$wrapper_path" 2>/dev/null; then
			echo "  [!!] Failed to download CCP wrapper"
			rm -f "$so_path"
			return 1
		fi
	elif command -v wget >/dev/null 2>&1; then
		if ! wget -q "$wrapper_url" -O "$wrapper_path" 2>/dev/null; then
			echo "  [!!] Failed to download CCP wrapper"
			rm -f "$so_path"
			return 1
		fi
	fi

	chmod +x "$wrapper_path"

	echo "  [..] Verifying CCP binary..."
	local ccp_version
	ccp_version=$("$wrapper_path" --version 2>/dev/null) || true

	if [ -z "$ccp_version" ] && [ "$(uname -s)" = "Darwin" ]; then
		echo "  [..] Removing macOS quarantine attributes..."
		xattr -cr "$bin_dir" 2>/dev/null || true
		spctl --add "$wrapper_path" 2>/dev/null || true
		spctl --add "$so_path" 2>/dev/null || true
		ccp_version=$("$wrapper_path" --version 2>/dev/null) || true
	fi

	if [ -z "$ccp_version" ]; then
		if [ "$(uname -s)" = "Darwin" ]; then
			show_macos_gatekeeper_warning
			exit 1
		else
			echo "  [!!] CCP binary failed to execute"
			return 1
		fi
	fi

	# Extract version (handles both "v5.2.2" and "vdev-xxx" formats)
	local installed_version
	installed_version=$(echo "$ccp_version" | sed -n 's/.*CodePro v\(.*\)/\1/p')

	if [ -z "$installed_version" ]; then
		echo "  [!!] Could not determine CCP version"
		return 1
	fi

	echo "  [OK] CCP binary ready (v${installed_version})"
}

run_installer() {
	local installer_dir=".claude/installer"
	local saved_mode
	saved_mode=$(get_saved_install_mode)

	echo ""

	export PYTHONPATH="$installer_dir:${PYTHONPATH:-}"

	local version_arg=""
	if [ -n "$VERSION" ] && [ "$VERSION" != "$DEFAULT_VERSION" ]; then
		version_arg="--target-version $VERSION"
	fi

	if ! is_in_container && [ "$saved_mode" = "local" ]; then
		uv run --python 3.12 --no-project --with rich \
			python -m installer install --local-system $version_arg "$@"
	else
		uv run --python 3.12 --no-project --with rich \
			python -m installer install $version_arg "$@"
	fi
}

if ! is_in_container; then
	echo ""
	echo "======================================================================"
	echo "  Claude CodePro Installer (v${VERSION})"
	echo "======================================================================"
	echo ""

	if [ -d ".devcontainer" ]; then
		echo "  Detected existing .devcontainer - using Dev Container mode."
		echo ""
		setup_devcontainer
	fi

	saved_mode=$(get_saved_install_mode)
	if [ "$saved_mode" = "local" ]; then
		echo "  Using saved preference: Local Installation"
		echo ""
	elif [ "$saved_mode" = "container" ]; then
		echo "  Using saved preference: Dev Container"
		echo ""
		setup_devcontainer
	else
		echo "  Choose installation method:"
		echo ""
		echo "    1) Dev Container - Isolated, pre-configured environment (RECOMMENDED)"
		echo "    2) Local - Install directly on your system (requires Homebrew)"
		echo ""

		choice=""
		if [ -t 0 ]; then
			printf "  Enter choice [1-2]: "
			read -r choice
		elif [ -e /dev/tty ]; then
			printf "  Enter choice [1-2]: "
			read -r choice </dev/tty
		else
			echo "  No interactive terminal available, defaulting to Dev Container."
			choice="1"
		fi

		case $choice in
		2)
			save_install_mode "local"
			echo ""
			echo "  Local Installation selected (preference saved)"
			echo ""
			confirm_local_install
			;;
		*)
			save_install_mode "container"
			setup_devcontainer
			;;
		esac
	fi
fi

echo ""
echo "Downloading Claude CodePro (v${VERSION})..."
echo ""

if check_uv; then
	echo "  [OK] uv already installed"
else
	install_uv
fi

download_installer
download_ccp_binary

run_installer $INSTALLER_ARGS
