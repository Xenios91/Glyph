#!/bin/bash
set -e

# Define variables for easier updates later
GHIDRA_ZIP="ghidra_12.0.4_PUBLIC_20260303.zip"
GHIDRA_URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.0.4_build/${GHIDRA_ZIP}"
GHIDRA_FOLDER="ghidra_12.0.4_PUBLIC"
TARGET_DIR="/opt/Ghidra"

echo "--- Downloading Ghidra 12.0.4 ---"
wget -q $GHIDRA_URL

echo "--- Extracting and Moving to $TARGET_DIR ---"
unzip -q $GHIDRA_ZIP
sudo mv $GHIDRA_FOLDER $TARGET_DIR
rm $GHIDRA_ZIP

echo "--- Setting up Python Environment ---"
# Creating the venv as requested
python3 -m venv glyph_venv

# Install requirements using the venv's pip to ensure isolation
./glyph_venv/bin/pip install -r requirements.txt

echo "--- Clanker environment setup complete ---"