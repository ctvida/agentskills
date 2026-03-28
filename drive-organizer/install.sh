#!/usr/bin/env bash
set -e

echo "=== Drive Organizer Skill Installer ==="

TARGET_DIR=${1:-"drive-organizer"}

if [ -d "$TARGET_DIR" ]; then
    echo "Directory $TARGET_DIR already exists in the current path. Aborting."
    exit 1
fi

echo "-> Fetching Drive Organizer from ctvida/agentskills..."
git clone --depth 1 --filter=blob:none --sparse https://github.com/ctvida/agentskills.git _tmp_agentskills_clone > /dev/null 2>&1
cd _tmp_agentskills_clone
git sparse-checkout set drive-organizer > /dev/null 2>&1
cd ..

mv _tmp_agentskills_clone/drive-organizer "$TARGET_DIR"
rm -rf _tmp_agentskills_clone

echo "-> Installing Python dependencies..."
cd "$TARGET_DIR"
pip3 install -r requirements.txt

echo "=== Installation Complete! ==="
echo "Drive Organizer has been installed into: $(pwd)"
echo "You can now run:"
echo "  cd $TARGET_DIR"
echo "  python3 scanner.py [gdrive://root | /local/path]"
