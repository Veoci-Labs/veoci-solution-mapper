#!/bin/bash
# Build script for veoci-map executable
# Usage: GEMINI_API_KEY=xxx ./build.sh

set -e

echo "=== Veoci Map Build Script ==="
echo ""

# Check for PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "ERROR: PyInstaller not found. Install with: pip install pyinstaller"
    exit 1
fi

# Backup config.py (in case script exits early)
CONFIG_PATH="src/veoci_mapper/config.py"
BACKUP_PATH="/tmp/config.py.backup"
cp "$CONFIG_PATH" "$BACKUP_PATH"

# Function to restore backup on exit
restore_config() {
    if [ -f "$BACKUP_PATH" ]; then
        echo ""
        echo "Restoring config.py..."
        mv "$BACKUP_PATH" "$CONFIG_PATH"
    fi
}
trap restore_config EXIT

# Inject secret
echo "Step 1: Injecting build-time secrets..."
python3 build/inject_secret.py
echo ""

# Build executable
echo "Step 2: Building executable with PyInstaller..."
python3 -m PyInstaller veoci-map.spec --clean --noconfirm
echo ""

# Success
echo "=== Build Complete ==="
echo ""
echo "Executable: dist/veoci-map"
echo ""
echo "Test it:"
echo "  ./dist/veoci-map --help"
echo ""
