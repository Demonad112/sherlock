#!/bin/bash
# Quick start script for Sherlock in GitHub Codespaces

set -e  # Exit on error

echo "🔍 Sherlock Quick Start Setup"
echo "=============================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9 or later."
    exit 1
fi

echo "✅ Python $(python3 --version | cut -d' ' -f2) detected"
echo ""

# Install in development mode
echo "📦 Installing Sherlock..."
pip install -e . > /dev/null 2>&1

# Verify installation
if command -v sherlock &> /dev/null; then
    echo "✅ Sherlock installed successfully"
    echo ""
    echo "📊 Version information:"
    sherlock --version
    echo ""
else
    echo "❌ Installation failed"
    exit 1
fi

echo "🎯 Ready to use!"
echo ""
echo "Try these commands:"
echo "  sherlock --help          # Show all options"
echo "  sherlock alice           # Search for 'alice'"
echo "  sherlock --csv alice     # Export results to CSV"
echo "  sherlock --verbose alice # Show detailed output"
echo ""
