#!/bin/bash

# =============================================================================
# Claude CodePro Installation & Update Script
# Idempotent: Safe to run multiple times (install + update)
# Supports: macOS, Linux, WSL
# =============================================================================

set -e

# =============================================================================
# Parse Command Line Arguments
# =============================================================================

NON_INTERACTIVE=false
SKIP_ENV_SETUP=false
LOCAL_MODE=false
LOCAL_REPO_DIR=""

while [[ $# -gt 0 ]]; do
	case $1 in
	--non-interactive)
		NON_INTERACTIVE=true
		shift
		;;
	--skip-env)
		SKIP_ENV_SETUP=true
		shift
		;;
	--local)
		LOCAL_MODE=true
		# Detect local repo directory (script location)
		SCRIPT_LOCATION="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
		LOCAL_REPO_DIR="$(cd "$SCRIPT_LOCATION/.." && pwd)"
		shift
		;;
	--help)
		echo "Usage: $0 [OPTIONS]"
		echo ""
		echo "Options:"
		echo "  --non-interactive  Run without interactive prompts (use env vars)"
		echo "  --skip-env        Skip environment setup (API keys)"
		echo "  --local           Use local files instead of downloading from GitHub"
		echo "  --help            Show this help message"
		echo ""
		echo "Environment Variables for Non-Interactive Mode:"
		echo "  INSTALL_PYTHON=Y|N  Install Python support (default: Y)"
		echo "  OVERWRITE_SETTINGS=Y|N  Overwrite settings.local.json if exists (default: N)"
		echo ""
		echo "Local Testing:"
		echo "  --local --non-interactive --skip-env"
		exit 0
		;;
	*)
		echo "Unknown option: $1"
		echo "Run '$0 --help' for usage information"
		exit 1
		;;
	esac
done

# =============================================================================
# Configuration & Constants
# =============================================================================

# Repository configuration
REPO_URL="https://github.com/maxritter/claude-codepro"
REPO_BRANCH="main"

# Installation paths
PROJECT_DIR="$(pwd)"
TEMP_DIR=$(mktemp -d)

# =============================================================================
# Bootstrap - Download and source library modules
# =============================================================================

# Minimal download function for bootstrapping (before lib modules are loaded)
_bootstrap_download() {
	local repo_path=$1
	local dest_path=$2

	mkdir -p "$(dirname "$dest_path")"

	# Use local files if in local mode
	if [[ "$LOCAL_MODE" == "true" ]]; then
		local source_file="$LOCAL_REPO_DIR/$repo_path"
		if [[ -f "$source_file" ]]; then
			cp "$source_file" "$dest_path"
			return 0
		else
			return 1
		fi
	else
		# Download from GitHub
		local file_url="${REPO_URL}/raw/${REPO_BRANCH}/${repo_path}"
		if curl -sL --fail "$file_url" -o "$dest_path" 2>/dev/null; then
			return 0
		else
			return 1
		fi
	fi
}

# Library modules list (single source of truth)
# Add new modules here and they'll be automatically downloaded and checked
LIB_MODULES=(
	"ui.sh"
	"utils.sh"
	"download.sh"
	"files.sh"
	"dependencies.sh"
	"shell.sh"
	"migration.sh"
	"setup-env.sh"
)

# Download library modules
download_lib_modules() {
	local lib_dir="$PROJECT_DIR/scripts/lib"
	mkdir -p "$lib_dir"

	for module in "${LIB_MODULES[@]}"; do
		if ! _bootstrap_download "scripts/lib/$module" "$lib_dir/$module"; then
			echo "Warning: Failed to download lib/$module" >&2
		fi
	done
}

# Always download library modules to ensure latest versions
# This prevents using stale cached versions from previous installations
download_lib_modules

# Source library modules
# shellcheck source=lib/ui.sh
source "$PROJECT_DIR/scripts/lib/ui.sh"
# shellcheck source=lib/utils.sh
source "$PROJECT_DIR/scripts/lib/utils.sh"
# shellcheck source=lib/download.sh
source "$PROJECT_DIR/scripts/lib/download.sh"
# shellcheck source=lib/files.sh
source "$PROJECT_DIR/scripts/lib/files.sh"
# shellcheck source=lib/dependencies.sh
source "$PROJECT_DIR/scripts/lib/dependencies.sh"
# shellcheck source=lib/shell.sh
source "$PROJECT_DIR/scripts/lib/shell.sh"
# shellcheck source=lib/migration.sh
source "$PROJECT_DIR/scripts/lib/migration.sh"

# =============================================================================
# Setup cleanup trap
# =============================================================================

trap cleanup EXIT

# =============================================================================
# Config Merging
# =============================================================================

# Merge rules config.yaml preserving custom sections
# Args: $1 = new config path, $2 = existing config path
merge_rules_config() {
	local new_config=$1
	local existing_config=$2

	# Try to install and use yq for YAML merging
	if ensure_yq; then
		# Extract custom sections from existing config
		local temp_merged="${TEMP_DIR}/merged-config.yaml"

		# Use yq to merge: take all from new config, but preserve custom arrays from existing
		yq eval-all '
			select(fileIndex == 0) as $new |
			select(fileIndex == 1) as $old |
			$new |
			.commands = ($new.commands * $old.commands |
				with_entries(
					.value.rules.custom = ($old.commands[.key].rules.custom // [])
				)
			)
		' "$new_config" "$existing_config" > "$temp_merged"

		mv "$temp_merged" "$existing_config"
		print_success "Merged config.yaml (preserved custom rules)"
	else
		# Fallback: manually preserve custom sections using grep/awk
		print_warning "yq not available - using manual config merge"

		local temp_merged="${TEMP_DIR}/merged-config.yaml"
		local current_command=""
		local in_custom=false

		# Read new config and inject custom sections from old config
		while IFS= read -r line; do
			echo "$line" >> "$temp_merged"

			# Detect command name
			if [[ "$line" =~ ^[[:space:]]*([a-z_-]+):$ ]]; then
				current_command="${BASH_REMATCH[1]}"
			fi

			# When we see "custom:" in new config, replace with custom from old config
			if [[ "$line" =~ ^[[:space:]]*custom: ]]; then
				# Extract custom section from old config for this command
				if [[ -n "$current_command" ]] && [[ -f "$existing_config" ]]; then
					# Use awk to extract custom rules for this command
					local custom_rules=$(awk -v cmd="$current_command" '
						/^[[:space:]]*[a-z_-]+:$/ {
							current_cmd = $1;
							gsub(/:/, "", current_cmd);
							gsub(/^[[:space:]]+/, "", current_cmd);
							in_target = (current_cmd == cmd);
							in_custom = 0;
						}
						in_target && /^[[:space:]]*custom:/ { in_custom = 1; next; }
						in_target && in_custom && /^[[:space:]]*-/ { print; }
						in_target && in_custom && /^[[:space:]]*[a-z_-]+:/ { in_custom = 0; }
					' "$existing_config")

					# If we found custom rules, output them (remove the "custom: []" line we just wrote)
					if [[ -n "$custom_rules" ]]; then
						# Remove the last line (custom: [])
						sed -i.bak '$ d' "$temp_merged" && rm -f "${temp_merged}.bak"
						# Add custom: header and the rules
						echo "      custom:" >> "$temp_merged"
						echo "$custom_rules" >> "$temp_merged"
					fi
				fi
			fi
		done < "$new_config"

		mv "$temp_merged" "$existing_config"
		print_success "Merged config.yaml (manually preserved custom rules)"
	fi
}

# =============================================================================
# Build Rules
# =============================================================================

# Build Claude Code commands and skills
# Executes the build-rules.sh script to generate command/skill files
build_rules() {
	print_status "Building Claude Code commands and skills..."

	if [[ ! -f "$PROJECT_DIR/scripts/build-rules.sh" ]]; then
		print_warning "build-rules.sh not found, skipping"
		return
	fi

	if bash "$PROJECT_DIR/scripts/build-rules.sh"; then
		print_success "Built commands and skills"
	else
		print_error "Failed to build commands and skills"
		print_warning "You may need to run 'bash scripts/build-rules.sh' manually"
	fi
}

# =============================================================================
# Main Installation Flow
# =============================================================================

main() {
	print_section "Claude CodePro Installation"

	# Check for required system dependencies
	if ! check_required_dependencies; then
		exit 1
	fi

	print_status "Installing into: $PROJECT_DIR"
	echo ""

	# Run migration if needed (must be before file installation)
	run_migration

	# Ask about Python support (skip if non-interactive)
	if [[ $NON_INTERACTIVE == true ]]; then
		# Use environment variable or default to Y
		INSTALL_PYTHON=${INSTALL_PYTHON:-Y}
		print_status "Non-interactive mode: Python support = $INSTALL_PYTHON"
		echo ""
	else
		echo "Do you want to install advanced Python features?"
		echo "This includes: uv, ruff, mypy, basedpyright, and Python quality hooks"
		read -r -p "Install Python support? (Y/n): " INSTALL_PYTHON </dev/tty
		INSTALL_PYTHON=${INSTALL_PYTHON:-Y}
		echo ""
		echo ""
	fi

	# =============================================================================
	# Install Claude CodePro Files
	# =============================================================================

	print_section "Installing Claude CodePro Files"

	# Download .claude directory (update existing files, preserve settings.local.json and custom rules)
	print_status "Installing .claude files..."

	local files
	files=$(get_repo_files ".claude")

	local file_count=0
	if [[ -n $files ]]; then
		while IFS= read -r file_path; do
			if [[ -n $file_path ]]; then
				# Skip custom rules (never overwrite)
				if [[ $file_path == *"rules/custom/"* ]]; then
					continue
				fi

				# Skip Python hook if Python not selected
				if [[ $INSTALL_PYTHON =~ ^[Yy]$ ]] || [[ $file_path != *"file_checker_python.sh"* ]]; then
					# Ask about settings.local.json if it already exists
					if [[ $file_path == *"settings.local.json"* ]] && [[ -f "$PROJECT_DIR/.claude/settings.local.json" ]]; then
						print_warning "settings.local.json already exists"
						echo "This file may contain new features in this version."
						read -r -p "Overwrite settings.local.json? (y/N): " -n 1 </dev/tty
						echo
						[[ ! $REPLY =~ ^[Yy]$ ]] && print_success "Kept existing settings.local.json" && continue
					fi

					# Special handling for config.yaml to preserve custom rules
					if [[ $file_path == *"rules/config.yaml"* ]] && [[ -f "$PROJECT_DIR/.claude/rules/config.yaml" ]]; then
						# Download new config to temp location
						local temp_config="${TEMP_DIR}/config.yaml"
						if download_file "$file_path" "$temp_config" 2>/dev/null; then
							# Merge configs preserving custom sections
							merge_rules_config "$temp_config" "$PROJECT_DIR/.claude/rules/config.yaml"
							((file_count++)) || true
							echo "   ✓ config.yaml (merged with custom rules)"
						fi
						continue
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

	# Create custom rules directories if they don't exist
	print_status "Setting up custom rules directories..."
	for category in core extended workflow; do
		local custom_dir="$PROJECT_DIR/.claude/rules/custom/$category"
		if [[ ! -d "$custom_dir" ]]; then
			mkdir -p "$custom_dir"
			touch "$custom_dir/.gitkeep"
			echo "   ✓ Created custom/$category/"
		fi
	done

	# Remove Python hook from settings.local.json if Python not selected
	if [[ ! $INSTALL_PYTHON =~ ^[Yy]$ ]] && [[ -f "$PROJECT_DIR/.claude/settings.local.json" ]]; then
		print_status "Removing Python hook from settings.local.json..."

		# Ensure jq is available
		if ! ensure_jq; then
			print_warning "jq not available, skipping Python hook removal"
		else
			# Use jq to cleanly remove Python hook and permissions
			local temp_file="${TEMP_DIR}/settings-temp.json"
			jq '
				# Remove Python hook from PostToolUse
				if .hooks.PostToolUse then
					.hooks.PostToolUse |= map(
						if .hooks then
							.hooks |= map(select(.command | contains("file_checker_python.sh") | not))
						else . end
					)
				else . end |
				# Remove Python-related permissions
				if .permissions.allow then
					.permissions.allow |= map(
						select(
							. != "Bash(basedpyright:*)" and
							. != "Bash(mypy:*)" and
							. != "Bash(python tests:*)" and
							. != "Bash(python:*)" and
							. != "Bash(pyright:*)" and
							. != "Bash(pytest:*)" and
							. != "Bash(ruff check:*)" and
							. != "Bash(ruff format:*)" and
							. != "Bash(uv add:*)" and
							. != "Bash(uv pip show:*)" and
							. != "Bash(uv pip:*)" and
							. != "Bash(uv run:*)"
						)
					)
				else . end
			' "$PROJECT_DIR/.claude/settings.local.json" >"$temp_file"
			mv "$temp_file" "$PROJECT_DIR/.claude/settings.local.json"
			print_success "Configured settings.local.json without Python support"
		fi
	fi

	chmod +x "$PROJECT_DIR/.claude/hooks/"*.sh 2>/dev/null || true
	print_success "Installed $file_count .claude files"
	echo ""

	# Install other configuration directories
	if [[ ! -d "$PROJECT_DIR/.cipher" ]]; then
		install_directory ".cipher" "$PROJECT_DIR"
		echo ""
	fi

	if [[ ! -d "$PROJECT_DIR/.qlty" ]]; then
		install_directory ".qlty" "$PROJECT_DIR"
		echo ""
	fi

	# Install MCP configurations
	merge_mcp_config ".mcp.json" "$PROJECT_DIR/.mcp.json"
	merge_mcp_config ".mcp-funnel.json" "$PROJECT_DIR/.mcp-funnel.json"
	echo ""

	# Install scripts
	mkdir -p "$PROJECT_DIR/scripts/lib"
	install_file "scripts/lib/setup-env.sh" "$PROJECT_DIR/scripts/lib/setup-env.sh"
	install_file "scripts/build-rules.sh" "$PROJECT_DIR/scripts/build-rules.sh"
	chmod +x "$PROJECT_DIR/scripts/"*.sh
	chmod +x "$PROJECT_DIR/scripts/lib/"*.sh
	echo ""

	# Create .nvmrc for Node.js version management
	print_status "Creating .nvmrc for Node.js 22..."
	echo "22" >"$PROJECT_DIR/.nvmrc"
	print_success "Created .nvmrc"
	echo ""

	# =============================================================================
	# Environment Setup
	# =============================================================================

	if [[ $SKIP_ENV_SETUP == true ]] || [[ $NON_INTERACTIVE == true ]]; then
		print_section "Environment Setup"
		print_status "Skipping interactive environment setup (non-interactive mode)"
		print_warning "Make sure to set up .env file manually or via environment variables"
		echo ""
	else
		print_section "Environment Setup"
		bash "$PROJECT_DIR/scripts/lib/setup-env.sh"
	fi

	# =============================================================================
	# Install Dependencies
	# =============================================================================

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

	# =============================================================================
	# Build Rules
	# =============================================================================

	print_section "Building Rules"
	build_rules
	echo ""

	# =============================================================================
	# Configure Shell
	# =============================================================================

	print_section "Configuring Shell"
	add_cc_alias

	# =============================================================================
	# Success Message
	# =============================================================================

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

# =============================================================================
# Execute Main
# =============================================================================

main "$@"
