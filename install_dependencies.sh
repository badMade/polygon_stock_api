#!/bin/bash
# install_dependencies.sh - Install all project dependencies
# Usage: ./install_dependencies.sh [--dev] [--all]
#
# Options:
#   --dev   Install development dependencies (pytest, flake8, etc.)
#   --all   Install all optional dependencies (Notion, Polygon clients)
#   (no args) Install only runtime dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📦 Installing dependencies for polygon_stock_api..."

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo "❌ Error: pip is not installed. Please install Python and pip first."
    exit 1
fi

# Parse arguments
INSTALL_DEV=false
INSTALL_ALL=false

for arg in "$@"; do
    case $arg in
        --dev)
            INSTALL_DEV=true
            ;;
        --all)
            INSTALL_ALL=true
            ;;
        --help|-h)
            echo "Usage: ./install_dependencies.sh [--dev] [--all]"
            echo ""
            echo "Options:"
            echo "  --dev   Install development dependencies (pytest, flake8, etc.)"
            echo "  --all   Install all dependencies including optional integrations"
            echo "  (no args) Install only runtime dependencies"
            exit 0
            ;;
        *)
            echo "⚠️  Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Upgrade pip first
echo "🔄 Upgrading pip..."
pip install --upgrade pip

# Install runtime dependencies
echo "📥 Installing runtime dependencies..."
pip install -r requirements.txt

if [ "$INSTALL_DEV" = true ]; then
    echo "📥 Installing development dependencies..."
    pip install -r requirements-dev.txt

    # Install pylint separately for cross-version compatibility
    echo "📥 Installing pylint..."
    pip install pylint
fi

if [ "$INSTALL_ALL" = true ]; then
    echo "📥 Installing optional integration packages..."
    pip install notion-client polygon-api-client
fi

echo ""
echo "✅ Installation complete!"
echo ""

# Show what was installed
echo "📋 Installed packages:"
pip list --format=columns | grep -E "(requests|pytest|flake8|pylint|notion|polygon)" || true

echo ""
echo "🚀 You're ready to go!"
if [ "$INSTALL_DEV" = true ]; then
    echo "   Run tests with: pytest"
    echo "   Run linting with: flake8"
fi
