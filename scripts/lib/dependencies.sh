#!/bin/bash
# =============================================================================
# Dependency Installation Functions - Node.js, Python, and other tools
# =============================================================================

# Install Node.js via NVM
# Installs NVM if not present, then installs Node.js 22.x
# Returns: 0 on success, exits on failure
install_nodejs() {
	# Function to detect and load NVM from various locations
	load_nvm() {
		# Common NVM installation locations
		local nvm_locations=(
			"$HOME/.nvm"
			"/usr/local/share/nvm"
			"$NVM_DIR"
		)

		for nvm_dir in "${nvm_locations[@]}"; do
			if [[ -n $nvm_dir ]] && [[ -s "$nvm_dir/nvm.sh" ]]; then
				export NVM_DIR="$nvm_dir"
				# shellcheck source=/dev/null
				\. "$NVM_DIR/nvm.sh"
				# shellcheck source=/dev/null
				[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
				return 0
			fi
		done
		return 1
	}

	# Try to load existing NVM installation
	if load_nvm; then
		print_success "NVM already installed at $NVM_DIR"
	else
		print_status "Installing NVM (Node Version Manager)..."

		# Install NVM
		curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

		# Try to load the newly installed NVM
		if ! load_nvm; then
			print_error "NVM installation failed or unable to load NVM"
			print_error "Please install NVM manually: https://github.com/nvm-sh/nvm"
			exit 1
		fi

		print_success "Installed NVM at $NVM_DIR"
	fi

	# Verify nvm command is available
	if ! command -v nvm &>/dev/null; then
		print_error "nvm command not found after loading"
		print_error "NVM_DIR: $NVM_DIR"
		print_error "Please restart your shell or manually source NVM"
		exit 1
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

# Install uv (Python package manager)
# Returns: 0 on success
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

# Install Python development tools
# Installs: ruff, mypy, basedpyright
# Requires: uv must be installed first
install_python_tools() {
	print_status "Installing Python tools globally..."

	uv tool install ruff
	uv tool install mypy
	uv tool install basedpyright

	print_success "Installed Python tools (ruff, mypy, basedpyright)"
}

# Install qlty (code quality tool)
# Returns: 0 on success
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

# Install Claude Code CLI
# Returns: 0 on success
install_claude_code() {
	if command -v claude &>/dev/null; then
		print_success "Claude Code already installed"
		return 0
	fi

	print_status "Installing Claude Code..."
	curl -fsSL https://claude.ai/install.sh | bash

	print_success "Installed Claude Code"
}

# Install Cipher (memory management for Claude)
# Returns: 0 on success
# Requires: npm must be installed
install_cipher() {
	if command -v cipher &>/dev/null; then
		print_success "Cipher already installed"
		return 0
	fi

	print_status "Installing Cipher..."
	npm install -g @byterover/cipher

	print_success "Installed Cipher"
}

# Install Newman (Postman CLI)
# Returns: 0 on success
# Requires: npm must be installed
install_newman() {
	if command -v newman &>/dev/null; then
		print_success "Newman already installed"
		return 0
	fi

	print_status "Installing Newman..."
	npm install -g newman

	print_success "Installed Newman"
}

# Install dotenvx (environment variable management)
# Returns: 0 on success
# Requires: npm must be installed
install_dotenvx() {
	if command -v dotenvx &>/dev/null; then
		print_success "dotenvx already installed"
		return 0
	fi

	print_status "Installing dotenvx..."
	npm install -g @dotenvx/dotenvx

	print_success "Installed dotenvx"
}
