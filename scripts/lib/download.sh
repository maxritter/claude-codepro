#!/bin/bash
# =============================================================================
# Download Functions - GitHub file downloads and API interactions
# =============================================================================

# Download a file from the repository
# Args:
#   $1 - Repository path (e.g., "scripts/install.sh")
#   $2 - Destination path on local filesystem
# Returns: 0 on success, 1 on failure
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

# Get all files from a repository directory using GitHub API
# Args:
#   $1 - Directory path in repository (e.g., ".claude")
# Returns: List of file paths, one per line
# Requires: jq must be available (use ensure_jq first)
get_repo_files() {
	local dir_path=$1
	local branch="main"
	local repo_path
	repo_path="${REPO_URL#https://github.com/}"
	local tree_url="https://api.github.com/repos/${repo_path}/git/trees/${branch}?recursive=true"

	local response
	response=$(curl -sL "$tree_url")

	# Ensure jq is available
	if ! ensure_jq; then
		print_error "jq is required but not available"
		return 1
	fi

	# Parse JSON with jq to extract file paths
	echo "$response" | jq -r ".tree[]? | select(.type == \"blob\" and (.path | startswith(\"$dir_path\"))) | .path"
}
