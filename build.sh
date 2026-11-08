#!/usr/bin/env bash
set -e

echo "Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "Installing dependencies..."
pip install pynput pyinstaller

echo "Building binary..."
pyinstaller --onefile --name autoclicker autoclicker.py

echo
echo "Done! Your binary is at: dist/autoclicker"
