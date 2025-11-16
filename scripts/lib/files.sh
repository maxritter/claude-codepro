#!/bin/bash
# =============================================================================
# File Management Functions - Install and manage Claude CodePro files
# =============================================================================

# Install all files from a repository directory
# Args:
#   $1 - Repository directory path (e.g., ".claude")
#   $2 - Destination base directory (e.g., "$PROJECT_DIR")
# Returns: Number of files installed
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

# Install a single file from repository
# Args:
#   $1 - Repository file path
#   $2 - Destination file path
# Returns: 0 on success, 1 on failure
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

# Merge MCP configuration files
# Preserves existing server configurations while adding new ones
# Args:
#   $1 - Repository file path (e.g., ".mcp.json")
#   $2 - Destination file path
# Returns: 0 on success, 1 on failure
# Requires: jq must be available
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
