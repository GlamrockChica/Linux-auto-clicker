#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

APP="$HOME/.local/bin/autoclicker"
# How to spot a running Auto Clicker: the installed app, or `python autoclicker.py`
RUNNING_APP="^$APP( |$)"
# (only a process that *is* Python, never a shell that mentions it)
RUNNING_SCRIPT="^[^ ]*python[0-9.]* ([^ ]*/)?autoclicker\.py( |$)"

is_running() {
    pgrep -f "$RUNNING_APP" >/dev/null || pgrep -f "$RUNNING_SCRIPT" >/dev/null
}

close_app() {
    is_running || return 0
    echo "Closing Auto Clicker..."
    # Ask nicely first: the app saves its settings and lets go of anything held down
    pkill -TERM -f "$RUNNING_APP" || true
    pkill -TERM -f "$RUNNING_SCRIPT" || true
    for _ in $(seq 1 50); do  # wait up to 5 seconds
        is_running || return 0
        sleep 0.1
    done
    echo "It didn't close by itself, so forcing it to close..."
    pkill -KILL -f "$RUNNING_APP" || true
    pkill -KILL -f "$RUNNING_SCRIPT" || true
    sleep 0.5
}

close_app

echo "Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install pynput pyinstaller

echo "Making the app icon..."
# (white for light mode, black for dark mode: the computer picks the right one itself)
python autoclicker.py --write-icons

echo "Building app..."
pyinstaller --onefile --windowed --name autoclicker autoclicker.py

echo "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
cp dist/autoclicker "$APP.new"
chmod +x "$APP.new"
mv -f "$APP.new" "$APP"

echo "Creating menu entry..."
cat > "$HOME/.local/share/applications/autoclicker.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=Auto Clicker
Comment=Simple auto clicker
Exec=$APP
Icon=autoclicker
StartupWMClass=Autoclicker
Terminal=false
Categories=Utility;
DESKTOP

chmod +x "$HOME/.local/share/applications/autoclicker.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "Starting Auto Clicker..."
# Start it from the menu entry (so the dock shows it properly), or directly if that
# doesn't work. Either way it keeps running after this terminal closes.
if ! (command -v gtk-launch >/dev/null && gtk-launch autoclicker >/dev/null 2>&1); then
    setsid -f "$APP" >/dev/null 2>&1 < /dev/null
fi

echo
echo "Done! Auto Clicker has been updated and started."
