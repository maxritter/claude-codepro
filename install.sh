#!/bin/bash
# Claude CodePro Installer Bootstrap Script
# Phase 1: Downloads .devcontainer on any platform
# Phase 2: Runs full installer inside the dev container

set -e

# Version is updated by semantic-release
VERSION="3.1.1"

REPO="maxritter/claude-codepro"
REPO_RAW="https://raw.githubusercontent.com/${REPO}/v${VERSION}"
BINARY_PREFIX="ccp-installer"

# Check if running inside a container
is_in_container() {
    [ -f "/.dockerenv" ] || [ -f "/run/.containerenv" ]
}

# Download a file from the repo
download_file() {
    local path="$1"
    local dest="$2"
    local url="${REPO_RAW}/${path}"

    mkdir -p "$(dirname "$dest")"
    if command -v curl > /dev/null 2>&1; then
        curl -fsSL "$url" -o "$dest"
    elif command -v wget > /dev/null 2>&1; then
        wget -q "$url" -O "$dest"
    else
        echo "Error: Neither curl nor wget found."
        exit 1
    fi
}

# Phase 1: Not in container - download .devcontainer and exit
if ! is_in_container; then
    echo ""
    echo "======================================================================"
    echo "  Claude CodePro - Dev Container Setup (v${VERSION})"
    echo "======================================================================"
    echo ""

    if [ -d ".devcontainer" ]; then
        echo "  [OK] .devcontainer already exists"
    else
        echo "  [..] Downloading dev container configuration..."
        download_file ".devcontainer/Dockerfile" ".devcontainer/Dockerfile"
        download_file ".devcontainer/devcontainer.json" ".devcontainer/devcontainer.json"

        # Replace placeholders with current directory name
        PROJECT_NAME="$(basename "$(pwd)")"
        PROJECT_SLUG="$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | tr ' _' '-')"
        if [ -f ".devcontainer/devcontainer.json" ]; then
            sed -i.bak "s/{{PROJECT_NAME}}/${PROJECT_NAME}/g" ".devcontainer/devcontainer.json"
            sed -i.bak "s/{{PROJECT_SLUG}}/${PROJECT_SLUG}/g" ".devcontainer/devcontainer.json"
            rm -f ".devcontainer/devcontainer.json.bak"
        fi

        echo "  [OK] Dev container configuration installed"
    fi

    # Download VS Code extensions recommendations (so they're ready when VS Code opens)
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
fi

# Phase 2: Inside container - run full installer
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64) ARCH="x86_64" ;;
    arm64|aarch64) ARCH="arm64" ;;
    *)
        echo "Error: Unsupported architecture: $ARCH"
        echo "Supported: x86_64, arm64"
        exit 1
        ;;
esac

BINARY_NAME="${BINARY_PREFIX}-linux-${ARCH}"
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/v${VERSION}/${BINARY_NAME}"
INSTALL_PATH="/tmp/${BINARY_NAME}"

echo "Downloading Claude CodePro Installer (v${VERSION})..."
echo "  Platform: linux-${ARCH}"
echo ""

# Download binary
if command -v curl > /dev/null 2>&1; then
    curl -fsSL "$DOWNLOAD_URL" -o "$INSTALL_PATH"
elif command -v wget > /dev/null 2>&1; then
    wget -q "$DOWNLOAD_URL" -O "$INSTALL_PATH"
else
    echo "Error: Neither curl nor wget found. Please install one of them."
    exit 1
fi

# Make executable
chmod +x "$INSTALL_PATH"

# Run installer (handles TTY input internally for piped execution)
"$INSTALL_PATH" install "$@"

# Clean up
rm -f "$INSTALL_PATH"
