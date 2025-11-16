#!/bin/bash
# =============================================================================
# UI Functions - Colors and Print Utilities
# =============================================================================

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
