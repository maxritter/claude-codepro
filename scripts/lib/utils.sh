#!/bin/bash
# =============================================================================
# Utility Functions - Cleanup, jq installation, and helper utilities
# =============================================================================

# Cleanup on exit
# Removes temporary directory and restores cursor visibility
cleanup() {
	if [[ -d $TEMP_DIR ]]; then
		rm -rf "$TEMP_DIR"
	fi
	tput cnorm 2>/dev/null || true
}

# Install jq if needed
# jq is required for JSON processing (GitHub API, MCP config merging)
# Returns: 0 if jq is available, 1 otherwise
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
