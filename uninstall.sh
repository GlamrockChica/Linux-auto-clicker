#!/usr/bin/env bash
# Removes Auto Clicker from this computer. Your settings, profiles, areas and macros are kept unless you
# answer "y" when asked at the end.
set -e

APP="$HOME/.local/bin/autoclicker"
CONFIG="$HOME/.config/autoclicker"

# Close the app if it's running (it saves its settings and lets go of anything held down)
if pgrep -f "^$APP( |$)" >/dev/null; then
    echo "Closing Auto Clicker..."
    pkill -TERM -f "^$APP( |$)" || true
    for _ in $(seq 1 50); do  # wait up to 5 seconds
        pgrep -f "^$APP( |$)" >/dev/null || break
        sleep 0.1
    done
    pkill -KILL -f "^$APP( |$)" || true
fi

echo "Removing the app, its menu entry and its icons..."
rm -f "$APP" "$HOME/.local/share/applications/autoclicker.desktop"
find "$HOME/.local/share/icons" -name 'autoclicker*.png' -delete 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Auto Clicker has been removed."
echo

# Where the settings, profiles, areas and macros are (they can be moved from inside the app)
SETTINGS="$CONFIG"
PROFILES="$CONFIG/profiles"
AREAS="$CONFIG/areas"
MACROS="$CONFIG/macros"
where() {  # locations.json's setting for "settings", "profiles", "areas" or "macros", or nothing
    python3 -c 'import json, sys
try:
    print(json.load(open(sys.argv[1])).get(sys.argv[2]) or "")
except (OSError, ValueError):
    pass' "$CONFIG/locations.json" "$1" 2>/dev/null || true
}
if [ -f "$CONFIG/locations.json" ] && command -v python3 >/dev/null; then
    moved="$(where settings)"; [ -n "$moved" ] && SETTINGS="$moved"
    moved="$(where profiles)"; [ -n "$moved" ] && PROFILES="$moved"
    moved="$(where areas)"; [ -n "$moved" ] && AREAS="$moved"
    moved="$(where macros)"; [ -n "$moved" ] && MACROS="$moved"
fi

echo "Your settings are in:  $SETTINGS"
echo "Your profiles are in:  $PROFILES"
echo "Your areas are in:     $AREAS"
echo "Your macros are in:    $MACROS"
read -r -p "Delete your settings, profiles, areas and macros too? This can't be undone. [y/N] " answer
if [[ "$answer" =~ ^[Yy] ]]; then
    # Only folders the app made (they hold its marker file), never anything else
    for folder in "$PROFILES:.autoclicker-profiles" "$AREAS:.autoclicker-areas" \
                  "$MACROS:.autoclicker-macros" "$SETTINGS:.autoclicker-settings"; do
        dir="${folder%:*}"
        marker="${folder##*:}"
        if [ -n "$dir" ] && [ "$dir" != "/" ] && [ "$dir" != "$HOME" ] && [ -f "$dir/$marker" ]; then
            rm -rf -- "$dir"
            echo "Deleted $dir"
        elif [ -d "$dir" ]; then
            echo "Left $dir alone (it doesn't look like an Auto Clicker folder)"
        fi
    done
    rm -f "$CONFIG/locations.json"
    rmdir "$CONFIG" 2>/dev/null || true
else
    echo "Kept your settings, profiles, areas and macros."
fi
