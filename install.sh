#!/bin/bash

set -e

VERSION="4.5.1"

REPO="maxritter/claude-codepro"
REPO_RAW="https://raw.githubusercontent.com/${REPO}/v${VERSION}"
LOCAL_INSTALL=false

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

check_homebrew() {
    command -v brew >/dev/null 2>&1
}

install_homebrew() {
    echo "  [..] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    if [ -d "/opt/homebrew/bin" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)" # macOS ARM
    elif [ -d "/usr/local/bin" ] && [ -f "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)" # macOS Intel
    elif [ -d "/home/linuxbrew/.linuxbrew/bin" ]; then
        eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)" # Linux
    fi

    if ! check_homebrew; then
        echo ""
        echo "  [!!] Homebrew installation failed or brew not in PATH."
        echo "      Please install Homebrew manually or use Dev Container instead."
        exit 1
    fi
    echo "  [OK] Homebrew installed"
}

BREW_PACKAGES="git gh python@3.12 node@22 nvm pnpm bun uv"

install_brew_packages() {
    echo ""
    echo "  Installing required packages via Homebrew..."
    echo ""
    for pkg in $BREW_PACKAGES; do
        if brew list "$pkg" >/dev/null 2>&1; then
            echo "  [OK] $pkg already installed"
        else
            echo "  [..] Installing $pkg..."
            if ! brew install "$pkg"; then
                echo "  [!!] Failed to install $pkg"
                echo "      Please try installing manually or use Dev Container instead."
                exit 1
            fi
            echo "  [OK] $pkg installed"
        fi
    done
    echo ""
    echo "  [OK] All Homebrew packages installed"
}

confirm_local_install() {
    echo ""
    echo "  Local installation will:"
    echo "    • Install Homebrew packages: python@3.12, node@22, nvm, pnpm, bun, uv, git, gh"
    echo "    • Add PATH and 'ccp' alias to your shell config (~/.bashrc, ~/.zshrc, fish)"
    echo "    • Configure Claude Code (~/.claude.json): theme, auto-compact off, MCP servers"
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
            sed -i.bak "s/{{PROJECT_NAME}}/${PROJECT_NAME}/g" ".devcontainer/devcontainer.json"
            sed -i.bak "s/{{PROJECT_SLUG}}/${PROJECT_SLUG}/g" ".devcontainer/devcontainer.json"
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

    echo "  Choose installation method:"
    echo ""
    echo "    1) Dev Container - Isolated environment, consistent tooling"
    echo "    2) Local - Install directly on your system via Homebrew (macOS/Linux)"
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
        LOCAL_INSTALL=true
        echo ""
        echo "  Local Installation selected"
        echo ""

        confirm_local_install

        if check_homebrew; then
            echo "  [OK] Homebrew already installed"
        else
            install_homebrew
        fi

        install_brew_packages
        ;;
    *)
        setup_devcontainer
        ;;
    esac
fi

ARCH="$(uname -m)"
case "$ARCH" in
x86_64 | amd64) ARCH="x86_64" ;;
arm64 | aarch64) ARCH="arm64" ;;
*)
    echo "Error: Unsupported architecture: $ARCH"
    echo "Supported: x86_64, arm64"
    exit 1
    ;;
esac

OS="$(uname -s)"
case "$OS" in
Linux) PLATFORM="linux" ;;
Darwin) PLATFORM="darwin" ;;
*)
    echo "Error: Unsupported operating system: $OS"
    echo "Supported: Linux, macOS (Darwin)"
    exit 1
    ;;
esac

INSTALLER_NAME="ccp-installer-${PLATFORM}-${ARCH}"
INSTALLER_URL="https://github.com/${REPO}/releases/download/v${VERSION}/${INSTALLER_NAME}"
INSTALLER_PATH=".claude/bin/ccp-installer"

CCP_NAME="ccp-${PLATFORM}-${ARCH}"
CCP_URL="https://github.com/${REPO}/releases/download/v${VERSION}/${CCP_NAME}"
CCP_PATH=".claude/bin/ccp"

echo "Downloading Claude CodePro (v${VERSION})..."
echo "  Platform: ${PLATFORM}-${ARCH}"
echo ""

mkdir -p .claude/bin

if [ -f ".claude/bin/ccp" ]; then
    if ! rm -f ".claude/bin/ccp" 2>/dev/null; then
        echo "Error: Cannot update CCP binary - it may be in use."
        echo ""
        echo "Please quit Claude CodePro first (Ctrl+C or /exit), then run this installer again."
        exit 1
    fi
fi

echo "  [..] Downloading installer..."
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$INSTALLER_URL" -o "$INSTALLER_PATH"
elif command -v wget >/dev/null 2>&1; then
    wget -q "$INSTALLER_URL" -O "$INSTALLER_PATH"
else
    echo "Error: Neither curl nor wget found. Please install one of them."
    exit 1
fi
chmod +x "$INSTALLER_PATH"
echo "  [OK] Installer downloaded"

echo "  [..] Downloading ccp binary..."
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$CCP_URL" -o "$CCP_PATH"
elif command -v wget >/dev/null 2>&1; then
    wget -q "$CCP_URL" -O "$CCP_PATH"
else
    echo "Error: Neither curl nor wget found. Please install one of them."
    exit 1
fi
chmod +x "$CCP_PATH"
echo "  [OK] CCP binary downloaded"
echo ""

if [ "$LOCAL_INSTALL" = true ]; then
    "$INSTALLER_PATH" install --local-system "$@"
else
    "$INSTALLER_PATH" install "$@"
fi
