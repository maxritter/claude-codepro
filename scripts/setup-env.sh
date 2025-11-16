#!/bin/bash

# =============================================================================
# Claude CodePro Environment Setup
# Interactive script to create .env file with API keys
# Compatible with bash 3.2+ (macOS, Linux, WSL2)
# =============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Color codes
BLUE='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

key_exists() {
    grep -q "^${1}=" "$2" 2>/dev/null
}

add_env_key() {
    local key=$1 value=$2 comment=$3 env_file=$4
    key_exists "$key" "$env_file" && return 0
    echo "" >> "$env_file"
    [[ -n "$comment" ]] && echo "# $comment" >> "$env_file"
    echo "${key}=${value}" >> "$env_file"
}

prompt_api_key() {
    local title=$1 key=$2 description=$3 url=$4
    shift 4
    local steps=("$@")

    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${title}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "   Used for: $description"
    echo "   Create at: $url"
    [[ ${#steps[@]} -gt 0 ]] && echo "" && printf "   %s\n" "${steps[@]}"
    echo ""
}

# Get API config data for a given key (bash 3.2+ compatible)
get_api_config() {
    local key=$1
    case $key in
        OPENAI_API_KEY)
            echo "2. OpenAI API Key - For Memory LLM Calls|Low-usage LLM calls in Cipher memory system|https://platform.openai.com/account/api-keys"
            ;;
        CONTEXT7_API_KEY)
            echo "3. Context7 API Key - Free Library Documentation|Up-to-date library documentation access|https://context7.com/dashboard"
            ;;
        REF_API_KEY)
            echo "4. Ref API Key - Free Documentation Search|Searching public and private documentation|https://ref.tools/dashboard"
            ;;
        FIRECRAWL_API_KEY)
            echo "5. Firecrawl API Key - Web Crawling|Web scraping and crawling capabilities|https://www.firecrawl.dev/app"
            ;;
    esac
}

# -----------------------------------------------------------------------------
# Interactive .env Setup
# -----------------------------------------------------------------------------

setup_env_file() {
    print_section "API Keys Setup"

    local ENV_FILE="$PROJECT_DIR/.env"
    local APPEND_MODE=false

    if [[ -f "$ENV_FILE" ]]; then
        print_success "Found existing .env file"
        echo "We'll append Claude CodePro configuration to your existing file."
        echo ""
        APPEND_MODE=true
    else
        echo "Let's set up your API keys. I'll guide you through each one."
        echo ""
    fi

    # Zilliz Cloud (Milvus)
    if ! $APPEND_MODE || ! key_exists "MILVUS_TOKEN" "$ENV_FILE"; then
        prompt_api_key "1. Zilliz Cloud - Free Vector DB for Semantic Search & Memory" \
            "MILVUS_TOKEN" \
            "Persistent memory across CC sessions & semantic code search" \
            "https://zilliz.com/cloud" \
            "Steps:" \
            "1. Sign up for free account" \
            "2. Create a new cluster (Serverless is free)" \
            "3. Go to Cluster -> Overview -> Connect" \
            "4. Copy the Token and Public Endpoint" \
            "5. Go to Clusters -> Users -> Admin -> Reset Password"
        read -r -p "   Enter MILVUS_TOKEN: " MILVUS_TOKEN < /dev/tty
        read -r -p "   Enter MILVUS_ADDRESS (Public Endpoint): " MILVUS_ADDRESS < /dev/tty
        read -r -p "   Enter VECTOR_STORE_USERNAME (usually db_xxxxx): " VECTOR_STORE_USERNAME < /dev/tty
        read -r -p "   Enter VECTOR_STORE_PASSWORD: " VECTOR_STORE_PASSWORD < /dev/tty
        echo ""
    else
        print_success "Zilliz Cloud configuration already exists, skipping"
        echo ""
    fi

    # OpenAI, Context7, Ref, Firecrawl
    for key in OPENAI_API_KEY CONTEXT7_API_KEY REF_API_KEY FIRECRAWL_API_KEY; do
        if ! $APPEND_MODE || ! key_exists "$key" "$ENV_FILE"; then
            local config_data=$(get_api_config "$key")
            IFS='|' read -r title description url <<< "$config_data"
            prompt_api_key "$title" "$key" "$description" "$url"
            read -r -p "   Enter $key: " value < /dev/tty
            eval "$key=\"\$value\""
            echo ""
        else
            print_success "$key already exists, skipping"
            echo ""
        fi
    done

    # Create or append to .env file
    if $APPEND_MODE; then
        # Append mode: add missing keys (only add header if not already present)
        if ! grep -q "# Claude CodePro Configuration" "$ENV_FILE"; then
            echo "" >> "$ENV_FILE"
            echo "# =============================================================================" >> "$ENV_FILE"
            echo "# Claude CodePro Configuration" >> "$ENV_FILE"
            echo "# =============================================================================" >> "$ENV_FILE"
        fi

        add_env_key "MILVUS_TOKEN" "${MILVUS_TOKEN}" "Zilliz Cloud (Free Vector DB for Semantic Search & Persistent Memory)" "$ENV_FILE"
        add_env_key "MILVUS_ADDRESS" "${MILVUS_ADDRESS}" "" "$ENV_FILE"
        add_env_key "VECTOR_STORE_URL" "${MILVUS_ADDRESS}" "" "$ENV_FILE"
        add_env_key "VECTOR_STORE_USERNAME" "${VECTOR_STORE_USERNAME}" "" "$ENV_FILE"
        add_env_key "VECTOR_STORE_PASSWORD" "${VECTOR_STORE_PASSWORD}" "" "$ENV_FILE"
        add_env_key "OPENAI_API_KEY" "${OPENAI_API_KEY}" "OpenAI API Key - Used for Persistent Memory LLM Calls (Low Usage)" "$ENV_FILE"
        add_env_key "CONTEXT7_API_KEY" "${CONTEXT7_API_KEY}" "Context7 API Key - Free Tier Available" "$ENV_FILE"
        add_env_key "REF_API_KEY" "${REF_API_KEY}" "Ref API Key - Free Tier Available" "$ENV_FILE"
        add_env_key "FIRECRAWL_API_KEY" "${FIRECRAWL_API_KEY}" "Firecrawl API Key - Free Tier Available" "$ENV_FILE"
        add_env_key "USE_ASK_CIPHER" "true" "Configuration Settings" "$ENV_FILE"
        add_env_key "VECTOR_STORE_TYPE" "milvus" "" "$ENV_FILE"
        add_env_key "FASTMCP_LOG_LEVEL" "ERROR" "" "$ENV_FILE"

        print_success "Updated .env file with Claude CodePro configuration"
    else
        # Create new file
        cat > "$ENV_FILE" <<EOF
# Zilliz Cloud (Free Vector DB for Semantic Search & Persistent Memory)
# Create at https://zilliz.com/cloud
MILVUS_TOKEN=${MILVUS_TOKEN}
MILVUS_ADDRESS=${MILVUS_ADDRESS}
VECTOR_STORE_URL=${MILVUS_ADDRESS}
VECTOR_STORE_USERNAME=${VECTOR_STORE_USERNAME}
VECTOR_STORE_PASSWORD=${VECTOR_STORE_PASSWORD}

# OpenAI API Key - Used for Persistent Memory LLM Calls (Low Usage)
# Create at https://platform.openai.com/account/api-keys
OPENAI_API_KEY=${OPENAI_API_KEY}

# Context7 API Key - Free Tier Available, Limit Tokens to 2000 in Libraries -> Token Limit
# Create at https://context7.com/dashboard
CONTEXT7_API_KEY=${CONTEXT7_API_KEY}

# Ref API Key - Free Tier Available, You can add your own Resources in the UI
# Create at https://ref.tools/dashboard
REF_API_KEY=${REF_API_KEY}

# Firecrawl API Key - Free Tier Available, Used for Web Crawling
# Create at https://www.firecrawl.dev/app
FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}

# Configuration Settings - No need to adjust
USE_ASK_CIPHER=true
VECTOR_STORE_TYPE=milvus
FASTMCP_LOG_LEVEL=ERROR
EOF

        print_success "Created .env file with your API keys"
    fi
    echo ""
}

# Main
setup_env_file
