#!/bin/bash
# =============================================================================
# Shell Configuration Functions - Aliases and shell environment setup
# =============================================================================

# Add or update alias in a shell configuration file
# Args:
#   $1 - Shell configuration file path (e.g., "$HOME/.bashrc")
#   $2 - Alias command to add
#   $3 - Shell name for display (e.g., ".bashrc")
#   $4 - Alias name (e.g., "ccp")
# Returns: void
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

# Ensure NVM initialization is present in shell configuration
# Args:
#   $1 - Shell configuration file path
#   $2 - Shell name for display
# Returns: void
ensure_nvm_in_shell() {
	local shell_file=$1
	local shell_name=$2

	[[ ! -f $shell_file ]] && return

	# Check if NVM is already sourced in the shell config
	if ! grep -q "NVM_DIR" "$shell_file"; then
		print_status "Adding NVM initialization to $shell_name..."
		cat >>"$shell_file" <<'EOF'

# NVM (Node Version Manager) - flexible location detection
if [ -z "$NVM_DIR" ]; then
  if [ -s "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"
  elif [ -s "/usr/local/share/nvm/nvm.sh" ]; then
    export NVM_DIR="/usr/local/share/nvm"
  fi
fi
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
EOF
		print_success "Added NVM initialization to $shell_name"
	fi
}

# Add 'ccp' alias to all detected shells
# Creates an alias that:
#   - Changes to project directory
#   - Loads NVM
#   - Builds rules
#   - Starts Claude Code with dotenvx
# Returns: void
add_cc_alias() {
	local alias_name="ccp"

	print_status "Configuring shell for NVM and '$alias_name' alias..."

	# Ensure NVM initialization is in shell configs
	ensure_nvm_in_shell "$HOME/.bashrc" ".bashrc"
	ensure_nvm_in_shell "$HOME/.zshrc" ".zshrc"

	# Flexible NVM detection for bash/zsh alias
	local bash_alias="alias ${alias_name}=\"cd '$PROJECT_DIR' && ([ -s \\\"\\\$HOME/.nvm/nvm.sh\\\" ] && export NVM_DIR=\\\"\\\$HOME/.nvm\\\" || [ -s \\\"/usr/local/share/nvm/nvm.sh\\\" ] && export NVM_DIR=\\\"/usr/local/share/nvm\\\") && [ -s \\\"\\\$NVM_DIR/nvm.sh\\\" ] && . \\\"\\\$NVM_DIR/nvm.sh\\\" && nvm use && bash scripts/build-rules.sh &>/dev/null && clear && dotenvx run -- claude\""

	# Flexible NVM detection for fish alias
	local fish_alias="alias ${alias_name}='cd $PROJECT_DIR; and begin; if test -s \"\$HOME/.nvm/nvm.sh\"; set -x NVM_DIR \"\$HOME/.nvm\"; else if test -s \"/usr/local/share/nvm/nvm.sh\"; set -x NVM_DIR \"/usr/local/share/nvm\"; end; end; and test -s \"\$NVM_DIR/nvm.sh\"; and source \"\$NVM_DIR/nvm.sh\"; and nvm use; and bash scripts/build-rules.sh &>/dev/null; and clear; and dotenvx run -- claude; end'"

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
