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
	if [[ -d $TEMP_DIR ]]; then
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

	if command -v python3 &>/dev/null; then
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

	if [[ -n $files ]]; then
		while IFS= read -r file_path; do
			if [[ -n $file_path ]]; then
				local dest_file="${dest_base}/${file_path}"

				if download_file "$file_path" "$dest_file" 2>/dev/null; then
					((file_count++)) || true
					echo "   ✓ $(basename "$file_path")"
				fi
			fi
		done <<<"$files"
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

# Install jq if needed
ensure_jq() {
	if command -v jq &>/dev/null; then
		return 0
	fi

	print_status "Installing jq (JSON processor)..."

	if [[ $OSTYPE == "darwin"* ]]; then
		if command -v brew &>/dev/null; then
			brew install jq &>/dev/null
		else
			print_error "Homebrew not found. Please install jq manually: brew install jq"
			return 1
		fi
	elif command -v apt-get &>/dev/null; then
		sudo apt-get update &>/dev/null && sudo apt-get install -y jq &>/dev/null
	elif command -v yum &>/dev/null; then
		sudo yum install -y jq &>/dev/null
	elif command -v dnf &>/dev/null; then
		sudo dnf install -y jq &>/dev/null
	else
		print_error "Could not install jq. Please install manually"
		return 1
	fi

	if command -v jq &>/dev/null; then
		print_success "Installed jq"
		return 0
	else
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
	if [[ ! -f $dest_file ]]; then
		cp "$temp_file" "$dest_file"
		print_success "Created $repo_file"
		return 0
	fi

	# Ensure jq is available
	if ! ensure_jq; then
		print_warning "jq not available, preserving existing $repo_file"
		return 1
	fi

	# Merge configurations using jq
	# This merges new servers into existing without overwriting existing servers
	local merged
	if merged=$(jq -s '
		(.[0].mcpServers // .[0].servers // {}) as $existing |
		(.[1].mcpServers // .[1].servers // {}) as $new |
		if (.[0] | has("mcpServers")) then
			.[0] * .[1] | .mcpServers = ($new + $existing)
		elif (.[0] | has("servers")) then
			.[0] * .[1] | .servers = ($new + $existing)
		else
			.[0] * .[1]
		end' \
		"$dest_file" "$temp_file" 2>/dev/null); then
		echo "$merged" >"$dest_file"
		print_success "Merged MCP servers (preserved existing configuration)"
		return 0
	else
		print_warning "Failed to merge MCP configuration, preserving existing"
		return 1
	fi
}

# -----------------------------------------------------------------------------
# Dependency Installation Functions
# -----------------------------------------------------------------------------

install_nodejs() {
	# Check if NVM is already installed
	if [[ ! -d "$HOME/.nvm" ]] && [[ ! -s "$HOME/.nvm/nvm.sh" ]]; then
		print_status "Installing NVM (Node Version Manager)..."

		# Install NVM
		curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

		# Load NVM into current shell
		export NVM_DIR="$HOME/.nvm"
		# shellcheck source=/dev/null
		[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

		print_success "Installed NVM"
	else
		print_success "NVM already installed"

		# Load NVM into current shell
		export NVM_DIR="$HOME/.nvm"
		# shellcheck source=/dev/null
		[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
	fi

	# Install Node.js 22 (latest) using NVM
	print_status "Installing Node.js 22.x (required for Claude Context)..."

	# Install the latest Node.js 22.x version
	nvm install 22
	nvm use 22
	nvm alias default 22

	# Verify installation
	if command -v npm &>/dev/null; then
		local node_version
		node_version=$(node --version)
		print_success "Installed Node.js $node_version and npm $(npm --version)"

		# Verify it's version 22.x
		if [[ ! $node_version =~ ^v22\. ]]; then
			print_warning "Warning: Expected Node.js 22.x but got $node_version"
		fi
	else
		print_error "npm installation failed. Please install Node.js manually using NVM"
		exit 1
	fi
}

install_uv() {
	if command -v uv &>/dev/null; then
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
	if command -v qlty &>/dev/null; then
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
	if command -v claude &>/dev/null; then
		print_success "Claude Code already installed"
		return 0
	fi

	print_status "Installing Claude Code..."
	curl -fsSL https://claude.ai/install.sh | bash

	print_success "Installed Claude Code"
}

install_cipher() {
	if command -v cipher &>/dev/null; then
		print_success "Cipher already installed"
		return 0
	fi

	print_status "Installing Cipher..."
	npm install -g @byterover/cipher

	print_success "Installed Cipher"
}

install_newman() {
	if command -v newman &>/dev/null; then
		print_success "Newman already installed"
		return 0
	fi

	print_status "Installing Newman..."
	npm install -g newman

	print_success "Installed Newman"
}

install_dotenvx() {
	if command -v dotenvx &>/dev/null; then
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
	local alias_name=$4

	[[ ! -f $shell_file ]] && return

	# Check if this specific project alias exists
	if grep -q "# Claude CodePro alias - $PROJECT_DIR" "$shell_file"; then
		# Update existing alias for this project
		sed -i.bak "/# Claude CodePro alias - ${PROJECT_DIR//\//\\/}/,/^alias ${alias_name}=/c\\
# Claude CodePro alias - $PROJECT_DIR\\
$alias_cmd" "$shell_file" && rm -f "${shell_file}.bak"
		print_success "Updated alias '$alias_name' in $shell_name"
	elif grep -q "^alias ${alias_name}=" "$shell_file"; then
		print_warning "Alias '$alias_name' already exists in $shell_name (skipped)"
	else
		printf "\n# Claude CodePro alias - %s\n%s\n" "$PROJECT_DIR" "$alias_cmd" >>"$shell_file"
		print_success "Added alias '$alias_name' to $shell_name"
	fi
}

ensure_nvm_in_shell() {
	local shell_file=$1
	local shell_name=$2

	[[ ! -f $shell_file ]] && return

	# Check if NVM is already sourced in the shell config
	if ! grep -q "NVM_DIR" "$shell_file"; then
		print_status "Adding NVM initialization to $shell_name..."
		cat >>"$shell_file" <<'EOF'

# NVM (Node Version Manager)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
EOF
		print_success "Added NVM initialization to $shell_name"
	fi
}

add_cc_alias() {
	local alias_name="ccp"

	print_status "Configuring shell for NVM and '$alias_name' alias..."

	# Ensure NVM initialization is in shell configs
	ensure_nvm_in_shell "$HOME/.bashrc" ".bashrc"
	ensure_nvm_in_shell "$HOME/.zshrc" ".zshrc"

	local bash_alias="alias ${alias_name}=\"cd '$PROJECT_DIR' && [ -s \\\"\\\$HOME/.nvm/nvm.sh\\\" ] && . \\\"\\\$HOME/.nvm/nvm.sh\\\" && nvm use && bash scripts/build-rules.sh &>/dev/null && clear && dotenvx run -- claude\""
	local fish_alias="alias ${alias_name}='cd $PROJECT_DIR; and [ -s \"\$HOME/.nvm/nvm.sh\" ]; and source \"\$HOME/.nvm/nvm.sh\"; and nvm use; and bash scripts/build-rules.sh &>/dev/null; and clear; and dotenvx run -- claude'"

	add_shell_alias "$HOME/.bashrc" "$bash_alias" ".bashrc" "$alias_name"
	add_shell_alias "$HOME/.zshrc" "$bash_alias" ".zshrc" "$alias_name"

	if command -v fish &>/dev/null; then
		mkdir -p "$HOME/.config/fish"
		add_shell_alias "$HOME/.config/fish/config.fish" "$fish_alias" "fish config" "$alias_name"
	fi

	echo ""
	print_success "Alias '$alias_name' configured!"
	echo "   Run '$alias_name' from anywhere to start Claude Code for this project"
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
	read -r -p "Install Python support? (Y/n): " INSTALL_PYTHON </dev/tty
	INSTALL_PYTHON=${INSTALL_PYTHON:-Y}
	echo ""
	echo ""

	# Install Claude CodePro files
	print_section "Installing Claude CodePro Files"

	# Download .claude directory (update existing files, preserve settings.local.json)
	print_status "Installing .claude files..."

	local files
	files=$(get_repo_files ".claude")

	local file_count=0
	if [[ -n $files ]]; then
		while IFS= read -r file_path; do
			if [[ -n $file_path ]]; then
				# Skip Python hook if Python not selected
				if [[ $INSTALL_PYTHON =~ ^[Yy]$ ]] || [[ $file_path != *"file_checker_python.sh"* ]]; then
					# Ask about settings.local.json if it already exists
					if [[ $file_path == *"settings.local.json"* ]] && [[ -f "$PROJECT_DIR/.claude/settings.local.json" ]]; then
						print_warning "settings.local.json already exists"
						echo "This file may contain new features in this version."
						read -r -p "Overwrite settings.local.json? (y/n): " -n 1 </dev/tty
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
		done <<<"$files"
	fi

	# Remove Python hook from settings.local.json if Python not selected
	if [[ ! $INSTALL_PYTHON =~ ^[Yy]$ ]] && [[ -f "$PROJECT_DIR/.claude/settings.local.json" ]]; then
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

	# Create .nvmrc for Node.js version management
	print_status "Creating .nvmrc for Node.js 22..."
	echo "22" >"$PROJECT_DIR/.nvmrc"
	print_success "Created .nvmrc"
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
	if [[ $INSTALL_PYTHON =~ ^[Yy]$ ]]; then
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

	install_dotenvx
	echo ""

	# Build rules
	print_section "Building Rules"
	build_rules
	echo ""

	# Configure shells
	print_section "Configuring Shell"
	add_cc_alias

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
	echo "   → Run: source ~/.zshrc  (or 'source ~/.bashrc' for bash or 'source ~/.config/fish/config.fish' for fish)"
	echo ""
	echo -e "${YELLOW}STEP 2: Start Claude Code${NC}"
	echo "   → Launch with: ccp"
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
