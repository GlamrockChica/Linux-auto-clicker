"""
Auto Clicker (GUI) with sidebar, smooth dark mode, rounded widgets, accent colours
and saved settings
Requires: pynput, and python3-tk on Linux
Settings file: ~/.config/autoclicker/settings.json
"""

import base64
import colorsys
import json
import math
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
import zlib
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from pynput import keyboard, mouse

WINDOW_SIZE = "680x680"
MIN_SIZE = (600, 340)
FONT_SIZE = 10
TEXT_SIZES = {"Small": 9, "Normal": FONT_SIZE, "Large": 11}  # Settings > Text size
# The first of these that's installed is used. Noto Sans looks the cleanest in this app
# (Tk draws Inter a bit heavy and blotchy); the rest are fallbacks.
FONT_CHOICES = ("Noto Sans", "Cantarell", "Roboto", "Ubuntu", "Inter", "DejaVu Sans")

BUTTON_RADIUS = 10   # corner roundness of the buttons, in pixels
FIELD_RADIUS = 8     # corner roundness of the number boxes and dropdowns
FIELD_WIDTH = 120
FIELD_HEIGHT = 32
KEY_FIELD_WIDTH = 140
SIDEBAR_MIN, SIDEBAR_MAX = 100, 320  # how narrow / wide the sidebar can be dragged
BAR_MIN, BAR_MAX = 60, 140           # how short / tall a top or bottom menu can be dragged
CARD_COLUMN_MIN = 380  # in a wide window, card rows sit side by side once each gets this much
CARD_COLUMNS_MAX = 3
MENU_FILL = 0.4  # with a side menu, the button card reaches about this far down it
SIDEBAR_SIDES = ("Left", "Right", "Top", "Bottom")  # where the menu can go
BADGE_SHOW = ("While running", "Always", "Off")       # when the floating card shows
BADGE_CORNERS = ("Top left", "Top right", "Bottom left", "Bottom right")
BAR_EXTRA_HEIGHT = 70  # extra window height a top/bottom menu needs
MINI_GAP = 8     # space between the boxes in mini mode
MINI_MARGIN = 1  # mini mode's window edge: a thin outline around its rounded card
MINI_PAD = 4     # space inside it
PAGE_MIN_WIDTH = 400  # the window always keeps at least this much room for the page
ROW_WORDS_MIN = 180   # a card row's words get at least this; if not, its box moves below them

THEME_MS = 250    # length of the dark mode fade
THEME_STEPS = 15  # number of animation frames
TEXT_COLORS = ("fg", "muted", "accent_fg", "select_fg")  # these swap rather than fade

BUTTONS = {
    "Left": mouse.Button.left,
    "Right": mouse.Button.right,
    "Middle": mouse.Button.middle,
}
CLICK_TYPES = {"Single": 1, "Double": 2, "Triple": 3}  # clicks in each go

# Keys the keyboard clicker isn't allowed to press
BLOCKED_KEYS = {"key:esc", "key:tab", "key:cmd", "key:cmd_l", "key:cmd_r"}

SETTINGS_PATH = Path.home() / ".config" / "autoclicker" / "settings.json"
# Profiles are .txt files in a "profiles" folder, next to the settings unless it's moved
PROFILES_DIR = Path.home() / ".config" / "autoclicker" / "profiles"

# Both folders can be moved (Settings > Storage, or by hand). This file never moves and
# remembers where they are; each folder also holds a small hidden marker file, so if you
# move a folder yourself the app can find it again.
CONFIG_DIR = Path.home() / ".config" / "autoclicker"
POINTER_PATH = CONFIG_DIR / "locations.json"
DEFAULT_SETTINGS_DIR = CONFIG_DIR
DEFAULT_PROFILES_DIR = PROFILES_DIR
SETTINGS_MARKER = ".autoclicker-settings"
PROFILES_MARKER = ".autoclicker-profiles"

APP_CLASS = "autoclicker"  # window class; install.sh sets StartupWMClass to match
# Dock / app list icon: the sidebar logo (cursor on a rounded square) in black and white,
# matching the computer's light/dark mode. install.sh saves it as PNGs (see write_icons).
ICON_STYLES = {  # style: (square colour, cursor colour)
    "light": ("#d9d9d9", "#1a1a1a"),  # computer in light mode: light grey, dark cursor
    "dark": ("#333333", "#f2f2f2"),   # computer in dark mode: dark grey, light cursor
}
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICONS_HOME = Path.home() / ".local" / "share" / "icons"  # your own icons
SYSTEM_ICONS = Path("/usr/share/icons")                  # the installed icon themes
DEFAULTS = {
    # mouse clicker
    "cps": 10.0,
    "button": "Left",
    "click_type": "Single",    # Single / Double / Triple
    "click_delay_on": False,   # wait a set time between clicks instead of using cps
    "click_delay": 2.0,        # seconds to wait, when click_delay_on is True
    "limit_on": False,         # stop after a set number of clicks
    "limit": 100,              # how many clicks, when limit_on is True
    "time_limit_on": False,    # stop after a set time
    "time_limit": 60.0,        # seconds, when time_limit_on is True
    "delay": 0.0,              # start delay
    "location_on": False,      # click at saved spots instead of wherever the mouse is
    "locations": None,         # [[x, y], ...] - one spot, or several clicked in turn
    "multi_location": False,   # several spots in a row (F7 / Pick add a spot)
    "hold": False,             # hold the button down instead of clicking
    # keyboard clicker
    "kb_key": "char:w",        # a key, or a combo like "ctrl+shift+char:c"
    "kb_cps": 10.0,
    "kb_delay": 0.0,           # start delay
    "kb_limit_on": False,
    "kb_limit": 100,
    "kb_time_limit_on": False,
    "kb_time_limit": 60.0,
    "kb_hold": False,          # hold the key down instead of tapping it
    # record and replay
    "replay_loop": True,       # play the recording over and over
    "replay_limit_on": False,  # ...but stop after a set number of plays
    "replay_limit": 5,
    "record_keys_only": False, # record only the keyboard
    "record_moves": True,      # record mouse movement (off: only clicks and scrolls)
    "recording": None,         # list of recorded actions, see AutoClicker.record_event
    # shared
    "active_mode": "mouse",    # which clicker the start/stop key runs: follows the page
                               # you're on (mouse, keyboard or replay on Profiles)
    "hotkey": "key:f6",        # starts / stops clicking
    "location_key": "key:f7",  # saves the mouse position as the click spot
    "record_key": "key:f8",    # starts / stops recording
    "auto_stop": False,        # stop if you move or click the mouse yourself
    "always_on_top": False,
    "mini_mode": False,        # a small window with just the mouse clicker
    "mini_position": [-1, -1], # where it was last dragged to (-1: not yet)
    "badge_show": "While running",  # floating card: While running / Always / Off
    "badge_corner": "Top left",     # which corner of the screen it sits in
    "finish_sound": True,      # play a sound when a run finishes by itself
    "text_size": "Normal",     # Small / Normal / Large
    "dark_mode": False,
    "accent": "#4a8fd9",
    "sidebar_width": 150,      # dragged with the handle between sidebar and page
    "bar_height": BAR_MIN,     # the same, for a menu along the top or bottom
    "sidebar_side": "Left",    # where the menu goes: Left, Right, Top or Bottom
}

# Which clicker each page runs: the start/stop key runs the clicker of the page you're
# on (on Settings, the last one you used)
MODE_PAGES = {"mouse": "clicker", "keyboard": "keyboard", "replay": "recording"}
PAGE_MODES = {page: mode for mode, page in MODE_PAGES.items()}

# The app's own keys (Settings page); they must all be different
APP_KEYS = ("hotkey", "location_key", "record_key")

# Preset accent colours shown as squares in Settings (the last square is "custom")
ACCENTS = (
    "#4a8fd9",  # blue
    "#8e6bdf",  # purple
    "#e0579c",  # pink
    "#e05555",  # red
    "#e8893a",  # orange
    "#e3b505",  # yellow
    "#4caf6a",  # green
    "#2fb5a8",  # teal
)

# Base colours. The accent-based colours are added by build_palette().
LIGHT = {
    "bg": "#f0f0f0", "fg": "#1a1a1a", "field": "#ffffff", "button": "#e1e1e1",
    "active": "#d0d0d0", "border": "#b5b5b5", "muted": "#666666",
    # cards (grouped settings): the card, boxes inside a card, and lines between rows
    "card": "#ffffff", "card_field": "#f3f3f3", "divider": "#e6e6e6",
}
DARK = {
    "bg": "#1e1e1e", "fg": "#e6e6e6", "field": "#2b2b2b", "button": "#333333",
    "active": "#444444", "border": "#4a4a4a", "muted": "#9a9a9a",
    "card": "#292929", "card_field": "#1f1f1f", "divider": "#353535",
}

NAMED_FONTS = (
    "TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
    "TkCaptionFont", "TkSmallCaptionFont", "TkTooltipFont",
)


# ---------------- Keys and mouse buttons ----------------
# Keys/buttons are stored as short text codes so they can be saved:
#   "key:f6"  special keys     "char:a"  letter/number keys
#   "vk:123"  other keys       "mouse:right"  mouse buttons

# Modifier keys that can be part of a key combo, e.g. "ctrl+shift+char:c" = Ctrl+Shift+C
MODIFIERS = {
    "ctrl": ("key:ctrl", "key:ctrl_l", "key:ctrl_r"),
    "shift": ("key:shift", "key:shift_l", "key:shift_r"),
    "alt": ("key:alt", "key:alt_l", "key:alt_r", "key:alt_gr"),
}
MODIFIER_OF = {code: name for name, codes in MODIFIERS.items() for code in codes}


def input_code(thing) -> str:
    """Turn a pynput key or mouse button into a code like 'key:f6' or 'mouse:right'."""
    if isinstance(thing, mouse.Button):
        return f"mouse:{thing.name}"
    if isinstance(thing, keyboard.Key):
        return f"key:{thing.name}"
    if isinstance(thing, keyboard.KeyCode):
        if thing.char and thing.char.isprintable():
            return f"char:{thing.char.lower()}"
        if thing.vk is not None:
            # With Ctrl held, letters arrive without a usable character; on Linux the
            # key number is still the plain letter, so use that
            if 32 < thing.vk < 127:
                return f"char:{chr(thing.vk).lower()}"
            return f"vk:{thing.vk}"
    return ""


def split_combo(code: str):
    """'ctrl+shift+char:c' -> (['ctrl', 'shift'], 'char:c'). A plain key has no modifiers."""
    mods = []
    changed = True
    while changed:
        changed = False
        for name in MODIFIERS:
            if code.startswith(name + "+"):
                mods.append(name)
                code = code[len(name) + 1:]
                changed = True
    return mods, code


def make_combo(mods, key_code: str) -> str:
    order = [name for name in MODIFIERS if name in mods]  # always ctrl, shift, alt order
    return "+".join(order + [key_code])


def input_name(code: str) -> str:
    """Friendly name for a code, e.g. 'key:ctrl_l' -> 'Left Ctrl', 'mouse:button8' -> 'Mouse 4',
    'ctrl+char:c' -> 'Ctrl+C'."""
    mods, code = split_combo(code)
    if mods:
        return "+".join([m.capitalize() for m in mods] + [input_name(code)])
    kind, _, name = code.partition(":")
    if kind == "mouse":
        fixed = {"left": "Left Click", "right": "Right Click", "middle": "Middle Click",
                 "x1": "Mouse 4", "x2": "Mouse 5"}
        if name in fixed:
            return fixed[name]
        if name.startswith("button") and name[6:].isdigit():
            return f"Mouse {int(name[6:]) - 4}"  # X11 button 8/9 are the side buttons 4/5
        return name.title()
    if kind == "key":
        if re.fullmatch(r"f\d+", name):
            return name.upper()
        parts = name.split("_")
        side = ""
        if len(parts) > 1 and parts[-1] in ("l", "r"):
            side = "Left " if parts[-1] == "l" else "Right "
            parts = parts[:-1]
        word = " ".join(part.capitalize() for part in parts)
        word = {"Cmd": "Super", "Alt Gr": "AltGr"}.get(word, word)
        return side + word
    if kind == "char":
        return "Space" if name == " " else name.upper()
    if kind == "vk":
        return f"Key {name}"
    return "None"


def is_valid_input(code) -> bool:
    if not isinstance(code, str):
        return False
    kind, _, name = code.partition(":")
    if kind == "key":
        return name in keyboard.Key.__members__
    if kind == "mouse":
        # left click can't be a hotkey: you need it to use everything else
        return name in mouse.Button.__members__ and name not in ("left", "unknown")
    if kind == "char":
        return len(name) == 1
    if kind == "vk":
        return name.isdigit()
    return False


def is_keyboard_key(code) -> bool:
    """Keys the keyboard clicker can press: any key or key combo, except Esc, Tab and Super."""
    if not isinstance(code, str):
        return False
    _mods, key = split_combo(code)
    return is_valid_input(key) and not key.startswith("mouse:") and key not in BLOCKED_KEYS


def key_from_code(code: str):
    """Turn a code like 'char:w' or 'key:space' back into a pynput key to press."""
    kind, _, name = code.partition(":")
    if kind == "key":
        return keyboard.Key[name]
    if kind == "char":
        return keyboard.KeyCode.from_char(name)
    return keyboard.KeyCode.from_vk(int(name))


def keys_for_combo(code: str):
    """The pynput keys to press for a key or combo, modifiers first."""
    mods, key = split_combo(code)
    return [getattr(keyboard.Key, m) for m in mods] + [key_from_code(key)]


def codes_for_combo(code: str):
    """Every input code the listener might report while this key/combo is pressed."""
    mods, key = split_combo(code)
    codes = {key}
    for m in mods:
        codes.update(MODIFIERS[m])
    return codes


def clean_recording(recording):
    """Check a recording loaded from a file, keeping only well-formed actions."""
    if not isinstance(recording, list):
        return None
    good = []
    for action in recording:
        if not isinstance(action, list) or len(action) < 2:
            continue
        t, kind = action[0], action[1]
        if not isinstance(t, (int, float)):
            continue
        nums = action[2:] if kind in ("move", "scroll") else action[3:]
        if not all(isinstance(n, (int, float)) for n in nums):
            continue
        if kind == "move" and len(action) == 4:
            good.append(action)
        elif kind == "scroll" and len(action) == 6:
            good.append(action)
        elif (kind in ("press", "release") and len(action) == 5
              and isinstance(action[2], str) and action[2].startswith("mouse:")
              and action[2][6:] in mouse.Button.__members__):
            good.append(action)
        elif kind in ("kpress", "krelease") and len(action) == 3 and is_valid_input(action[2]):
            good.append(action)
    return good or None


def clean_settings(saved, base=None) -> dict:
    """Merge saved values over `base` (default: DEFAULTS), fixing anything missing or invalid."""
    settings = dict(base or DEFAULTS)
    if isinstance(saved, dict):
        for key, default in DEFAULTS.items():
            if key in saved and default is not None:
                try:
                    settings[key] = type(default)(saved[key])
                except (TypeError, ValueError):
                    pass
        def is_point(p):
            return (isinstance(p, list) and len(p) == 2
                    and all(isinstance(v, (int, float)) for v in p))
        if "locations" in saved:
            spots = saved.get("locations")
            spots = [[int(p[0]), int(p[1])] for p in spots if is_point(p)] \
                if isinstance(spots, list) else []
            settings["locations"] = spots or None
        elif is_point(saved.get("location")):  # older versions had a single spot
            settings["locations"] = [[int(v) for v in saved["location"]]]
        if "recording" in saved:
            settings["recording"] = clean_recording(saved.get("recording"))
        # Older settings files used "limit": 0 to mean "never stop"
        if "limit" in saved and "limit_on" not in saved:
            settings["limit_on"] = settings["limit"] > 0
        # Older settings files stored the hotkey as just "F6"
        for name in APP_KEYS:
            if re.fullmatch(r"F\d+", settings[name]):
                settings[name] = "key:" + settings[name].lower()
    for name in ("limit", "kb_limit", "replay_limit"):
        if settings[name] < 1:
            settings[name] = DEFAULTS[name]
    settings["sidebar_width"] = min(max(settings["sidebar_width"], SIDEBAR_MIN), SIDEBAR_MAX)
    settings["bar_height"] = min(max(settings["bar_height"], BAR_MIN), BAR_MAX)
    for name in ("click_delay", "time_limit", "kb_time_limit"):
        if settings[name] <= 0:
            settings[name] = DEFAULTS[name]
    if settings["button"] not in BUTTONS:
        settings["button"] = DEFAULTS["button"]
    if settings["click_type"] not in CLICK_TYPES:
        settings["click_type"] = DEFAULTS["click_type"]
    used = set()
    for name in APP_KEYS:  # each app key must be valid and different from the others
        if not is_valid_input(settings[name]) or settings[name] in used:
            settings[name] = DEFAULTS[name]
        if settings[name] in used:
            settings[name] = next(f"key:f{n}" for n in range(6, 13) if f"key:f{n}" not in used)
        used.add(settings[name])
    if not is_keyboard_key(settings["kb_key"]) or settings["kb_key"] in used:
        settings["kb_key"] = DEFAULTS["kb_key"]
    if isinstance(saved, dict) and "badge_show" not in saved and saved.get("floating_badge") is False:
        settings["badge_show"] = "Off"  # older versions had an on/off switch
    if settings["badge_show"] not in BADGE_SHOW:
        settings["badge_show"] = DEFAULTS["badge_show"]
    if settings["badge_corner"] not in BADGE_CORNERS:
        settings["badge_corner"] = DEFAULTS["badge_corner"]
    if settings["text_size"] not in TEXT_SIZES:
        settings["text_size"] = DEFAULTS["text_size"]
    if settings["sidebar_side"] not in SIDEBAR_SIDES:
        settings["sidebar_side"] = DEFAULTS["sidebar_side"]
    if settings["active_mode"] not in MODE_PAGES:
        settings["active_mode"] = DEFAULTS["active_mode"]
    if isinstance(saved, dict) and "active_mode" not in saved:
        # older versions had switches instead: keyboard "Enabled" and "Replay mode"
        if saved.get("replay_on"):
            settings["active_mode"] = "replay"
        elif saved.get("kb_on"):
            settings["active_mode"] = "keyboard"
    if not is_hex_color(settings["accent"]):
        settings["accent"] = DEFAULTS["accent"]
    settings["accent"] = settings["accent"].lower()
    return settings


def load_settings() -> dict:
    """Load saved settings, falling back to defaults for anything missing or invalid."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = None
    return clean_settings(saved)


def current_recording_path() -> Path:
    """The recording you're working with right now (not saved to a profile yet)."""
    return SETTINGS_PATH.parent / "current_recording.json"


def write_recording(path: Path, recording, profile=None) -> None:
    """Save a recording as easy-to-read JSON: the profile name, then one input per line:
    [seconds since the start, what happened, details...]. No recording deletes the file."""
    try:
        if not recording:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        inputs = ",\n".join("    " + json.dumps(action) for action in recording)
        text = ("{\n"
                f'  "profile": {json.dumps(profile)},\n'
                '  "inputs": [\n' + inputs + "\n  ]\n}\n")
        temp = path.with_name(path.name + ".tmp")  # write fully, then swap in
        temp.write_text(text, encoding="utf-8")
        temp.replace(path)
    except OSError as err:
        print(f"Could not save recording: {err}")


def read_recording(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return clean_recording(data.get("inputs") if isinstance(data, dict) else data)


def safe_profile_name(name: str) -> str:
    """Profile names are also file names, so swap out characters files can't have."""
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")[:40]


def profile_path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.txt"


def list_profiles() -> list:
    """Profile names = the .txt files in the profiles folder."""
    try:
        return sorted((p.stem for p in PROFILES_DIR.glob("*.txt") if p.is_file()),
                      key=str.lower)
    except OSError:
        return []


# Profile files are one input per line, for example:
#   {profile:"hellohello"}
#   {[0.0],kpress:"h"}          <- wait 0 seconds, then press H
#   {[0.135],krelease:"h"}      <- wait 0.135 seconds, then let go of H
#   {[0.015],move:"812,440"}    <- move the mouse to x 812, y 440
#   {[0.03],press:"left,812,440"}   (release:"left,812,440" lets go)
#   {[0.1],scroll:"0,-2,812,440"}   (sideways, up/down, then where)
# The number in [ ] is the delay: seconds since the previous input.
PROFILE_LINE = re.compile(r'^\{\s*\[\s*"?(-?\d+(?:\.\d+)?)"?\s*\]\s*,\s*(\w+)\s*:\s*(".*")\s*\}$')


def key_to_text(code: str) -> str:
    """'char:h' -> 'h', 'key:space' -> 'space', 'vk:65027' -> '#65027'."""
    kind, _, name = code.partition(":")
    return "#" + name if kind == "vk" else name


def key_from_text(text: str) -> str:
    """The reverse of key_to_text: one character is that key, '#123' is a key number,
    anything else is a special key's name like 'space' or 'ctrl_l'."""
    if len(text) == 1:
        return "char:" + text
    if text.startswith("#") and text[1:].isdigit():
        return "vk:" + text[1:]
    return "key:" + text


def profile_lines(name: str, recording, hotkey=None) -> list:
    lines = ["{profile:" + json.dumps(name) + "}"]
    if hotkey:
        lines.append("{hotkey:" + json.dumps(hotkey) + "}")
    previous = 0.0
    for action in recording or []:
        t, kind = action[0], action[1]
        delay = round(max(0.0, t - previous), 3)
        previous = t
        if kind in ("kpress", "krelease"):
            value = key_to_text(action[2])
        elif kind in ("press", "release"):
            value = f"{action[2][6:]},{action[3]},{action[4]}"  # button,x,y
        elif kind == "move":
            value = f"{action[2]},{action[3]}"
        else:  # scroll
            value = ",".join(str(n) for n in action[2:6])
        lines.append("{[" + f"{delay:g}" + "]," + kind + ":" + json.dumps(value) + "}")
    return lines


def parse_profile(text: str):
    """Recording from a profile file. Lines that don't make sense are skipped."""
    recording, t = [], 0.0
    for line in text.splitlines():
        match = PROFILE_LINE.match(line.strip())
        if not match:
            continue  # the {profile:...} line, blank lines, or anything mistyped
        delay, kind, raw = match.groups()
        try:
            value = json.loads(raw)
            t = round(t + float(delay), 3)
            if kind in ("kpress", "krelease"):
                recording.append([t, kind, key_from_text(value)])
            elif kind in ("press", "release"):
                button, x, y = value.split(",")
                recording.append([t, kind, "mouse:" + button.strip(), int(x), int(y)])
            elif kind == "move":
                x, y = value.split(",")
                recording.append([t, kind, int(x), int(y)])
            elif kind == "scroll":
                recording.append([t, kind, *(int(n) for n in value.split(","))])
        except (ValueError, TypeError, AttributeError):
            continue
    return clean_recording(recording)


def write_profile(name: str, recording, hotkey=None) -> bool:
    """Save a profile (a named recording, plus its hotkey if it has one) as an easy-to-read
    .txt file, one input per line."""
    try:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        path = profile_path(name)
        temp = path.with_name(path.name + ".tmp")  # write fully, then swap in
        temp.write_text("\n".join(profile_lines(name, recording, hotkey)) + "\n",
                        encoding="utf-8")
        temp.replace(path)
        return True
    except OSError as err:
        print(f"Could not save profile {name}: {err}")
        return False


def read_profile(name: str):
    """A profile's recording from its .txt file. Returns (ok, recording); ok is False if
    the file can't be read. Also reads the older JSON-style profile files."""
    try:
        text = profile_path(name).read_text(encoding="utf-8")
    except OSError:
        return False, None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return True, clean_recording(data.get("inputs"))
    except ValueError:
        pass
    return True, parse_profile(text)


HOTKEY_LINE = re.compile(r'^\{\s*hotkey\s*:\s*(".*")\s*\}$')


def read_profile_hotkey(name: str):
    """The hotkey saved in a profile's file (its first few lines), or None."""
    try:
        with open(profile_path(name), encoding="utf-8") as f:
            for _ in range(5):
                match = HOTKEY_LINE.match(f.readline().strip())
                if match:
                    code = json.loads(match.group(1))
                    return code if is_valid_input(code) else None
    except (OSError, ValueError):
        pass
    return None


def mark_folder(folder: Path, marker: str, what: str) -> None:
    """Make sure the folder exists and holds its marker file (so it can be found if moved)."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / marker
        if not path.exists():
            path.write_text(f"This folder holds Auto Clicker's {what}. You can move it: the "
                            "app will find it again.\n", encoding="utf-8")
    except OSError:
        pass


def find_marker(marker: str, max_depth=5, time_limit=2.0):
    """Look through your home folder for a folder holding `marker` (one that was moved)."""
    home, began = Path.home(), time.monotonic()
    skip = {"node_modules", "__pycache__", "venv", ".venv", "site-packages", "snap"}
    for root, dirs, files in os.walk(home):
        if marker in files:
            return Path(root)
        if time.monotonic() - began > time_limit:
            return None
        depth = len(Path(root).relative_to(home).parts)
        if depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in skip
                   and (not d.startswith(".") or (depth == 0 and d == ".config"))]
    return None


def remember_locations() -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        POINTER_PATH.write_text(json.dumps({"settings": str(SETTINGS_PATH.parent),
                                            "profiles": str(PROFILES_DIR)}, indent=2),
                                encoding="utf-8")
    except OSError as err:
        print(f"Could not save folder locations: {err}")


def resolve_locations() -> list:
    """Work out where settings and profiles are kept. If a remembered folder has gone
    (because it was moved), look for its marker file. Returns what was found elsewhere."""
    global SETTINGS_PATH, PROFILES_DIR
    try:
        saved = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        saved = saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        saved = {}
    found = []
    folders = {}
    for kind, marker, default in (("settings", SETTINGS_MARKER, DEFAULT_SETTINGS_DIR),
                                  ("profiles", PROFILES_MARKER, DEFAULT_PROFILES_DIR)):
        folder = Path(saved[kind]) if isinstance(saved.get(kind), str) else default
        if kind in saved and not (folder / marker).exists():
            moved_to = find_marker(marker)
            if moved_to is not None:
                folder = moved_to
                found.append(kind)
        folders[kind] = folder
    SETTINGS_PATH = folders["settings"] / "settings.json"
    PROFILES_DIR = folders["profiles"]
    mark_folder(SETTINGS_PATH.parent, SETTINGS_MARKER, "settings")
    mark_folder(PROFILES_DIR, PROFILES_MARKER, "profiles")
    remember_locations()
    return found


def choose_folder(root, start: Path):
    """Ask for a folder with the system's folder picker (zenity), or Tk's if that's missing."""
    if shutil.which("zenity"):
        try:
            proc = subprocess.Popen(
                ["zenity", "--file-selection", "--directory", "--title=Choose a folder",
                 f"--filename={start}/"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True)
            while proc.poll() is None:  # keep the app drawing while the picker is open
                root.update()
                time.sleep(0.03)
            chosen = proc.stdout.read().strip()
            return Path(chosen) if proc.returncode == 0 and chosen else None
        except OSError:
            pass
    from tkinter import filedialog
    chosen = filedialog.askdirectory(parent=root, initialdir=str(start), mustexist=False)
    return Path(chosen) if chosen else None


def short_path(path: Path) -> str:
    return str(path).replace(str(Path.home()), "~", 1)


def tidy_profiles() -> None:
    """Bring older profiles up to date: profiles.json in ~/.config/autoclicker becomes .txt
    files, and older JSON-style .txt files are rewritten one input per line. Old copies are
    only removed once the new files are safely written."""
    old_file = SETTINGS_PATH.parent / "profiles.json"
    old_dir = SETTINGS_PATH.parent / "recordings"
    if old_file.exists():
        try:
            profiles = json.loads(old_file.read_text(encoding="utf-8"))["profiles"]
            assert isinstance(profiles, dict)
        except (OSError, ValueError, KeyError, TypeError, AssertionError):
            profiles = None
        if profiles is not None:
            all_moved = True
            for name, values in profiles.items():
                if not isinstance(name, str) or not isinstance(values, dict):
                    continue
                new_name = safe_profile_name(name) or "profile"
                if profile_path(new_name).exists():
                    continue  # never overwrite a profile that's already in the folder
                if values.get("recording_file"):
                    recording = read_recording(old_dir / values["recording_file"])
                else:
                    recording = clean_recording(values.get("recording"))
                if not recording:
                    continue  # profiles are recordings now; one with nothing recorded is dropped
                all_moved = write_profile(new_name, recording) and all_moved
            if all_moved:
                try:
                    old_file.unlink()
                    for f in old_dir.glob("*.json"):
                        f.unlink()
                    old_dir.rmdir()
                except OSError:
                    pass
    # Older .txt files were JSON (some with settings in them): rewrite them in the
    # one-line-per-input style, keeping their inputs
    for name in list_profiles():
        try:
            data = json.loads(profile_path(name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # already the new style (or unreadable): leave it alone
        if isinstance(data, dict) and "inputs" in data:
            write_profile(name, clean_recording(data.get("inputs")))


def icon_path(size: int, style: str) -> Path:
    return ICONS_HOME / "hicolor" / f"{size}x{size}" / "apps" / f"autoclicker-{style}.png"


def system_is_dark() -> bool:
    """Is the computer (not just this app) set to dark mode?"""
    def setting(key):
        try:
            return subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", key],
                                  capture_output=True, text=True, timeout=2).stdout.lower()
        except (OSError, subprocess.SubprocessError):
            return ""
    return "dark" in setting("color-scheme") or "dark" in setting("gtk-theme")


def icon_png(size: int, style: str) -> bytes:
    """The app icon as a PNG: the sidebar logo in black and white (see ICON_STYLES),
    with a see-through background."""
    margin = round(size * 0.06)  # a little space around it, like other app icons
    inner = size - 2 * margin
    masks = logo_masks(inner, samples=4 if inner <= 64 else 2)
    square_rgb, cursor_rgb = ([int(c[i:i + 2], 16) for i in (1, 3, 5)]
                              for c in ICON_STYLES[style])
    blank = b"\0\0\0\0" * size
    rows = [blank] * margin
    for row in masks:
        pixels = bytearray(b"\0\0\0\0" * margin)
        for square, mark in row:
            if square <= 0:
                pixels += b"\0\0\0\0"
                continue
            cursor = mark / square  # how much of the visible part is the cursor
            pixels += bytes(round(a + (b - a) * cursor) for a, b in zip(square_rgb, cursor_rgb))
            pixels.append(round(255 * square))
        pixels += b"\0\0\0\0" * margin
        rows.append(bytes(pixels))
    rows += [blank] * margin

    def chunk(kind, data):
        return (len(data).to_bytes(4, "big") + kind + data
                + zlib.crc32(kind + data).to_bytes(4, "big"))

    header = size.to_bytes(4, "big") * 2 + bytes((8, 6, 0, 0, 0))  # 8-bit RGBA
    raw = b"".join(b"\0" + row for row in rows)  # each row starts with "no filter"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def theme_icon_folders(theme: Path) -> dict:
    """{size: folder} inside an icon theme, one folder for each icon size it has."""
    import configparser
    index = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        index.read(theme / "index.theme", encoding="utf-8")
        folders = index.get("Icon Theme", "Directories", fallback="")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return {}
    found = {}
    for folder in (f.strip() for f in folders.split(",")):
        if not folder or "@" in folder or folder.startswith("scalable"):
            continue  # skip the high-DPI and drawing-only (SVG) folders
        try:
            size = index.getint(folder, "Size")
        except (configparser.Error, ValueError):
            continue
        if 8 <= size <= 512:
            found.setdefault(size, folder)
    return found


def write_icons() -> None:
    """Save the icon where the app list and dock look for it.
    install.sh runs this (python autoclicker.py --write-icons). The menu entry just says
    Icon=autoclicker, and the computer finds the right version itself:
    - Light and dark icon themes (like ZorinPurple-Light / ZorinPurple-Dark, which Zorin
      switches between with light/dark mode) each get their own copy: white for light,
      black for dark. So the icon flips by itself, even while the app is closed.
    - Any other theme falls back to hicolor, which gets the version that suits the
      computer's mode right now (the app keeps it up to date, see update_icon)."""
    drawn = {}

    def png(size, style):
        if (size, style) not in drawn:
            drawn[size, style] = icon_png(size, style)
        return drawn[size, style]

    written = []

    def save(path, data):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written.append(path)
        except OSError as err:
            print(f"Could not save icon {path}: {err}", file=sys.stderr)

    now = "dark" if system_is_dark() else "light"
    for size in ICON_SIZES:
        for style in ICON_STYLES:  # both versions, for the app's own window
            save(icon_path(size, style), png(size, style))
        save(ICONS_HOME / "hicolor" / f"{size}x{size}" / "apps" / "autoclicker.png",
             png(size, now))
    try:
        themes = sorted(SYSTEM_ICONS.iterdir())
    except OSError:
        themes = []
    for theme in themes:
        name = theme.name.lower()
        style = "dark" if name.endswith("dark") else "light" if name.endswith("light") else None
        if style is None:
            continue
        for size, folder in theme_icon_folders(theme).items():
            save(ICONS_HOME / theme.name / folder / "autoclicker.png", png(size, style))
    # The desktop only notices changed icons when an icon theme's main folder changes,
    # so mark them all as changed (otherwise it can keep showing the old icon).
    for folder in {path.relative_to(ICONS_HOME).parts[0] for path in written}:
        try:
            os.utime(ICONS_HOME / folder)
        except OSError:
            pass


def update_fallback_icon(style: str) -> None:
    """Make the hicolor icon (for themes that aren't light/dark specific) match `style`."""
    for size in ICON_SIZES:
        source = icon_path(size, style)
        target = ICONS_HOME / "hicolor" / f"{size}x{size}" / "apps" / "autoclicker.png"
        try:
            data = source.read_bytes()
            if not target.is_file() or target.read_bytes() != data:
                temp = target.with_suffix(".new")
                temp.write_bytes(data)
                temp.replace(target)
        except OSError:
            pass


def write_settings(settings: dict) -> None:
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError as err:
        print(f"Could not save settings: {err}")


def mix_color(a: str, b: str, t: float) -> str:
    """Blend hex colour a into hex colour b (t = 0 gives a, t = 1 gives b)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def is_hex_color(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is not None


def text_on(color: str) -> str:
    """Pick dark or white text, whichever is easier to read on top of `color`."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#1a1a1a" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#ffffff"


def build_palette(dark: bool, accent: str) -> dict:
    """Full set of colours for light/dark mode with the chosen accent colour."""
    p = dict(DARK if dark else LIGHT)
    p["accent"] = accent                    # checkboxes, focus borders
    p["accent_fg"] = text_on(accent)        # tick mark drawn on the accent
    # softer version of the accent for selected sidebar items, menus, text selection
    p["select"] = mix_color(accent, p["bg"], 0.25 if dark else 0.55)
    p["select_fg"] = text_on(p["select"])
    return p


def rounded_points(x1, y1, x2, y2, r):
    """Polygon points for a rounded rectangle (draw with smooth=True)."""
    return [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
        x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
        x1, y1 + r, x1, y1,
    ]


def clamp_radius(r, x1, y1, x2, y2):
    return max(0, min(r, (y2 - y1) // 2, (x2 - x1) // 2))


def hex_to_hsv(color: str):
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)


def hsv_to_hex(h, s, v) -> str:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def arc_points(cx, cy, r, start_deg, end_deg, steps=8):
    """Points along a circle arc (angles in degrees, 0 = right, 90 = down)."""
    pts = []
    for i in range(steps + 1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def round_image_corners(canvas, x1, y1, x2, y2, r, bg, border):
    """Hide the square corners of an image on a canvas and draw a rounded border.

    Canvas images can't be clipped, so each corner is covered with a small
    shape in the background colour, shaped so only the rounded part shows."""
    corners = (
        (x1, y1, x1 + r, y1 + r, 180, 270),
        (x2, y1, x2 - r, y1 + r, 270, 360),
        (x2, y2, x2 - r, y2 - r, 0, 90),
        (x1, y2, x1 + r, y2 - r, 90, 180),
    )
    outline = []
    for cx, cy, ax, ay, a1, a2 in corners:
        arc = arc_points(ax, ay, r, a1, a2)
        canvas.create_polygon([cx, cy] + arc, fill=bg, outline=bg)
        outline += arc
    canvas.create_polygon(outline, fill="", outline=border, width=1)


class RoundedButton(tk.Canvas):
    """A button with rounded corners, hover/pressed colours and optional 'selected' state."""

    def __init__(self, parent, text, command, font="TkDefaultFont", radius=BUTTON_RADIUS,
                 height=34, width=100, flat=False, selectable=False, accent=False):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text = text
        self.command = command
        self.font = font
        self.radius = radius
        self.flat = flat              # flat = menu button (sits on the menu card)
        self.selectable = selectable  # can show a highlighted "selected" state
        self.accent = accent          # selected = full accent colour (e.g. Stop while running)
        self.selected = False
        self.hover = False
        self.pressed = False
        self.palette = None

        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)

    # ---- public API ----
    def set_text(self, text):
        self.text = text
        self.redraw()

    def set_selected(self, selected):
        self.selected = selected
        self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    # ---- drawing ----
    def fill_color(self):
        p = self.palette
        if self.selectable and self.selected:
            return p["accent"] if self.accent else p["select"]
        if self.flat:  # menu button on the menu card: card colour, a gentle shade on hover
            return p["field"] if (self.pressed or self.hover) else p["bg"]
        if self.pressed or self.hover:
            return p["active"]
        return p["button"]

    def redraw(self):
        self.delete("all")
        if not self.palette:
            return
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        r = clamp_radius(self.radius, x1, y1, x2, y2)
        selected = self.selectable and self.selected
        self.create_polygon(rounded_points(x1, y1, x2, y2, r), smooth=True,
                            fill=self.fill_color(), outline="")
        if selected and self.accent:
            text_color = self.palette["accent_fg"]
        elif selected:
            text_color = self.palette["select_fg"]
        else:
            text_color = self.palette["fg"]
        self.create_text(w / 2, h / 2, text=self.text, fill=text_color, font=self.font)

    # ---- mouse events ----
    def on_enter(self, _event):
        self.hover = True
        self.redraw()

    def on_leave(self, _event):
        self.hover = False
        self.pressed = False
        self.redraw()

    def on_press(self, _event):
        self.pressed = True
        self.redraw()

    def on_release(self, event):
        was_pressed = self.pressed
        self.pressed = False
        self.redraw()
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        if was_pressed and inside and self.command:
            self.command()


class RoundedSpin(tk.Canvas):
    """A number box with rounded corners and up/down arrows."""

    ARROW_ZONE = 28  # width of the arrow area on the right

    def __init__(self, parent, variable, from_, to, increment,
                 width=FIELD_WIDTH, height=FIELD_HEIGHT, radius=FIELD_RADIUS):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0)
        self.var = variable
        self.from_ = from_
        self.to = to
        self.increment = increment
        self.is_int = isinstance(variable, tk.IntVar)
        self.radius = radius
        self.focused = False
        self.palette = None
        self.repeat_job = None

        self.entry = tk.Entry(self, textvariable=variable, bd=0, highlightthickness=0,
                              relief="flat", font="TkTextFont")
        self.entry_window = self.create_window(0, 0, window=self.entry, anchor="w")

        self.entry.bind("<FocusIn>", lambda e: self.set_focus(True))
        self.entry.bind("<FocusOut>", lambda e: self.set_focus(False))
        self.entry.bind("<Up>", lambda e: self.step(1))
        self.entry.bind("<Down>", lambda e: self.step(-1))
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.stop_repeat)
        self.bind("<Leave>", self.stop_repeat)

    # ---- value handling ----
    def step(self, direction):
        try:
            value = float(self.var.get())
        except (tk.TclError, ValueError):
            value = self.from_
        new = min(max(value + direction * self.increment, self.from_), self.to)
        if self.is_int:
            self.var.set(int(round(new)))
        else:
            self.var.set(round(new, 4))

    def repeat(self, direction):
        self.step(direction)
        self.repeat_job = self.after(60, self.repeat, direction)

    def stop_repeat(self, _event=None):
        if self.repeat_job is not None:
            self.after_cancel(self.repeat_job)
            self.repeat_job = None

    def on_press(self, event):
        if event.x >= self.winfo_width() - self.ARROW_ZONE:
            direction = 1 if event.y < self.winfo_height() / 2 else -1
            self.step(direction)
            self.stop_repeat()
            self.repeat_job = self.after(400, self.repeat, direction)
        else:
            self.entry.focus_set()

    def set_focus(self, focused):
        self.focused = focused
        self.redraw()

    # ---- look ----
    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.entry.configure(bg=palette["field"], fg=palette["fg"],
                             insertbackground=palette["fg"],
                             selectbackground=palette["select"],
                             selectforeground=palette["select_fg"])
        self.redraw()

    def redraw(self):
        self.delete("shape")
        if not self.palette:
            return
        p = self.palette
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        r = clamp_radius(self.radius, x1, y1, x2, y2)
        border = p["accent"] if self.focused else p["border"]
        self.create_polygon(rounded_points(x1, y1, x2, y2, r), smooth=True,
                            fill=p["field"], outline=border, width=1, tags="shape")

        # arrows
        cx, cy = w - 15, h / 2
        self.create_polygon(cx - 4, cy - 3, cx + 4, cy - 3, cx, cy - 8,
                            fill=p["fg"], outline="", tags="shape")
        self.create_polygon(cx - 4, cy + 3, cx + 4, cy + 3, cx, cy + 8,
                            fill=p["fg"], outline="", tags="shape")

        self.coords(self.entry_window, 10, h / 2)
        self.itemconfigure(self.entry_window, width=max(10, w - 10 - self.ARROW_ZONE),
                           height=max(10, h - 10))


class RoundedEntry(tk.Canvas):
    """A rounded text box with grey placeholder text while it's empty."""

    def __init__(self, parent, variable, placeholder="", on_enter=None,
                 width=FIELD_WIDTH, height=FIELD_HEIGHT, radius=FIELD_RADIUS):
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0)
        self.var = variable
        self.placeholder = placeholder
        self.radius = radius
        self.focused = False
        self.palette = None
        self.entry = tk.Entry(self, textvariable=variable, bd=0, highlightthickness=0,
                              relief="flat", font="TkTextFont")
        self.entry_window = self.create_window(0, 0, window=self.entry, anchor="w")
        self.entry.bind("<FocusIn>", lambda e: self.set_focus(True))
        self.entry.bind("<FocusOut>", lambda e: self.set_focus(False))
        if on_enter:
            self.entry.bind("<Return>", lambda e: on_enter())
        self.var.trace_add("write", lambda *_: self.redraw())
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-1>", self.on_click)

    def on_click(self, _event):
        self.itemconfigure(self.entry_window, state="normal")  # un-hide before focusing
        self.entry.focus_set()

    def set_focus(self, focused):
        self.focused = focused
        self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.entry.configure(bg=palette["field"], fg=palette["fg"],
                             insertbackground=palette["fg"],
                             selectbackground=palette["select"],
                             selectforeground=palette["select_fg"])
        self.redraw()

    def redraw(self):
        self.delete("shape")
        if not self.palette:
            return
        p = self.palette
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        r = clamp_radius(self.radius, x1, y1, x2, y2)
        self.create_polygon(rounded_points(x1, y1, x2, y2, r), smooth=True, fill=p["field"],
                            outline=p["accent"] if self.focused else p["border"], tags="shape")
        self.tag_lower("shape")
        self.coords(self.entry_window, 10, h / 2)
        self.itemconfigure(self.entry_window, width=max(10, w - 20), height=max(10, h - 10))
        # placeholder: drawn on the canvas, hidden by showing the entry only when needed
        if not self.var.get() and not self.focused:
            self.itemconfigure(self.entry_window, state="hidden")
            self.create_text(10, h / 2, text=self.placeholder, anchor="w",
                             fill=p["muted"], font="TkTextFont", tags="shape")
        else:
            self.itemconfigure(self.entry_window, state="normal")


class RoundedCombo(tk.Canvas):
    """A dropdown with rounded corners. Opens a rounded list that matches the theme."""

    def __init__(self, parent, variable, values,
                 width=FIELD_WIDTH, height=FIELD_HEIGHT, radius=FIELD_RADIUS):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.var = variable
        self.values = list(values)
        self.radius = radius
        self.hover = False
        self.palette = None
        self.popup = None
        self.closed_at = 0.0
        self.placeholder = ""  # shown in grey when nothing is chosen

        self.var.trace_add("write", lambda *_: self.redraw())
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonRelease-1>", self.open_menu)

    def on_enter(self, _event):
        self.hover = True
        self.redraw()

    def on_leave(self, _event):
        self.hover = False
        self.redraw()

    def open_menu(self, event):
        if not (0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()):
            return
        # a click on this box while the list is open closes the list; don't reopen it
        if self.popup is not None or time.monotonic() - self.closed_at < 0.3:
            return
        if not self.values:
            return
        self.popup = DropdownPopup(self)
        self.redraw()

    def set_values(self, values):
        self.values = list(values)
        self.redraw()

    def popup_closed(self):
        self.popup = None
        self.closed_at = time.monotonic()
        self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.palette:
            return
        p = self.palette
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        r = clamp_radius(self.radius, x1, y1, x2, y2)
        border = p["accent"] if (self.hover or self.popup) else p["border"]
        self.create_polygon(rounded_points(x1, y1, x2, y2, r), smooth=True,
                            fill=p["field"], outline=border, width=1)
        text, color = self.var.get(), p["fg"]
        if not text:
            text, color = self.placeholder, p["muted"]
        pad = 8 if w < 90 else 12  # a narrow box (like in mini mode) keeps more room for text
        self.create_text(pad, h / 2, text=text, anchor="w", fill=color, font="TkTextFont")
        cx, cy = w - pad - 3, h / 2
        if self.popup:  # arrow points up while the list is open
            self.create_polygon(cx - 5, cy + 2, cx + 5, cy + 2, cx, cy - 4,
                                fill=p["fg"], outline="")
        else:
            self.create_polygon(cx - 5, cy - 2, cx + 5, cy - 2, cx, cy + 4,
                                fill=p["fg"], outline="")


class DropdownPopup(tk.Toplevel):
    """The rounded list that opens under a RoundedCombo.
    Click an item to pick it; click anywhere else or press Esc to close."""

    ITEM_H = 30  # height of each item
    PAD = 5      # space inside the list's edge

    def __init__(self, combo):
        root = combo.winfo_toplevel()
        super().__init__(root)
        self.combo = combo
        self.palette = p = combo.palette
        self.values = combo.values
        self.hover = None
        self.closed = False

        self.overrideredirect(True)  # no title bar
        try:
            self.attributes("-topmost", bool(root.attributes("-topmost")))
        except tk.TclError:
            pass

        self.w = combo.winfo_width()
        self.h = len(self.values) * self.ITEM_H + self.PAD * 2
        x = combo.winfo_rootx()
        y = combo.winfo_rooty() + combo.winfo_height() + 4
        if y + self.h > self.winfo_screenheight():  # no room below: open above instead
            y = combo.winfo_rooty() - self.h - 4
        self.geometry(f"{self.w}x{self.h}+{x}+{y}")

        # The window itself is square, so its corners are painted in the app's
        # background colour; sitting over the app, the list looks rounded.
        self.canvas = tk.Canvas(self, width=self.w, height=self.h, bg=p["bg"],
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Motion>", lambda e: self.set_hover(self.index_at(e.y)))
        self.canvas.bind("<Leave>", lambda e: self.set_hover(None))
        self.bind("<ButtonPress>", self.on_press)
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<Up>", lambda e: self.move(-1))
        self.bind("<Down>", lambda e: self.move(1))
        self.bind("<Return>", lambda e: self.pick(self.hover))
        self.redraw()

        try:
            self.wait_visibility()
            try:
                self.grab_set_global()  # so a click anywhere (even outside the app) closes it
            except tk.TclError:
                self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def index_at(self, y):
        i = int((y - self.PAD) // self.ITEM_H)
        if self.PAD <= y < self.h - self.PAD and 0 <= i < len(self.values):
            return i
        return None

    def set_hover(self, index):
        if index != self.hover:
            self.hover = index
            self.redraw()

    def move(self, step):
        if self.hover is None:
            current = self.combo.var.get()
            start = self.values.index(current) if current in self.values else -step
            self.set_hover((start + step) % len(self.values))
        else:
            self.set_hover((self.hover + step) % len(self.values))

    def on_press(self, event):
        x = event.x_root - self.winfo_rootx()
        y = event.y_root - self.winfo_rooty()
        if 0 <= x < self.w and 0 <= y < self.h:
            self.pick(self.index_at(y))
        else:
            self.close()

    def pick(self, index):
        if index is not None:
            self.combo.var.set(self.values[index])
            self.close()

    def redraw(self):
        c, p = self.canvas, self.palette
        c.delete("all")
        c.create_polygon(rounded_points(1, 1, self.w - 1, self.h - 1, FIELD_RADIUS),
                         smooth=True, fill=p["field"], outline=p["border"])
        current = self.combo.var.get()
        for i, value in enumerate(self.values):
            y1 = self.PAD + i * self.ITEM_H
            text_color = p["fg"]
            if i == self.hover:
                c.create_polygon(rounded_points(self.PAD, y1 + 1, self.w - self.PAD,
                                                y1 + self.ITEM_H - 1, 6),
                                 smooth=True, fill=p["select"], outline="")
                text_color = p["select_fg"]
            c.create_text(12, y1 + self.ITEM_H / 2, text=value, anchor="w",
                          fill=text_color, font="TkTextFont")
            if value == current:  # tick next to the chosen item
                cx, cy = self.w - 18, y1 + self.ITEM_H / 2
                c.create_line(cx - 4, cy, cx - 1, cy + 3, cx + 5, cy - 4,
                              fill=text_color if i == self.hover else p["accent"],
                              width=2, capstyle="round", joinstyle="round")

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.combo.popup_closed()


_switch_mask_cache = {}


def switch_masks(w, h, pad, pos):
    """For each pixel of a switch: how much is track, knob shadow and knob (0..1 each).
    Worked out from each pixel's distance to the shapes' edges, which gives smooth
    (anti-aliased) edges. Cached, because only the colours change during a theme fade."""
    key = (w, h, pad, round(pos, 3))
    if key in _switch_mask_cache:
        return _switch_mask_cache[key]

    def coverage(distance):  # distance < 0 is inside the shape
        return min(max(0.5 - distance, 0.0), 1.0)

    r = h / 2                       # track radius
    kr = (h - 2 * pad) / 2          # knob radius
    kx = pad + kr + pos * (w - 2 * pad - 2 * kr)
    ky = h / 2
    masks = []
    for y in range(h):
        py = y + 0.5
        for x in range(w):
            px = x + 0.5
            # track: distance to a capsule (a line from r to w-r, thickened by r)
            cx = min(max(px, r), w - r)
            track = coverage(math.hypot(px - cx, py - r) - r)
            shadow_dist = math.hypot(px - kx, py - ky - 1) - kr
            shadow = min(max((1.2 - shadow_dist) / 2.4, 0.0), 1.0) * 0.18 * track
            knob = coverage(math.hypot(px - kx, py - ky) - kr)
            masks.append((track, shadow, knob))
    if pos in (0.0, 1.0) or len(_switch_mask_cache) < 64:  # keep the resting states
        _switch_mask_cache[key] = masks
    return masks


def render_switch(image, w, h, pad, pos, track_color, bg_color):
    """Draw a switch (pill-shaped track + round knob) into a PhotoImage with smooth edges."""
    bg = [int(bg_color[i:i + 2], 16) for i in (1, 3, 5)]
    tc = [int(track_color[i:i + 2], 16) for i in (1, 3, 5)]
    pixels = []
    for track, shadow, knob in switch_masks(w, h, pad, pos):
        color = []
        for b, t in zip(bg, tc):
            c = b + (t - b) * track       # track over background
            c -= c * shadow               # darken a little for the shadow
            c += (255 - c) * knob         # white knob on top
            color.append(round(c))
        pixels.append("#%02x%02x%02x" % tuple(color))
    image.put(" ".join("{" + " ".join(pixels[y * w:(y + 1) * w]) + "}" for y in range(h)))


def logo_masks(size, samples=4):
    """Work out the logo's shapes once: for each pixel, how much is covered by the
    rounded square, and how much by the white cursor + click lines (0..1 each).
    Drawn on a 28x28 grid and scaled to `size`, with 4x4 samples per pixel for smooth edges."""
    s = size / 28
    radius = 7 * s
    # cursor arrow, tip at (11, 9)
    arrow = [(x * s, y * s) for x, y in
             ((11, 9), (11, 22.5), (14.2, 19.4), (16.6, 24.4), (19, 23.3),
              (16.7, 18.4), (21.2, 18.4))]
    # three short "click" lines around the tip
    rays = [((11 * s, 5.6 * s), (11 * s, 3.4 * s)),
            ((7.6 * s, 9 * s), (5.4 * s, 9 * s)),
            ((8.5 * s, 6.5 * s), (6.9 * s, 4.9 * s))]
    ray_half_width = 0.85 * s

    def in_square(x, y):
        cx = min(max(x, radius), size - radius)
        cy = min(max(y, radius), size - radius)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2

    def in_arrow(x, y):  # standard even-odd point-in-polygon test
        inside = False
        for (x1, y1), (x2, y2) in zip(arrow, arrow[1:] + arrow[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        return inside

    def on_ray(x, y):
        for (x1, y1), (x2, y2) in rays:
            dx, dy = x2 - x1, y2 - y1
            t = min(max(((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy), 0), 1)
            if math.hypot(x - x1 - t * dx, y - y1 - t * dy) <= ray_half_width:
                return True
        return False

    masks = []
    step = 1 / samples
    for py in range(size):
        row = []
        for px in range(size):
            square = white = 0
            for sy in range(samples):
                for sx in range(samples):
                    x, y = px + (sx + 0.5) * step, py + (sy + 0.5) * step
                    if in_square(x, y):
                        square += 1
                        if in_arrow(x, y) or on_ray(x, y):
                            white += 1
            n = samples * samples
            row.append((square / n, white / n))
        masks.append(row)
    return masks


class Logo(tk.Canvas):
    """The app's logo for the top of the sidebar: a rounded square in the soft accent colour
    of the highlighted sidebar tab, with a cursor, and the name stacked next to it."""

    ICON = 30  # icon size in pixels
    GAP = 8    # space between icon and name

    def __init__(self, parent, font, width=92):
        f = tkfont.Font(font=font)
        height = max(self.ICON, f.metrics("linespace") * 2)
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0)
        self.font = font
        self.palette = None
        self.masks = logo_masks(self.ICON)  # shapes don't change, only colours do
        self.image = tk.PhotoImage(width=self.ICON, height=self.ICON)
        self.bind("<Configure>", lambda e: self.redraw())

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    def refit(self):
        """The text size changed: fit the logo to it again."""
        f = tkfont.Font(font=self.font)
        self.configure(height=max(self.ICON, f.metrics("linespace") * 2),
                       width=self.ICON + self.GAP + max(f.measure("Auto"), f.measure("Clicker")) + 4)
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.palette:
            return
        p = self.palette
        bg = [int(p["bg"][i:i + 2], 16) for i in (1, 3, 5)]
        # same softer accent and text colour as the highlighted sidebar tab
        accent = [int(p["select"][i:i + 2], 16) for i in (1, 3, 5)]
        cursor = [int(p["select_fg"][i:i + 2], 16) for i in (1, 3, 5)]
        rows = []
        for row in self.masks:
            pixels = []
            for square, mark in row:
                # background where the square isn't, accent inside it, cursor colour on top
                color = [b * (1 - square) + a * (square - mark) + c * mark
                         for b, a, c in zip(bg, accent, cursor)]
                pixels.append("#%02x%02x%02x" % tuple(round(c) for c in color))
            rows.append("{" + " ".join(pixels) + "}")
        self.image.put(" ".join(rows))

        h = self.winfo_height()
        self.create_image(0, (h - self.ICON) // 2, image=self.image, anchor="nw")
        x = self.ICON + self.GAP
        self.create_text(x, h / 2, text="Auto", anchor="sw", fill=p["fg"], font=self.font)
        self.create_text(x, h / 2, text="Clicker", anchor="nw", fill=p["fg"], font=self.font)


_corner_cache = {}


def corner_mask(r):
    """Coverage (0..1) of a quarter circle of radius r in an r x r square, for the
    top-left corner: 1 inside the rounded corner, 0 in the cut-off bit. Smooth edges."""
    if r not in _corner_cache:
        mask = []
        for y in range(r):
            for x in range(r):
                d = math.hypot(r - (x + 0.5), r - (y + 0.5)) - r
                mask.append(min(max(0.5 - d, 0.0), 1.0))
        _corner_cache[r] = mask
    return _corner_cache[r]


class Card(tk.Canvas):
    """A rounded panel that groups related settings, like the boxed lists in phone and
    GNOME settings. Put rows in `self.body` (a frame the same colour as the card)."""

    RADIUS = 10
    INSET_X, INSET_Y = 6, 4  # keeps the body clear of the rounded corners

    def __init__(self, parent):
        # width=1: the card just stretches to the space it's given (unless fit is on)
        super().__init__(parent, highlightthickness=0, bd=0, height=10, width=1)
        self.palette = None
        self.body = tk.Frame(self, bd=0, highlightthickness=0)
        self.body.columnconfigure(0, weight=1)
        self.window = self.create_window(self.INSET_X, self.INSET_Y, window=self.body,
                                         anchor="nw")
        self.corners = [tk.PhotoImage(width=self.RADIUS, height=self.RADIUS) for _ in range(4)]
        self.rows = []  # (row frame, divider above it, should_show) - see AutoClicker.card_row
        self.fit = False  # True: the card is as wide as its contents instead of stretching
        self.columns = 1  # rows side by side in a wide window (see AutoClicker.layout_card)
        self.on_width = None  # called with the new width when the card is resized
        # the card grows and shrinks with its rows, and stretches with the page
        self.body.bind("<Configure>", self.on_body_resize)
        self.bind("<Configure>", self.on_resize)

    def set_fit(self, fit):
        self.fit = fit
        if fit:
            self.itemconfigure(self.window, width=0)  # 0: the body takes the width it wants
        else:
            self.configure(width=1)

    def on_body_resize(self, event):
        self.configure(height=event.height + 2 * self.INSET_Y)
        if self.fit:
            self.configure(width=event.width + 2 * self.INSET_X)

    def fit_to_body(self):
        """Size a fit card from what its contents ask for. (Waiting for the contents to
        report their size isn't enough: while the card is still tiny they're out of view,
        so they never get laid out and never report it.)"""
        if not self.fit:
            return
        self.body.update_idletasks()
        self.configure(width=self.body.winfo_reqwidth() + 2 * self.INSET_X,
                       height=self.body.winfo_reqheight() + 2 * self.INSET_Y)

    def on_resize(self, event):
        if not self.fit:
            self.itemconfigure(self.window, width=max(10, event.width - 2 * self.INSET_X))
        self.redraw()
        if self.on_width is not None:
            self.on_width(event.width)

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.body.configure(bg=palette["card"])
        self.paint_corners()
        self.redraw()

    def paint_corners(self):
        """Colour the 4 smooth corner images: page colour outside, card colour inside."""
        p, r = self.palette, self.RADIUS
        outer = [int(p["bg"][i:i + 2], 16) for i in (1, 3, 5)]
        inner = [int(p["card"][i:i + 2], 16) for i in (1, 3, 5)]
        mask = corner_mask(r)
        for n, image in enumerate(self.corners):
            rows = []
            for y in range(r):
                pixels = []
                for x in range(r):
                    # mirror the top-left mask for the other corners
                    mx = x if n in (0, 3) else r - 1 - x
                    my = y if n in (0, 1) else r - 1 - y
                    c = mask[my * r + mx]
                    pixels.append("#%02x%02x%02x" % tuple(
                        round(o + (i - o) * c) for o, i in zip(outer, inner)))
                rows.append("{" + " ".join(pixels) + "}")
            image.put(" ".join(rows))

    def redraw(self):
        self.delete("bg")
        if not self.palette:
            return
        w, h, r = self.winfo_width(), self.winfo_height(), self.RADIUS
        if w < 2 * r or h < 2 * r:
            return
        fill = self.palette["card"]
        self.create_rectangle(r, 0, w - r, h, fill=fill, outline="", tags="bg")
        self.create_rectangle(0, r, w, h - r, fill=fill, outline="", tags="bg")
        for image, (x, y) in zip(self.corners, ((0, 0), (w - r, 0), (w - r, h - r), (0, h - r))):
            self.create_image(x, y, image=image, anchor="nw", tags="bg")
        self.tag_lower("bg")


class ToggleSwitch(tk.Canvas):
    """An on/off switch with its label on the left. The knob slides and the track
    fades to the accent colour when it's switched on. Click anywhere on the row to flip it."""

    TRACK_W, TRACK_H = 40, 22  # size of the switch
    KNOB_PAD = 3               # gap between the knob and the edge of the track
    GAP = 16                   # space between the label and the switch
    ANIM_MS = 180              # length of the slide
    FRAME_MS = 12              # time between animation frames

    def __init__(self, parent, text, variable, font="TkDefaultFont"):
        f = tkfont.nametofont(font)
        height = max(self.TRACK_H + 6, f.metrics("linespace") + 6)
        super().__init__(parent, width=self.width_for(text, font), height=height,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text = text
        self.var = variable
        self.font = font
        self.hover = False
        self.palette = None
        self.pos = 1.0 if variable.get() else 0.0  # 0 = off, 1 = on, in between while sliding
        self.anim_job = None
        self.image = None

        self.var.trace_add("write", lambda *_: self.animate())
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonRelease-1>", self.on_click)

    @classmethod
    def width_for(cls, text, font):
        if not text:  # just the switch, e.g. at the end of a card row
            return cls.TRACK_W + 4
        return tkfont.nametofont(font).measure(text) + cls.GAP + cls.TRACK_W + 4

    def set_text(self, text):
        if text != self.text:
            self.text = text
            self.configure(width=self.width_for(text, self.font))
            self.redraw()

    def on_enter(self, _event):
        self.hover = True
        self.redraw()

    def on_leave(self, _event):
        self.hover = False
        self.redraw()

    def on_click(self, event):
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.var.set(not self.var.get())

    def animate(self):
        """Slide the knob towards the variable's new value."""
        if self.anim_job is not None:
            self.after_cancel(self.anim_job)
            self.anim_job = None
        target = 1.0 if self.var.get() else 0.0
        start = self.pos
        began = time.monotonic()

        def step():
            t = min(1.0, (time.monotonic() - began) * 1000 / self.ANIM_MS)
            eased = 1 - (1 - t) ** 3  # ease-out: quick start, soft landing
            self.pos = start + (target - start) * eased
            self.redraw()
            self.anim_job = self.after(self.FRAME_MS, step) if t < 1 else None

        step()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.palette:
            return
        p = self.palette
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return

        self.create_text(1, h / 2, text=self.text, anchor="w", fill=p["fg"], font=self.font)

        # The switch itself is drawn pixel by pixel into an image with smooth
        # (anti-aliased) edges, because Tk's own circles have jagged edges.
        track = mix_color(p["border"], p["accent"], self.pos)
        if self.hover:
            track = mix_color(track, p["fg"], 0.12)
        if self.image is None:
            self.image = tk.PhotoImage(width=self.TRACK_W, height=self.TRACK_H)
        render_switch(self.image, self.TRACK_W, self.TRACK_H, self.KNOB_PAD,
                      self.pos, track, p["bg"])
        self.create_image(w - 2 - self.TRACK_W, (h - self.TRACK_H) // 2,
                          image=self.image, anchor="nw")


_swatch_mask_cache = {}


def swatch_masks(size, radius, border_width, mark):
    """For each pixel of a colour swatch: how much is fill, border and mark (0..1 each).
    `mark` is None, "check" or "plus". Smooth edges come from each pixel's distance to
    the shape's edge. Cached, because only the colours change between redraws."""
    key = (size, radius, border_width, mark)
    if key in _swatch_mask_cache:
        return _swatch_mask_cache[key]

    def coverage(distance):  # distance < 0 is inside the shape
        return min(max(0.5 - distance, 0.0), 1.0)

    half = size / 2
    c = half
    if mark == "check":
        segments = [((c - 5, c), (c - 1.5, c + 3.5)), ((c - 1.5, c + 3.5), (c + 5.5, c - 4))]
    elif mark == "plus":
        segments = [((c - 5, c), (c + 5, c)), ((c, c - 5), (c, c + 5))]
    else:
        segments = []

    def segment_distance(px, py):
        best = float("inf")
        for (x1, y1), (x2, y2) in segments:
            dx, dy = x2 - x1, y2 - y1
            t = min(max(((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy), 0.0), 1.0)
            best = min(best, math.hypot(px - x1 - t * dx, py - y1 - t * dy))
        return best

    masks = []
    for y in range(size):
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            # signed distance to a rounded square (negative inside)
            qx = abs(px - half) - (half - radius)
            qy = abs(py - half) - (half - radius)
            dist = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
            inside = coverage(dist)
            border = inside - coverage(dist + border_width)  # a ring just inside the edge
            mark_cov = coverage(segment_distance(px, py) - 1.0) if segments else 0.0
            masks.append((inside, border, mark_cov))
    _swatch_mask_cache[key] = masks
    return masks


def render_swatch(image, size, radius, fill, bg, border, border_width, mark, mark_color):
    """Draw one rounded colour swatch (with an optional tick or plus) into a PhotoImage."""
    fill_rgb, bg_rgb, border_rgb, mark_rgb = (
        [int(col[i:i + 2], 16) for i in (1, 3, 5)] for col in (fill, bg, border, mark_color))
    pixels = []
    for inside, ring, mark_cov in swatch_masks(size, radius, border_width, mark):
        color = []
        for b, f, r, m in zip(bg_rgb, fill_rgb, border_rgb, mark_rgb):
            c = b + (f - b) * inside      # swatch colour over the background
            c += (r - c) * ring           # border ring
            c += (m - c) * mark_cov       # tick / plus on top
            color.append(round(c))
        pixels.append("#%02x%02x%02x" % tuple(color))
    image.put(" ".join("{" + " ".join(pixels[y * size:(y + 1) * size]) + "}"
                       for y in range(size)))


class ColorSwatches(tk.Canvas):
    """A row of rounded colour swatches. The last one opens a colour picker."""

    SIZE = 24  # size of each square
    GAP = 6    # space between squares
    PAD = 2    # room around the edge so outlines are not cut off
    RADIUS = 6  # corner roundness

    def __init__(self, parent, variable, colors):
        self.colors = [c.lower() for c in colors]
        count = len(self.colors) + 1  # +1 for the custom square
        width = count * self.SIZE + (count - 1) * self.GAP + self.PAD * 2
        height = self.SIZE + self.PAD * 2
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.var = variable
        self.hover_index = None
        self.palette = None
        self.images = []  # one smooth-edged image per square

        self.var.trace_add("write", lambda *_: self.redraw())
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Motion>", self.on_motion)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonRelease-1>", self.on_click)

    def index_at(self, x, y):
        """Which square is under (x, y), or None if it's in a gap."""
        if not self.PAD <= y <= self.PAD + self.SIZE:
            return None
        x -= self.PAD
        i = int(x // (self.SIZE + self.GAP))
        inside = 0 <= x - i * (self.SIZE + self.GAP) <= self.SIZE
        if inside and 0 <= i <= len(self.colors):
            return i
        return None

    def on_motion(self, event):
        index = self.index_at(event.x, event.y)
        if index != self.hover_index:
            self.hover_index = index
            self.redraw()

    def on_leave(self, _event):
        self.hover_index = None
        self.redraw()

    def on_click(self, event):
        index = self.index_at(event.x, event.y)
        if index is None:
            return
        if index < len(self.colors):
            self.var.set(self.colors[index])
            return
        picker = ColorPicker(self.winfo_toplevel(), self.var.get(), self.palette)
        self.wait_window(picker)
        if picker.result:
            self.var.set(picker.result)

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.palette:
            return
        p = self.palette
        current = self.var.get().lower()
        is_custom = current not in self.colors
        count = len(self.colors) + 1
        while len(self.images) < count:
            self.images.append(tk.PhotoImage(width=self.SIZE, height=self.SIZE))

        for i in range(count):
            if i < len(self.colors):
                fill = self.colors[i]
                selected = fill == current
            else:
                # custom square: shows the custom colour once one is picked
                fill = current if is_custom else p["field"]
                selected = is_custom

            hovered = i == self.hover_index
            if selected:
                mark, mark_color = "check", text_on(fill)
            elif i == len(self.colors):
                mark, mark_color = "plus", p["fg"]
            else:
                mark, mark_color = None, p["fg"]
            render_swatch(self.images[i], self.SIZE, self.RADIUS, fill, p["bg"],
                          p["fg"] if hovered else p["border"], 2 if hovered else 1,
                          mark, mark_color)
            x = self.PAD + i * (self.SIZE + self.GAP)
            self.create_image(x, self.PAD, image=self.images[i], anchor="nw")


class ColorPicker(tk.Toplevel):
    """A colour picker window that matches the app's light/dark theme.

    Drag in the big square to pick shade (left/right = how colourful,
    up/down = how bright), drag the rainbow bar to pick the hue,
    or type a hex code. After the window closes, `result` holds the
    chosen colour, or None if it was cancelled."""

    SV_W, SV_H = 260, 160  # size of the shade square
    HUE_H = 12             # height of the rainbow bar
    MARGIN = 9             # room around the square/bar so the round markers can overhang
    RADIUS = 10

    def __init__(self, parent, color, palette, title="Pick an accent colour"):
        super().__init__(parent)
        self.result = None
        self.palette = p = palette
        self.h, self.s, self.v = hex_to_hsv(color if is_hex_color(color) else "#4a8fd9")
        self.render_job = None
        self.typing = False
        self.exact = None  # a hex code typed by hand, kept as-is (no rounding)

        self.title(title)
        self.configure(bg=p["bg"])
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.attributes("-topmost", bool(parent.attributes("-topmost")))
        except tk.TclError:
            pass

        m = self.MARGIN
        body = tk.Frame(self, bg=p["bg"], padx=16 - m, pady=16 - m)
        body.pack(fill="both", expand=True)

        # ---- shade square ----
        self.sv = tk.Canvas(body, width=self.SV_W + 2 * m, height=self.SV_H + 2 * m,
                            bg=p["bg"], highlightthickness=0, bd=0, cursor="crosshair")
        self.sv.grid(row=0, column=0, columnspan=3)
        self.sv_img = tk.PhotoImage(width=self.SV_W, height=self.SV_H)
        self.sv.create_image(m, m, image=self.sv_img, anchor="nw")
        round_image_corners(self.sv, m, m, m + self.SV_W, m + self.SV_H,
                            self.RADIUS, p["bg"], p["border"])
        self.sv.bind("<Button-1>", self.on_sv)
        self.sv.bind("<B1-Motion>", self.on_sv)

        # ---- rainbow (hue) bar ----
        self.hue = tk.Canvas(body, width=self.SV_W + 2 * m, height=self.HUE_H + 2 * m,
                             bg=p["bg"], highlightthickness=0, bd=0, cursor="hand2")
        self.hue.grid(row=1, column=0, columnspan=3)
        self.hue_img = tk.PhotoImage(width=self.SV_W, height=self.HUE_H)
        row = "{" + " ".join(hsv_to_hex(x / (self.SV_W - 1), 1, 1)
                             for x in range(self.SV_W)) + "}"
        self.hue_img.put(" ".join([row] * self.HUE_H))
        self.hue.create_image(m, m, image=self.hue_img, anchor="nw")
        round_image_corners(self.hue, m, m, m + self.SV_W, m + self.HUE_H,
                            self.HUE_H // 2, p["bg"], p["border"])
        self.hue.bind("<Button-1>", self.on_hue)
        self.hue.bind("<B1-Motion>", self.on_hue)

        # ---- preview swatch + hex box ----
        bottom = tk.Frame(body, bg=p["bg"], padx=m, pady=4)
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew")
        bottom.columnconfigure(2, weight=1)

        self.preview = tk.Canvas(bottom, width=FIELD_HEIGHT, height=FIELD_HEIGHT,
                                 bg=p["bg"], highlightthickness=0, bd=0)
        self.preview.grid(row=0, column=0, padx=(0, 10))

        self.hex_box = tk.Canvas(bottom, width=110, height=FIELD_HEIGHT,
                                 bg=p["bg"], highlightthickness=0, bd=0)
        self.hex_box.grid(row=0, column=1)
        self.hex_var = tk.StringVar()
        self.hex_entry = tk.Entry(self.hex_box, textvariable=self.hex_var, bd=0,
                                  highlightthickness=0, relief="flat", font="TkTextFont",
                                  bg=p["field"], fg=p["fg"], insertbackground=p["fg"],
                                  selectbackground=p["select"],
                                  selectforeground=p["select_fg"])
        self.hex_box.create_window(10, FIELD_HEIGHT / 2, window=self.hex_entry, anchor="w",
                                   width=110 - 20, height=FIELD_HEIGHT - 10)
        self.hex_entry.bind("<FocusIn>", lambda e: self.draw_hex_box(True))
        self.hex_entry.bind("<FocusOut>", self.on_hex_done)
        self.hex_entry.bind("<Return>", self.on_hex_done)
        self.hex_var.trace_add("write", self.on_hex_typed)

        # ---- buttons ----
        buttons = tk.Frame(body, bg=p["bg"], padx=m, pady=m)
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        cancel = RoundedButton(buttons, "Cancel", self.cancel, height=34)
        cancel.set_palette(p)
        cancel.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        choose = RoundedButton(buttons, "Choose", self.choose, height=34, selectable=True)
        choose.set_palette(p)
        choose.set_selected(True)  # drawn in the accent colour
        choose.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.bind("<Escape>", lambda e: self.cancel())
        self.bind("<Return>", lambda e: self.choose())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.render_square()
        self.update_all()
        self.place_over(parent)
        try:
            self.wait_visibility()
            self.grab_set()  # block the main window while the picker is open
        except tk.TclError:
            pass

    # ---- helpers ----
    def color(self):
        return self.exact or hsv_to_hex(self.h, self.s, self.v)

    def place_over(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def render_square(self):
        """Fill the shade square for the current hue (white -> hue across, -> black down)."""
        self.render_job = None
        hr, hg, hb = (int(c * 255) for c in colorsys.hsv_to_rgb(self.h, 1, 1))
        w, h = self.SV_W, self.SV_H
        top = []  # brightest row: white on the left, full hue on the right
        for x in range(w):
            s = x / (w - 1)
            top.append((255 + (hr - 255) * s, 255 + (hg - 255) * s, 255 + (hb - 255) * s))
        rows = []
        for y in range(h):
            v = 1 - y / (h - 1)
            rows.append("{" + " ".join(
                f"#{int(r * v):02x}{int(g * v):02x}{int(b * v):02x}" for r, g, b in top) + "}")
        self.sv_img.put(" ".join(rows))

    def update_all(self):
        """Move the markers and refresh the preview and hex box."""
        p, m = self.palette, self.MARGIN
        current = self.color()

        x = m + self.s * self.SV_W
        y = m + (1 - self.v) * self.SV_H
        self.sv.delete("marker")
        self.sv.create_oval(x - 8, y - 8, x + 8, y + 8, outline="#000000", width=1, tags="marker")
        self.sv.create_oval(x - 7, y - 7, x + 7, y + 7, fill=current, outline="#ffffff",
                            width=2, tags="marker")

        hx = m + self.h * self.SV_W
        hy = m + self.HUE_H / 2
        self.hue.delete("marker")
        self.hue.create_oval(hx - 9, hy - 9, hx + 9, hy + 9, outline="#000000", width=1,
                             tags="marker")
        self.hue.create_oval(hx - 8, hy - 8, hx + 8, hy + 8, fill=hsv_to_hex(self.h, 1, 1),
                             outline="#ffffff", width=2, tags="marker")

        self.preview.delete("all")
        self.preview.create_polygon(rounded_points(1, 1, FIELD_HEIGHT - 1, FIELD_HEIGHT - 1,
                                                   FIELD_RADIUS),
                                    smooth=True, fill=current, outline=p["border"])
        if not self.typing:
            self.hex_var.set(current)
        self.draw_hex_box(self.focus_get() == self.hex_entry)

    def draw_hex_box(self, focused):
        p = self.palette
        self.hex_box.delete("shape")
        self.hex_box.create_polygon(rounded_points(1, 1, 109, FIELD_HEIGHT - 1, FIELD_RADIUS),
                                    smooth=True, fill=p["field"],
                                    outline=p["accent"] if focused else p["border"],
                                    tags="shape")
        self.hex_box.tag_lower("shape")

    # ---- mouse ----
    def on_sv(self, event):
        m = self.MARGIN
        self.exact = None
        self.s = min(max((event.x - m) / self.SV_W, 0), 1)
        self.v = 1 - min(max((event.y - m) / self.SV_H, 0), 1)
        self.update_all()

    def on_hue(self, event):
        self.exact = None
        self.h = min(max((event.x - self.MARGIN) / self.SV_W, 0), 0.9999)
        self.update_all()
        if self.render_job is None:  # redraw the square at most once per idle moment
            self.render_job = self.after_idle(self.render_square)

    # ---- hex box ----
    def on_hex_typed(self, *_):
        text = self.hex_var.get().strip()
        if not text.startswith("#"):
            text = "#" + text
        if is_hex_color(text) and text.lower() != self.color():
            self.exact = text.lower()
            self.h, self.s, self.v = hex_to_hsv(self.exact)
            self.typing = True
            self.render_square()
            self.update_all()
            self.typing = False

    def on_hex_done(self, _event=None):
        self.hex_var.set(self.color())
        self.draw_hex_box(self.focus_get() == self.hex_entry)
        return "break"

    # ---- close ----
    def choose(self):
        self.result = self.color()
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class KeyChooser(tk.Canvas):
    """Shows a key or mouse button. Click it, then press a key or mouse button to change it.
    The listening itself is done by the app (see AutoClicker.start_capture)."""

    def __init__(self, parent, variable, on_click, purpose, allowed=is_valid_input,
                 combos=False,
                 width=KEY_FIELD_WIDTH, height=FIELD_HEIGHT, radius=FIELD_RADIUS):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.var = variable
        self.on_click = on_click
        self.purpose = purpose    # e.g. "Start / stop", shown if another box clashes
        self.allowed = allowed    # function: can this code be used here?
        self.combos = combos      # True: hold Ctrl/Shift/Alt to make a combo like Ctrl+C
        self.radius = radius
        self.listening = False
        self.hover = False
        self.message = None       # short note shown for a moment, e.g. "Can't use Tab"
        self.message_job = None
        self.palette = None

        self.var.trace_add("write", lambda *_: self.redraw())
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonRelease-1>", self.on_release)

    def on_enter(self, _event):
        self.hover = True
        self.redraw()

    def on_leave(self, _event):
        self.hover = False
        self.redraw()

    def on_release(self, event):
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.on_click(self)

    def set_listening(self, listening):
        self.listening = listening
        if not listening:
            self.message = None
        self.redraw()

    def flash(self, message, seconds=1.5):
        """Show a short note in the box (it keeps listening). seconds=None keeps it up."""
        self.message = message
        if self.message_job is not None:
            self.after_cancel(self.message_job)
            self.message_job = None
        if seconds:
            self.message_job = self.after(int(seconds * 1000), self.clear_message)
        self.redraw()

    def clear_message(self):
        self.message = None
        self.message_job = None
        self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.palette:
            return
        p = self.palette
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        r = clamp_radius(self.radius, x1, y1, x2, y2)
        border = p["accent"] if (self.listening or self.hover) else p["border"]
        self.create_polygon(rounded_points(x1, y1, x2, y2, r), smooth=True,
                            fill=p["field"], outline=border, width=2 if self.listening else 1)
        if self.listening and self.message:
            text, color = self.message, p["accent"]
        elif self.listening:
            text, color = "Press a key...", p["muted"]
        else:
            text, color = input_name(self.var.get()), p["fg"]
        self.create_text(w / 2, h / 2, text=text, fill=color, font="TkTextFont")


_dot_cache = {}


def dot_mask(size):
    """Coverage (0..1) of a circle filling a size x size square, with smooth edges."""
    if size not in _dot_cache:
        r = size / 2
        _dot_cache[size] = [min(max(0.5 - (math.hypot(x + 0.5 - r, y + 0.5 - r) - r), 0.0), 1.0)
                            for y in range(size) for x in range(size)]
    return _dot_cache[size]


def paint_dot(image, size, color, bg):
    c = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    mask = dot_mask(size)
    rows = []
    for y in range(size):
        rows.append("{" + " ".join(
            "#%02x%02x%02x" % tuple(round(bb + (cc - bb) * mask[y * size + x]) for bb, cc in zip(b, c))
            for x in range(size)) + "}")
    image.put(" ".join(rows))


class StatusDot(tk.Canvas):
    """A small round light next to the status: accent colour while running, grey (like an
    off switch) when stopped."""

    SIZE = 10

    def __init__(self, parent):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, highlightthickness=0, bd=0)
        self.image = tk.PhotoImage(width=self.SIZE, height=self.SIZE)
        self.create_image(0, 0, image=self.image, anchor="nw")
        self.on = False
        self.palette = None

    def set_on(self, on):
        self.on = on
        self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    def redraw(self):
        if self.palette:
            p = self.palette
            paint_dot(self.image, self.SIZE, p["accent"] if self.on else p["border"], p["bg"])


def screen_areas():
    """[(x, y, w, h)] for each monitor, trimmed to the usable area (not under panels)."""
    monitors = []
    try:
        out = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True,
                             timeout=2).stdout
        for m in re.finditer(r"(\d+)/\d+x(\d+)/\d+\+(\d+)\+(\d+)", out):
            w, h, x, y = (int(v) for v in m.groups())
            monitors.append((x, y, w, h))
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        out = subprocess.run(["xprop", "-root", "_NET_WORKAREA"], capture_output=True,
                             text=True, timeout=2).stdout
        wx, wy, ww, wh = (int(v) for v in re.findall(r"\d+", out.split("=", 1)[1])[:4])
        trimmed = []
        for x, y, w, h in monitors or [(wx, wy, ww, wh)]:
            top, bottom = max(y, wy), min(y + h, wy + wh)
            left, right = max(x, wx), min(x + w, wx + ww)
            trimmed.append((left, top, right - left, bottom - top))
        return trimmed
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return monitors


def round_window(window, radius, w=0, h=0):
    """Cut a window's corners round, so it really is rounded (not just painted). Uses the
    X11 shape extension; if that isn't available the window just stays square.
    radius=None makes the window square again."""
    try:
        import ctypes
        import ctypes.util
        x11 = ctypes.CDLL(ctypes.util.find_library("X11"))
        xext = ctypes.CDLL(ctypes.util.find_library("Xext"))
    except (OSError, TypeError):
        return

    class Rect(ctypes.Structure):
        _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short),
                    ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]

    rows = []  # [inset, first row, number of rows]: each row is shortened at the corners
    for y in range(h if radius is not None else 0):
        d = radius - y - 0.5 if y < radius else (y - (h - radius) + 0.5 if y >= h - radius else 0)
        inset = int(round(radius - math.sqrt(max(radius * radius - d * d, 0)))) if d else 0
        if rows and rows[-1][0] == inset:
            rows[-1][2] += 1
        else:
            rows.append([inset, y, 1])
    rects = (Rect * len(rows))(*[Rect(i, y, max(w - 2 * i, 0), n) for i, y, n in rows])
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xext.XShapeCombineMask.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_ulong, ctypes.c_int]
    xext.XShapeCombineRectangles.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(Rect), ctypes.c_int, ctypes.c_int, ctypes.c_int]
    x11.XQueryTree.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
        ctypes.POINTER(ctypes.c_uint)]
    x11.XFree.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        return
    try:
        # Tk wraps each top-level window in an outer X window: cut that one too
        inner = window.winfo_id()
        root_id, parent = ctypes.c_ulong(), ctypes.c_ulong()
        children, count = ctypes.POINTER(ctypes.c_ulong)(), ctypes.c_uint()
        x11.XQueryTree(display, inner, ctypes.byref(root_id), ctypes.byref(parent),
                       ctypes.byref(children), ctypes.byref(count))
        if children:
            x11.XFree(children)
        targets = [inner]
        if parent.value and parent.value != root_id.value:
            targets.append(parent.value)
        for xid in targets:
            if radius is None:  # no mask at all: the window's whole rectangle again
                xext.XShapeCombineMask(display, xid, 0, 0, 0, 0, 0)
                continue
            # 0, 0, 0, 0: the window's outline (ShapeBounding), no offset, replace (ShapeSet)
            xext.XShapeCombineRectangles(display, xid, 0, 0, 0, rects, len(rows), 0, 0)
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)


def set_title_bar(window, show):
    """Show or hide a window's title bar (it stays a normal window: in the dock, and it
    gets the keyboard when clicked). Asks the window manager through the "Motif" hint,
    which GNOME and most others follow. Returns False if that wasn't possible."""
    try:
        from Xlib import display as xdisplay
        d = xdisplay.Display()
    except Exception:  # no X connection / Xlib: just keep the title bar
        return False
    try:
        # Tk puts each top-level window inside a "wrapper" window: that's the one the
        # window manager looks after, so the hint goes on it
        wrapper = d.create_resource_object("window", window.winfo_id()).query_tree().parent
        hints = d.intern_atom("_MOTIF_WM_HINTS")
        if show:
            wrapper.delete_property(hints)
        else:
            # flags = 2: only the "decorations" part is set; decorations = 0: none
            wrapper.change_property(hints, hints, 32, [2, 0, 0, 0, 0])
        d.flush()
        return True
    except Exception:
        return False
    finally:
        d.close()


_REPAINT_X = []  # [x11 library, display], opened the first time repaint() needs them


def repaint(widget):
    """Make `widget` and everything inside it redraw from scratch.
    When a switch shows or hides rows, things on the page slide to new places, and now
    and then X leaves a few old pixels behind (specks, or half-drawn words). Asking X to
    'expose' every window makes each one paint itself again, without any flicker."""
    if not _REPAINT_X:
        try:
            import ctypes
            import ctypes.util
            x11 = ctypes.CDLL(ctypes.util.find_library("X11"))
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XClearArea.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_int]
            x11.XFlush.argtypes = [ctypes.c_void_p]
            display = x11.XOpenDisplay(None)
        except (OSError, TypeError, AttributeError):
            display = None
        _REPAINT_X[:] = [x11, display] if display else [None, None]
    x11, display = _REPAINT_X
    if not display:
        return
    todo = [widget]
    while todo:
        w = todo.pop()
        try:
            if not w.winfo_ismapped():
                continue  # hidden: it gets drawn fresh when it's shown anyway
            # the whole window (0 = all the way), and send the "please redraw" event
            x11.XClearArea(display, w.winfo_id(), 0, 0, 0, 0, 1)
        except tk.TclError:
            continue
        todo.extend(w.winfo_children())
    x11.XFlush(display)


class FloatingBadge(tk.Toplevel):
    """A small rounded card in the top-left corner of the screen while the clicker is running,
    so you can see it's on even with the window hidden. It shows what's happening and the
    details (speed, button or key, how to stop), and hides itself when stopped.
    Click it to bring the window back."""

    MARGIN = 12   # gap from the corner of the screen
    RADIUS = 10
    PAD_X = 14

    def __init__(self, root, on_click):
        super().__init__(root)
        self.withdraw()  # hidden until something is running
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonRelease-1>", lambda e: on_click())
        self.dot = tk.PhotoImage(width=8, height=8)
        self.areas = screen_areas()
        base = tkfont.nametofont("TkDefaultFont").actual()
        self.title_font = tkfont.Font(family=base["family"], size=base["size"], weight="bold")
        self.detail_font = tkfont.Font(family=base["family"], size=max(base["size"] - 1, 7))
        self.shape = None  # size the rounded shape was made for
        self.showing = False

    def update_state(self, show, on, title, details, progress, palette, near, corner):
        """show: whether the card is on screen. on: running (accent colour) or not (grey).
        progress: an extra live line like "23 of 100 clicks · 0:42 left" (or "")."""
        if not show:
            if self.showing:
                self.withdraw()
                self.showing = False
            return
        fill = palette["accent"] if on else palette["border"]
        ink = palette["accent_fg"] if on else text_on(fill)
        soft = mix_color(ink, fill, 0.25)  # details slightly softer than the title
        lines = [(title, self.title_font, ink)]
        if details:
            lines.append((details, self.detail_font, soft))
        if progress:
            lines.append((progress, self.title_font, ink))
        text_w = max(font.measure(text) for text, font, _ in lines)
        width = self.PAD_X + 8 + 8 + text_w + self.PAD_X
        # don't jiggle narrower and wider as the numbers tick over during a run
        if title != getattr(self, "last_title", None):
            self.min_width = 0
        self.last_title = title
        width = self.min_width = max(width, getattr(self, "min_width", 0))
        line_h = self.title_font.metrics("linespace") + 1
        height = max(30, 12 + line_h * len(lines))
        c = self.canvas
        c.delete("all")
        c.configure(width=width, height=height, bg=fill)
        paint_dot(self.dot, 8, ink, fill)
        y = (height - line_h * len(lines)) // 2 + 1
        c.create_image(self.PAD_X, y + line_h // 2 - 4, image=self.dot, anchor="nw")
        for text, font, color in lines:
            c.create_text(self.PAD_X + 16, y, text=text, anchor="nw", fill=color, font=font)
            y += line_h
        # the chosen corner of the monitor the app window is on (clear of any panels)
        x0, y0, w0, h0 = self.areas[0] if self.areas else (0, 0, 1280, 720)
        for x, y, w, h in self.areas:
            if x <= near[0] < x + w and y <= near[1] < y + h:
                x0, y0, w0, h0 = x, y, w, h
                break
        left = x0 + self.MARGIN if "left" in corner else x0 + w0 - width - self.MARGIN
        top = y0 + self.MARGIN if corner.startswith("Top") else y0 + h0 - height - self.MARGIN
        self.geometry(f"{width}x{height}+{left}+{top}")
        self.size = (width, height)
        if not self.showing:
            self.showing = True
            if self.shape is None:
                # First time: the corners can only be cut once the window is on screen, so
                # keep it invisible for that moment (no flash of square corners)
                self.set_alpha(0.0)
                self.deiconify()
                self.after(60, self.first_shape)
                return
            self.deiconify()
        if self.shape is not None and self.shape != (width, height):
            self.shape = (width, height)
            self.update_idletasks()
            round_window(self, self.RADIUS, width, height)

    def first_shape(self):
        self.update_idletasks()
        self.shape = self.size
        round_window(self, self.RADIUS, *self.size)
        self.set_alpha(1.0)

    def set_alpha(self, value):
        try:
            self.attributes("-alpha", value)
        except tk.TclError:
            pass


class ScreenPicker(tk.Toplevel):
    """Dims the whole screen; click anywhere to pick that spot. Esc cancels."""

    def __init__(self, root, message, on_pick):
        super().__init__(root)
        self.on_pick = on_pick
        self.overrideredirect(True)
        width, height = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{width}x{height}+0+0")
        self.configure(bg="#000000", cursor="crosshair")
        try:
            self.attributes("-topmost", True)
            self.attributes("-alpha", 0.35)
        except tk.TclError:
            pass
        # the message sits in the middle of the monitor the mouse is on
        mx, my = self.winfo_pointerxy()
        for x, y, w, h in screen_areas() or [(0, 0, width, height)]:
            if x <= mx < x + w and y <= my < y + h:
                mx, my = x + w // 2, y + h // 2
                break
        tk.Label(self, text=message, bg="#000000", fg="#ffffff",
                 font=("TkDefaultFont", 16, "bold")).place(x=mx, y=my, anchor="center")
        self.bind("<ButtonRelease-1>", self.picked)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<ButtonRelease-3>", lambda e: self.destroy())
        try:
            self.wait_visibility()
            self.grab_set_global()
        except tk.TclError:
            pass
        self.focus_force()

    def picked(self, event):
        x, y = event.x_root, event.y_root
        self.destroy()
        self.on_pick(x, y)


class RecordingEditor(tk.Toplevel):
    """Edit the current recording as text, one input per line (the same style as the
    profile files). Lines that don't make sense are skipped when you save."""

    def __init__(self, parent, recording, palette, on_save):
        super().__init__(parent)
        self.on_save = on_save
        p = palette
        self.title("Edit recording")
        self.configure(bg=p["bg"])
        self.geometry("560x560")
        self.minsize(420, 360)
        self.transient(parent)
        body = tk.Frame(self, bg=p["bg"], padx=16, pady=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        tk.Label(body, text='One input per line, e.g. {[0.1],kpress:"h"}. The number in [ ] '
                            "is the wait in seconds since the line before.", bg=p["bg"],
                 fg=p["muted"], wraplength=520, justify="left", anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.text = tk.Text(body, wrap="none", undo=True, bd=0, highlightthickness=1,
                            highlightbackground=p["border"], highlightcolor=p["accent"],
                            bg=p["field"], fg=p["fg"], insertbackground=p["fg"],
                            selectbackground=p["select"], selectforeground=p["select_fg"],
                            padx=8, pady=6, font=("DejaVu Sans Mono", 10))
        self.text.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)
        lines = profile_lines("", recording)[1:] if recording else []
        self.text.insert("1.0", "\n".join(lines))
        self.text.edit_reset()
        self.message = tk.Label(body, text=f"{len(lines)} {'line' if len(lines) == 1 else 'lines'}", bg=p["bg"], fg=p["muted"],
                                anchor="w")
        self.message.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        buttons = tk.Frame(body, bg=p["bg"])
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        cancel = RoundedButton(buttons, "Cancel", self.destroy, height=34)
        cancel.set_palette(p)
        cancel.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        save = RoundedButton(buttons, "Save", self.save, height=34, selectable=True, accent=True)
        save.set_palette(p)
        save.set_selected(True)
        save.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.bind("<Escape>", lambda e: self.destroy())
        self.text.focus_set()

    def save(self):
        text = self.text.get("1.0", "end")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        skipped = sum(1 for line in lines if not PROFILE_LINE.match(line)
                      and not line.startswith("{profile:") and not HOTKEY_LINE.match(line))
        recording = parse_profile(text)
        if lines and recording is None:
            self.message.configure(text="None of the lines could be read, so nothing was saved.")
            return
        self.destroy()
        self.on_save(recording, skipped)


class ScrollArea(ttk.Frame):
    """A page area that scrolls when its contents are taller than the window. Put things in
    `self.inner`. The thin scroll bar only shows when it's needed; the mouse wheel works
    anywhere over the area."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, yscrollincrement=20)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                 style="Thin.Vertical.TScrollbar")
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.palette = None
        self.bar_job = None  # see update_scroll
        self.inner.bind("<Configure>", lambda e: self.update_scroll())
        self.canvas.bind("<Configure>", self.on_resize)
        self.bind("<Enter>", lambda e: self.wheel(True))
        self.bind("<Leave>", self.on_leave)

    def on_resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        self.update_scroll()

    def needs_scrolling(self):
        return self.inner.winfo_reqheight() > self.canvas.winfo_height() > 1

    def update_scroll(self):
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(),
                                            self.inner.winfo_reqheight()))
        # Decide about the scroll bar once things have settled. Showing it makes the page a
        # little narrower, so text wraps onto more lines and the page gets taller (and
        # hiding it does the opposite). Deciding mid-way, from heights that are still out
        # of date, could make it flick on and off for ever.
        if self.bar_job is not None:
            self.after_cancel(self.bar_job)
        self.bar_job = self.after(40, self.show_bar_if_needed)

    def show_bar_if_needed(self):
        self.bar_job = None
        if self.needs_scrolling():
            self.bar.grid()
        else:
            self.bar.grid_remove()
            self.canvas.yview_moveto(0)

    def wheel(self, on):
        """Catch the mouse wheel only while the pointer is over this area."""
        for sequence in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
            if on:
                self.bind_all(sequence, self.on_wheel)
            else:
                self.unbind_all(sequence)

    def on_leave(self, _event):
        x, y = self.winfo_pointerxy()
        inside = (self.winfo_rootx() <= x < self.winfo_rootx() + self.winfo_width()
                  and self.winfo_rooty() <= y < self.winfo_rooty() + self.winfo_height())
        if not inside:  # moving onto something inside the area also counts as "leaving"
            self.wheel(False)

    def on_wheel(self, event):
        if not self.needs_scrolling():
            return
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-2, "units")
        else:
            self.canvas.yview_scroll(2, "units")

    def set_palette(self, palette):
        self.palette = palette
        self.canvas.configure(bg=palette["bg"])


class SidebarHandle(tk.Canvas):
    """The line between the menu and the page. Drag it to make a side menu wider or
    narrower (or a top/bottom menu taller or shorter); double-click it to put the menu
    back to its normal size."""

    WIDTH = 7  # how wide the grabbable strip is; the line is drawn in its middle

    def __init__(self, parent, on_drag, on_release, on_reset):
        super().__init__(parent, width=self.WIDTH, highlightthickness=0, bd=0,
                         cursor="sb_h_double_arrow")
        self.on_drag = on_drag
        self.palette = None
        self.hover = False
        self.dragging = False
        self.vertical = True  # False when the menu is along the top or bottom
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", lambda e: self.set_hover(True))
        self.bind("<Leave>", lambda e: self.set_hover(False))
        self.bind("<ButtonPress-1>", self.start_drag)
        self.bind("<B1-Motion>", lambda e: on_drag(e.x_root, e.y_root))
        self.bind("<ButtonRelease-1>", lambda e: (self.stop_drag(), on_release()))
        self.bind("<Double-Button-1>", lambda e: on_reset())

    def set_vertical(self, vertical):
        """Upright between a side menu and the page, or flat under/over a top/bottom menu.
        Either way it can be dragged."""
        self.vertical = vertical
        if vertical:
            self.configure(width=self.WIDTH, height=1, cursor="sb_h_double_arrow")
        else:
            self.configure(height=self.WIDTH, width=1, cursor="sb_v_double_arrow")
        self.redraw()

    def set_hover(self, hover):
        self.hover = hover
        self.redraw()

    def start_drag(self, _event):
        self.dragging = True
        self.redraw()

    def stop_drag(self):
        self.dragging = False
        self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.palette:
            return
        w, h = self.winfo_width(), self.winfo_height()
        mid = self.WIDTH // 2

        def line(before, after, color):  # a line from `before` px before the middle to `after` after
            if self.vertical:
                self.create_rectangle(mid - before, 0, mid + after, h, fill=color, outline="")
            else:
                self.create_rectangle(0, mid - before, w, mid + after, fill=color, outline="")

        if self.dragging:  # accent only while it's actually being dragged
            line(1, 2, self.palette["accent"])
        elif self.hover:  # just passing over: a slightly thicker grey line shows it can be dragged
            line(1, 1, self.palette["muted"])
        else:
            line(0, 1, self.palette["border"])


class AutoClicker:
    SYNTHETIC_WINDOW = 0.03  # seconds: presses this soon after our own click/press are ours
    REPEAT_WINDOW = 0.2      # seconds: the same key again this soon is a duplicate/held key
    MOVE_TOLERANCE = 10      # pixels: auto stop ignores mouse wobbles smaller than this
    MOVE_SAMPLE = 0.015      # seconds: record at most one mouse move this often

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Clicker")
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(*MIN_SIZE)
        self.set_window_icon()

        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self.running = threading.Event()   # set while clicking/pressing/replaying
        self.stopped = threading.Event()   # set by stop(), wakes the worker from its wait
        self.shutdown = threading.Event()
        self.events = queue.Queue()
        self.settings = {}
        self.clicks = 0
        self.armed = False  # True during start delay or while running
        self.started_at = 0.0     # when clicking began (for "stop after a set time")
        self.round_widgets = []  # every custom-drawn widget, so the theme can reach them
        self.nav_buttons = {}
        self.key_choosers = []
        self.optional_rows = []   # (widgets, should_show) pairs, see show_optional_rows
        self.column_groups = []   # side-by-side fields, see field_columns
        self.cards = []           # (card, heading) pairs, see card_section
        self.card_frames = []     # plain frames on cards, recoloured with the theme
        self.dividers = []        # thin lines between card rows
        self.default_surface = "page"
        self.capturing = None     # the KeyChooser waiting for a key press, if any
        self.capture_mods = []    # modifiers held while choosing a combo, e.g. ["ctrl"]
        self.last_synthetic = {}  # input code -> time of our last automatic press of it
        self.last_input = {}      # input code -> time it was last pressed
        self.anchor = None        # where the mouse was when clicking began (for auto stop)
        self.held = []            # what Hold mode is holding down right now: (kind, thing)
        self.held_codes = set()
        self.hold_lock = threading.Lock()
        self.theme_job = None
        self.repaint_jobs = []  # see repaint_soon
        # recording
        self.recording_active = False
        self.recording_buf = []
        self.record_t0 = 0.0
        self.record_last_move = 0.0
        self.record_pressed = set()   # buttons/keys pressed since recording began
        self.record_exclude = set()   # the app's own keys, never recorded
        self.record_rect = None       # the app window, to trim clicks on "Stop recording"
        self.record_from_button = False
        # profiles
        tidy_profiles()
        self.needs_settings_rewrite = False
        self.delete_armed_job = None

        self.style = ttk.Style()
        self.setup_fonts()

        saved = load_settings()
        self.locations = saved["locations"] or []  # click spots: one, or several in a row
        self.profile_hotkeys = {}                  # hotkey code -> profile name
        self.hotkey_var_busy = False               # True while showing a profile's hotkey
        self.badge = None                          # the floating running indicator
        self.last_badge_update = 0.0
        self.plays_done = 0
        self.recording_name = None  # the profile the current recording came from, if any
        self.recording = self.load_current_recording(saved)
        self.build_ui(saved)

        threading.Thread(target=self.click_loop, daemon=True).start()
        self.listener = keyboard.Listener(on_press=self.on_key, on_release=self.on_key_release)
        self.listener.start()
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse, on_move=self.on_mouse_move,
                                             on_scroll=self.on_scroll)
        self.mouse_listener.start()

        if self.needs_settings_rewrite:
            self.save_settings()  # takes the old built-in recording out of settings.json
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll()

    def set_window_icon(self):
        """Give the window, dock and app list the icon that suits the computer's light/dark
        mode, and swap it whenever that mode changes."""
        self.icon_style = None
        self.icon_images = []
        self.update_icon()
        self.theme_watcher = None
        threading.Thread(target=self.watch_system_theme, daemon=True).start()

    def watch_system_theme(self):
        """(Background thread) Wait for the computer's light/dark setting to change."""
        try:
            self.theme_watcher = subprocess.Popen(
                ["gsettings", "monitor", "org.gnome.desktop.interface"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            for line in self.theme_watcher.stdout:
                if "color-scheme" in line or "gtk-theme" in line:
                    self.events.put(("system_theme",))
        except (OSError, ValueError):
            pass  # no gsettings: the icon just stays as it was at startup

    def update_icon(self):
        style = "dark" if system_is_dark() else "light"
        if style == self.icon_style:
            return
        self.icon_style = style
        images = []  # kept on self so Tk doesn't throw the images away
        for size in (16, 32, 48, 64, 128):
            try:
                path = icon_path(size, style)
                if path.is_file():
                    images.append(tk.PhotoImage(file=str(path)))
                elif size in (32, 64):  # quick to draw, and enough for the dock
                    data = base64.b64encode(icon_png(size, style))
                    images.append(tk.PhotoImage(data=data, format="png"))
            except (tk.TclError, OSError):
                pass
        if images:
            self.icon_images = images
            self.root.iconphoto(True, *images)  # True: popups get it too
        update_fallback_icon(style)

    # ---------------- Fonts ----------------
    def setup_fonts(self):
        """Use a clean sans-serif if one is installed, otherwise the system default."""
        families = set(tkfont.families(self.root))
        family = tkfont.nametofont("TkDefaultFont").actual("family")
        for name in FONT_CHOICES:
            if name in families:
                family = name
                break
        for name in NAMED_FONTS:
            try:
                tkfont.nametofont(name).configure(family=family, size=FONT_SIZE)
            except tk.TclError:
                pass
        self.font_family = family
        self.font_title = tkfont.Font(family=family, size=FONT_SIZE + 5, weight="bold")
        self.font_brand = tkfont.Font(family=family, size=FONT_SIZE + 1, weight="bold")
        self.font_section = tkfont.Font(family=family, size=FONT_SIZE + 1, weight="bold")
        self.font_caption = tkfont.Font(family=family, size=FONT_SIZE - 1, weight="bold")
        self.font_nav = tkfont.Font(family=family, size=FONT_SIZE)  # menu buttons

    # ---------------- UI ----------------
    def build_ui(self, saved: dict):
        # Mouse clicker
        self.cps = tk.DoubleVar(value=saved["cps"])
        self.button = tk.StringVar(value=saved["button"])
        self.click_type = tk.StringVar(value=saved["click_type"])
        self.click_delay_on = tk.BooleanVar(value=saved["click_delay_on"])
        self.click_delay = tk.DoubleVar(value=saved["click_delay"])
        self.limit_on = tk.BooleanVar(value=saved["limit_on"])
        self.limit = tk.IntVar(value=saved["limit"])
        self.time_limit_on = tk.BooleanVar(value=saved["time_limit_on"])
        self.time_limit = tk.DoubleVar(value=saved["time_limit"])
        self.delay = tk.DoubleVar(value=saved["delay"])
        self.location_on = tk.BooleanVar(value=saved["location_on"])
        self.multi_location = tk.BooleanVar(value=saved["multi_location"])
        self.hold = tk.BooleanVar(value=saved["hold"])
        # Keyboard clicker
        self.kb_key = tk.StringVar(value=saved["kb_key"])
        self.kb_cps = tk.DoubleVar(value=saved["kb_cps"])
        self.kb_delay = tk.DoubleVar(value=saved["kb_delay"])
        self.kb_limit_on = tk.BooleanVar(value=saved["kb_limit_on"])
        self.kb_limit = tk.IntVar(value=saved["kb_limit"])
        self.kb_time_limit_on = tk.BooleanVar(value=saved["kb_time_limit_on"])
        self.kb_time_limit = tk.DoubleVar(value=saved["kb_time_limit"])
        self.kb_hold = tk.BooleanVar(value=saved["kb_hold"])
        # Record and replay
        self.replay_loop = tk.BooleanVar(value=saved["replay_loop"])
        self.replay_limit_on = tk.BooleanVar(value=saved["replay_limit_on"])
        self.replay_limit = tk.IntVar(value=saved["replay_limit"])
        self.record_keys_only = tk.BooleanVar(value=saved["record_keys_only"])
        self.record_moves = tk.BooleanVar(value=saved["record_moves"])
        # Profiles
        self.profile_name = tk.StringVar()
        self.profile_choice = tk.StringVar(value=next(iter(list_profiles()), ""))
        self.profile_hotkey = tk.StringVar(value="")  # hotkey of the chosen profile
        # Settings
        self.hotkey = tk.StringVar(value=saved["hotkey"])
        self.location_key = tk.StringVar(value=saved["location_key"])
        self.record_key = tk.StringVar(value=saved["record_key"])
        self.auto_stop = tk.BooleanVar(value=saved["auto_stop"])
        self.on_top = tk.BooleanVar(value=saved["always_on_top"])
        self.mini = tk.BooleanVar(value=saved["mini_mode"])
        self.mini_shown = False  # see apply_mini
        self.full_size = None    # the window's size before mini mode, to go back to
        try:
            self.mini_position = [int(v) for v in saved["mini_position"]][:2]
        except (TypeError, ValueError):
            self.mini_position = []
        if len(self.mini_position) != 2:
            self.mini_position = [-1, -1]
        self.sidebar_side = tk.StringVar(value=saved["sidebar_side"])
        self.badge_show = tk.StringVar(value=saved["badge_show"])
        self.badge_corner = tk.StringVar(value=saved["badge_corner"])
        self.finish_sound = tk.BooleanVar(value=saved["finish_sound"])
        self.text_size = tk.StringVar(value=saved["text_size"])
        self.dark = tk.BooleanVar(value=saved["dark_mode"])
        self.accent = tk.StringVar(value=saved["accent"])
        self.active_mode = saved["active_mode"]
        self.page = tk.StringVar(value=MODE_PAGES[self.active_mode])  # open where you left off

        # Settings saved in settings.json (with the keys and look, added in collect_settings)
        self.profile_vars = {
            "cps": self.cps, "button": self.button, "click_type": self.click_type,
            "click_delay_on": self.click_delay_on, "click_delay": self.click_delay,
            "limit_on": self.limit_on, "limit": self.limit,
            "time_limit_on": self.time_limit_on, "time_limit": self.time_limit,
            "delay": self.delay, "location_on": self.location_on, "hold": self.hold,
            "kb_key": self.kb_key, "kb_cps": self.kb_cps,
            "kb_delay": self.kb_delay, "kb_limit_on": self.kb_limit_on,
            "kb_limit": self.kb_limit, "kb_time_limit_on": self.kb_time_limit_on,
            "kb_time_limit": self.kb_time_limit, "kb_hold": self.kb_hold,
            "replay_loop": self.replay_loop,
            "replay_limit_on": self.replay_limit_on, "replay_limit": self.replay_limit,
            "record_keys_only": self.record_keys_only, "record_moves": self.record_moves,
            "multi_location": self.multi_location,
        }

        # Apply the starting colours instantly (no animation on launch)
        self.style.theme_use("clam")
        self.style.layout("Thin.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        self.apply_palette(build_palette(saved["dark_mode"], saved["accent"]))

        self.hotkey.trace_add("write", lambda *_: self.refresh_button())
        self.location_key.trace_add("write", lambda *_: self.refresh_location())
        self.record_key.trace_add("write", lambda *_: self.refresh_recording_info())
        self.on_top.trace_add("write", lambda *_: self.apply_on_top())
        self.badge_show.trace_add("write", lambda *_: (self.refresh_running(),
                                                        self.show_optional_rows(),
                                                        self.save_settings()))
        self.badge_corner.trace_add("write", lambda *_: (self.refresh_running(),
                                                          self.save_settings()))
        self.profile_choice.trace_add("write", lambda *_: self.show_profile_hotkey())
        self.finish_sound.trace_add("write", lambda *_: self.save_settings())
        self.text_size.trace_add("write", lambda *_: (self.apply_text_size(), self.save_settings()))
        self.profile_hotkey.trace_add("write", lambda *_: self.on_profile_hotkey_set())
        for var in (self.location_on, self.multi_location):
            var.trace_add("write", lambda *_: self.refresh_location())
        self.dark.trace_add("write", lambda *_: self.animate_theme())
        self.accent.trace_add("write", lambda *_: self.animate_theme())

        # Layout: menu | handle | page. The menu can sit on any side (see layout_sidebar)
        sidebar = ttk.Frame(self.root, padding=(8, 12))
        self.sidebar = sidebar
        self.handle = self.register(SidebarHandle(self.root, self.drag_sidebar,
                                                  self.save_settings, self.reset_sidebar))
        content = ttk.Frame(self.root, padding=20)
        self.content = content

        # Menu: logo, page buttons, then the status at the far end
        self.logo = self.register(Logo(sidebar, self.font_brand))
        pages = (("clicker", "Mouse"), ("keyboard", "Keyboard"), ("recording", "Profiles"),
                 ("settings", "Settings"))
        # the page buttons sit together in a rounded card, with thin lines between them
        self.nav_card = self.register(Card(sidebar))
        self.nav_lines = []
        for i, (name, label) in enumerate(pages):
            self.nav_buttons[name] = self.register(
                RoundedButton(self.nav_card.body, label, lambda n=name: self.go_to(n),
                              font=self.font_nav, height=34, width=92, flat=True,
                              selectable=True), surface="card")
            if i:
                line = tk.Frame(self.nav_card.body, bd=0, highlightthickness=0,
                                bg=self.palette["divider"])
                self.dividers.append(line)
                self.nav_lines.append(line)

        status_row = ttk.Frame(sidebar)
        self.status_row = status_row
        status_row.columnconfigure(1, weight=1)
        # a light that's accent coloured while running, grey when stopped
        self.status_dot = self.register(StatusDot(status_row))
        self.status_dot.grid(row=0, column=0, sticky="n", pady=(4, 0), padx=(0, 6))
        self.status = ttk.Label(status_row, text="Stopped", justify="left")
        self.status.grid(row=0, column=1, sticky="w")
        # always-visible reminder of the emergency stop
        self.esc_hint = ttk.Label(sidebar, text="Esc stops everything", style="Muted.TLabel",
                                  justify="left")
        self.sidebar_width = saved["sidebar_width"]
        self.bar_height = saved["bar_height"]
        self.layout_sidebar()
        sidebar.bind("<Configure>", self.size_nav_buttons)  # buttons follow the window height
        self.sidebar_side.trace_add("write", lambda *_: (self.layout_sidebar(),
                                                         self.save_settings()))

        # Pages (stacked in the same cell, raised one at a time)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.pages = {}
        for name, _label in pages:
            frame = ttk.Frame(content)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            self.pages[name] = frame

        self.build_clicker_page(self.pages["clicker"])
        self.build_keyboard_page(self.pages["keyboard"])
        self.build_recording_page(self.pages["recording"])
        self.build_settings_page(self.pages["settings"])
        self.mini_frame = ttk.Frame(self.root, padding=MINI_MARGIN, style="Edge.TFrame")
        self.build_mini_view(self.mini_frame)

        for var in (self.click_delay_on, self.limit_on, self.time_limit_on, self.location_on,
                    self.multi_location, self.hold, self.kb_limit_on, self.kb_time_limit_on,
                    self.kb_hold, self.replay_loop, self.replay_limit_on, self.record_keys_only):
            var.trace_add("write", lambda *_: self.show_optional_rows())
        self.show_optional_rows()

        self.show_page()
        self.refresh_profile_list()
        self.refresh_button()
        self.refresh_location()
        self.refresh_recording_info()
        self.apply_on_top()
        self.bind_page_shortcuts()
        # after the window is resized, things have moved: redraw so nothing is left behind
        self.root.bind("<Configure>", lambda e: e.widget is self.root and self.repaint_soon(),
                       add="+")
        if self.text_size.get() != "Normal":
            self.apply_text_size()
        self.root.after(300, self.refresh_running)  # once the window has its place on screen
        self.mini.trace_add("write", lambda *_: self.apply_mini())
        if self.mini.get():  # once the window is on screen (its title bar can't go before)
            self.root.after(150, lambda: self.apply_mini(save=False))

    # ---- widget factories (each registers itself for theming) ----
    def register(self, widget, surface=None):
        """Theme a custom widget now and on every colour change. surface="card" gives it
        the card colours, for widgets that sit on a card."""
        widget.surface = surface or self.default_surface
        widget.set_palette(self.surface_palette(widget.surface))
        self.round_widgets.append(widget)
        return widget

    def surface_palette(self, surface):
        p = self.palette
        if surface == "card":
            return dict(p, bg=p["card"], field=p["card_field"])
        if surface == "edge":  # mini mode's card sits on its window's outline
            return dict(p, bg=p["border"])
        return p

    def make_button(self, parent, text, command, **kwargs):
        return self.register(RoundedButton(parent, text, command, **kwargs))

    def make_spin(self, parent, variable, from_, to, increment):
        return self.register(RoundedSpin(parent, variable, from_, to, increment))

    def make_combo(self, parent, variable, values, width=FIELD_WIDTH):
        return self.register(RoundedCombo(parent, variable, values, width=width))

    def make_switch(self, parent, text, variable):
        return self.register(ToggleSwitch(parent, text, variable))

    def make_swatches(self, parent, variable, colors):
        return self.register(ColorSwatches(parent, variable, colors))

    def make_key_chooser(self, parent, variable, purpose, allowed=is_valid_input, combos=False):
        chooser = self.register(KeyChooser(parent, variable, self.start_capture,
                                           purpose, allowed, combos))
        self.key_choosers.append(chooser)
        return chooser

    def field_columns(self, frame, row, fields, columns, narrowest=96, label_style="TLabel",
                      gap=12, frame_style="TFrame"):
        """Fields side by side, each with its label above a box that fills its column.
        fields = [(label, factory, show)]; show=None means always shown.
        Hidden fields close up, so the visible ones always start from the left."""
        holder = ttk.Frame(frame, style=frame_style)
        holder.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for c in range(columns):
            holder.columnconfigure(c, weight=1, uniform="field")
        slots = []
        for label, factory, show in fields:
            slot = ttk.Frame(holder, style=frame_style)
            slot.columnconfigure(0, weight=1)
            ttk.Label(slot, text=label, style=label_style).grid(row=0, column=0, sticky="w",
                                                                pady=(0, 4 if label_style == "TLabel" else 2))
            factory(slot).grid(row=1, column=0, sticky="ew")
            slots.append((slot, show))
        group = {"holder": holder, "slots": slots, "columns": columns, "per_line": None,
                 "narrowest": narrowest,  # how narrow a field can get
                 "gap": gap}              # space between side-by-side fields
        self.column_groups.append(group)
        # in a narrow window, fewer fields fit on a line: the rest go on the next line
        holder.bind("<Configure>", lambda e: self.fields_per_line(group) != group["per_line"]
                    and self.layout_fields(group))

    def fields_per_line(self, group):
        visible = [slot for slot, show in group["slots"] if show is None or show()]
        width = group["holder"].winfo_width()
        if width <= 1 or not visible:
            return group["columns"]
        # the labels decide (the boxes under them can shrink), plus the gap beside each field
        need = max(group["narrowest"],
                   max(slot.winfo_children()[0].winfo_reqwidth() for slot in visible))
        need += group["gap"] * 3 // 4
        return max(1, min(group["columns"], width // need))

    def layout_fields(self, group):
        """Fields side by side, as many to a line as fit (see field_columns)."""
        gap = group["gap"]
        holder, slots, columns = group["holder"], group["slots"], group["columns"]
        per_line = self.fields_per_line(group)
        group["per_line"] = per_line
        for c in range(columns):
            holder.columnconfigure(c, weight=1 if c < per_line else 0,
                                   uniform="field" if c < per_line else "")
        visible = [slot for slot, show in slots if show is None or show()]
        for slot, _show in slots:
            if slot not in visible:
                slot.grid_forget()
        for i, slot in enumerate(visible):
            line, col = divmod(i, per_line)
            left = 0 if col == 0 else gap // 2
            right = 0 if col == per_line - 1 else gap // 2
            slot.grid(row=line, column=col, sticky="ew", padx=(left, right),
                      pady=(8 if line else 0, 0))

    @staticmethod
    def flow_label(label, reserve=0, most=500):
        """Make a label's text wrap to fit the page (up to `most` pixels wide), leaving
        `reserve` pixels for whatever sits beside it."""
        label.master.bind("<Configure>", lambda e: label.configure(
            wraplength=max(150, min(most, e.width - reserve))), add="+")
        return label

    def button_group(self, parent, buttons):
        """Small buttons side by side, for the end of a card row."""
        frame = tk.Frame(parent, bd=0, highlightthickness=0, bg=self.palette["card"])
        self.card_frames.append(frame)
        for i, (text, command) in enumerate(buttons):
            self.make_button(frame, text, command, height=28, width=64).grid(
                row=0, column=i, padx=(0 if i == 0 else 6, 0))
        return frame

    def card_section(self, frame, row, caption=None):
        """A small grey heading with a rounded card under it (grid rows `row` and `row + 1`).
        Add rows to the card with card_row. Cards with no visible rows hide themselves."""
        heading = None
        if caption:
            heading = ttk.Label(frame, text=caption, style="Caption.TLabel")
            heading.grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 5))
        card = self.register(Card(frame))
        gap = 10 if row and not caption else 0  # a little space when there's no heading
        card.grid(row=row + 1, column=0, columnspan=2, sticky="ew", pady=(gap, 6))
        self.cards.append((card, heading))
        card.vlines = []  # lines between side-by-side columns (made when needed)
        # a wider window can fit more rows side by side: re-arrange when that changes
        def on_width(width):
            if self.card_columns(card, width) != card.columns:
                self.layout_card(card, heading)
                self.repaint_soon()
            else:
                self.fit_card_rows(card, width)
        card.on_width = on_width
        return card

    def card_row(self, card, title, variable=None, subtitle=None, value=None,
                 value_show=None, show=None):
        """One row in a card: a title (and optional grey subtitle) on the left, then an
        optional box made by `value(parent)`, then a switch for `variable`.
        Clicking the words flips the switch too.
        show(): the whole row is hidden while this is False.
        value_show(): the box is only shown while this is True (e.g. while the switch is on)."""
        row = tk.Frame(card.body, bd=0, highlightthickness=0)
        row.columnconfigure(0, weight=1)
        divider = tk.Frame(card.body, height=1, bd=0, highlightthickness=0)
        words = tk.Frame(row, bd=0, highlightthickness=0)
        words.grid(row=0, column=0, sticky="w", pady=7)
        self.card_frames += [row, words]
        self.dividers.append(divider)
        for frame in (row, words):  # colour them now too, not just on the next theme change
            frame.configure(bg=self.palette["card"])
        divider.configure(bg=self.palette["divider"])

        title_label = ttk.Label(words, text=title, style="Card.TLabel")
        title_label.grid(row=0, column=0, sticky="w")
        subtitle_label = None
        if subtitle is not None:
            subtitle_label = ttk.Label(words, text=subtitle, style="CardMuted.TLabel",
                                       wraplength=320, justify="left")
            subtitle_label.grid(row=1, column=0, sticky="w", pady=(1, 0))

        box = None
        if value:
            self.default_surface = "card"  # the box sits on the card, so use card colours
            try:
                box = value(row)
            finally:
                self.default_surface = "page"
            box.grid(row=0, column=1, padx=(10, 0), pady=6)
            if value_show:
                self.optional_rows.append(((box,), value_show))
            if subtitle_label is not None:  # leave room for the box (and switch) next to the words
                box.update_idletasks()      # so a row of buttons knows how wide it is
                room = 400 - box.winfo_reqwidth() - (48 if variable is not None else 0)
                subtitle_label.configure(wraplength=max(200, room))

        if variable is not None:
            switch = self.register(ToggleSwitch(row, "", variable), surface="card")
            switch.grid(row=0, column=2, padx=(12, 0))
            flip = lambda e: variable.set(not variable.get())
            for widget in (row, words, title_label, subtitle_label):
                if widget is not None:
                    widget.bind("<ButtonRelease-1>", flip)
                    widget.configure(cursor="hand2")

        row.parts = {"title": title_label, "subtitle": subtitle_label, "box": box,
                     "box_show": value_show, "switch": variable is not None,
                     "wrap": int(subtitle_label.cget("wraplength")) if subtitle_label else 0,
                     "stacked": False}
        card.rows.append((row, divider, show))
        return title_label, subtitle_label, box

    def layout_cards(self):
        """Show each card's visible rows with a thin line between them; hide empty cards."""
        for card, heading in self.cards:
            self.layout_card(card, heading)

    def card_columns(self, card, width):
        """How many rows fit side by side in a card this wide (1 in a normal-size window)."""
        shown = [row for row, _divider, show in card.rows if show is None or show()]
        if len(shown) < 2 or width <= 1:
            return 1
        # the row needing the most room decides, so nothing gets squashed
        need = max(CARD_COLUMN_MIN, max(self.row_extras(row) + ROW_WORDS_MIN + 70
                                        for row in shown))
        room = width - 2 * Card.INSET_X
        columns = max(1, min(CARD_COLUMNS_MAX, len(shown), room // need))
        lines = -(-len(shown) // columns)  # rounded up
        while columns > 1 and -(-len(shown) // (columns - 1)) == lines:
            columns -= 1  # fewer columns, same number of lines: e.g. 4 rows as 2 x 2, not 3 + 1
        return columns

    def layout_card(self, card, heading):
        """Lay out one card's visible rows: one under another, or in a wide window, side by
        side in columns (filled left to right, then the next line), e.g.
            Click delay       (o)  |  Hold                     (o)
            Click at a set location (o)  |  Several spots in a row (o)"""
        body = card.body
        shown = [(row, divider) for row, divider, show in card.rows if show is None or show()]
        columns = self.card_columns(card, card.winfo_width())
        card.columns = columns
        for row, divider, _show in card.rows:
            row.grid_remove()
            divider.grid_remove()
        for line in card.vlines:
            line.grid_remove()
        for c in range(2 * CARD_COLUMNS_MAX):
            # even grid columns hold rows (all the same width), odd ones the lines between
            body.columnconfigure(c, weight=0, uniform="")
        for c in range(columns):
            body.columnconfigure(2 * c, weight=1, uniform="rows")

        for i, (row, divider) in enumerate(shown):
            r, c = divmod(i, columns)
            if r:  # a thin line above every row except the first line of them
                divider.grid(row=2 * r, column=2 * c, sticky="ew", padx=8)
            row.grid(row=2 * r + 1, column=2 * c, sticky="nsew", padx=8)
            row.rowconfigure(0, weight=1)  # keeps the words centred if the next column is taller

        lines = (len(shown) + columns - 1) // columns
        for c in range(1, columns):  # an upright line between columns
            while len(card.vlines) < c:
                line = tk.Frame(body, width=1, bd=0, highlightthickness=0,
                                bg=self.palette["divider"])
                self.dividers.append(line)
                card.vlines.append(line)
            card.vlines[c - 1].grid(row=0, column=2 * c - 1, rowspan=2 * lines, sticky="ns",
                                    pady=8)

        for widget in (card, heading):
            if widget is not None:
                if shown:
                    widget.grid()
                else:
                    widget.grid_remove()
        self.fit_card_rows(card, card.winfo_width())

    @staticmethod
    def words_need(row):
        """How much room a card row's words need before its box has to move below them:
        the whole title, and a reasonable width for grey text (which can wrap)."""
        parts = row.parts
        title = parts["title"]
        width = tkfont.Font(font=title.cget("font") or "TkDefaultFont").measure(title.cget("text"))
        if parts["subtitle"] is not None:
            width = max(width, 140)
        return min(ROW_WORDS_MIN, width + 12)

    @staticmethod
    def row_extras(row):
        """Room a card row needs beside its words: its box (if any) and its switch."""
        parts = row.parts
        box = parts["box"]
        return (box.winfo_reqwidth() + 10 if box is not None else 0) + (48 if parts["switch"] else 0)

    def fit_card_rows(self, card, width):
        """Fit each row to its column: grey text wraps tighter, and if there still isn't
        room for the words, the row's box (buttons, dropdown...) moves below them."""
        if width <= 1:
            return
        columns = card.columns
        column = (width - 2 * Card.INSET_X - (columns - 1)) / columns - 16  # 16: row padding
        for row, _divider, _show in card.rows:
            parts = row.parts
            box = parts["box"]
            switch = 48 if parts["switch"] else 0
            stacked = box is not None and column - self.row_extras(row) < self.words_need(row)
            if box is not None and stacked != parts["stacked"]:
                parts["stacked"] = stacked
                shown = parts["box_show"] is None or parts["box_show"]()
                if stacked:  # under the words, lined up with them
                    box.grid(row=1, column=0, sticky="w", padx=0, pady=(0, 8))
                else:
                    box.grid(row=0, column=1, sticky="", padx=(10, 0), pady=6)
                if not shown:
                    box.grid_remove()  # (it remembers where to go when it's shown)
            room = int(column - (switch if stacked or box is None else self.row_extras(row))) - 6
            if int(parts["title"].cget("wraplength") or 0) != max(100, room):
                parts["title"].configure(wraplength=max(100, room))
            if parts["subtitle"] is not None:
                wrap = max(100, min(parts["wrap"], room - 4))
                if int(parts["subtitle"].cget("wraplength")) != wrap:
                    parts["subtitle"].configure(wraplength=wrap)

    def page_body(self, frame, title):
        """A page: its title, then an area that scrolls if the page doesn't fit (the
        Start/Reset button below it, in grid row 2, stays put)."""
        ttk.Label(frame, text=title, font=self.font_title).grid(
            row=0, column=0, sticky="w", pady=(0, 12))
        scroll = self.register(ScrollArea(frame))
        scroll.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)
        sub = scroll.inner
        sub.columnconfigure(0, weight=1)
        return sub

    def build_clicker_page(self, frame):
        sub = self.page_body(frame, "Mouse")
        clicking = lambda: not self.hold.get()  # these only matter when not holding

        # Main settings side by side. "Wait" takes the place of clicks per second
        # while Click delay is on.
        self.field_columns(sub, 0, [
            ("Clicks per second", lambda p: self.make_spin(p, self.cps, 0.1, 100, 1),
             lambda: clicking() and not self.click_delay_on.get()),
            ("Wait (seconds)", lambda p: self.make_spin(p, self.click_delay, 0.1, 3600, 0.5),
             lambda: clicking() and self.click_delay_on.get()),
            ("Mouse button", lambda p: self.make_combo(p, self.button, list(BUTTONS)), None),
            ("Click type", lambda p: self.make_combo(p, self.click_type, list(CLICK_TYPES)),
             clicking),
            ("Start delay (s)", lambda p: self.make_spin(p, self.delay, 0, 60, 1), None),
        ], columns=4)

        card = self.card_section(sub, 1, "Options")
        self.card_row(card, "Click delay", self.click_delay_on,
                      subtitle="Wait a set time between clicks", show=clicking)
        self.card_row(card, "Hold", self.hold, subtitle="Hold the button down until you stop")
        self.hold.trace_add("write", lambda *_: self.refresh_location())
        # Set location. Its wording says "Click" or "Hold" to match the Hold switch,
        # and the hint shows the saved spot (see refresh_location).
        self.location_title, self.location_hint, _ = self.card_row(
            card, "Click at a set location", self.location_on, subtitle="",
            value=lambda p: self.button_group(p, [("Pick", self.pick_location)]),
            value_show=self.location_on.get)
        self.optional_rows.append(((self.location_hint,), self.location_on.get))
        self.card_row(card, "Several spots in a row", self.multi_location,
                      subtitle="Press Pick or the set location key to add a spot. "
                               "They're clicked in turn.",
                      value=lambda p: self.button_group(p, [("Clear", self.clear_locations)]),
                      value_show=self.multi_location.get,
                      show=lambda: self.location_on.get() and not self.hold.get())

        card = self.card_section(sub, 3, "Stopping")
        self.card_row(card, "After a number of clicks", self.limit_on,
                      value=lambda p: self.make_spin(p, self.limit, 1, 1000000, 10),
                      value_show=self.limit_on.get, show=clicking)
        self.card_row(card, "After a set time (seconds)", self.time_limit_on,
                      value=lambda p: self.make_spin(p, self.time_limit, 1, 86400, 5),
                      value_show=self.time_limit_on.get)


        self.toggle_btn = self.make_button(frame, "", self.toggle, height=42, selectable=True,
                                           accent=True)
        self.toggle_btn.grid(row=2, column=0, sticky="ew", pady=(14, 0))

    def build_keyboard_page(self, frame):
        sub = self.page_body(frame, "Keyboard")
        pressing = lambda: not self.kb_hold.get()

        self.field_columns(sub, 2, [
            ("Key to press",
             lambda p: self.make_key_chooser(p, self.kb_key, "Keyboard clicker",
                                             is_keyboard_key, combos=True),
             None),
            ("Presses per second", lambda p: self.make_spin(p, self.kb_cps, 0.1, 100, 1), pressing),
            ("Start delay (s)", lambda p: self.make_spin(p, self.kb_delay, 0, 60, 1), None),
        ], columns=3)
        self.flow_label(ttk.Label(
            sub, text="Hold Ctrl, Shift or Alt for a combo. Esc, Tab and Super can't be used.",
            style="Muted.TLabel", wraplength=500, justify="left")).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))

        card = self.card_section(sub, 4, "Options")
        self.card_row(card, "Hold", self.kb_hold, subtitle="Hold the key down until you stop")

        card = self.card_section(sub, 6, "Stopping")
        self.card_row(card, "After a number of presses", self.kb_limit_on,
                      value=lambda p: self.make_spin(p, self.kb_limit, 1, 1000000, 10),
                      value_show=self.kb_limit_on.get, show=pressing)
        self.card_row(card, "After a set time (seconds)", self.kb_time_limit_on,
                      value=lambda p: self.make_spin(p, self.kb_time_limit, 1, 86400, 5),
                      value_show=self.kb_time_limit_on.get)

        self.kb_toggle_btn = self.make_button(frame, "", self.toggle, height=42, selectable=True,
                                              accent=True)
        self.kb_toggle_btn.grid(row=2, column=0, sticky="ew", pady=(14, 0))

    def build_recording_page(self, frame):
        """Profiles at the top, then recording and replay. The middle scrolls; the title and
        the Start button stay put."""
        sub = self.page_body(frame, "Profiles")

        # ---- Profiles (the page title already says so, so no heading here) ----
        ttk.Label(sub, text="Save the current recording as").grid(row=1, column=0, sticky="w",
                                                                 pady=(0, 4))
        save_row = ttk.Frame(sub)
        save_row.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        save_row.columnconfigure(0, weight=1)
        self.register(RoundedEntry(save_row, self.profile_name, "Profile name",
                                   on_enter=self.save_profile)).grid(row=0, column=0, sticky="ew")
        self.make_button(save_row, "Save", self.save_profile, height=FIELD_HEIGHT, width=90).grid(
            row=0, column=1, padx=(10, 0))

        ttk.Label(sub, text="Saved profiles").grid(row=3, column=0, sticky="w", pady=(0, 4))
        load_row = ttk.Frame(sub)
        load_row.grid(row=4, column=0, sticky="ew")
        load_row.columnconfigure(0, weight=1)
        self.profile_combo = self.make_combo(load_row, self.profile_choice, list_profiles())
        self.profile_combo.placeholder = "No profiles yet"
        self.profile_combo.grid(row=0, column=0, sticky="ew")
        self.make_button(load_row, "Load", self.load_profile, height=FIELD_HEIGHT, width=90).grid(
            row=0, column=1, padx=(10, 0))
        self.delete_btn = self.make_button(load_row, "Delete", self.delete_profile,
                                           height=FIELD_HEIGHT, width=90)
        self.delete_btn.grid(row=0, column=2, padx=(10, 0))

        card = self.card_section(sub, 5)
        self.card_row(card, "Hotkey",
                      subtitle="Plays this profile straight away, even when it isn't loaded. "
                               "Backspace removes it.",
                      value=lambda p: self.make_key_chooser(p, self.profile_hotkey, "Profile",
                                                            self.profile_hotkey_allowed))

        where = ttk.Frame(sub)
        where.grid(row=7, column=0, sticky="ew", pady=(6, 0))
        where.columnconfigure(0, weight=1)
        self.profiles_where = self.flow_label(
            ttk.Label(where, text="", style="Muted.TLabel", justify="left", wraplength=360),
            reserve=130, most=360)  # leaves room for the Open folder button
        self.profiles_where.grid(row=0, column=0, sticky="w")
        self.make_button(where, "Open folder", lambda: self.open_folder(PROFILES_DIR),
                         height=FIELD_HEIGHT, width=110).grid(row=0, column=1, padx=(10, 0))

        # ---- Recording ----
        ttk.Label(sub, text="Record and replay", font=self.font_section).grid(
            row=8, column=0, sticky="w", pady=(24, 8))
        rec_row = ttk.Frame(sub)
        rec_row.grid(row=9, column=0, sticky="ew")
        rec_row.columnconfigure(0, weight=1)
        self.record_btn = self.make_button(rec_row, "Record", self.toggle_recording,
                                           height=FIELD_HEIGHT, selectable=True, accent=True)
        self.record_btn.grid(row=0, column=0, sticky="ew")
        self.make_button(rec_row, "Edit", self.edit_recording, height=FIELD_HEIGHT,
                         width=80).grid(row=0, column=1, padx=(10, 0))
        self.make_button(rec_row, "Clear", self.clear_recording, height=FIELD_HEIGHT,
                         width=80).grid(row=0, column=2, padx=(10, 0))
        self.recording_info = self.flow_label(ttk.Label(sub, text="", style="Muted.TLabel",
                                                        wraplength=500, justify="left"))
        self.recording_info.grid(row=10, column=0, sticky="w", pady=(4, 0))

        card = self.card_section(sub, 11, "While recording")
        self.card_row(card, "Keys only", self.record_keys_only,
                      subtitle="Only record the keyboard")
        self.card_row(card, "Record mouse movement", self.record_moves,
                      subtitle="When off, clicks are kept, but not the movement in between",
                      show=lambda: not self.record_keys_only.get())

        card = self.card_section(sub, 13, "Playing it back")
        self.card_row(card, "Loop", self.replay_loop, subtitle="Keep playing until you stop it")
        self.card_row(card, "Stop after a number of plays", self.replay_limit_on,
                      value=lambda p: self.make_spin(p, self.replay_limit, 1, 100000, 1),
                      value_show=self.replay_limit_on.get, show=self.replay_loop.get)

        self.replay_btn = self.make_button(frame, "", self.toggle, height=42, selectable=True,
                                           accent=True)
        self.replay_btn.grid(row=2, column=0, sticky="ew", pady=(14, 0))

    def build_mini_view(self, frame):
        """Mini mode: a small window with just the mouse clicker's main settings, Hold,
        a switch back to the full app, and the Start button. Short labels keep it small."""
        # everything sits on a rounded card, like the badge
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.mini_card = self.register(Card(frame), surface="edge")
        self.mini_card.grid(row=0, column=0, sticky="nsew")
        self.default_surface = "card"  # the boxes and switches use the card's colours
        try:
            self.build_mini_card(ttk.Frame(self.mini_card.body, style="Card.TFrame",
                                           padding=(MINI_PAD, MINI_PAD + 2)))
        finally:
            self.default_surface = "page"

    def build_mini_card(self, frame):
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        clicking = lambda: not self.hold.get()
        self.field_columns(frame, 0, [
            ("CPS", lambda p: self.make_spin(p, self.cps, 0.1, 100, 1),
             lambda: clicking() and not self.click_delay_on.get()),
            ("Wait (s)", lambda p: self.make_spin(p, self.click_delay, 0.1, 3600, 0.5),
             lambda: clicking() and self.click_delay_on.get()),
            ("Button", lambda p: self.make_combo(p, self.button, list(BUTTONS), width=70), None),
            ("Type", lambda p: self.make_combo(p, self.click_type, list(CLICK_TYPES), width=70),
             clicking),
        ], columns=3, narrowest=64, label_style="CardCaption.TLabel", gap=MINI_GAP,
            frame_style="Card.TFrame")
        # the two switches side by side on one line
        switches = ttk.Frame(frame, style="Card.TFrame")
        switches.grid(row=1, column=0, sticky="ew")
        switches.columnconfigure(1, weight=1)
        self.make_switch(switches, "Hold", self.hold).grid(row=0, column=0, sticky="w")
        self.make_switch(switches, "Mini", self.mini).grid(row=0, column=2, sticky="e")
        frame.rowconfigure(2, weight=1)  # any spare height goes above the button
        self.mini_toggle_btn = self.make_button(frame, "", self.toggle, height=30,
                                                selectable=True, accent=True)
        self.mini_toggle_btn.grid(row=3, column=0, sticky="sew", pady=(6, 0))
        self.make_mini_draggable(self.mini_frame)

    def make_mini_draggable(self, widget):
        """Mini mode has no title bar, so drag the panel itself (any empty part of it, or
        its labels) to move it. Boxes, switches and buttons still work as normal."""
        if isinstance(widget, (ttk.Frame, tk.Frame, ttk.Label, Card)):
            widget.bind("<ButtonPress-1>", self.mini_drag_start, add="+")
            widget.bind("<B1-Motion>", self.mini_drag, add="+")
            widget.bind("<ButtonRelease-1>", self.mini_drag_end, add="+")
        for child in widget.winfo_children():
            self.make_mini_draggable(child)

    def mini_drag_start(self, event):
        self.mini_grab = (event.x_root - self.root.winfo_rootx(),
                          event.y_root - self.root.winfo_rooty())

    def mini_drag(self, event):
        if self.mini_shown and getattr(self, "mini_grab", None):
            dx, dy = self.mini_grab
            self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def mini_drag_end(self, event):
        if self.mini_shown and getattr(self, "mini_grab", None):
            dx, dy = self.mini_grab
            self.mini_grab = None
            self.mini_position = [event.x_root - dx, event.y_root - dy]
            self.save_settings()

    def shape_mini(self, width, height):
        if self.mini_shown:
            round_window(self.root, Card.RADIUS + MINI_MARGIN, width, height)
        self.set_alpha(1.0)

    def set_alpha(self, value):
        try:
            self.root.attributes("-alpha", value)
        except tk.TclError:
            pass

    def mini_width(self):
        """Just wide enough for three boxes that fit the longest choice (like "Double"):
        the text, plus the box's edges and its arrow (see RoundedCombo.redraw)."""
        font = tkfont.nametofont("TkTextFont")
        box = max(font.measure(t) for t in list(CLICK_TYPES) + list(BUTTONS)) + 32
        edges = 2 * (MINI_MARGIN + Card.INSET_X + MINI_PAD)  # the window's, card's and panel's
        return edges + 3 * box + 2 * MINI_GAP

    def apply_mini(self, save=True):
        """Switch between mini mode and the full app (the Mini mode switch)."""
        on = bool(self.mini.get())
        if on == self.mini_shown:
            return
        root = self.root
        if on:
            self.go_to("clicker")  # the start key runs the mouse clicker
            self.full_size = root.geometry().split("+")[0]
            if root.winfo_ismapped() and save:
                # where the window's contents are now (below its title bar), to stay put
                x, y = root.winfo_rootx(), root.winfo_rooty()
            elif min(self.mini_position) >= 0:  # starting up: where it was last time
                x, y = self.mini_position
            else:
                x, y = 100, 100
            self.mini_position = [x, y]
            self.mini_shown = True
            for widget in (self.sidebar, self.handle, self.content):
                widget.grid_remove()
            for i in range(3):
                root.columnconfigure(i, weight=0, minsize=0)
                root.rowconfigure(i, weight=0, minsize=0)
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)
            self.mini_frame.grid(row=0, column=0, sticky="nsew")
            root.update_idletasks()
            card = self.mini_card  # (it may not have been shown yet, so size it here)
            card.configure(height=card.body.winfo_reqheight() + 2 * Card.INSET_Y)
            root.update_idletasks()
            height = self.mini_frame.winfo_reqheight()
            width = self.mini_width()
            root.minsize(width, height)
            root.resizable(False, False)  # a fixed little panel, like the badge
            # no title bar, and the window itself cut round (like the badge). It's see-through
            # until it has been cut, so it never shows square corners.
            self.set_alpha(0.0)
            set_title_bar(root, False)
            self.apply_on_top()  # always on top while it's mini
            size = f"{width}x{height}+{max(0, x)}+{max(0, y)}"
            # (the window manager takes a moment to drop the title bar: size it after that)
            root.after(40, lambda: (root.geometry(size),
                                    root.after(60, lambda: self.shape_mini(width, height))))
        else:
            self.mini_shown = False
            x, y = root.winfo_rootx(), root.winfo_rooty()
            round_window(root, None)    # the window is square again
            set_title_bar(root, True)   # and gets its title bar back
            root.withdraw()             # (shown again below, so the title bar appears)
            root.resizable(True, True)
            self.mini_frame.grid_remove()
            self.layout_sidebar()  # puts the menu and pages back (and the window's minimum)
            root.deiconify()
            size = f"{self.full_size or WINDOW_SIZE}+{x}+{y}"
            # once it's back on screen: its size, and the "Keep window on top" setting again
            # (hiding the window cleared it)
            root.after(40, lambda: (root.geometry(size), self.apply_on_top()))
        self.repaint_soon()
        if save:
            self.save_settings()

    def build_settings_page(self, frame):
        sub = self.page_body(frame, "Settings")

        self.field_columns(sub, 0, [
            ("Start/stop key",
             lambda p: self.make_key_chooser(p, self.hotkey, "Start/stop"), None),
            ("Set location key",
             lambda p: self.make_key_chooser(p, self.location_key, "Set location"), None),
            ("Record key",
             lambda p: self.make_key_chooser(p, self.record_key, "Record"), None),
        ], columns=3)
        self.flow_label(ttk.Label(
            sub, text="Click a box, then press a key or mouse button. Esc cancels.\n"
                      "In the app, Ctrl+1 to Ctrl+4 switch pages and Ctrl+Tab goes to the "
                      "next one.",
            style="Muted.TLabel", wraplength=500, justify="left")).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))

        card = self.card_section(sub, 2, "Appearance")
        self.card_row(card, "Accent colour",
                      value=lambda p: self.make_swatches(p, self.accent, ACCENTS))
        self.card_row(card, "Dark mode", self.dark)
        self.card_row(card, "Text size",
                      value=lambda p: self.make_combo(p, self.text_size, list(TEXT_SIZES)))
        self.card_row(card, "Menu position",
                      value=lambda p: self.make_combo(p, self.sidebar_side, list(SIDEBAR_SIDES)))
        self.card_row(card, "Mini mode", self.mini,
                      subtitle="A small window with just the mouse clicker")

        card = self.card_section(sub, 4, "Badge")
        self.card_row(card, "Show",
                      subtitle="A small card on the screen showing what's running",
                      value=lambda p: self.make_combo(p, self.badge_show, list(BADGE_SHOW),
                                                      width=KEY_FIELD_WIDTH))
        self.card_row(card, "Position",
                      subtitle="Which corner of the screen it sits in",
                      value=lambda p: self.make_combo(p, self.badge_corner, list(BADGE_CORNERS),
                                                      width=KEY_FIELD_WIDTH),
                      show=lambda: self.badge_show.get() != "Off")

        card = self.card_section(sub, 6, "Behaviour")
        self.card_row(card, "Keep window on top", self.on_top)
        self.card_row(card, "Auto stop", self.auto_stop,
                      subtitle="Stop when you move or click the mouse yourself")
        self.card_row(card, "Sound when finished", self.finish_sound,
                      subtitle="When a limit is reached or a replay ends")

        card = self.card_section(sub, 8, "Storage")
        _, self.settings_where, _ = self.card_row(
            card, "Settings folder", subtitle="",
            value=lambda p: self.button_group(p, [
                ("Open", lambda: self.open_folder(SETTINGS_PATH.parent)),
                ("Move", lambda: self.move_folder("settings"))]))
        _, self.profiles_where_card, _ = self.card_row(
            card, "Profiles folder", subtitle="",
            value=lambda p: self.button_group(p, [
                ("Open", lambda: self.open_folder(PROFILES_DIR)),
                ("Move", lambda: self.move_folder("profiles"))]))

        self.make_button(frame, "Reset to defaults", self.reset_defaults, height=36).grid(
            row=2, column=0, sticky="ew", pady=(14, 0))

    def show_optional_rows(self):
        """Show or hide everything that depends on a toggle (see card_row, field_columns)."""
        for widgets, should_show in self.optional_rows:
            visible = should_show()
            for widget in widgets:
                if visible:
                    widget.grid()
                else:
                    widget.grid_remove()

        for group in self.column_groups:
            self.layout_fields(group)

        self.layout_cards()
        self.repaint_soon()

    def repaint_soon(self):
        """Redraw the window once things have finished moving (see repaint)."""
        for job in self.repaint_jobs:
            self.root.after_cancel(job)
        # once the layout has settled, and again a moment later in case it was still moving
        self.repaint_jobs = [self.root.after(delay, lambda: repaint(self.root))
                             for delay in (50, 250)]

    def refresh_location(self):
        key = input_name(self.location_key.get())
        verb = "hold" if self.hold.get() else "click"
        self.location_title.config(text=f"{verb.capitalize()} at a set location")
        spots = self.locations
        if not spots:
            text = f"Not set yet. Press Pick, or move your mouse there and press {key}."
        elif self.multi_location.get() and not self.hold.get():
            shown = " → ".join(f"{x},{y}" for x, y in spots[:3]) + (" → …" if len(spots) > 3 else "")
            text = (f"{len(spots)} {'spot' if len(spots) == 1 else 'spots'}: {shown}. "
                    f"Press Pick or {key} to add another.")
        else:
            x, y = spots[0]
            text = f"Set to {x}, {y}. Press Pick or {key} to change it."
        self.location_hint.config(text=text)

    # ---- the menu: on any side, and resizable when it's on the left or right ----
    def menu_is_vertical(self):
        return self.sidebar_side.get() in ("Left", "Right")

    def layout_sidebar(self):
        """Put the menu on the chosen side and arrange its contents to suit."""
        if self.mini_shown:
            return  # no menu in mini mode (it's laid out again when mini mode ends)
        side = self.sidebar_side.get()
        vertical = self.menu_is_vertical()
        root, bar = self.root, self.sidebar
        for i in range(3):
            root.columnconfigure(i, weight=0, minsize=0)
            root.rowconfigure(i, weight=0, minsize=0)
        for i in range(12):
            bar.columnconfigure(i, weight=0)
            bar.rowconfigure(i, weight=0)
        self.handle.set_vertical(vertical)

        order = [bar, self.handle, self.content]
        if side in ("Right", "Bottom"):
            order.reverse()
        for i, widget in enumerate(order):
            sticky = ("ns" if vertical else "ew") if widget is self.handle else "nsew"
            if vertical:
                widget.grid(row=0, column=i, sticky=sticky)
            else:
                widget.grid(row=i, column=0, sticky=sticky)
        page_at, self.sidebar_index = order.index(self.content), order.index(bar)
        if vertical:
            root.columnconfigure(page_at, weight=1)
            root.rowconfigure(0, weight=1)
        else:
            root.rowconfigure(page_at, weight=1)
            root.columnconfigure(0, weight=1)

        # the page buttons in their card: down the card (side menu) or across it (top/bottom)
        nav, body = list(self.nav_buttons.values()), self.nav_card.body
        for i in range(2 * len(nav)):
            body.columnconfigure(i, weight=0)
            body.rowconfigure(i, weight=0)
        self.nav_card.set_fit(not vertical)
        for i, btn in enumerate(nav):
            line = self.nav_lines[i - 1] if i else None
            if vertical:
                if line is not None:
                    line.configure(height=1, width=1)
                    line.grid(row=2 * i - 1, column=0, sticky="ew", padx=6, pady=0)
                btn.grid(row=2 * i, column=0, sticky="ew", padx=0, pady=1)
            else:
                if line is not None:
                    line.configure(width=1, height=18)
                    line.grid(row=0, column=2 * i - 1, sticky="", padx=0, pady=0)
                btn.grid(row=0, column=2 * i, sticky="", padx=1, pady=0)
        if vertical:
            body.columnconfigure(0, weight=1)  # buttons stretch with the menu

        if vertical:  # a tall menu: logo, the button card, status at the bottom
            bar.configure(padding=(8, 12))
            bar.columnconfigure(0, weight=1)
            self.logo.grid(row=0, column=0, rowspan=1, sticky="w", padx=0, pady=(0, 14))
            # the card wraps the buttons; the buttons grow with the window so the card
            # reaches about halfway down the menu (see size_nav_buttons)
            self.nav_card.grid(row=1, column=0, rowspan=1, sticky="ew", padx=0, pady=0)
            bar.rowconfigure(2, weight=1)  # pushes the status to the bottom
            self.status_row.grid(row=3, column=0, sticky="ew", padx=0, pady=(10, 2))
            self.esc_hint.grid(row=4, column=0, sticky="w", padx=0, pady=(4, 0))
            self.set_sidebar_width(self.sidebar_width)
        else:  # a slim bar: logo, the button card in a row, status at the far end
            bar.configure(padding=(12, 8))
            self.logo.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 16), pady=0)
            self.nav_card.grid(row=0, column=1, rowspan=2, sticky="", padx=0, pady=0)
            bar.columnconfigure(2, weight=1)  # pushes the status to the far end
            # status and Esc hint stay together in the middle, however tall the bar is
            bar.rowconfigure(0, weight=1)
            bar.rowconfigure(1, weight=1)
            self.status_row.grid(row=0, column=3, sticky="se", padx=(12, 0), pady=0)
            self.esc_hint.grid(row=1, column=3, sticky="ne", padx=(12, 0), pady=0)
            self.status.configure(wraplength=0)
            self.esc_hint.configure(wraplength=0)
            self.set_bar_height(self.bar_height)
        self.size_nav_buttons()

    # ---- text size, finish sound, page shortcuts ----
    def apply_text_size(self):
        """Make all the text Small, Normal or Large (straight away, no restart)."""
        base = TEXT_SIZES.get(self.text_size.get(), FONT_SIZE)
        for name in NAMED_FONTS:
            try:
                tkfont.nametofont(name).configure(size=base)
            except tk.TclError:
                pass
        for font, extra in ((self.font_title, 5), (self.font_brand, 1), (self.font_section, 1),
                            (self.font_caption, -1), (self.font_nav, 0)):
            font.configure(size=base + extra)
        self.logo.refit()
        if self.badge is not None:
            self.badge.title_font.configure(size=base)
            self.badge.detail_font.configure(size=max(base - 1, 7))
        for widget in self.round_widgets:  # redraw text drawn on custom widgets
            if hasattr(widget, "redraw"):
                widget.redraw()
        self.root.update_idletasks()
        self.size_nav_buttons()
        self.refresh_running()

    def play_finish_sound(self):
        """A short "done" sound when a run finishes by itself (not when you stop it)."""
        if not self.finish_sound.get():
            return
        attempts = (["canberra-gtk-play", "-i", "complete", "-d", "Auto Clicker"],
                    ["pw-play", "/usr/share/sounds/freedesktop/stereo/complete.oga"])
        for command in attempts:
            if shutil.which(command[0]):
                try:
                    subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
                    return
                except OSError:
                    pass
        self.root.bell()

    def bind_page_shortcuts(self):
        """Ctrl+1 to Ctrl+4 go to a page; Ctrl+Tab / Ctrl+Shift+Tab go to the next / previous."""
        pages = list(self.nav_buttons)
        # bound on the window itself, so they're handled before Tk's own Tab handling
        for number, name in enumerate(pages, start=1):
            self.root.bind(f"<Control-Key-{number}>",
                           lambda e, n=name: (self.go_to(n), "break")[1])

        def step(direction):
            i = pages.index(self.page.get()) if self.page.get() in pages else 0
            self.go_to(pages[(i + direction) % len(pages)])
            return "break"
        self.root.bind("<Control-Tab>", lambda e: step(1))
        for sequence in ("<Control-Shift-Tab>", "<Control-ISO_Left_Tab>"):
            try:
                self.root.bind(sequence, lambda e: step(-1))
            except tk.TclError:
                pass  # that key name doesn't exist on this system

    def size_nav_buttons(self, _event=None):
        """Side menu: make the buttons tall enough that their card reaches about halfway
        down the menu (they grow and shrink with the window).
        Top/bottom bar: as tall as the bar allows (it can be dragged taller)."""
        if self.menu_is_vertical():
            room = self.sidebar.winfo_height() * MENU_FILL - self.logo.winfo_reqheight() - 14
            spare = 2 * Card.INSET_Y + (len(self.nav_buttons) - 1) * 1 + len(self.nav_buttons) * 2
            height = int(max(34, min(90, (room - spare) / len(self.nav_buttons))))
        else:
            # the bar's padding (8 above and below) and the card's own edges
            height = int(max(34, min(90, self.bar_height - 16 - 2 * Card.INSET_Y)))
        changed = False
        for btn in self.nav_buttons.values():
            if int(btn.cget("height")) != height:
                btn.configure(height=height)
                changed = True
        if changed or (self.nav_card.fit and self.nav_card.winfo_width() <= 1):
            self.nav_card.fit_to_body()

    def set_sidebar_width(self, width):
        width = int(min(max(width, SIDEBAR_MIN), SIDEBAR_MAX))
        self.sidebar_width = width
        if not self.menu_is_vertical() or self.mini_shown:
            return  # a top/bottom menu just fits its contents
        self.root.columnconfigure(self.sidebar_index, minsize=width)
        self.status.configure(wraplength=width - 40)  # text wraps to fit the sidebar
        self.esc_hint.configure(wraplength=width - 24)
        # keep room for the page: if the window is too narrow, it grows to fit
        self.root.minsize(width + SidebarHandle.WIDTH + PAGE_MIN_WIDTH, MIN_SIZE[1])

    def set_bar_height(self, height):
        """How tall a top/bottom menu is (the page buttons grow with it)."""
        height = int(min(max(height, BAR_MIN), BAR_MAX))
        self.bar_height = height
        if self.menu_is_vertical() or self.mini_shown:
            return
        self.root.rowconfigure(self.sidebar_index, minsize=height)
        self.size_nav_buttons()
        # the bar takes some height, so the window keeps room for the page below it
        self.sidebar.update_idletasks()
        self.root.minsize(max(PAGE_MIN_WIDTH, self.sidebar.winfo_reqwidth()),
                          MIN_SIZE[1] + BAR_EXTRA_HEIGHT + height - BAR_MIN)

    def drag_sidebar(self, x_root, y_root):
        """The line between the menu and the page is being dragged to here."""
        root = self.root
        side = self.sidebar_side.get()
        if side == "Right":  # dragging left makes a right-hand menu wider
            self.set_sidebar_width(root.winfo_rootx() + root.winfo_width() - x_root)
        elif side == "Left":
            self.set_sidebar_width(x_root - root.winfo_rootx())
        elif side == "Bottom":  # dragging up makes a bottom menu taller
            self.set_bar_height(root.winfo_rooty() + root.winfo_height() - y_root)
        else:
            self.set_bar_height(y_root - root.winfo_rooty())

    def reset_sidebar(self):
        if self.menu_is_vertical():
            self.set_sidebar_width(DEFAULTS["sidebar_width"])
        else:
            self.set_bar_height(DEFAULTS["bar_height"])
        self.save_settings()

    def go_to(self, name):
        if self.mini_shown:
            return  # mini mode only has the mouse clicker
        if name == "recording":
            self.refresh_profile_list()  # picks up .txt files added or renamed by hand
        self.page.set(name)
        self.show_page()
        if name in PAGE_MODES and PAGE_MODES[name] != self.active_mode:
            # the start/stop key now runs this page's clicker (something already running
            # carries on until you stop it)
            self.active_mode = PAGE_MODES[name]
            self.refresh_button()
            self.save_settings()

    def show_page(self):
        current = self.page.get()
        self.pages[current].tkraise()
        for name, btn in self.nav_buttons.items():
            btn.set_selected(name == current)

    def mode(self):
        """Which clicker the start/stop key runs: the one for the page you're on
        ('mouse', 'keyboard' or 'replay'), or the last one you used if you're on Settings."""
        return self.active_mode

    def refresh_button(self):
        """Update the Start/Stop and Record buttons. Only the active clicker shows a Start button."""
        key = input_name(self.hotkey.get())
        text = f"{'Stop' if self.armed else 'Start'} ({key})"
        running_mode = self.settings.get("mode") if self.armed else None
        for btn, mode in ((self.toggle_btn, "mouse"), (self.mini_toggle_btn, "mouse"),
                          (self.kb_toggle_btn, "keyboard"),
                          (self.replay_btn, "replay")):
            btn.set_text(text)
            btn.set_selected(running_mode == mode)  # accent colour on the one that's running
        record_key = input_name(self.record_key.get())
        self.record_btn.set_text(f"Stop recording ({record_key})" if self.recording_active
                                 else f"Record ({record_key})")
        self.record_btn.set_selected(self.recording_active)
        self.refresh_running()

    def running_state(self):
        """(running?, title, details) for the status light and the floating card,
        e.g. (True, "Clicking", "10 CPS · Left button · F6 to stop")."""
        if self.recording_active:
            extra = " · keys only" if self.record_keys else ""
            return True, "Recording", f"{input_name(self.record_key.get())} to stop{extra}"
        if not self.armed:
            what = {"mouse": "mouse clicker", "keyboard": "keyboard clicker",
                    "replay": "recording"}[self.active_mode]
            return False, "Ready", f"{input_name(self.hotkey.get())} starts the {what}"
        s = self.settings
        title = s.get("title", "Running")
        if not self.running.is_set():
            title = f"Starting in {s['delay']:g}s"
        return True, title, s.get("details", "")

    def describe_run(self, label=None):
        """The floating card's title and details for what's about to run."""
        s = self.settings
        stop_key = input_name(self.hotkey.get())
        if label:  # started with a profile's hotkey: that key stops it too
            code = next((c for c, n in self.profile_hotkeys.items() if n == label), None)
            stop_key = input_name(code) if code else stop_key
        if s["mode"] == "replay":
            plays = {0: "on a loop", 1: "once"}.get(s["plays"], f"{s['plays']} times")
            # say what's playing: the profile, or the recording that isn't saved yet
            title = f"Playing {label or self.recording_name or 'unsaved recording'}"
            n = len(s["actions"])
            parts = [f"{n} {'action' if n == 1 else 'actions'}", plays]
        elif s["mode"] == "keyboard":
            key = input_name(self.kb_key.get())
            title = f"Holding {key}" if s["hold"] else f"Pressing {key}"
            parts = [] if s["hold"] else [f"{float(self.kb_cps.get()):g} per second"]
        else:
            button = f"{self.button.get()} button"
            spots = len(s["locations"] or [])
            if s["hold"]:
                title, parts = "Holding", [button]
            else:
                title = "Clicking"
                rate = (f"every {float(self.click_delay.get()):g}s" if self.click_delay_on.get()
                        else f"{float(self.cps.get()):g} CPS")
                parts = [rate, button]
                if s["count"] > 1:
                    parts.append(f"{self.click_type.get().lower()} clicks")
            if spots > 1:
                parts.append(f"{spots} spots")
            elif spots == 1:
                parts.append("set spot")
        s["title"] = title
        s["details"] = " · ".join(parts + [f"{stop_key} to stop"])

    def progress_text(self):
        """Live progress for the floating card, e.g. "23 of 100 clicks · 0:42 left"."""
        def clock(seconds):
            seconds = int(math.ceil(seconds))
            h, rest = divmod(seconds, 3600)
            return f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h else f"{rest // 60}:{rest % 60:02d}"

        if self.recording_active:
            return f"{clock(int(time.monotonic() - self.record_t0))} recorded"  # rounds down
        if not self.armed:
            return ""
        s, parts = self.settings, []
        if s.get("limit"):
            parts.append(f"{self.clicks} of {s['limit']} {s['unit'][1]}")
        if s.get("time_limit"):
            elapsed = time.monotonic() - self.started_at if self.running.is_set() else 0
            parts.append(f"{clock(max(0.0, s['time_limit'] - elapsed))} left")
        if s.get("mode") == "replay" and s.get("plays", 0) > 1:
            parts.append(f"play {min(self.plays_done + 1, s['plays'])} of {s['plays']}")
        return " · ".join(parts)

    def refresh_running(self):
        if not hasattr(self, "status_dot"):
            return
        on, title, details = self.running_state()
        self.status_dot.set_on(on)
        when = self.badge_show.get()
        if when != "Off":
            if self.badge is None:
                self.badge = FloatingBadge(self.root, self.show_window)
            near = (self.root.winfo_rootx() + self.root.winfo_width() // 2,
                    self.root.winfo_rooty() + self.root.winfo_height() // 2)
            show = when == "Always" or on
            self.badge.update_state(show, on, title, details, self.progress_text(),
                                    self.palette, near, self.badge_corner.get())
        elif self.badge is not None:
            self.badge.destroy()
            self.badge = None

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def apply_on_top(self):
        # mini mode always floats above other windows; otherwise it's the setting
        self.root.attributes("-topmost", bool(self.on_top.get()) or self.mini_shown)

    # ---------------- Theme ----------------
    def apply_palette(self, p: dict):
        """Apply one set of colours to every widget style and custom widget."""
        self.palette = p
        s = self.style
        self.root.configure(bg=p["bg"])

        s.configure(".", background=p["bg"], foreground=p["fg"], fieldbackground=p["field"],
                    bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"],
                    troughcolor=p["field"], insertcolor=p["fg"],
                    selectbackground=p["select"], selectforeground=p["fg"])
        s.configure("TSeparator", background=p["border"])
        s.configure("Thin.Vertical.TScrollbar", troughcolor=p["bg"], background=p["border"],
                    bordercolor=p["bg"], lightcolor=p["border"], darkcolor=p["border"],
                    arrowsize=8, gripcount=0)
        s.map("Thin.Vertical.TScrollbar", background=[("active", p["muted"])],
              lightcolor=[("active", p["muted"])], darkcolor=[("active", p["muted"])])
        s.configure("Muted.TLabel", foreground=p["muted"])
        s.configure("Caption.TLabel", foreground=p["muted"], font=self.font_caption)
        s.configure("Card.TLabel", background=p["card"], foreground=p["fg"])
        s.configure("CardMuted.TLabel", background=p["card"], foreground=p["muted"])
        s.configure("Card.TFrame", background=p["card"])
        s.configure("Edge.TFrame", background=p["border"])
        s.configure("CardCaption.TLabel", background=p["card"], foreground=p["muted"],
                    font=self.font_caption)
        for frame in self.card_frames:
            frame.configure(bg=p["card"])
        for line in self.dividers:
            line.configure(bg=p["divider"])

        card_palette = self.surface_palette("card")
        for widget in self.round_widgets:
            widget.set_palette(card_palette if widget.surface == "card" else p)
        if getattr(self, "badge", None) is not None:
            self.refresh_running()

    def animate_theme(self):
        """Fade from the current colours to the new light/dark + accent palette."""
        accent = self.accent.get()
        if not is_hex_color(accent):
            accent = DEFAULTS["accent"]
        target = build_palette(bool(self.dark.get()), accent)
        if self.theme_job is not None:
            self.root.after_cancel(self.theme_job)
            self.theme_job = None
        start = dict(self.palette)
        began = time.monotonic()

        def step():
            # timed by the clock, so the fade always takes THEME_MS even if frames are slow
            t = min(1.0, (time.monotonic() - began) * 1000 / THEME_MS)
            eased = t * t * (3 - 2 * t)  # smoothstep: gentle start and end
            # Text doesn't fade: fading it along with the background would turn both the
            # same grey halfway and the words would vanish. It swaps at the halfway point
            # instead, where the background is mid-grey and either text colour reads fine.
            self.apply_palette({
                k: (target[k] if eased >= 0.5 else start[k]) if k in TEXT_COLORS
                else mix_color(start[k], target[k], eased)
                for k in target})
            if t < 1:
                self.theme_job = self.root.after(max(1, THEME_MS // THEME_STEPS), step)
            else:
                self.theme_job = None

        step()

    # ---------------- Choosing keys ----------------
    def start_capture(self, chooser):
        """Called when a key box is clicked: wait for the next key / mouse button."""
        if chooser.purpose == "Profile" and not profile_path(self.profile_choice.get()).exists():
            self.status.config(text="Pick a profile first")
            return
        if self.capturing is chooser:  # clicked the same box again: cancel
            self.stop_capture()
            return
        self.stop_capture()
        self.capturing = chooser
        self.capture_mods = []
        chooser.set_listening(True)

    def stop_capture(self):
        if self.capturing is not None:
            self.capturing.set_listening(False)
            self.capturing = None
        self.capture_mods = []

    def finish_capture(self, code):
        """Give the waiting key box its new key. Returns True if the input was used up."""
        chooser = self.capturing
        if code == "key:esc":
            self.stop_capture()
            return True
        if code == "mouse:left":
            return False  # left clicks just use the app while a box is waiting
        if chooser.purpose == "Profile" and code in ("key:backspace", "key:delete"):
            chooser.var.set("")  # remove the profile's hotkey
            self.stop_capture()
            return True
        if chooser.combos and code in MODIFIER_OF:
            # a modifier on its own: wait for the main key (or its release, see capture_release)
            name = MODIFIER_OF[code]
            if name not in self.capture_mods:
                self.capture_mods.append(name)
            chooser.flash(self.mods_preview(), seconds=None)
            return True
        if chooser.combos and self.capture_mods:
            code = make_combo(self.capture_mods, code)
        self.capture_mods = []
        if not chooser.allowed(code):
            in_use = code in (self.hotkey.get(), self.location_key.get(), self.record_key.get())
            chooser.flash("Already in use" if in_use else "Can't use that")
            return True
        if chooser.purpose != "Profile" and self.profile_hotkeys.get(code):
            chooser.flash("Used by a profile")
            return True
        self.assign_key(chooser, code)
        return True

    def capture_release(self, code):
        """A key was let go while choosing a combo: a lone modifier becomes the key itself."""
        chooser = self.capturing
        if chooser is None or not chooser.combos or code not in MODIFIER_OF:
            return
        name = MODIFIER_OF[code]
        if self.capture_mods == [name]:
            self.capture_mods = []
            self.assign_key(chooser, code)  # e.g. just Shift
        elif name in self.capture_mods:
            self.capture_mods.remove(name)
            chooser.flash(self.mods_preview(), seconds=None)

    def mods_preview(self):
        """e.g. 'Ctrl+Shift+...' while modifiers are held in a combo key box."""
        order = [m.capitalize() for m in MODIFIERS if m in self.capture_mods]
        return "+".join(order) + "+..."

    def assign_key(self, chooser, code):
        old = chooser.var.get()
        # If another box already uses this key, swap so the two never clash
        for other in self.key_choosers:
            if other is not chooser and other.var.get() == code:
                if not other.allowed(old):
                    chooser.flash("Already in use")  # by `other`, and can't swap
                    return
                other.var.set(old)
        chooser.var.set(code)
        self.stop_capture()
        self.save_settings()

    # ---------------- Settings ----------------
    def collect_settings(self):
        """Read the current UI values. Returns None if any field is invalid."""
        try:
            values = {name: var.get() for name, var in self.profile_vars.items()}
            values.update({
                "locations": self.locations or None,
                "recording": self.recording,
                "hotkey": self.hotkey.get(),
                "location_key": self.location_key.get(),
                "record_key": self.record_key.get(),
                "auto_stop": bool(self.auto_stop.get()),
                "always_on_top": bool(self.on_top.get()),
                "mini_mode": bool(self.mini.get()),
                "mini_position": list(self.mini_position),
                "sidebar_side": self.sidebar_side.get(),
                "active_mode": self.active_mode,
                "badge_show": self.badge_show.get(),
                "badge_corner": self.badge_corner.get(),
                "finish_sound": bool(self.finish_sound.get()),
                "text_size": self.text_size.get(),
                "sidebar_width": self.sidebar_width,
                "bar_height": self.bar_height,
                "dark_mode": bool(self.dark.get()),
                "accent": self.accent.get(),
            })
            for name in ("limit", "kb_limit"):
                values[name] = max(1, int(values[name]))
            return values
        except (tk.TclError, ValueError):
            return None

    def save_settings(self):
        current = self.collect_settings()
        if current is not None:
            current.pop("recording")  # recordings live in their own files
            write_settings(current)

    def save_current_recording(self):
        """Only called when the recording changes, so saving settings stays instant."""
        write_recording(current_recording_path(), self.recording, self.recording_name)

    def reset_defaults(self):
        self.stop_capture()
        if self.armed:
            self.stop()
        variables = dict(self.profile_vars)
        variables.update({
            "hotkey": self.hotkey, "location_key": self.location_key,
            "record_key": self.record_key,
            "auto_stop": self.auto_stop, "always_on_top": self.on_top, "mini_mode": self.mini,
            "badge_show": self.badge_show, "badge_corner": self.badge_corner,
            "sidebar_side": self.sidebar_side,
            "finish_sound": self.finish_sound, "text_size": self.text_size,
            "dark_mode": self.dark, "accent": self.accent,
        })
        for name, var in variables.items():
            var.set(DEFAULTS[name])
        self.status.config(text="Settings reset")

    # ---------------- Profiles ----------------
    def refresh_profile_list(self, select=None):
        names = list_profiles()
        self.profile_combo.set_values(names)
        # which key plays which profile (read from the top of each profile file)
        self.profile_hotkeys = {}
        for name in names:
            code = read_profile_hotkey(name)
            if code and code not in self.profile_hotkeys:
                self.profile_hotkeys[code] = name
        if select is not None:
            self.profile_choice.set(select)
        elif self.profile_choice.get() not in names:
            self.profile_choice.set(names[0] if names else "")
        self.show_profile_hotkey()
        self.refresh_storage_labels()

    def show_profile_hotkey(self):
        """Show the chosen profile's hotkey in its key box (without saving anything)."""
        name = self.profile_choice.get()
        code = next((c for c, n in self.profile_hotkeys.items() if n == name), "")
        self.hotkey_var_busy = True
        try:
            self.profile_hotkey.set(code)
        finally:
            self.hotkey_var_busy = False

    def profile_hotkey_allowed(self, code):
        return is_valid_input(code) and code not in (
            self.hotkey.get(), self.location_key.get(), self.record_key.get())

    def on_profile_hotkey_set(self):
        """The profile hotkey box was changed: save it in the profile's file."""
        if self.hotkey_var_busy:
            return
        name, code = self.profile_choice.get(), self.profile_hotkey.get()
        if not profile_path(name).exists():
            return
        # one key plays one profile: take it off any other profile that had it
        other = self.profile_hotkeys.get(code)
        if code and other and other != name:
            ok, recording = read_profile(other)
            if ok:
                write_profile(other, recording, None)
        ok, recording = read_profile(name)
        if not ok:
            self.status.config(text=f"Couldn't read {name}")
            return
        write_profile(name, recording, code or None)
        self.refresh_profile_list(select=name)
        self.status.config(text=f"{input_name(code)} plays {name}" if code
                           else f"Hotkey removed from {name}")

    def play_profile(self, name):
        """A profile's hotkey was pressed: play its recording straight away."""
        ok, recording = read_profile(name)
        if not ok or not recording:
            self.status.config(text=f"Couldn't play {name}")
            return
        self.start(recording=recording, label=name)

    def save_profile(self):
        name = safe_profile_name(self.profile_name.get())
        if not name:
            self.status.config(text="Type a profile name first")
            return
        if not self.recording:
            self.status.config(text="Record something first")
            return
        updating = profile_path(name).exists()
        hotkey = read_profile_hotkey(name) if updating else None  # keep its hotkey
        if not write_profile(name, self.recording, hotkey):
            self.status.config(text="Couldn't save the profile")
            return
        self.recording_name = name
        self.save_current_recording()
        self.refresh_recording_info()
        self.refresh_profile_list(select=name)
        self.profile_name.set("")
        self.root.focus_set()
        self.status.config(text=f"Updated {name}" if updating else f"Saved {name}")

    def load_profile(self):
        """Swap in a profile's recording. Your other settings stay as they are."""
        name = self.profile_choice.get()
        ok, recording = read_profile(name) if name else (False, None)
        if not ok:
            self.status.config(text="Pick a profile first" if not name else f"Couldn't read {name}")
            self.refresh_profile_list()
            return
        if not recording:
            self.status.config(text=f"{name} has nothing recorded")
            return
        if self.armed and self.settings.get("mode") == "replay":
            self.stop()  # don't swap the recording in the middle of playing it
        if self.recording_active:
            self.stop_recording()
        self.recording = recording
        self.recording_name = name
        self.refresh_recording_info()
        self.save_current_recording()
        self.status.config(text=f"Loaded {name}")

    def delete_profile(self):
        name = self.profile_choice.get()
        if not name or not profile_path(name).exists():
            self.status.config(text="Pick a profile first")
            self.refresh_profile_list()
            return
        if self.delete_armed_job is None:
            # first press: ask to press again, so a profile isn't deleted by accident
            self.delete_btn.set_text("Sure?")
            self.delete_armed_job = self.root.after(3000, self.disarm_delete)
            return
        self.disarm_delete()
        try:
            profile_path(name).unlink()
        except OSError:
            self.status.config(text=f"Couldn't delete {name}")
            return
        self.refresh_profile_list()
        self.status.config(text=f"Deleted {name}")

    def disarm_delete(self):
        if self.delete_armed_job is not None:
            self.root.after_cancel(self.delete_armed_job)
            self.delete_armed_job = None
        self.delete_btn.set_text("Delete")

    def open_folder(self, folder):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            self.status.config(text="Couldn't open the folder")

    def refresh_storage_labels(self):
        self.profiles_where.config(text="A profile is a saved recording. Each one is a .txt "
                                        f"file in {short_path(PROFILES_DIR)}.")
        self.settings_where.config(text=short_path(SETTINGS_PATH.parent))
        self.profiles_where_card.config(text=short_path(PROFILES_DIR))

    def move_folder(self, kind):
        """Move the settings or profiles folder somewhere else (Settings > Storage)."""
        global SETTINGS_PATH, PROFILES_DIR
        current = SETTINGS_PATH.parent if kind == "settings" else PROFILES_DIR
        marker = SETTINGS_MARKER if kind == "settings" else PROFILES_MARKER
        chosen = choose_folder(self.root, current.parent)
        if chosen is None:
            return
        # Use the chosen folder itself if it's empty or already ours; otherwise make a
        # folder for it inside (so picking e.g. the Desktop doesn't scatter files on it)
        try:
            empty = chosen.is_dir() and not any(chosen.iterdir())
        except OSError:
            empty = False
        if (chosen / marker).exists() or empty or not chosen.exists():
            target = chosen
        else:
            target = chosen / ("Auto Clicker settings" if kind == "settings"
                               else "Auto Clicker profiles")
        if target.resolve() == current.resolve():
            self.status.config(text="It's already there")
            return
        if current.resolve() in target.resolve().parents:
            self.status.config(text="Can't move a folder inside itself")
            return
        if kind == "settings":
            self.save_settings()
            names = ["settings.json", "current_recording.json"]
        else:
            names = [p.name for p in current.glob("*.txt")]
        clash = next((n for n in names if (target / n).exists()), None)
        if clash:
            self.status.config(text=f"That folder already has {clash}")
            return
        try:
            target.mkdir(parents=True, exist_ok=True)
            for n in names:
                if (current / n).exists():
                    shutil.move(str(current / n), str(target / n))
            (current / marker).unlink(missing_ok=True)
            try:
                current.rmdir()  # only if nothing else is left in it
            except OSError:
                pass
        except OSError as err:
            self.status.config(text=f"Couldn't move it: {err.strerror or err}")
            return
        if kind == "settings":
            SETTINGS_PATH = target / "settings.json"
            mark_folder(target, SETTINGS_MARKER, "settings")
        else:
            PROFILES_DIR = target
            mark_folder(target, PROFILES_MARKER, "profiles")
        remember_locations()
        self.refresh_profile_list()
        self.status.config(text=f"Moved to {short_path(target)}")

    def edit_recording(self):
        if self.recording_active:
            self.stop_recording()
        RecordingEditor(self.root, self.recording, self.palette, self.recording_edited)

    def recording_edited(self, recording, skipped):
        if self.armed and self.settings.get("mode") == "replay":
            self.stop()
        self.recording = recording
        if self.recording_name and not self.recording_name.endswith(" (edited)"):
            self.recording_name += " (edited)"
        if not recording:
            self.recording_name = None
        self.save_current_recording()
        self.refresh_recording_info()
        note = f" ({skipped} {'line' if skipped == 1 else 'lines'} skipped)" if skipped else ""
        self.status.config(text="Recording saved" + note)

    def load_current_recording(self, saved):
        """The recording you're working with lives in its own file. Older versions kept it
        inside settings.json; if so, move it into its file (only once)."""
        if saved["recording"]:
            write_recording(current_recording_path(), saved["recording"])
            self.needs_settings_rewrite = True
            return saved["recording"]
        try:  # the file also notes which profile the recording came from
            data = json.loads(current_recording_path().read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("profile"), str):
                self.recording_name = data["profile"]
        except (OSError, ValueError):
            pass
        return read_recording(current_recording_path())

    # ---------------- Recording ----------------
    def refresh_recording_info(self):
        if self.recording_active:
            self.recording_info.config(
                text=f"Recording. Press {input_name(self.record_key.get())} or Esc to stop.")
        elif not self.recording:
            self.recording_info.config(text="No recording yet")
        else:
            n = len(self.recording)
            seconds = self.recording[-1][0]
            source = f" · from {self.recording_name}" if self.recording_name else " · not saved yet"
            self.recording_info.config(
                text=f"{n} {'action' if n == 1 else 'actions'}, {seconds:.1f} seconds{source}")
        self.refresh_button()

    def toggle_recording(self, from_button=True):
        """The Record button (from_button=True) or the record key."""
        if self.recording_active:
            self.stop_recording(from_button=from_button)
        else:
            self.start_recording(from_button=from_button)

    def start_recording(self, from_button=False):
        if self.armed:
            self.stop()
        self.stop_capture()
        self.root.update_idletasks()
        self.record_rect = (self.root.winfo_rootx(), self.root.winfo_rooty(),
                            self.root.winfo_width(), self.root.winfo_height())
        self.record_exclude = {self.hotkey.get(), self.location_key.get(),
                               self.record_key.get(), "key:esc", *self.profile_hotkeys}
        self.record_keys = bool(self.record_keys_only.get())
        self.record_movement = bool(self.record_moves.get()) and not self.record_keys
        self.record_from_button = from_button
        self.recording_buf = []
        self.record_pressed = set()
        self.record_last_move = 0.0
        self.record_t0 = time.monotonic()
        self.recording_active = True
        self.status.config(text="Recording...")
        self.refresh_recording_info()

    def stop_recording(self, from_button=False):
        self.recording_active = False
        actions = list(self.recording_buf)
        self.recording_buf = []

        def in_window(action):
            if action[1] not in ("move", "press", "release", "scroll") or not self.record_rect:
                return False
            x, y = action[-2], action[-1]
            rx, ry, rw, rh = self.record_rect
            return rx <= x < rx + rw and ry <= y < ry + rh

        # Drop the mouse travelling from the Record button at the start, and to the
        # "Stop recording" button at the end (those aren't part of what you wanted).
        # With the record key you never touch the app, so nothing is dropped.
        while self.record_from_button and actions and in_window(actions[0]):
            actions.pop(0)
        if from_button:
            while actions and in_window(actions[-1]):
                actions.pop()

        # Let go of anything still held down at the end, and drop releases of things
        # that were pressed before recording began
        pressed, cleaned = set(), []
        for action in actions:
            kind = action[1]
            if kind in ("press", "kpress"):
                pressed.add(action[2])
            elif kind in ("release", "krelease"):
                if action[2] not in pressed:
                    continue
                pressed.discard(action[2])
            cleaned.append(action)
        if cleaned:
            end = cleaned[-1][0]
            for code in sorted(pressed):
                if code.startswith("mouse:"):
                    x, y = self.mouse.position
                    cleaned.append([end, "release", code, int(x), int(y)])
                else:
                    cleaned.append([end, "krelease", code])
            start = cleaned[0][0]
            for action in cleaned:  # start the recording at its first action
                action[0] = round(action[0] - start, 3)
            self.recording = cleaned
            self.recording_name = None  # a new recording, not saved as a profile yet
            self.status.config(text="Recorded")
            self.save_current_recording()
        else:
            self.status.config(text="Nothing recorded")
        self.refresh_recording_info()

    def clear_recording(self):
        if self.recording_active:
            self.stop_recording()
        if self.armed and self.settings.get("mode") == "replay":
            self.stop()
        self.recording = None
        self.recording_name = None
        self.save_current_recording()
        self.refresh_recording_info()
        self.status.config(text="Recording cleared")

    def record_event(self, *action):
        """Called from the listener threads while recording."""
        if not self.recording_active:
            return
        t = round(time.monotonic() - self.record_t0, 3)
        self.recording_buf.append([t, *action])

    # ---------------- Control ----------------
    def read_settings(self, recording=None, label=None):
        """Turn the current values into the settings the worker thread uses.
        recording: play this instead (a profile's hotkey), whatever mode is on."""
        mode = "replay" if recording is not None else self.mode()
        try:
            if mode == "replay":
                actions = recording if recording is not None else self.recording
                if not actions:
                    self.status.config(text="Record something first")
                    return False
                if not self.replay_loop.get():
                    plays = 1
                elif self.replay_limit_on.get():
                    plays = max(1, int(self.replay_limit.get()))
                else:
                    plays = 0  # forever
                self.settings = {
                    "mode": "replay", "hold": False, "actions": actions, "plays": plays,
                    "label": label, "limit": 0, "time_limit": 0,
                    "delay": 0.0, "locations": None, "codes": set(),
                }
            elif mode == "keyboard":
                hold = bool(self.kb_hold.get())
                code = self.kb_key.get()
                self.settings = {
                    "mode": "keyboard",
                    "hold": hold,
                    "keys": keys_for_combo(code),   # modifiers first, e.g. [Ctrl, C]
                    "codes": codes_for_combo(code),
                    "count": 1,
                    "interval": 1.0 / max(0.1, float(self.kb_cps.get())),
                    # 0 means "never stop"; only used when the toggle is on and not holding
                    "limit": (max(1, int(self.kb_limit.get()))
                              if self.kb_limit_on.get() and not hold else 0),
                    "time_limit": (max(1.0, float(self.kb_time_limit.get()))
                                   if self.kb_time_limit_on.get() else 0),
                    "delay": max(0.0, float(self.kb_delay.get())),
                    "locations": None,
                    "unit": ("press", "presses"),
                }
            else:
                hold = bool(self.hold.get())
                button = BUTTONS[self.button.get()]
                if self.click_delay_on.get():
                    interval = max(0.01, float(self.click_delay.get()))
                else:
                    interval = 1.0 / max(0.1, float(self.cps.get()))
                self.settings = {
                    "mode": "mouse",
                    "hold": hold,
                    "button": button,
                    "codes": {input_code(button)},
                    "count": CLICK_TYPES.get(self.click_type.get(), 1),
                    "interval": interval,
                    "limit": (max(1, int(self.limit.get()))
                              if self.limit_on.get() and not hold else 0),
                    "time_limit": (max(1.0, float(self.time_limit.get()))
                                   if self.time_limit_on.get() else 0),
                    "delay": max(0.0, float(self.delay.get())),
                    # None means "click wherever the mouse is"
                    "locations": (self.click_spots()
                                  if self.location_on.get() and self.locations else None),
                    "unit": ("click", "clicks"),
                }
            # replays move the mouse themselves, so auto stop would stop them straight away
            self.settings["auto_stop"] = bool(self.auto_stop.get()) and mode != "replay"
        except (tk.TclError, ValueError, KeyError):
            self.status.config(text="Invalid setting. Check the numbers.")
            return False
        if mode == "mouse" and self.location_on.get() and not self.locations:
            self.status.config(
                text=f"Set a location first (press Pick or {input_name(self.location_key.get())})")
            return False
        self.describe_run(label)
        return True

    def set_location(self, x=None, y=None):
        """Save a spot to click (where the mouse is now, unless given). With several spots
        in a row it's added to the list; otherwise it replaces the spot."""
        if x is None:
            x, y = self.mouse.position
        spot = [int(x), int(y)]
        if self.multi_location.get() and not self.hold.get():
            self.locations = (self.locations + [spot])[-50:]
            message = f"Spot {len(self.locations)} added"
        else:
            self.locations = [spot]
            message = "Location set"
        if self.armed and self.settings.get("mode") == "mouse" and self.settings.get("locations"):
            self.settings["locations"] = self.click_spots()  # takes effect straight away
        elif not self.armed:
            self.status.config(text=message)
        self.refresh_location()
        self.save_settings()

    def click_spots(self):
        spots = self.locations if self.multi_location.get() and not self.hold.get() \
            else self.locations[:1]
        return [tuple(p) for p in spots]

    def clear_locations(self):
        self.locations = []
        self.refresh_location()
        self.save_settings()
        self.status.config(text="Spots cleared")

    def pick_location(self):
        verb = "hold" if self.hold.get() else "click"
        ScreenPicker(self.root, f"Click where you want to {verb}  ·  Esc to cancel",
                     lambda x, y: self.set_location(x, y))

    def toggle(self):
        if self.recording_active:
            return  # recording has its own key; don't start clicking in the middle of it
        if self.armed:
            self.stop()
        else:
            self.start()

    def start(self, recording=None, label=None):
        if not self.read_settings(recording, label):
            return
        self.save_settings()
        self.armed = True
        self.clicks = 0
        self.plays_done = 0
        self.stopped.clear()
        self.refresh_button()
        delay = self.settings["delay"]
        if delay > 0:
            self.status.config(text=f"Starting in {delay:g}s...")
            self.root.after(int(delay * 1000), self.begin_clicking)
        else:
            self.begin_clicking()

    def begin_clicking(self):
        if not self.armed:  # may have been cancelled during the delay
            return
        mode = self.settings["mode"]
        if mode == "replay" and self.settings.get("label"):
            self.status.config(text=f"Playing {self.settings['label']}...")
        elif mode == "replay":
            self.status.config(text="Replaying...")
        elif self.settings["hold"]:
            self.status.config(text="Holding...")
        elif mode == "keyboard":
            self.status.config(text="Pressing...")
        else:
            self.status.config(text="Clicking...")
        self.anchor = self.mouse.position
        self.started_at = time.monotonic()
        self.running.set()
        self.refresh_running()

    def stop(self, message="Stopped"):
        self.armed = False
        self.running.clear()
        self.stopped.set()
        self.release_held()
        self.refresh_button()
        self.status.config(text=message)

    # ---------------- Worker thread ----------------
    def mark_synthetic(self, codes):
        """Remember that we're about to press these, so the listeners can ignore them."""
        now = time.monotonic()
        for code in codes:
            self.last_synthetic[code] = now

    def tap(self, s):
        """One click (or double/triple click), or one key/combo press."""
        self.mark_synthetic(s["codes"])
        if s["mode"] == "keyboard":
            for key in s["keys"]:
                self.keyboard.press(key)
            for key in reversed(s["keys"]):
                self.keyboard.release(key)
        else:
            if s["locations"]:  # one spot, or several clicked in turn
                self.mouse.position = s["locations"][self.clicks % len(s["locations"])]
            self.mouse.click(s["button"], s["count"])

    def press_and_hold(self, s):
        with self.hold_lock:
            if not self.running.is_set():
                return
            self.mark_synthetic(s["codes"])
            self.held_codes = set(s["codes"])
            if s["mode"] == "keyboard":
                for key in s["keys"]:
                    self.keyboard.press(key)
                    self.held.append(("keyboard", key))
            else:
                if s["locations"]:
                    self.mouse.position = s["locations"][0]
                self.mouse.press(s["button"])
                self.held.append(("mouse", s["button"]))

    def release_held(self):
        """Let go of whatever Hold mode or a replay is holding (safe to call any time)."""
        with self.hold_lock:
            held, self.held = self.held, []
            self.held_codes = set()
            for kind, thing in reversed(held):
                try:
                    if kind == "keyboard":
                        self.keyboard.release(thing)
                    else:
                        self.mouse.release(thing)
                except Exception as err:  # never leave the app stuck because of a release
                    print(f"Could not release {thing}: {err}")

    def replay(self, s):
        """Play the recorded actions with their original timing: once, a set number of
        times, or until stopped."""
        played = 0
        while self.running.is_set():
            began = time.monotonic()
            for action in s["actions"]:
                wait = began + action[0] - time.monotonic()
                if wait > 0 and self.stopped.wait(wait):
                    return  # stopped
                if not self.running.is_set():
                    return
                self.do_action(action)
            played += 1
            self.plays_done = played
            if s["plays"] and played >= s["plays"]:
                self.running.clear()
                self.events.put(("replay_done", played))
                return
            if self.stopped.wait(0.05):  # tiny pause between loops
                return

    def do_action(self, action):
        kind = action[1]
        with self.hold_lock:
            if kind == "move":
                self.mouse.position = (action[2], action[3])
            elif kind == "scroll":
                self.mouse.position = (action[4], action[5])
                self.mouse.scroll(action[2], action[3])
            elif kind in ("press", "release"):
                button = mouse.Button[action[2][6:]]
                self.mouse.position = (action[3], action[4])
                if kind == "press":
                    self.mark_synthetic({action[2]})
                    self.held_codes.add(action[2])
                    self.mouse.press(button)
                    self.held.append(("mouse", button))
                else:
                    self.mouse.release(button)
                    self.held_codes.discard(action[2])
                    if ("mouse", button) in self.held:
                        self.held.remove(("mouse", button))
            elif kind in ("kpress", "krelease"):
                key = key_from_code(action[2])
                if kind == "kpress":
                    self.mark_synthetic({action[2]})
                    self.held_codes.add(action[2])  # so key repeat while held is ignored
                    self.keyboard.press(key)
                    self.held.append(("keyboard", key))
                else:
                    self.keyboard.release(key)
                    self.held_codes.discard(action[2])
                    if ("keyboard", key) in self.held:
                        self.held.remove(("keyboard", key))

    def click_loop(self):
        while not self.shutdown.is_set():
            if not self.running.wait(timeout=0.1):
                continue
            s = self.settings

            if s["mode"] == "replay":
                try:
                    self.replay(s)
                finally:
                    self.release_held()  # nothing stays pressed if a replay is stopped
                continue

            if s["hold"]:
                self.press_and_hold(s)
                while self.running.is_set() and not self.shutdown.is_set():
                    time.sleep(0.02)
                self.release_held()
                continue

            self.tap(s)
            self.clicks += 1

            limit = s["limit"]
            if limit and self.clicks >= limit:
                self.running.clear()
                self.events.put("limit")
                continue

            self.stopped.wait(s["interval"])  # returns early if stopped

    # ---------------- Keys, mouse buttons + polling ----------------
    # These run on pynput's threads, so they only pass the input on to poll()
    def is_synthetic(self, code):
        if code and code in self.held_codes:
            return True  # what Hold mode is holding (incl. key repeat)
        last = self.last_synthetic.get(code)
        return last is not None and time.monotonic() - last < self.SYNTHETIC_WINDOW

    def on_key(self, key):
        code = input_code(key)
        if self.is_synthetic(code):
            return  # one of our own key presses
        if self.recording_active and code and code not in self.record_exclude:
            if code not in self.record_pressed:  # skip key repeat while held
                self.record_pressed.add(code)
                self.record_event("kpress", code)
        self.events.put(("input", code, time.monotonic()))

    def on_key_release(self, key):
        code = input_code(key)
        if self.recording_active and code in self.record_pressed:
            self.record_pressed.discard(code)
            self.record_event("krelease", code)
        if self.capturing is not None and code in MODIFIER_OF:
            self.events.put(("release", code, time.monotonic()))

    def on_mouse(self, x, y, button, pressed):
        code = input_code(button)
        if self.recording_active and not self.record_keys and code not in self.record_exclude:
            if pressed:
                self.record_pressed.add(code)
                self.record_event("press", code, int(x), int(y))
            elif code in self.record_pressed:
                self.record_pressed.discard(code)
                self.record_event("release", code, int(x), int(y))
        if not pressed:
            return
        if self.is_synthetic(code):
            return  # one of our own automatic clicks
        self.events.put(("input", code, time.monotonic()))

    def on_scroll(self, x, y, dx, dy):
        if self.recording_active and not self.record_keys:
            self.record_event("scroll", int(dx), int(dy), int(x), int(y))

    def on_mouse_move(self, x, y):
        if self.recording_active and self.record_movement:
            now = time.monotonic()
            if now - self.record_last_move >= self.MOVE_SAMPLE:
                self.record_last_move = now
                self.record_event("move", int(x), int(y))
        # Auto stop: notice when you move the mouse away while it's clicking
        if not self.running.is_set() or not self.settings.get("auto_stop"):
            return
        # With set spots the app moves the mouse there itself, so measure from those;
        # otherwise measure from where the mouse was when clicking began.
        spots = self.settings.get("locations") or ([self.anchor] if self.anchor else [])
        if spots and all(math.hypot(x - sx, y - sy) > self.MOVE_TOLERANCE for sx, sy in spots):
            self.events.put("moved")

    def handle_input(self, code, when=None):
        if not code:
            return
        # The same key twice in a row very quickly (a duplicate event, or a key being
        # held down) only counts once, so one press can't set a key AND trigger it
        when = time.monotonic() if when is None else when
        last = self.last_input.get(code)
        self.last_input[code] = when
        if last is not None and when - last < self.REPEAT_WINDOW:
            return
        if self.capturing is not None:
            if self.finish_capture(code):
                return
            if code == "mouse:left":
                return
        # Esc: emergency stop for everything
        if code == "key:esc":
            if self.recording_active:
                self.stop_recording()
            elif self.armed:
                self.stop("Stopped (Esc)")
            return
        # Auto stop: a mouse click of your own (not one of the app's keys) stops clicking
        if (self.running.is_set() and self.settings.get("auto_stop")
                and code.startswith("mouse:")
                and code not in (self.hotkey.get(), self.location_key.get(),
                                 self.record_key.get())):
            self.stop("Stopped (you clicked)")
            return
        if code == self.record_key.get():
            self.toggle_recording(from_button=False)
        elif code == self.hotkey.get():
            self.toggle()
        elif code in self.profile_hotkeys and not self.recording_active:
            if self.armed:
                self.stop()
            else:
                self.play_profile(self.profile_hotkeys[code])
        elif (code == self.location_key.get() and self.location_on.get()
              and not self.recording_active):
            self.set_location()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event == "limit":
                    count = self.settings["limit"]
                    one, many = self.settings["unit"]
                    self.stop(f"Done: {count} {one if count == 1 else many}")
                    self.play_finish_sound()
                elif event == "moved":
                    if self.running.is_set():
                        self.stop("Stopped (mouse moved)")
                elif event[0] == "replay_done":
                    played = event[1]
                    self.stop("Replay finished" if played == 1 else f"Done: played {played} times")
                    self.play_finish_sound()
                elif event[0] == "system_theme":
                    self.update_icon()
                elif event[0] == "release":
                    self.capture_release(event[1])
                else:
                    self.handle_input(event[1], event[2])
        except queue.Empty:
            pass
        # Keep the floating card's progress (count, time left) up to date
        if (self.badge is not None and self.badge.showing and self.progress_text()
                and time.monotonic() - self.last_badge_update >= 0.25):
            self.last_badge_update = time.monotonic()
            self.refresh_running()
        # Stop after a set time
        limit = self.settings.get("time_limit")
        if self.running.is_set() and limit and time.monotonic() - self.started_at >= limit:
            self.stop(f"Done: {limit:g} {'second' if limit == 1 else 'seconds'}")
            self.play_finish_sound()
        self.poll_job = self.root.after(50, self.poll)

    def on_close(self):
        if self.shutdown.is_set():
            return  # already closing (e.g. asked to quit twice)
        self.recording_active = False
        self.root.after_cancel(self.poll_job)
        self.running.clear()
        self.stopped.set()
        self.release_held()  # never leave a key or button stuck down
        self.save_settings()
        self.shutdown.set()
        self.listener.stop()
        self.mouse_listener.stop()
        if self.theme_watcher is not None:
            self.theme_watcher.terminate()
        self.root.destroy()


def main():
    if "--write-icons" in sys.argv:
        write_icons()
        return
    found = resolve_locations()  # where settings and profiles are (and if they were moved)
    root = tk.Tk(className=APP_CLASS)  # window class the dock uses to find the app entry
    app = AutoClicker(root)
    if found:
        app.status.config(text="Found your moved " + " and ".join(found)
                                + (" folders" if len(found) > 1 else " folder"))
    # When something asks the app to quit (like install.sh updating it), close it the same
    # way as the window's close button: settings are saved and nothing is left held down.
    signal.signal(signal.SIGTERM, lambda *_: root.after(0, app.on_close))
    root.mainloop()


if __name__ == "__main__":
    main()
