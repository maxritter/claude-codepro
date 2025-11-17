#!/bin/bash
# =============================================================================
# Migration Functions - Handle upgrades from older versions
# =============================================================================

# Check if migration is needed
# Returns: 0 if migration needed, 1 otherwise
needs_migration() {
	local rules_dir="$PROJECT_DIR/.claude/rules"

	# Check if old structure exists (core/extended/workflow at root level)
	if [[ -d "$rules_dir/core" ]] || [[ -d "$rules_dir/extended" ]] || [[ -d "$rules_dir/workflow" ]]; then
		# Make sure it's not already migrated (check for standard/ or custom/)
		if [[ ! -d "$rules_dir/standard" ]]; then
			return 0
		fi
	fi

	return 1
}

# Migrate from old rules structure to new standard/custom structure
# Moves old core/extended/workflow to standard/
# Creates empty custom/ directories
migrate_rules_structure() {
	local rules_dir="$PROJECT_DIR/.claude/rules"

	print_section "Migrating Rules Structure"

	echo "We detected an old rules directory structure that needs to be migrated."
	echo "This will move your existing rules to the new 'standard/' directory."
	echo ""
	print_warning "Any custom rules you created will need to be manually moved to 'custom/' after migration."
	echo ""
	read -r -p "Continue with migration? (Y/n): " -n 1 </dev/tty
	echo ""
	echo ""

	# Default to Y
	REPLY=${REPLY:-Y}

	if [[ ! $REPLY =~ ^[Yy]$ ]]; then
		print_error "Migration cancelled. Please migrate manually before continuing."
		echo ""
		echo "To migrate manually:"
		echo "  1. Create .claude/rules/standard/"
		echo "  2. Move core/, extended/, workflow/ into standard/"
		echo "  3. Create .claude/rules/custom/core/, custom/extended/, custom/workflow/"
		echo "  4. Re-run installation"
		exit 1
	fi

	# Create backup
	local backup_dir="$PROJECT_DIR/.claude/rules.backup.$(date +%s)"
	print_status "Creating backup at rules.backup.$(basename "$backup_dir")..."
	cp -r "$rules_dir" "$backup_dir"
	print_success "Backup created"

	# Create new structure
	print_status "Creating new directory structure..."
	mkdir -p "$rules_dir/standard"
	mkdir -p "$rules_dir/custom/core"
	mkdir -p "$rules_dir/custom/extended"
	mkdir -p "$rules_dir/custom/workflow"

	# Move old directories to standard/
	for dir in core extended workflow; do
		if [[ -d "$rules_dir/$dir" ]]; then
			print_status "Moving $dir/ to standard/$dir/..."
			mv "$rules_dir/$dir" "$rules_dir/standard/"
			print_success "Moved $dir/"
		fi
	done

	# Create .gitkeep files in custom directories
	touch "$rules_dir/custom/core/.gitkeep"
	touch "$rules_dir/custom/extended/.gitkeep"
	touch "$rules_dir/custom/workflow/.gitkeep"

	print_success "Migration complete!"
	echo ""
	print_status "Next steps:"
	echo "  → If you have custom rules, move them from standard/ to custom/"
	echo "  → Backup saved at: $(basename "$backup_dir")"
	echo ""
}

# Migrate config.yaml from old format to new standard/custom format
# Only runs if config.yaml exists and doesn't have standard/custom sections
migrate_config_yaml() {
	local config_file="$PROJECT_DIR/.claude/rules/config.yaml"

	[[ ! -f "$config_file" ]] && return

	# Check if already migrated (has 'standard:' in it)
	if grep -q "standard:" "$config_file"; then
		return
	fi

	print_status "Migrating config.yaml to new format..."

	local temp_config="$TEMP_DIR/config-migrated.yaml"

	# Read old config and convert to new format
	awk '
		/^commands:/ {
			print
			in_commands=1
			next
		}
		in_commands && /^  [a-z_-]+:/ && !/^    / {
			# New command starting, close previous rules if needed
			if (in_rules) {
				print "      custom: []"
				in_rules=0
			}
			print
			command=1
			next
		}
		command && /^    rules:/ {
			print "    rules:"
			print "      standard:"
			in_rules=1
			next
		}
		command && in_rules && /^    - / {
			print "      " $0
			next
		}
		command && in_rules && /^    [a-z_-]+:/ {
			# End of rules section, add empty custom
			print "      custom: []"
			in_rules=0
			print
			next
		}
		# Skip blank lines while in rules section
		in_rules && /^[[:space:]]*$/ {
			next
		}
		# Default: print line as-is
		{ print }
		END {
			# Close last command rules if needed
			if (in_rules) {
				print "      custom: []"
			}
		}
	' "$config_file" > "$temp_config"

	mv "$temp_config" "$config_file"
	print_success "Migrated config.yaml"
}

# Run full migration
run_migration() {
	if needs_migration; then
		migrate_rules_structure
		migrate_config_yaml
	fi
}
