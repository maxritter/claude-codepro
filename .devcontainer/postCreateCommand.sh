#!/usr/bin/env bash

set -e

# =============================================================================
# Dev Container Post-Create Setup
# Runs automatically after dev container is created
# =============================================================================

echo "=================================================="
echo "Dev Container Post-Create Setup"
echo "=================================================="
echo ""

# Install zsh fzf
echo "Configuring zsh with fzf..."
echo -e "\nsource <(fzf --zsh)" >>~/.zshrc

# Enable dotenv plugin for automatic .env loading
# This will auto-load .env files when you cd into directories
if ! grep -q "plugins=.*dotenv" ~/.zshrc; then
    # Add dotenv to plugins array if not already present
    sed -i 's/plugins=(/plugins=(dotenv /' ~/.zshrc

    # Disable prompt for auto-loading .env (trust dev container environment)
    echo -e "\n# Auto-load .env files without prompting" >>~/.zshrc
    echo 'export ZSH_DOTENV_PROMPT=false' >>~/.zshrc
fi

# Make zsh the default shell
chsh -s $(which zsh)

echo "✓ Shell configuration complete"
echo ""

# =============================================================================
# Install Claude CodePro (latest version)
# =============================================================================

echo "=================================================="
echo "Installing Claude CodePro..."
echo "=================================================="
echo ""

# Download and run the latest installer
curl -sSL https://raw.githubusercontent.com/maxritter/claude-codepro/main/scripts/install.py -o /tmp/claude-codepro-install.py
python3 /tmp/claude-codepro-install.py --non-interactive

# Get project slug from workspace folder name (matches container name)
PROJECT_SLUG=$(basename "$PWD")

echo ""
echo "=================================================="
echo "Dev Container Setup Complete!"
echo "=================================================="
echo ""
echo "To continue Claude Code setup in your favorite terminal:"
echo ""
echo "  1. Open your preferred terminal (iTerm, Terminal, etc.)"
echo ""
echo "  2. Connect to the dev container:"
echo "     docker exec -it \$(docker ps --filter \"name=${PROJECT_SLUG}\" -q) zsh"
echo ""
echo "  3. Start Claude CodePro:"
echo "     ccp"
echo ""
echo "  4. In Claude Code, run: /config"
echo "     - Set 'Auto-connect to IDE' = true"
echo "     - Set 'Auto-compact' = false"
echo ""
echo "  5. Initialize your project:"
echo "     /setup"
echo ""
echo "=================================================="
