#!/bin/bash

# =============================================================================
# Claude CodePro Installation & Update Script
# Idempotent: Safe to run multiple times (install + update)
# Supports: macOS, Linux, WSL
# =============================================================================

set -e

# Repository configuration
REPO_URL="https://github.com/maxritter/claude-codepro"
REPO_BRANCH="main"

# Installation paths
PROJECT_DIR="$(pwd)"
TEMP_DIR=$(mktemp -d)

# Color codes
BLUE='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Print functions
print_status() {
    echo -e "${BLUE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

# Cleanup on exit
cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
    tput cnorm 2>/dev/null || true
}
trap cleanup EXIT

# -----------------------------------------------------------------------------
# Download Functions
# -----------------------------------------------------------------------------

download_file() {
    local repo_path=$1
    local dest_path=$2
    local file_url="${REPO_URL}/raw/${REPO_BRANCH}/${repo_path}"

    mkdir -p "$(dirname "$dest_path")"

    if curl -sL --fail "$file_url" -o "$dest_path" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Get all files from repo directory
get_repo_files() {
    local dir_path=$1
    local branch="main"
    local repo_path
    repo_path="${REPO_URL#https://github.com/}"
    local tree_url="https://api.github.com/repos/${repo_path}/git/trees/${branch}?recursive=true"

    local response
    response=$(curl -sL "$tree_url")

    if command -v python3 &> /dev/null; then
        echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('tree', []):
    if item.get('type') == 'blob' and item.get('path', '').startswith('$dir_path'):
        print(item.get('path', ''))
"
    fi
}

# -----------------------------------------------------------------------------
# Installation Functions - Claude CodePro Files
# -----------------------------------------------------------------------------

install_directory() {
    local repo_dir=$1
    local dest_base=$2

    print_status "Installing $repo_dir files..."

    local file_count=0
    local files
    files=$(get_repo_files "$repo_dir")

    if [[ -n "$files" ]]; then
        while IFS= read -r file_path; do
            if [[ -n "$file_path" ]]; then
                local dest_file="${dest_base}/${file_path}"

                if download_file "$file_path" "$dest_file" 2>/dev/null; then
                    ((file_count++)) || true
                    echo "   ✓ $(basename "$file_path")"
                fi
            fi
        done <<< "$files"
    fi

    print_success "Installed $file_count files"
}

install_file() {
    local repo_file=$1
    local dest_file=$2

    if download_file "$repo_file" "$dest_file"; then
        print_success "Installed $repo_file"
        return 0
    else
        print_warning "Failed to install $repo_file"
        return 1
    fi
}

# Merge MCP configuration
merge_mcp_config() {
    local repo_file=$1
    local dest_file=$2
    local temp_file="${TEMP_DIR}/mcp-temp.json"

    print_status "Installing MCP configuration..."

    # Download the new config
    if ! download_file "$repo_file" "$temp_file"; then
        print_warning "Failed to download $repo_file"
        return 1
    fi

    # If destination doesn't exist, just copy it
    if [[ ! -f "$dest_file" ]]; then
        cp "$temp_file" "$dest_file"
        print_success "Created $repo_file"
        return 0
    fi

    # Merge the configurations using Python
    python3 <<EOF
import json
import sys

try:
    # Load existing config
    with open('$dest_file', 'r') as f:
        existing = json.load(f)

    # Load new config
    with open('$temp_file', 'r') as f:
        new = json.load(f)

    # Detect server key (mcpServers for .mcp.json, servers for .mcp-funnel.json)
    server_key = 'mcpServers' if 'mcpServers' in new else 'servers'

    # Ensure server key exists
    if server_key not in existing:
        existing[server_key] = {}

    # Merge new servers into existing (don't overwrite existing servers)
    for server_name, server_config in new.get(server_key, {}).items():
        if server_name not in existing[server_key]:
            existing[server_key][server_name] = server_config

    # Merge other top-level keys (for .mcp-funnel.json)
    for key in ['exposeTools', 'alwaysVisibleTools', 'exposeCoreTools']:
        if key in new and key not in existing:
            existing[key] = new[key]

    # Write merged config
    with open('$dest_file', 'w') as f:
        json.dump(existing, f, indent=2)
        f.write('\n')

    sys.exit(0)
except Exception as e:
    print(f"Error merging MCP config: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    if [[ $? -eq 0 ]]; then
        print_success "Merged MCP servers (preserved existing configuration)"
        return 0
    else
        print_warning "Failed to merge MCP configuration"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Dependency Installation Functions
# -----------------------------------------------------------------------------

install_nodejs() {
    if command -v npm &> /dev/null; then
        print_success "npm already installed"
        return 0
    fi

    print_status "Installing Node.js and npm..."

    # Detect OS and install Node.js accordingly
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - use official installer
        print_status "Downloading Node.js for macOS..."
        local node_pkg="/tmp/node-installer.pkg"
        curl -sL "https://nodejs.org/dist/v20.11.0/node-v20.11.0.pkg" -o "$node_pkg"
        sudo installer -pkg "$node_pkg" -target /
        rm -f "$node_pkg"
    else
        # Linux - use NodeSource repository
        print_status "Setting up NodeSource repository..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 2>/dev/null || \
        curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash - 2>/dev/null

        # Try apt-get first (Debian/Ubuntu)
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y nodejs
        # Try yum (RHEL/CentOS/Fedora)
        elif command -v yum &> /dev/null; then
            sudo yum install -y nodejs
        # Try dnf (Fedora)
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y nodejs
        else
            print_error "Could not detect package manager. Please install Node.js manually from https://nodejs.org/"
            exit 1
        fi
    fi

    # Verify installation
    if command -v npm &> /dev/null; then
        print_success "Installed Node.js and npm"
        npm --version
    else
        print_error "npm installation failed. Please install Node.js manually from https://nodejs.org/"
        exit 1
    fi
}

install_uv() {
    if command -v uv &> /dev/null; then
        print_success "uv already installed"
        return 0
    fi

    print_status "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Source the uv env
    export PATH="$HOME/.cargo/bin:$PATH"

    print_success "Installed uv"
}

install_python_tools() {
    print_status "Installing Python tools globally..."

    uv tool install ruff
    uv tool install mypy
    uv tool install basedpyright

    print_success "Installed Python tools (ruff, mypy, basedpyright)"
}

install_qlty() {
    if command -v qlty &> /dev/null; then
        print_success "qlty already installed"
        return 0
    fi

    print_status "Installing qlty..."
    curl -s https://qlty.sh | sh

    # Add to PATH
    export QLTY_INSTALL="$HOME/.qlty"
    export PATH="$QLTY_INSTALL/bin:$PATH"

    # Initialize qlty for this project
    cd "$PROJECT_DIR" && "$HOME/.qlty/bin/qlty" check --install-only

    print_success "Installed qlty"
}

install_claude_code() {
    if command -v claude &> /dev/null; then
        print_success "Claude Code already installed"
        return 0
    fi

    print_status "Installing Claude Code..."
    curl -fsSL https://claude.ai/install.sh | bash

    print_success "Installed Claude Code"
}

install_cipher() {
    if command -v cipher &> /dev/null; then
        print_success "Cipher already installed"
        return 0
    fi

    print_status "Installing Cipher..."
    npm install -g @byterover/cipher

    print_success "Installed Cipher"
}

install_newman() {
    if command -v newman &> /dev/null; then
        print_success "Newman already installed"
        return 0
    fi

    print_status "Installing Newman..."
    npm install -g newman

    print_success "Installed Newman"
}

install_statusline() {
    # Check if jq is installed (required by statusline)
    if ! command -v jq &> /dev/null; then
        print_status "Installing jq (required for statusline)..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install jq 2>/dev/null || {
                print_warning "Please install jq manually: brew install jq"
                return 1
            }
        else
            sudo apt-get install -y jq 2>/dev/null || sudo yum install -y jq 2>/dev/null || {
                print_warning "Please install jq manually"
                return 1
            }
        fi
    fi

    print_status "Installing Claude Code Statusline..."
    curl -fsSL https://raw.githubusercontent.com/hagan/claudia-statusline/main/scripts/quick-install.sh | bash

    print_success "Installed Claude Code Statusline"
}

install_dotenvx() {
    if command -v dotenvx &> /dev/null; then
        print_success "dotenvx already installed"
        return 0
    fi

    print_status "Installing dotenvx..."
    npm install -g @dotenvx/dotenvx

    print_success "Installed dotenvx"
}

# -----------------------------------------------------------------------------
# Shell Configuration
# -----------------------------------------------------------------------------

add_shell_alias() {
    local shell_file=$1
    local alias_cmd=$2
    local shell_name=$3

    [[ ! -f "$shell_file" ]] && return

    if grep -q "# Claude CodePro alias" "$shell_file"; then
        sed -i.bak '/# Claude CodePro alias/,/^alias cc=/c\
# Claude CodePro alias\
'"$alias_cmd" "$shell_file" && rm -f "${shell_file}.bak"
        print_success "Updated alias in $shell_name"
    elif ! grep -q "^alias cc=" "$shell_file"; then
        printf "\n# Claude CodePro alias\n%s\n" "$alias_cmd" >> "$shell_file"
        print_success "Added alias to $shell_name"
    else
        print_success "Alias cc already exists in $shell_name (skipped)"
    fi
}

add_cc_alias() {
    print_status "Configuring cc alias in shell configurations..."

    local bash_alias="alias cc=\"cd '$PROJECT_DIR' && bash scripts/build-rules.sh &>/dev/null && clear && dotenvx run -- claude\""
    local fish_alias="alias cc='cd $PROJECT_DIR; and bash scripts/build-rules.sh &>/dev/null; and clear; and dotenvx run -- claude'"

    add_shell_alias "$HOME/.bashrc" "$bash_alias" ".bashrc"
    add_shell_alias "$HOME/.zshrc" "$bash_alias" ".zshrc"

    if command -v fish &> /dev/null; then
        mkdir -p "$HOME/.config/fish"
        add_shell_alias "$HOME/.config/fish/config.fish" "$fish_alias" "fish config"
    fi
}

# -----------------------------------------------------------------------------
# Build Rules
# -----------------------------------------------------------------------------

build_rules() {
    print_status "Building Claude Code commands and skills..."

    if [[ -f "$PROJECT_DIR/scripts/build-rules.sh" ]]; then
        bash "$PROJECT_DIR/scripts/build-rules.sh"
        print_success "Built commands and skills"
    else
        print_warning "build-rules.sh not found, skipping"
    fi
}

# -----------------------------------------------------------------------------
# Main Installation
# -----------------------------------------------------------------------------

main() {
    print_section "Claude CodePro Installation"

    print_status "Installing into: $PROJECT_DIR"
    echo ""

    # Ask about Python support
    echo "Do you want to install advanced Python features?"
    echo "This includes: uv, ruff, mypy, basedpyright, and Python quality hooks"
    read -r -p "Install Python support? (y/n): " -n 1 INSTALL_PYTHON < /dev/tty
    echo ""
    echo ""

    # Install Claude CodePro files
    print_section "Installing Claude CodePro Files"

    # Download .claude directory (update existing files, preserve settings.local.json)
    print_status "Installing .claude files..."

    local files
    files=$(get_repo_files ".claude")

    local file_count=0
    if [[ -n "$files" ]]; then
        while IFS= read -r file_path; do
            if [[ -n "$file_path" ]]; then
                # Skip Python hook if Python not selected
                if [[ "$INSTALL_PYTHON" =~ ^[Yy]$ ]] || [[ "$file_path" != *"file_checker_python.sh"* ]]; then
                    # Ask about settings.local.json if it already exists
                    if [[ "$file_path" == *"settings.local.json"* ]] && [[ -f "$PROJECT_DIR/.claude/settings.local.json" ]]; then
                        print_warning "settings.local.json already exists"
                        echo "This file may contain new features in this version."
                        read -r -p "Overwrite settings.local.json? (y/n): " -n 1 < /dev/tty
                        echo
                        [[ ! $REPLY =~ ^[Yy]$ ]] && print_success "Kept existing settings.local.json" && continue
                    fi

                    local dest_file="${PROJECT_DIR}/${file_path}"
                    if download_file "$file_path" "$dest_file" 2>/dev/null; then
                        ((file_count++)) || true
                        echo "   ✓ $(basename "$file_path")"
                    fi
                fi
            fi
        done <<< "$files"
    fi

    # Remove Python hook from settings.local.json if Python not selected
    if [[ ! "$INSTALL_PYTHON" =~ ^[Yy]$ ]] && [[ -f "$PROJECT_DIR/.claude/settings.local.json" ]]; then
        print_status "Removing Python hook from settings.local.json..."
        # Use Python to cleanly remove the Python hook entry from JSON
        python3 -c "
import json
with open('$PROJECT_DIR/.claude/settings.local.json', 'r') as f:
    config = json.load(f)

# Remove Python hook
if 'hooks' in config and 'PostToolUse' in config['hooks']:
    for hook_group in config['hooks']['PostToolUse']:
        if 'hooks' in hook_group:
            hook_group['hooks'] = [h for h in hook_group['hooks'] if 'file_checker_python.sh' not in h.get('command', '')]

# Remove Python-related permissions
python_perms = ['Bash(basedpyright:*)', 'Bash(mypy:*)', 'Bash(python tests:*)', 'Bash(python:*)',
                'Bash(pyright:*)', 'Bash(pytest:*)', 'Bash(ruff check:*)', 'Bash(ruff format:*)',
                'Bash(uv add:*)', 'Bash(uv pip show:*)', 'Bash(uv pip:*)', 'Bash(uv run:*)']
if 'permissions' in config and 'allow' in config['permissions']:
    config['permissions']['allow'] = [p for p in config['permissions']['allow'] if p not in python_perms]

with open('$PROJECT_DIR/.claude/settings.local.json', 'w') as f:
    json.dump(config, f, indent=2)
"
        print_success "Configured settings.local.json without Python support"
    fi

    chmod +x "$PROJECT_DIR/.claude/hooks/"*.sh 2>/dev/null || true
    print_success "Installed $file_count .claude files"
    echo ""

    if [[ ! -d "$PROJECT_DIR/.cipher" ]]; then
        install_directory ".cipher" "$PROJECT_DIR"
        echo ""
    fi

    if [[ ! -d "$PROJECT_DIR/.qlty" ]]; then
        install_directory ".qlty" "$PROJECT_DIR"
        echo ""
    fi

    merge_mcp_config ".mcp.json" "$PROJECT_DIR/.mcp.json"
    merge_mcp_config ".mcp-funnel.json" "$PROJECT_DIR/.mcp-funnel.json"
    echo ""

    mkdir -p "$PROJECT_DIR/scripts"
    install_file "scripts/setup-env.sh" "$PROJECT_DIR/scripts/setup-env.sh"
    install_file "scripts/build-rules.sh" "$PROJECT_DIR/scripts/build-rules.sh"
    chmod +x "$PROJECT_DIR/scripts/"*.sh
    echo ""

    # Run .env setup
    print_section "Environment Setup"
    bash "$PROJECT_DIR/scripts/setup-env.sh"

    # Install dependencies
    print_section "Installing Dependencies"

    # Install Node.js first (required for npm packages)
    install_nodejs
    echo ""

    # Install Python tools if selected
    if [[ "$INSTALL_PYTHON" =~ ^[Yy]$ ]]; then
        install_uv
        echo ""

        install_python_tools
        echo ""
    fi

    install_qlty
    echo ""

    install_claude_code
    echo ""

    install_cipher
    echo ""

    install_newman
    echo ""

    install_statusline
    echo ""

    install_dotenvx
    echo ""

    # Build rules
    print_section "Building Rules"
    build_rules
    echo ""

    # Configure shells
    print_section "Configuring Shell"
    add_cc_alias
    echo ""

    # Success message
    print_section "🎉 Installation Complete!"

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Claude CodePro has been successfully installed! 🚀${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}What's next?${NC} Follow these steps to get started:"
    echo ""
    echo -e "${YELLOW}STEP 1: Reload Your Shell${NC}"
    echo "   → Run: source ~/.zshrc  (or ~/.bashrc for bash)"
    echo ""
    echo -e "${YELLOW}STEP 2: Start Claude Code${NC}"
    echo "   → Launch with: cc"
    echo ""
    echo -e "${YELLOW}STEP 3: Configure Claude Code${NC}"
    echo "   → In Claude Code, run: /config"
    echo "   → Set 'Auto-connect to IDE' = true"
    echo "   → Set 'Auto-compact' = false"
    echo ""
    echo -e "${YELLOW}STEP 4: Verify Everything Works${NC}"
    echo "   → Run: /ide        (Connect to VS Code diagnostics)"
    echo "   → Run: /mcp        (Verify all MCP servers are online)"
    echo "   → Run: /context    (Check context usage is below 20%)"
    echo ""
    echo -e "${YELLOW}STEP 5: Start Building!${NC}"
    echo ""
    echo -e "   ${BLUE}For quick changes:${NC}"
    echo "   → /quick           Fast development for fixes and refactoring"
    echo ""
    echo -e "   ${BLUE}For complex features:${NC}"
    echo "   → /plan            Create detailed spec with TDD"
    echo "   → /implement       Execute spec with mandatory testing"
    echo "   → /verify          Run end-to-end quality checks"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}📚 Learn more: https://www.claude-code.pro${NC}"
    echo -e "${GREEN}💬 Questions? https://github.com/maxritter/claude-codepro/issues${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Run main
main "$@"
