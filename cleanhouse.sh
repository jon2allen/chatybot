#!/bin/bash

echo "Starting clean house for chatybot environment..."

# 1. Remove persistent config directory
if [ -d "$HOME/.config/chatybot" ]; then
    echo "Removing config directory: $HOME/.config/chatybot"
    rm -rf "$HOME/.config/chatybot"
fi

# 2. Remove persistent data directory (history and db)
if [ -d "$HOME/.local/share/chatybot" ]; then
    echo "Removing local share directory: $HOME/.local/share/chatybot"
    rm -rf "$HOME/.local/share/chatybot"
fi

# 3. Clean up the chatybot repository clone
REPO_DIR="$HOME/github/chatybot"
if [ -d "$REPO_DIR" ]; then
    echo "Cleaning up repository at $REPO_DIR..."
    cd "$REPO_DIR"
    
    # Remove virtual environment
    if [ -d ".venv" ]; then
        echo "Removing virtual environment: $REPO_DIR/.venv"
        rm -rf .venv
    fi
    
    # Pull the latest changes from master
    echo "Pulling the latest changes from git master..."
    git checkout master
    git pull origin master
else
    echo "Repository directory $REPO_DIR not found. Skipping repo cleanup."
fi

# 4. Look for and remove any lingering global bin entry if installed out of venv
if [ -f "$HOME/.local/bin/chatybot" ]; then
    echo "Removing global binary: $HOME/.local/bin/chatybot"
    rm "$HOME/.local/bin/chatybot"
fi

echo "Clean house complete! You are ready to create a fresh virtual environment and install."
