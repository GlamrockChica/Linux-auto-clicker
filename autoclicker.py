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
import struct
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
# Recording accuracy: how often mouse movement is written down (seconds between "move"
# lines). Higher is smoother but makes bigger profiles. Clicks and keys are always exact.
ACCURACY = {"Lowest": 0.1, "Low": 0.05, "Medium": 0.03, "High": 0.015, "Ultra": 0.004}
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
# Saved areas (see AreaPlan) are .txt files in an "areas" folder, the same way
AREAS_DIR = Path.home() / ".config" / "autoclicker" / "areas"
# Saved macros (.txt files), see read_macro
MACROS_DIR = Path.home() / ".config" / "autoclicker" / "macros"

# All three folders can be moved (Settings > Storage, or by hand). This file never moves and
# remembers where they are; each folder also holds a small hidden marker file, so if you
# move a folder yourself the app can find it again.
CONFIG_DIR = Path.home() / ".config" / "autoclicker"
POINTER_PATH = CONFIG_DIR / "locations.json"
DEFAULT_SETTINGS_DIR = CONFIG_DIR
DEFAULT_PROFILES_DIR = PROFILES_DIR
DEFAULT_AREAS_DIR = AREAS_DIR
DEFAULT_MACROS_DIR = MACROS_DIR
SETTINGS_MARKER = ".autoclicker-settings"
PROFILES_MARKER = ".autoclicker-profiles"
AREAS_MARKER = ".autoclicker-areas"
MACROS_MARKER = ".autoclicker-macros"

APP_VERSION = "3.2"  # bump this for each GitHub release, and tag the release "v" + this
GITHUB_REPO = "GlamrockChica/Linux-auto-clicker"
GITHUB_PAGE = f"https://github.com/{GITHUB_REPO}"
APP_CLASS = "autoclicker"  # window class; install.sh sets StartupWMClass to match
# Dock / app list icon: the sidebar logo (cursor on a rounded square) in black and white,
# matching the computer's light/dark mode. install.sh saves it as PNGs (see write_icons).
ICON_STYLES = {  # style: the penguin's colour (see logo_gradient)
    "light": "#8a4dff",  # computer in light mode
    "dark": "#8a4dff",   # computer in dark mode (the same: it shows well on both)
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
    "area_on": False,          # click every spot inside the area's shapes
    "area": [],                # the shapes to click inside (see AreaPlan)
    "area_gap": 10,            # pixels between the spots it clicks
    "area_return": True,       # put the mouse back after each area click
    "area_in_order": False,    # click one shape's spots, then the next shape's (see AreaPlan)
    "hold": False,             # hold the button down instead of clicking
    # macros
    "macro": [],               # the clicks, in order: {"button": "Left", "x": 10, "y": 20}
    "macro_wait": 0.5,         # seconds between its clicks
    "macro_delay": 0.0,        # start delay
    "macro_loop": True,        # play it over and over
    "macro_limit_on": False,   # ...but stop after a set number of plays
    "macro_limit": 5,
    "macro_return": True,      # put the mouse back after each click
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
    "replay_speed": 1.0,       # 2 = twice as fast, 0.5 = half speed
    "record_keys_only": False, # record only the keyboard
    "record_moves": True,      # record mouse movement (off: only clicks and scrolls)
    "record_repeats": False,   # keep the same key/button pressed twice very quickly
    "record_accuracy": "High", # how smoothly mouse movement is recorded, see ACCURACY
    "recording": None,         # list of recorded actions, see AutoClicker.record_event
    # shared
    "active_mode": "mouse",    # which clicker the start/stop key runs: follows the page
                               # you're on (mouse, keyboard or replay on Profiles)
    "hotkey": "key:f6",        # starts / stops clicking
    "location_key": "key:f7",  # saves the mouse position as the click spot
    "record_key": "key:f8",    # starts / stops recording
    "draw_key": "key:f9",      # opens the menu for drawing an area's shapes
    "auto_stop": False,        # stop if you move or click the mouse yourself
    "always_on_top": False,
    "mini_mode": False,        # a small window with just the mouse clicker
    "mini_position": [-1, -1], # where it was last dragged to (-1: not yet)
    "badge_show": "While running",  # floating card: While running / Always / Off
    "badge_corner": "Top left",     # which corner of the screen it sits in
    "finish_sound": True,      # play a sound when a run finishes by itself
    "countdown": True,         # count down the start delay (3, 2, 1) on the badge
    "check_updates": True,     # look for a newer version on GitHub when the app starts
    "text_size": "Normal",     # Small / Normal / Large
    "dark_mode": False,
    "accent": "#4a8fd9",
    "sidebar_width": 150,      # dragged with the handle between sidebar and page
    "bar_height": BAR_MIN,     # the same, for a menu along the top or bottom
    "sidebar_side": "Left",    # where the menu goes: Left, Right, Top or Bottom
}

# Which clicker each page runs: the start/stop key runs the clicker of the page you're
# on (on Settings, the last one you used)
MAX_CPS = 1000  # fastest clicks / key presses per second you can set


MODE_PAGES = {"mouse": "clicker", "macro": "macros", "keyboard": "keyboard",
              "replay": "recording"}
PAGE_MODES = {page: mode for mode, page in MODE_PAGES.items()}
PAGE_MODES["areas"] = "mouse"  # the Areas page sets up the mouse clicker

# The app's own keys (Settings page); they must all be different
APP_KEYS = ("hotkey", "location_key", "record_key", "draw_key")

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
        if kind == "move" and len(action) in (4, 6):
            good.append([*action[:2], *(int(n) for n in action[2:])])
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
        area = saved.get("area")
        if (isinstance(area, list) and len(area) == 4
                and all(isinstance(v, (int, float)) for v in area)):  # older: one box
            x, y, w, h = (int(v) for v in area)
            area = [{"type": "rectangle", "points": [x, y, x + w, y + h]}]
        settings["area"] = clean_shapes(area if isinstance(area, list) else [])
        settings["macro"] = clean_macro(saved.get("macro"))
        if "recording" in saved:
            settings["recording"] = clean_recording(saved.get("recording"))
        # Older settings files used "limit": 0 to mean "never stop"
        if "limit" in saved and "limit_on" not in saved:
            settings["limit_on"] = settings["limit"] > 0
        # Older settings files stored the hotkey as just "F6"
        for name in APP_KEYS:
            if re.fullmatch(r"F\d+", settings[name]):
                settings[name] = "key:" + settings[name].lower()
    for name in ("limit", "kb_limit", "replay_limit", "macro_limit"):
        if settings[name] < 1:
            settings[name] = DEFAULTS[name]
    settings["sidebar_width"] = min(max(settings["sidebar_width"], SIDEBAR_MIN), SIDEBAR_MAX)
    settings["bar_height"] = min(max(settings["bar_height"], BAR_MIN), BAR_MAX)
    for name in ("click_delay", "time_limit", "kb_time_limit"):
        if settings[name] <= 0:
            settings[name] = DEFAULTS[name]
    settings["replay_speed"] = min(max(settings["replay_speed"], SPEED_MIN), SPEED_MAX)
    settings["area_gap"] = min(max(settings["area_gap"], AREA_GAP_MIN), AREA_GAP_MAX)
    settings["macro_wait"] = min(max(settings["macro_wait"], MACRO_WAIT_MIN), MACRO_WAIT_MAX)
    settings["macro_delay"] = min(max(settings["macro_delay"], 0.0), 60.0)
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
    if settings["record_accuracy"] not in ACCURACY:
        settings["record_accuracy"] = DEFAULTS["record_accuracy"]
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


SPEED_MIN, SPEED_MAX = 0.1, 10.0  # replay speed limits


def version_numbers(text):
    """(3, 1) for "v3.1" or "3.1"; None if there are no numbers in it."""
    numbers = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in numbers) if numbers else None


def latest_release():
    """(tag, web page) of the newest release on GitHub. Raises an error if it can't tell."""
    import urllib.request
    request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
        headers={"User-Agent": "Auto-Clicker-update-check",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=8) as reply:
        data = json.load(reply)
    return data.get("tag_name", ""), data.get("html_url") or GITHUB_PAGE


def on_wayland() -> bool:
    """True on a Wayland session, where the clicking and key presses can't reach most apps."""
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session == "wayland" or (session != "x11" and bool(os.environ.get("WAYLAND_DISPLAY")))


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
#   {[0.015],move:"812,440,6,-3"}  <- the mouse moved 6 right and 3 up, ending at
#                                     x 812, y 440 (games turn the camera with the 6,-3;
#                                     older files have just "812,440")
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
        elif kind == "move":  # where it ended up (and how far it moved, if known)
            value = ",".join(str(n) for n in action[2:6])
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
                numbers = [int(n) for n in value.split(",")]
                if len(numbers) in (2, 4):
                    recording.append([t, kind, *numbers])
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


# ---------------- Areas ----------------
# An area is one or more shapes on the screen. The clicker clicks every spot inside them,
# `gap` pixels apart, row by row. A shape is {"type": ..., "points": [x1, y1, x2, y2, ...]}:
#   rectangle, circle: two opposite corners of the box it fills (a circle is an oval in it)
#   triangle, polygon: its corners
# Saved areas are .txt files in the areas folder (AREAS_DIR):
#   {area:"farm"}
#   {gap:"10"}
#   {order:"1"}       (only if it clicks one shape after another, see AreaPlan)
#   {rectangle:"812,440,1112,590"}
#   {circle:"100,100,300,300"}
#   {polygon:"10,10,80,20,60,90"}
AREA_GAP_MIN, AREA_GAP_MAX = 1, 500
AREA_LINE = re.compile(r'^\{\s*(\w+)\s*:\s*(".*")\s*\}$')
SHAPE_NAMES = {"rectangle": "Rectangle", "circle": "Circle", "triangle": "Triangle",
               "polygon": "Polygon"}


def clean_shape(shape):
    """A well-formed copy of a shape, or None if it isn't one."""
    if not isinstance(shape, dict) or shape.get("type") not in SHAPE_NAMES:
        return None
    try:
        points = [int(round(float(v))) for v in shape.get("points", [])]
    except (TypeError, ValueError):
        return None
    kind = shape["type"]
    if kind in ("rectangle", "circle"):
        if len(points) != 4:
            return None
        x1, y1, x2, y2 = points
        points = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
        if points[2] - points[0] < 1 or points[3] - points[1] < 1:
            return None
    elif len(points) < 6 or len(points) % 2 or (kind == "triangle" and len(points) != 6):
        return None
    return {"type": kind, "points": points}


def clean_shapes(shapes):
    return [s for s in (clean_shape(x) for x in shapes or []) if s]


def shape_corners(shape):
    p = shape["points"]
    return list(zip(p[0::2], p[1::2]))


def shapes_box(shapes):
    """(left, top, right, bottom) around all the shapes."""
    xs = [x for s in shapes for x in s["points"][0::2]]
    ys = [y for s in shapes for y in s["points"][1::2]]
    return min(xs), min(ys), max(xs), max(ys)


def describe_shape(shape):
    left, top, right, bottom = shapes_box([shape])
    size = f"{right - left} × {bottom - top}"
    if shape["type"] == "polygon":
        return f"Polygon, {len(shape['points']) // 2} corners, {size} at {left}, {top}"
    return f"{SHAPE_NAMES[shape['type']]}, {size} at {left}, {top}"


def shape_spans(shape, y):
    """Where a shape is along the row at height y: a list of (from x, to x)."""
    p = shape["points"]
    if shape["type"] == "rectangle":
        return [(p[0], p[2])] if p[1] <= y <= p[3] else []
    if shape["type"] == "circle":
        cx, cy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2
        rx, ry = (p[2] - p[0]) / 2, (p[3] - p[1]) / 2
        d = (y - cy) / ry if ry else 2
        if abs(d) > 1:
            return []
        half = rx * math.sqrt(1 - d * d)
        return [(cx - half, cx + half)]
    # triangle / polygon: where the row crosses its edges, paired up (inside between pairs)
    corners = shape_corners(shape)
    lowest = max(y for _x, y in corners)
    if y == lowest:
        y -= 1e-6  # (so the bottom row counts as inside, like a rectangle's does)
    crossings = []
    for (xa, ya), (xb, yb) in zip(corners, corners[1:] + corners[:1]):
        if (ya <= y < yb) or (yb <= y < ya):
            crossings.append(xa + (y - ya) * (xb - xa) / (yb - ya))
    crossings.sort()
    return list(zip(crossings[0::2], crossings[1::2]))


def area_rows(shapes, gap):
    """Every spot to click, row by row: [(y, [x, x, ...]), ...] (rows with no spots are left
    out). The spots sit on a grid `gap` pixels apart, starting at the top-left of all the
    shapes, so shapes next to each other line up and overlapping ones aren't clicked twice."""
    from array import array
    if not shapes:
        return []
    left, top, right, bottom = shapes_box(shapes)
    rows = []
    for y in range(top, bottom + 1, gap):
        spans = sorted(span for shape in shapes for span in shape_spans(shape, y))
        xs = array("i")
        last = None
        for a, b in spans:
            first = left + math.ceil((a - left) / gap - 1e-9) * gap
            if last is not None and first <= last:
                first = last + gap  # (overlaps the span before: don't click spots twice)
            end = math.floor(b + 1e-9)
            if first <= end:
                xs.extend(range(first, end + 1, gap))
                last = xs[-1]
        if xs:
            rows.append((y, xs))
    return rows


class AreaPlan:
    """The spots in an area and the order they're clicked in: along each row, then back
    along the next (like mowing a lawn), so the mouse never jumps back across.
    in_order: every spot in the first shape, then every spot in the next one, and so on
    (in the order they were drawn), instead of all the shapes together row by row."""

    def __init__(self, shapes, gap, in_order=False):
        import bisect
        self.bisect = bisect.bisect_right
        self.parts = [AreaPlan([shape], gap) for shape in shapes] if in_order else []
        self.rows = ([row for part in self.parts for row in part.rows] if in_order
                     else area_rows(shapes, gap))
        self.starts, total = [], 0
        for item in self.parts or self.rows:
            self.starts.append(total)
            total += item.count if in_order else len(item[1])
        self.count = total

    def point(self, i):
        i %= self.count
        r = self.bisect(self.starts, i) - 1
        if self.parts:  # one shape after another
            return self.parts[r].point(i - self.starts[r])
        y, xs = self.rows[r]
        j = i - self.starts[r]
        return (xs[-1 - j] if r % 2 else xs[j]), y


def areas_dir() -> Path:
    return AREAS_DIR


def area_path(name: str) -> Path:
    return areas_dir() / f"{name}.txt"


def list_saved(folder: Path) -> list:
    """The names of the .txt files in a folder (saved areas or macros), A to Z."""
    try:
        return sorted((p.stem for p in folder.glob("*.txt") if p.is_file()), key=str.lower)
    except OSError:
        return []


def write_saved(path: Path, lines) -> bool:
    """Write a saved area's or macro's lines (to a new file first, so a half-written file
    never replaces a good one)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temp.replace(path)
        return True
    except OSError as err:
        print(f"Could not save {path.stem}: {err}")
        return False


def list_areas() -> list:
    return list_saved(areas_dir())


def write_area(name: str, shapes, gap: int, in_order=False) -> bool:
    lines = ["{area:" + json.dumps(name) + "}", "{gap:" + json.dumps(str(int(gap))) + "}"]
    if in_order:
        lines.append('{order:"1"}')
    for shape in shapes:
        lines.append("{" + shape["type"] + ":"
                     + json.dumps(",".join(str(v) for v in shape["points"])) + "}")
    return write_saved(area_path(name), lines)


def read_area(name: str):
    """(shapes, gap, in order) from a saved area's file, or None if it can't be read or is
    empty."""
    shapes, gap, in_order = [], DEFAULTS["area_gap"], False
    try:
        lines = area_path(name).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        match = AREA_LINE.match(line.strip())
        if not match:
            continue
        try:
            key, value = match.group(1), json.loads(match.group(2))
            if key == "gap":
                gap = min(max(int(value), AREA_GAP_MIN), AREA_GAP_MAX)
                continue
            if key == "order":
                in_order = value == "1"
                continue
            numbers = [int(v) for v in value.split(",")]
            if key == "box" and len(numbers) == 4:  # (an older area: x, y, width, height)
                key = "rectangle"
                numbers = [numbers[0], numbers[1], numbers[0] + numbers[2],
                           numbers[1] + numbers[3]]
            shape = clean_shape({"type": key, "points": numbers})
            if shape:
                shapes.append(shape)
        except (ValueError, TypeError, AttributeError):
            continue
    return (shapes, gap, in_order) if shapes else None


# ---------------- Macros ----------------
# A macro is a list of clicks, clicked one after another in order. A click is
# {"button": "Left" / "Right" / "Middle", "x": ..., "y": ...}. Saved macros are .txt files
# in the macros folder (MACROS_DIR):
#   {macro:"farm"}
#   {wait:"0.5"}
#   {left:"812,440"}
#   {right:"100,200"}
MACRO_MAX = 150  # most clicks in a macro (each one is a circle on the Macros menu)
MACRO_WAIT_MIN, MACRO_WAIT_MAX = 0.001, 3600
MACRO_LETTERS = {"Left": "L", "Right": "R", "Middle": "M"}


def clean_macro(clicks):
    """Well-formed copies of a macro's clicks (anything that isn't one is left out)."""
    good = []
    for click in clicks if isinstance(clicks, list) else []:
        try:
            if click["button"] in MACRO_LETTERS:
                good.append({"button": click["button"], "x": int(click["x"]),
                             "y": int(click["y"])})
        except (TypeError, KeyError, ValueError):
            pass
    return good[:MACRO_MAX]


def macro_label(i, click):
    """A click's letter and number: L1 is a left click and the first click, R2 a right
    click and the second, M3 a middle click and the third."""
    return f"{MACRO_LETTERS[click['button']]}{i + 1}"


def macros_dir() -> Path:
    return MACROS_DIR


def macro_path(name: str) -> Path:
    return macros_dir() / f"{name}.txt"


def list_macros() -> list:
    return list_saved(macros_dir())


def write_macro(name: str, clicks, wait: float) -> bool:
    lines = ["{macro:" + json.dumps(name) + "}", "{wait:" + json.dumps(f"{wait:g}") + "}"]
    for click in clicks:
        lines.append("{" + click["button"].lower() + ":"
                     + json.dumps(f"{click['x']},{click['y']}") + "}")
    return write_saved(macro_path(name), lines)


def read_macro(name: str):
    """(clicks, wait) from a saved macro's file, or None if it can't be read or is empty."""
    clicks, wait = [], DEFAULTS["macro_wait"]
    try:
        lines = macro_path(name).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        match = AREA_LINE.match(line.strip())
        if not match:
            continue
        try:
            key, value = match.group(1), json.loads(match.group(2))
            if key == "wait":
                wait = min(max(float(value), MACRO_WAIT_MIN), MACRO_WAIT_MAX)
            elif key.capitalize() in MACRO_LETTERS:
                x, y = (int(v) for v in value.split(","))
                clicks.append({"button": key.capitalize(), "x": x, "y": y})
        except (ValueError, TypeError, AttributeError):
            continue
    return (clicks[:MACRO_MAX], wait) if clicks else None


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
                                            "profiles": str(PROFILES_DIR),
                                            "areas": str(AREAS_DIR),
                                            "macros": str(MACROS_DIR)}, indent=2),
                                encoding="utf-8")
    except OSError as err:
        print(f"Could not save folder locations: {err}")


def resolve_locations() -> list:
    """Work out where settings, profiles and areas are kept. If a remembered folder has gone
    (because it was moved), look for its marker file. Returns what was found elsewhere."""
    global SETTINGS_PATH, PROFILES_DIR, AREAS_DIR, MACROS_DIR
    try:
        saved = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        saved = saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        saved = {}
    found = []
    folders = {}
    for kind, marker, default in (("settings", SETTINGS_MARKER, DEFAULT_SETTINGS_DIR),
                                  ("profiles", PROFILES_MARKER, DEFAULT_PROFILES_DIR),
                                  ("areas", AREAS_MARKER, DEFAULT_AREAS_DIR),
                                  ("macros", MACROS_MARKER, DEFAULT_MACROS_DIR)):
        if kind == "macros" and "macros" not in saved and "areas" in folders \
                and folders["areas"] != DEFAULT_AREAS_DIR:
            default = folders["areas"].parent / "macros"  # (first time: next to the areas)
        folder = Path(saved[kind]) if isinstance(saved.get(kind), str) else default
        if kind in saved and not (folder / marker).exists():
            moved_to = find_marker(marker)
            if moved_to is not None:
                folder = moved_to
                found.append(kind)
        folders[kind] = folder
    SETTINGS_PATH = folders["settings"] / "settings.json"
    PROFILES_DIR = folders["profiles"]
    AREAS_DIR = folders["areas"]
    MACROS_DIR = folders["macros"]
    mark_folder(SETTINGS_PATH.parent, SETTINGS_MARKER, "settings")
    mark_folder(PROFILES_DIR, PROFILES_MARKER, "profiles")
    mark_folder(AREAS_DIR, AREAS_MARKER, "saved areas")
    mark_folder(MACROS_DIR, MACROS_MARKER, "saved macros")
    move_old_areas()
    remember_locations()
    return found


def move_old_areas() -> None:
    """Areas used to be kept in an "areas" folder inside the profiles folder: move any
    found there into the areas folder (never replacing one that's already there)."""
    old = PROFILES_DIR / "areas"
    try:
        if not old.is_dir() or old.resolve() == AREAS_DIR.resolve():
            return
        AREAS_DIR.mkdir(parents=True, exist_ok=True)
        for file in old.glob("*.txt"):
            if not (AREAS_DIR / file.name).exists():
                shutil.move(str(file), str(AREAS_DIR / file.name))
        old.rmdir()  # only if nothing else is left in it
    except OSError:
        pass


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
    """The app icon as a PNG: the penguin logo (see ICON_STYLES), with a see-through
    background."""
    margin = round(size * 0.06)  # a little space around it, like other app icons
    inner = size - 2 * margin
    image = pointer_image()
    masks = logo_masks(inner, samples=4 if inner <= 64 else 2, arrow=image is None)
    pointer = pointer_layer(inner, image) if image else {}
    colors = logo_colors(ICON_STYLES[style])
    blank = b"\0\0\0\0" * size
    rows = [blank] * margin
    for y, row in enumerate(masks):
        pixels = bytearray(b"\0\0\0\0" * margin)
        for x, parts in enumerate(row):
            rgb, covered = logo_pixel(parts, colors, down=(y + 0.5) / inner)
            if (x, y) in pointer:
                rgb, covered = over(pointer[x, y], rgb, covered)
            pixels += bytes(rgb) + bytes((round(255 * covered),))
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
        self.max_items = None  # how many options the list shows before it scrolls

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
    """The rounded list that opens under a RoundedCombo (or above it, if there's more room
    there). Click an item to pick it; click anywhere else or press Esc to close. If the
    list doesn't fit on the screen, it scrolls: mouse wheel, arrow keys, or drag the bar."""

    ITEM_H = 30     # height of each item
    PAD = 5         # space inside the list's edge
    MAX_ITEMS = 8   # longer lists scroll
    BAR_ROOM = 12   # space on the right for the scroll bar, when there is one
    BAR_W = 4       # scroll bar thickness

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

        # Fit on the monitor the box is on: below it if the whole list fits there (or
        # there's more room below than above), otherwise above it
        self.w = combo.winfo_width()
        n = len(self.values)
        cx, cy, ch = combo.winfo_rootx(), combo.winfo_rooty(), combo.winfo_height()
        area = (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())
        for ax, ay, aw, ah in screen_areas():
            if ax <= cx < ax + aw and ay <= cy < ay + ah:
                area = (ax, ay, aw, ah)
                break
        ax, ay, aw, ah = area
        below = ay + ah - (cy + ch + 4) - 4  # room under the box
        above = cy - 4 - ay - 4              # room over it

        def items_in(room):
            return max(1, min(n, most, (room - self.PAD * 2) // self.ITEM_H))

        most = combo.max_items or self.MAX_ITEMS
        wanted = min(n, most)
        open_below = items_in(below) >= wanted or below >= above
        self.visible = items_in(below if open_below else above)
        self.scrolls = self.visible < n
        self.h = self.visible * self.ITEM_H + self.PAD * 2
        y = cy + ch + 4 if open_below else cy - self.h - 4
        x = max(ax, min(cx, ax + aw - self.w))
        # start scrolled so the chosen item shows
        current = combo.var.get()
        chosen = self.values.index(current) if current in self.values else 0
        self.top = max(0, min(chosen - self.visible // 2, n - self.visible))
        self.pos = float(self.top)  # where the list is drawn from: glides towards self.top
        self.glide_job = None
        self.drag_from = None  # (pointer y, top) while dragging the scroll bar
        self.set_alpha(0.0)  # hidden until its corners are cut round (see below)
        self.geometry(f"{self.w}x{self.h}+{x}+{y}")

        # The window's corners are cut round once it's on screen (round_window); the
        # canvas behind the list matches the list, so no square corners ever show
        self.canvas = tk.Canvas(self, width=self.w, height=self.h, bg=p["field"],
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Motion>", lambda e: self.set_hover(self.index_at(e.y)))
        self.canvas.bind("<Leave>", lambda e: self.set_hover(None))
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonPress-2>", self.on_press)
        self.bind("<ButtonPress-3>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.end_drag)
        # the wheel scrolls this list only, never the page behind it ("break")
        self.bind("<Button-4>", lambda e: (self.scroll(-1), "break")[1])
        self.bind("<Button-5>", lambda e: (self.scroll(1), "break")[1])
        self.bind("<MouseWheel>", lambda e: (self.scroll(-1 if e.delta > 0 else 1), "break")[1])
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<Up>", lambda e: self.move(-1))
        self.bind("<Down>", lambda e: self.move(1))
        self.bind("<Return>", lambda e: self.pick(self.hover))
        self.redraw()

        try:
            self.wait_visibility()
            self.update_idletasks()
            round_window(self, FIELD_RADIUS, self.w, self.h)
            self.set_alpha(1.0)
            try:
                self.grab_set_global()  # so a click anywhere (even outside the app) closes it
            except tk.TclError:
                self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def set_alpha(self, value):
        try:
            self.attributes("-alpha", value)
        except tk.TclError:
            pass

    def index_at(self, y):
        i = math.floor(self.pos + (y - self.PAD) / self.ITEM_H)
        if self.PAD <= y < self.h - self.PAD and 0 <= i < len(self.values):
            return i
        return None

    def scroll(self, step):
        top = max(0, min(self.top + step, len(self.values) - self.visible))
        if top != self.top:
            self.top = top
            if self.glide_job is None:
                self.glide()

    def glide(self):
        """Slide the list towards self.top a bit each frame, easing to a stop."""
        left = self.top - self.pos
        self.pos = float(self.top) if abs(left) < 0.02 else self.pos + left * 0.35
        pointer = self.winfo_pointery() - self.winfo_rooty()
        self.hover = self.index_at(pointer)
        self.redraw()
        self.glide_job = self.after(10, self.glide) if self.pos != self.top else None

    def bar(self):
        """The scroll bar's (x, top, bottom), or None if the list doesn't scroll."""
        if not self.scrolls:
            return None
        track_top, track_bottom = self.PAD + 3, self.h - self.PAD - 3
        track = track_bottom - track_top
        length = max(18, track * self.visible / len(self.values))
        spare = len(self.values) - self.visible
        top = track_top + (track - length) * self.pos / spare
        return self.w - self.PAD - self.BAR_ROOM / 2, top, top + length

    def end_drag(self, _event):
        if self.drag_from is not None:
            self.drag_from = None
            self.redraw()

    def on_drag(self, event):
        if self.drag_from is None:
            return
        start_y, start_top = self.drag_from
        _, top, bottom = self.bar()
        track = self.h - 2 * (self.PAD + 3) - (bottom - top)
        spare = len(self.values) - self.visible
        if track > 0:
            moved = (event.y_root - start_y) / track * spare
            self.scroll(round(start_top + moved) - self.top)

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
        # keep the highlighted item in view
        if self.hover < self.top:
            self.scroll(self.hover - self.top)
        elif self.hover >= self.top + self.visible:
            self.scroll(self.hover - self.top - self.visible + 1)

    def on_press(self, event):
        x = event.x_root - self.winfo_rootx()
        y = event.y_root - self.winfo_rooty()
        if not (0 <= x < self.w and 0 <= y < self.h):
            self.close()
            return
        bar = self.bar()
        if bar and x >= self.w - self.PAD - self.BAR_ROOM:  # on the scroll bar
            if event.num != 1:
                return
            _, top, bottom = bar
            if top <= y <= bottom:
                self.drag_from = (event.y_root, self.top)
            else:  # above or below the handle: a page that way
                self.scroll(-self.visible if y < top else self.visible)
            return
        self.pick(self.index_at(y))

    def pick(self, index):
        if index is not None:
            self.combo.var.set(self.values[index])
            self.close()

    def redraw(self):
        c, p = self.canvas, self.palette
        c.delete("all")
        current = self.combo.var.get()
        right = self.w - self.PAD - (self.BAR_ROOM if self.scrolls else 0)
        first = math.floor(self.pos)
        for i in range(first, min(len(self.values), first + self.visible + 1)):
            value = self.values[i]
            y1 = self.PAD + (i - self.pos) * self.ITEM_H
            text_color = p["fg"]
            if i == self.hover:
                c.create_polygon(rounded_points(self.PAD, y1 + 1, right,
                                                y1 + self.ITEM_H - 1, 6),
                                 smooth=True, fill=p["select"], outline="")
                text_color = p["select_fg"]
            c.create_text(12, y1 + self.ITEM_H / 2, text=value, anchor="w",
                          fill=text_color, font="TkTextFont")
            if value == current:  # tick next to the chosen item
                cx, cy = right - 13, y1 + self.ITEM_H / 2
                c.create_line(cx - 4, cy, cx - 1, cy + 3, cx + 5, cy - 4,
                              fill=text_color if i == self.hover else p["accent"],
                              width=2, capstyle="round", joinstyle="round")
        # While gliding, options can be half out of view: tidy the edges, then the border
        for y1, y2 in ((0, self.PAD), (self.h - self.PAD, self.h)):
            c.create_rectangle(0, y1, self.w, y2, fill=p["field"], outline="")
        c.create_polygon(rounded_points(1, 1, self.w - 1, self.h - 1, FIELD_RADIUS),
                         smooth=True, fill="", outline=p["border"])
        bar = self.bar()
        if bar:  # a thin rounded scroll bar on the right
            x, top, bottom = bar
            r = self.BAR_W / 2
            c.create_line(x, top + r, x, bottom - r, width=self.BAR_W, capstyle="round",
                          fill=(mix_color(p["muted"], p["fg"], 0.35) if self.drag_from
                                else mix_color(p["border"], p["muted"], 0.6)))

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.glide_job is not None:
            self.after_cancel(self.glide_job)
            self.glide_job = None
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


def logo_masks(size, samples=4, arrow=True):
    """Work out the logo's shapes once: a round penguin seen from the side, with a round
    white face, one eye, a white belly, a flipper, a little tail, orange beak and feet, and
    a mouse cursor on its belly (arrow=False leaves the cursor out: the computer's own
    mouse pointer goes there instead, see pointer_layer). Drawn
    on a 100x100 grid and scaled to `size`, with samples x samples points per pixel for
    smooth edges. For each pixel: {part: how much of it (0..1)}, where the parts are the
    names in `parts` below (later ones cover earlier ones)."""
    s = size / 100
    SHIFT = 3  # (moves the whole drawing right a little, to centre it)

    def ellipse(cx, cy, rx, ry, turn=0.0):
        cx, cy, rx, ry = (cx + SHIFT) * s, cy * s, rx * s, ry * s
        c, n = math.cos(math.radians(turn)), math.sin(math.radians(turn))

        def inside(x, y):
            dx, dy = x - cx, y - cy
            return ((dx * c + dy * n) / rx) ** 2 + ((-dx * n + dy * c) / ry) ** 2 <= 1
        reach = max(rx, ry)
        inside.box = (cx - reach, cy - reach, cx + reach, cy + reach)
        return inside

    def polygon(points, grow=0.0):
        """Inside the polygon, or within `grow` of its edges (which rounds its corners)."""
        pts = [((x + SHIFT) * s, y * s) for x, y in points]
        reach = grow * s

        def edge_distance(x, y):
            best = math.inf
            for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
                dx, dy = x2 - x1, y2 - y1
                t = min(max(((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy), 0), 1)
                best = min(best, math.hypot(x - x1 - t * dx, y - y1 - t * dy))
            return best

        def inside(x, y):  # even-odd test
            hit = False
            for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
                if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    hit = not hit
            if hit or not reach:
                return hit
            return edge_distance(x, y) <= reach
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        inside.box = (min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach)
        return inside

    def union(*parts):
        def inside(x, y):
            return any(p(x, y) for p in parts)
        inside.box = (min(p.box[0] for p in parts), min(p.box[1] for p in parts),
                      max(p.box[2] for p in parts), max(p.box[3] for p in parts))
        return inside

    def clip(part, within):
        def inside(x, y):
            return within(x, y) and part(x, y)
        inside.box = part.box
        return inside

    # the body: a round head on top of a wider, egg-shaped body, joined smoothly
    def body_shape(less=0.0):
        return union(ellipse(48, 27, 17 - less, 17 - less),
                     ellipse(44, 64, 25 - less, 31 - less),
                     polygon([(31 + less, 27), (65 - less, 27), (69 - less, 62),
                              (19 + less, 62)]))
    body, inner = body_shape(), body_shape(4)
    corners = [(0, 0), (0, 15), (3.6, 11.6), (6.2, 17.1), (8.8, 15.9), (6.3, 10.5), (11.3, 10.5)]
    corners = [(55 + x * 2.4, 53 + y * 2.4) for x, y in corners]  # (tip at POINTER_TIP)
    parts = [  # painted in this order
        ("feet", union(ellipse(36, 94, 9, 4), ellipse(52, 94.5, 11, 4.5))),
        ("beak", polygon([(59, 22), (80, 29), (59, 35)], grow=1.2)),
        ("body", union(body, polygon([(24, 82), (16, 92.5), (31, 91)], grow=1.5))),  # + tail
        # a round white face and a white belly down its front, kept just inside the body's
        # edge (so the body still shows round them on a white background)
        ("face", union(clip(ellipse(53, 27, 11.5, 11.5), inner),
                       clip(ellipse(55, 68, 16, 25), inner))),
        ("flipper", ellipse(29, 61, 6.5, 18.5, turn=-14)),
        ("eye", ellipse(54, 24, 4.6, 4.6)),
        ("shine", ellipse(55.6, 22.4, 1.6, 1.6)),
    ] + ([("cursor_edge", polygon(corners, grow=2.4)), ("cursor", polygon(corners))] if arrow
          else [])
    names = [name for name, _ in parts]
    masks = []
    step = 1 / samples
    n = samples * samples
    for py in range(size):
        row_parts = [(i, test) for i, (_name, test) in enumerate(parts)
                     if test.box[1] - 1 <= py + 1 and test.box[3] + 1 >= py]
        row = []
        for px in range(size):
            here = [(i, test) for i, test in row_parts
                    if test.box[0] - 1 <= px + 1 and test.box[2] + 1 >= px]
            counts = {}
            for sy in range(samples):
                for sx in range(samples):
                    x, y = px + (sx + 0.5) * step, py + (sy + 0.5) * step
                    for i, test in reversed(here):  # the top one that covers it
                        if test(x, y):
                            counts[names[i]] = counts.get(names[i], 0) + 1
                            break
            row.append({name: c / n for name, c in counts.items()})
        masks.append(row)
    return masks


def logo_gradient(color):
    """The penguin's body colours, top to bottom: a lighter colour a little round the
    colour wheel at the top, fading into `color` (a little deeper) at the bottom."""
    h, sat, v = hex_to_hsv(color)
    return (hsv_to_hex((h + 0.11) % 1, max(0.35, sat * 0.75), min(1, v * 1.08 + 0.08)),
            hsv_to_hex(h, min(1, sat * 1.05), v * 0.92))


def logo_colors(color):
    """The colour of each part of the logo (see logo_masks) for a penguin of `color`. The
    body and flipper are gradients: (top, bottom)."""
    top, bottom = logo_gradient(color)
    return {"body": (top, bottom), "beak": "#ff9f2e", "feet": "#ff9f2e", "face": "#ffffff",
            "flipper": (mix_color(top, "#000000", 0.2), mix_color(bottom, "#000000", 0.2)),
            "eye": "#17131f", "shine": "#ffffff", "cursor_edge": "#1a1a1a",
            "cursor": "#ffffff"}


def logo_pixel(parts, colors, bg=None, down=0.5):
    """One pixel of the logo: its parts mixed by how much of the pixel each covers (see
    logo_masks), over `bg`. down: how far down the logo the pixel is (0..1, for the
    body's gradient). Returns ((r, g, b), how much of the pixel the logo covers)."""
    covered = sum(parts.values())
    rgb = [0.0, 0.0, 0.0]
    for name, amount in parts.items():
        color = colors[name]
        if isinstance(color, tuple):  # a gradient from top to bottom
            color = mix_color(color[0], color[1], down)
        for c in range(3):
            rgb[c] += int(color[1 + 2 * c:3 + 2 * c], 16) * amount
    if bg is not None:  # (on a background: it fills in the rest)
        for c in range(3):
            rgb[c] += bg[c] * (1 - covered)
    elif covered:
        rgb = [v / covered for v in rgb]
    return tuple(round(v) for v in rgb), covered


# The computer's own mouse pointer goes on the logo's belly: its tip here (on the logo's
# 100x100 grid), and this tall
POINTER_TIP = (58, 53)
POINTER_HEIGHT = 42
_pointer_found = []  # [the pointer image, or None], once looked up


def pointer_image():
    """The mouse pointer of this computer's cursor theme (the one you see on screen), the
    biggest size the theme has: (width, height, hot x, hot y, pixels), the pixels being
    ARGB numbers (premultiplied, like the file has them). None if there isn't one: the
    logo then draws its own cursor."""
    if not _pointer_found:
        try:
            _pointer_found.append(find_pointer())
        except (OSError, ValueError, struct.error):
            _pointer_found.append(None)
    return _pointer_found[0]


def find_pointer():
    names = []
    try:
        theme = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface",
                                "cursor-theme"], capture_output=True, text=True,
                               timeout=2).stdout.strip().strip("'\"")
        names.append(theme)
    except (OSError, subprocess.SubprocessError):
        pass
    names += [os.environ.get("XCURSOR_THEME", ""), "default"]
    folders = [Path.home() / ".icons", Path.home() / ".local" / "share" / "icons",
               Path("/usr/share/icons"), Path("/usr/share/pixmaps")]
    seen = set()
    while names and len(seen) < 12:
        name = names.pop(0)
        if not name or name in seen or "/" in name:
            continue
        seen.add(name)
        for folder in folders:
            theme = folder / name
            for cursor in ("left_ptr", "default", "arrow"):
                image = read_xcursor(theme / "cursors" / cursor)
                if image:
                    return image
            try:  # a theme can borrow its cursors from another one
                index = (theme / "index.theme").read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in index.splitlines():
                if line.strip().lower().startswith("inherits") and "=" in line:
                    names += [n.strip() for n in re.split("[,;]", line.split("=", 1)[1])]
    return None


def read_xcursor(path: Path):
    """The biggest picture in an X cursor file, or None (see pointer_image)."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:4] != b"Xcur":
        return None
    best = None
    for i in range(min(struct.unpack_from("<I", data, 12)[0], 500)):
        kind, size, start = struct.unpack_from("<III", data, 16 + 12 * i)
        if kind == 0xFFFD0002 and (best is None or size > best[0]):  # a picture
            best = (size, start)
    if best is None:
        return None
    w, h, xhot, yhot = struct.unpack_from("<IIII", data, best[1] + 16)
    if not (0 < w <= 512 and 0 < h <= 512):
        return None
    return w, h, xhot, yhot, struct.unpack_from(f"<{w * h}I", data, best[1] + 36)


def pointer_layer(size, image):
    """The pointer scaled onto a logo `size` pixels across, its tip at POINTER_TIP:
    {(x, y): ((r, g, b), how much of the pixel it covers)} for the pixels it's on."""
    w, h, xhot, yhot, pixels = image
    rows = [y for y in range(h) if any(pixels[y * w + x] >> 24 for x in range(w))]
    if not rows:
        return {}
    k = POINTER_HEIGHT * size / 100 / (rows[-1] - rows[0] + 1)  # logo pixels per pointer pixel
    tx, ty = POINTER_TIP[0] * size / 100, POINTER_TIP[1] * size / 100
    n = max(2, min(8, math.ceil(1 / k) + 1))  # samples each way in each logo pixel
    layer = {}
    for py in range(max(0, int(ty - yhot * k)), min(size, math.ceil(ty + (h - yhot) * k) + 1)):
        for px in range(max(0, int(tx - xhot * k)), min(size, math.ceil(tx + (w - xhot) * k) + 1)):
            total = [0.0, 0.0, 0.0, 0.0]
            for sy in range(n):
                fy = yhot + (py + (sy + 0.5) / n - ty) / k - 0.5
                y0 = math.floor(fy)
                for sx in range(n):
                    fx = xhot + (px + (sx + 0.5) / n - tx) / k - 0.5
                    x0 = math.floor(fx)
                    # blend the 4 nearest pointer pixels (smooth when it's made bigger)
                    for cy, wy in ((y0, 1 - (fy - y0)), (y0 + 1, fy - y0)):
                        for cx, wx in ((x0, 1 - (fx - x0)), (x0 + 1, fx - x0)):
                            if 0 <= cx < w and 0 <= cy < h and wx * wy:
                                v, part = pixels[cy * w + cx], wx * wy
                                total[0] += ((v >> 16) & 255) * part
                                total[1] += ((v >> 8) & 255) * part
                                total[2] += (v & 255) * part
                                total[3] += (v >> 24) * part
            if total[3] > 0.01:
                rgb = tuple(min(255.0, c * 255 / total[3]) for c in total[:3])
                layer[px, py] = (rgb, total[3] / (n * n * 255))
    return layer


def over(top, rgb, covered):
    """A pixel of the pointer (see pointer_layer) on top of a logo pixel (see logo_pixel)."""
    (trgb, ta) = top
    out = ta + covered * (1 - ta)
    if out <= 0:
        return rgb, 0.0
    mixed = tuple(round((t * ta + b * covered * (1 - ta)) / out) for t, b in zip(trgb, rgb))
    return mixed, out


class Logo(tk.Canvas):
    """The app's logo for the top of the sidebar: the penguin with its cursor, in the
    accent colour, and the name stacked next to it."""

    ICON = 42  # icon size in pixels
    GAP = 8    # space between icon and name

    def __init__(self, parent, font):
        f = tkfont.Font(font=font)
        height = max(self.ICON, f.metrics("linespace") * 2)
        width = self.ICON + self.GAP + max(f.measure("Auto"), f.measure("Clicker")) + 4
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0)
        self.font = font
        self.palette = None
        # the shapes don't change, only the colours do
        image = pointer_image()
        self.masks = logo_masks(self.ICON, arrow=image is None)
        self.pointer = pointer_layer(self.ICON, image) if image else {}
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
        colors = logo_colors(p["accent"])
        rows = []
        for y, row in enumerate(self.masks):
            down = (y + 0.5) / self.ICON
            pixels = []
            for x, parts in enumerate(row):
                rgb = logo_pixel(parts, colors, bg, down)[0]
                if (x, y) in self.pointer:
                    rgb = over(self.pointer[x, y], rgb, 1.0)[0]
                pixels.append("#%02x%02x%02x" % rgb)
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
        look = (round(self.pos, 3), track, p["bg"])
        if look != getattr(self, "drawn", None):  # only redo the pixels if it looks different
            self.drawn = look
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
            look = (fill, p["bg"], p["fg"] if hovered else p["border"], hovered, mark, mark_color)
            if not hasattr(self, "drawn"):
                self.drawn = {}
            if self.drawn.get(i) != look:  # only redo the pixels if it looks different
                self.drawn[i] = look
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


class ClickBadge(tk.Canvas):
    """A small circle in the accent colour with a macro click's label in it (L1, R2...),
    for the list on the Macros page. It's themed like the other widgets, so it changes
    with the accent colour."""

    SIZE = 30
    _images = {}  # (accent, background) -> the circle's picture, shared by every badge

    def __init__(self, parent, text, font, small_font):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, highlightthickness=0,
                         bd=0)
        self.image = None
        self.picture = self.create_image(0, 0, anchor="nw")
        self.label = self.create_text(self.SIZE / 2, self.SIZE / 2, text=text,
                                      font=font if len(text) <= 3 else small_font)

    def set_palette(self, palette):
        key = (palette["accent"], palette["bg"])
        image = self._images.get(key)
        if image is None:
            if len(self._images) > 40:  # (fading between colours makes lots of them)
                self._images.clear()
            image = self._images[key] = tk.PhotoImage(width=self.SIZE, height=self.SIZE)
            paint_dot(image, self.SIZE, palette["accent"], palette["bg"])
        self.image = image  # (kept here too, so it lasts while this badge shows it)
        self.configure(bg=palette["bg"])
        self.itemconfigure(self.picture, image=image)
        self.itemconfigure(self.label, fill=palette["accent_fg"])


_areas = {"when": 0.0, "areas": None, "busy": False}  # see screen_areas


def screen_areas():
    """[(x, y, w, h)] for each monitor, trimmed to the usable area (not under panels).

    Looking this up takes about a tenth of a second, so the answer is kept: after half a
    minute it's looked up again in the background (monitors can be plugged in), while the
    kept answer is used straight away."""
    if _areas["areas"] is None:
        _areas["areas"], _areas["when"] = read_screen_areas(), time.monotonic()
    elif time.monotonic() - _areas["when"] > 30 and not _areas["busy"]:
        _areas["busy"] = True

        def refresh():
            try:
                _areas["areas"], _areas["when"] = read_screen_areas(), time.monotonic()
            finally:
                _areas["busy"] = False

        threading.Thread(target=refresh, daemon=True).start()
    return list(_areas["areas"])


def read_screen_areas():
    """screen_areas without keeping the answer. Asks X directly (quick); if that doesn't
    work, runs xrandr and xprop instead (which can take a while)."""
    try:
        from Xlib import display as xdisplay, X
        d = xdisplay.Display()
        try:
            root = d.screen().root
            monitors = [(m.x, m.y, m.width_in_pixels, m.height_in_pixels)
                        for m in root.xrandr_get_monitors().monitors]
            prop = root.get_full_property(d.intern_atom("_NET_WORKAREA"), X.AnyPropertyType)
            work = list(prop.value[:4]) if prop is not None else None
        finally:
            d.close()
        if monitors:
            return trim_to_work_area(monitors, work)
    except Exception:
        pass
    return read_screen_areas_slowly()


def trim_to_work_area(monitors, work):
    """Each monitor's (x, y, w, h), minus any panel space outside the work area."""
    if not work:
        return monitors
    wx, wy, ww, wh = work
    trimmed = []
    for x, y, w, h in monitors or [(wx, wy, ww, wh)]:
        top, bottom = max(y, wy), min(y + h, wy + wh)
        left, right = max(x, wx), min(x + w, wx + ww)
        trimmed.append((left, top, right - left, bottom - top))
    return trimmed


def read_screen_areas_slowly():
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
        work = [int(v) for v in re.findall(r"\d+", out.split("=", 1)[1])[:4]]
        return trim_to_work_area(monitors, work)
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
        areas = screen_areas()
        x0, y0, w0, h0 = areas[0] if areas else (0, 0, 1280, 720)
        for x, y, w, h in areas:
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


def draw_shape(canvas, shape, color, width=2, dash=None, tags=""):
    p = shape["points"]
    if shape["type"] == "rectangle":
        return canvas.create_rectangle(*p, outline=color, width=width, dash=dash, tags=tags)
    if shape["type"] == "circle":
        return canvas.create_oval(*p, outline=color, width=width, dash=dash, tags=tags)
    return canvas.create_polygon(*p, outline=color, fill="", width=width, dash=dash, tags=tags)


def outline_rects(shape, pad=3, step=3):
    """Little squares covering a shape's outline (pad pixels either side of it), for
    cutting a window down to just the outline (see WindowShape)."""
    p = shape["points"]
    size = 2 * pad + 1
    if shape["type"] == "rectangle":
        x1, y1, x2, y2 = p
        w, h = x2 - x1 + size, y2 - y1 + size
        return [(x1 - pad, y1 - pad, w, size), (x1 - pad, y2 - pad, w, size),
                (x1 - pad, y1 - pad, size, h), (x2 - pad, y1 - pad, size, h)]
    if shape["type"] == "circle":
        cx, cy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2
        rx, ry = (p[2] - p[0]) / 2, (p[3] - p[1]) / 2
        n = max(24, int(2 * math.pi * max(rx, ry) / step))
        points = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n))
                  for i in range(n)]
        return [(int(x) - pad, int(y) - pad, size, size) for x, y in points]
    return line_rects(shape_corners(shape), closed=True, pad=pad, step=step)


def line_rects(points, closed=False, pad=3, step=3):
    """Little squares covering the lines between some points."""
    size, rects = 2 * pad + 1, []
    pairs = list(zip(points, points[1:] + (points[:1] if closed else [])))
    for (xa, ya), (xb, yb) in pairs:
        n = max(1, int(math.hypot(xb - xa, yb - ya) / step))
        for i in range(n + 1):
            x, y = xa + (xb - xa) * i / n, ya + (yb - ya) * i / n
            rects.append((int(x) - pad, int(y) - pad, size, size))
    return rects


def rounded_rects(x, y, w, h, r):
    """Rows of rectangles that together make a rounded rectangle."""
    rects = []
    for row in range(h):
        d = r - row - 0.5 if row < r else (row - (h - r) + 0.5 if row >= h - r else 0)
        inset = int(round(r - math.sqrt(max(r * r - d * d, 0)))) if d else 0
        if rects and rects[-1][4] == inset:
            rects[-1][3] += 1
        else:
            rects.append([x + inset, y + row, w - 2 * inset, 1, inset])
    return [tuple(r_[:4]) for r_ in rects]


class WindowShape:
    """Cuts a window down to some rectangles: it only shows there, and the screen behind
    shows everywhere else. The mouse goes straight through it to whatever is underneath.
    X11 shape extension. `ok` is False if this computer can't do it."""

    def __init__(self, window):
        self.ok = False
        try:
            import ctypes
            import ctypes.util
            self.ctypes = ctypes
            x11 = ctypes.CDLL(ctypes.util.find_library("X11"))
            xext = ctypes.CDLL(ctypes.util.find_library("Xext"))
        except (OSError, TypeError):
            return

        class Rect(ctypes.Structure):
            _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short),
                        ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]
        self.Rect = Rect
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XQueryTree.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
            ctypes.POINTER(ctypes.c_uint)]
        x11.XFree.argtypes = [ctypes.c_void_p]
        xext.XShapeCombineRectangles.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(Rect), ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.x11, self.xext = x11, xext
        self.display = x11.XOpenDisplay(None)
        if not self.display:
            return
        # Tk wraps each top-level window in an outer X window: cut that one too
        inner = window.winfo_id()
        root_id, parent = ctypes.c_ulong(), ctypes.c_ulong()
        children, count = ctypes.POINTER(ctypes.c_ulong)(), ctypes.c_uint()
        x11.XQueryTree(self.display, inner, ctypes.byref(root_id), ctypes.byref(parent),
                       ctypes.byref(children), ctypes.byref(count))
        if children:
            x11.XFree(children)
        self.targets = [inner]
        if parent.value and parent.value != root_id.value:
            self.targets.append(parent.value)
        self.ok = True

    def set(self, rects, width, height):
        if not self.ok:
            return
        R = self.Rect
        shown = (R * max(1, len(rects)))(*[R(int(x), int(y), max(0, int(w)), max(0, int(h)))
                                          for x, y, w, h in rects])
        nothing = (R * 1)(R(0, 0, 0, 0))
        for xid in self.targets:
            # 0 = what's shown (ShapeBounding), 2 = what catches the mouse (ShapeInput:
            # none of it); 0, 0: no offset, 0: replace (ShapeSet), 0: in no particular order
            self.xext.XShapeCombineRectangles(self.display, xid, 0, 0, 0, shown, len(rects), 0, 0)
            self.xext.XShapeCombineRectangles(self.display, xid, 2, 0, 0, nothing, 0, 0, 0)
        self.x11.XFlush(self.display)

    def close(self):
        if self.ok and self.display:
            self.x11.XCloseDisplay(self.display)
            self.display = None


class ScreenLayer(tk.Toplevel):
    """A see-through layer over the whole screen, with a menu at the top (the Areas and
    Macros menus). Only the menu, what's drawn and a thin frame round the screen show, so
    you can see what's behind.
    It's two windows: this one is invisible and catches the mouse everywhere, and `view`
    on top shows the drawing but lets the mouse through (a window cut down to what's drawn
    can only catch the mouse on that, see WindowShape).
    Anything drawn in the accent colour is tagged (see ACCENT_TAGS), so set_accent can
    recolour it when the accent colour changes."""

    EDGE = "#000000"    # dark edge round outlines, so they show on light screens too
    PANEL = "#1f1f1f"   # behind the menu and labels
    BAR_H, BAR_GAP = 34, 6
    ACCENT_TAGS = {  # tag: (option, colour worked out from the accent)
        "accent_fill": ("fill", lambda a: a),
        "accent_outline": ("outline", lambda a: a),
        "accent_edge": ("outline", lambda a: mix_color(a, "#000000", 0.5)),  # a darker shade
        "accent_ink": ("fill", text_on),  # text on the accent colour
    }

    def __init__(self, root, accent):
        super().__init__(root)
        self.accent = accent
        self.buttons = {}   # menu button name -> (x1, y1, x2, y2)
        self.bar_down = None
        self.regions = {}   # name -> rectangles of this layer that show (see show_regions)
        self.cutter = None
        self.width, self.height = self.winfo_screenwidth(), self.winfo_screenheight()
        # this window: over the whole screen, catching the mouse, all but invisible
        self.overrideredirect(True)
        self.no_shadow(self)
        self.geometry(f"{self.width}x{self.height}+0+0")
        self.configure(bg="#000000", cursor="crosshair")
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        # (Tk can only make a window see-through once it's on screen: do it the moment
        # it appears)
        self.bind("<Map>", lambda e: e.widget is self and self.attributes("-alpha", 0.01),
                  add="+")
        self.catcher = tk.Frame(self, bg="#000000", cursor="crosshair")
        self.catcher.pack(fill="both", expand=True)
        # the drawing on top, see-through except for what's drawn on it
        self.view = view = tk.Toplevel(self)
        view.overrideredirect(True)
        self.no_shadow(view)
        view.geometry(f"{self.width}x{self.height}+0+0")
        try:
            view.attributes("-topmost", True)
        except tk.TclError:
            pass
        # until it's been cut down to what's drawn, keep it invisible (no black flash)
        view.bind("<Map>", lambda e: e.widget is view and self.set_alpha(0.0), add="+")
        c = self.canvas = tk.Canvas(view, width=self.width, height=self.height, bg=self.PANEL,
                                    highlightthickness=0, bd=0, cursor="crosshair")
        c.pack(fill="both", expand=True)
        # the menu and messages go on the monitor the mouse is on
        mx, my = self.winfo_pointerxy()
        self.monitor = (0, 0, self.width, self.height)
        for x, y, w, h in screen_areas() or [self.monitor]:
            if x <= mx < x + w and y <= my < y + h:
                self.monitor = (x, y, w, h)
                break
        x, y, w, h = self.monitor
        self.top_middle = (x + w // 2, y + 24)
        self.draw_frame()

    def bind_mouse(self, **handlers):
        """Bind mouse events on both layers. (The mouse normally reaches the catcher, but
        if the drawing can't be made see-through it covers the screen and gets it itself.)"""
        for widget in (self.catcher, self.canvas):
            for sequence, handler in handlers.items():
                widget.bind(f"<{sequence.replace('_', '-')}>", handler)

    def show_now(self):
        """Put it on screen, cut down to what's drawn, and catch the mouse and keys."""
        # wait (up to 2 seconds) until both layers are on screen
        began = time.monotonic()
        while time.monotonic() - began < 2:
            self.update()
            if self.winfo_viewable() and self.view.winfo_viewable():
                break
            time.sleep(0.01)
        self.update_idletasks()
        self.cutter = WindowShape(self.view)
        if self.cutter.ok:
            self.show_regions()
            self.set_alpha(1.0)
        else:  # can't cut it down: dim the screen instead, so it can still be used
            self.set_alpha(0.45)
        self.view.lift()
        try:
            self.grab_set_global()
        except tk.TclError:
            pass
        self.focus_force()

    @staticmethod
    def no_shadow(window):
        """Mark it as a drag-and-drop window: the desktop draws no shadow round those. (It
        would otherwise draw one round every outline and dot: smudgy, and very slow.)"""
        try:
            window.attributes("-type", "dnd")
        except tk.TclError:
            pass

    def set_alpha(self, value):
        """How see-through the drawing layer is."""
        try:
            self.view.attributes("-alpha", value)
        except tk.TclError:
            pass

    def set_accent(self, accent):
        """Recolour everything drawn in the accent colour (the app's accent changed)."""
        if accent == self.accent:
            return
        self.accent = accent
        try:
            for tag, (option, color) in self.ACCENT_TAGS.items():
                self.canvas.itemconfigure(tag, **{option: color(accent)})
        except tk.TclError:
            pass  # (closing)

    def show_regions(self):
        """Show just the parts that have something on them (see WindowShape)."""
        if self.cutter is not None and self.cutter.ok:
            self.cutter.set([r for rects in self.regions.values() for r in rects],
                            self.width, self.height)

    def close(self):
        if self.cutter is not None:
            self.cutter.close()
        self.destroy()

    def draw_frame(self):
        """A thin accent-coloured frame round the monitor: the menu is open."""
        x, y, w, h = self.monitor
        t = 3
        self.canvas.create_rectangle(x, y, x + w, y + h, outline=self.accent, width=2 * t,
                                     tags=("frame", "accent_outline"))
        self.regions["frame"] = [(x, y, w, t), (x, y + h - t, w, t), (x, y, t, h),
                                 (x + w - t, y, t, h)]

    def draw_panel(self, x1, y1, x2, y2, tags, region):
        """A dark rounded panel (behind the menu, messages and labels)."""
        self.canvas.create_polygon(rounded_points(x1, y1, x2, y2, 10), smooth=True,
                                   fill=self.PANEL, outline="#444444", tags=tags)
        self.regions[region] = rounded_rects(int(x1), int(y1), int(x2 - x1) + 1,
                                             int(y2 - y1) + 1, 10)

    def draw_message(self, text):
        c = self.canvas
        item = c.create_text(self.top_middle[0], self.top_middle[1] + 16, text=text,
                             fill="#ffffff", font=("TkDefaultFont", 14, "bold"), tags="bar")
        x1, y1, x2, y2 = c.bbox(item)
        self.draw_panel(x1 - 16, y1 - 10, x2 + 16, y2 + 10, "bar", "bar")
        c.tag_raise(item)

    def draw_menu(self, names, labels, hint, chosen=None, gap_before=None, lit=None):
        """The menu at the top: a row of buttons (Done and `lit`, a switch that's on, in the
        accent colour, `chosen` in white) with a hint under them. gap_before: a little space
        before this button."""
        c = self.canvas
        c.delete("bar")
        font = ("TkDefaultFont", 12, "bold")
        widths = [tkfont.Font(font=font).measure(labels[n]) + 28 for n in names]
        extra = 18 if gap_before in names else 0
        total = sum(widths) + self.BAR_GAP * (len(names) - 1) + extra
        x, y = self.top_middle[0] - total // 2, self.top_middle[1]
        hint_item = c.create_text(self.top_middle[0], y + self.BAR_H + 20, text=hint,
                                  fill="#dddddd", font=("TkDefaultFont", 12), tags="bar")
        hx1, _hy1, hx2, hy2 = c.bbox(hint_item)
        left = min(x, hx1) - 12
        right = max(x + total, hx2) + 12
        self.draw_panel(left, y - 10, right, hy2 + 10, "bar", "bar")
        c.tag_raise(hint_item)
        self.buttons = {}
        for name, w in zip(names, widths):
            if name == gap_before:
                x += extra
            points = rounded_points(x, y, x + w, y + self.BAR_H, 9)
            if name in ("done", lit):
                c.create_polygon(points, smooth=True, fill=self.accent, outline="",
                                 tags=("bar", "accent_fill"))
                ink, tags = text_on(self.accent), ("bar", "accent_ink")
            else:
                c.create_polygon(points, smooth=True, outline="", tags="bar",
                                 fill="#ffffff" if name == chosen else "#3a3a3a")
                ink, tags = ("#000000" if name == chosen else "#ffffff"), "bar"
            c.create_text(x + w / 2, y + self.BAR_H / 2, text=labels[name], font=font,
                          fill=ink, tags=tags)
            self.buttons[name] = (x, y, x + w, y + self.BAR_H)
            x += w + self.BAR_GAP
        self.show_regions()

    def on_bar(self, event):
        """The menu button under the mouse, if any."""
        for name, (x1, y1, x2, y2) in self.buttons.items():
            if x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2:
                return name
        return None


class ShapeDrawer(ScreenLayer):
    """The Areas menu: a see-through layer over the whole screen for drawing an area's
    shapes (see ScreenLayer). The menu picks the shape (Rectangle, Circle, Triangle,
    Polygon), Clear takes every shape away, Undo takes back the last thing done, and Done
    (or Esc) finishes; it stays open in between, so you can draw as many as you like.
    Rectangles, circles and triangles: drag. Hold Shift for a square / round circle, and
    drag upwards for a triangle that points down. Polygons: click each corner, then
    double-click or press Enter (Backspace takes the last corner off).
    kind=None just shows the shapes and the spots that will be clicked (click to close).
    In order (on the menu) switches between clicking one shape after another and all of
    them together; while it's on, each shape shows its number.
    on_done(shapes, cleared, in_order) gets the new shapes when it closes, whether Clear
    took the area's old ones away, and whether In order is on."""

    OTHER = "#b0b0b0"  # the area's shapes from before
    NEW = "#ffffff"     # shapes drawn this time

    def __init__(self, root, kind, shapes, on_done=None, plan=None, gap=10, accent="#4a8fd9",
                 in_order=False):
        super().__init__(root, accent)
        self.kind, self.on_done, self.in_order = kind, on_done, in_order
        self.existing = list(shapes)
        self.added = []     # shapes drawn this time
        self.cleared = False  # Clear took the area's old shapes away
        self.history = []   # what Undo takes back: ("add",) or ("clear", added, cleared)
        self.start = None   # where a drag began
        self.corners = []   # polygon corners so far
        for shape in self.existing:
            self.draw_outline(shape, self.OTHER if kind else self.NEW, "existing")
        self.regions["existing"] = [r for s_ in self.existing for r in outline_rects(s_)]
        self.redraw_numbers()
        if kind is None:
            every = self.show_spots(plan, gap) if plan is not None else 1
            self.draw_message(
                "These are the spots it will click" + (
                    f" (every {every}{'nd' if every == 2 else 'rd' if every == 3 else 'th'} "
                    "one each way: they're close together)" if every > 1 else "")
                + "  ·  Click or press Esc to close")
            self.bind_mouse(ButtonRelease_1=lambda e: self.close())
            self.bind("<Escape>", lambda e: self.close())
        else:
            self.draw_bar()
            self.bind_mouse(
                ButtonPress_1=self.press, B1_Motion=self.drag, ButtonRelease_1=self.release,
                Double_Button_1=lambda e: self.kind == "polygon" and self.finish_polygon(),
                Motion=self.follow)
            self.bind("<Return>", lambda e: self.finish_polygon())
            self.bind("<KP_Enter>", lambda e: self.finish_polygon())
            self.bind("<BackSpace>", lambda e: self.undo())
            self.bind("<Escape>", lambda e: self.finish())
            self.bind("<ButtonRelease-3>", lambda e: self.finish())
        self.show_now()

    # ---- drawing ----
    def draw_outline(self, shape, color, tags):
        draw_shape(self.canvas, shape, self.EDGE, width=5, tags=tags)
        draw_shape(self.canvas, shape, color, width=2, tags=tags)

    def draw_bar(self):
        n = len(self.added)
        if self.kind == "polygon":
            hint = "Click each corner, then double-click or press Enter"
        else:
            hint = f"Drag to draw a {SHAPE_NAMES[self.kind].lower()}" + (
                "  ·  Shift: a perfect circle" if self.kind == "circle" else
                "  ·  Shift: a square" if self.kind == "rectangle" else
                "  ·  drag upwards to point it down" if self.kind == "triangle" else "")
        if self.cleared:
            hint += "  ·  cleared" + (f", then {n} added" if n else " (Undo brings them back)")
        elif n:
            hint += f"  ·  {n} {'shape' if n == 1 else 'shapes'} added"
        if self.in_order:
            hint += "  ·  in order: one shape after another"
        hint += "  ·  Done or Esc to finish"
        self.draw_menu(list(SHAPE_NAMES) + ["order", "clear", "undo", "done"],
                       dict(SHAPE_NAMES, order="In order: " + ("on" if self.in_order else "off"),
                            clear="Clear", undo="Undo", done="Done"), hint,
                       chosen=self.kind, gap_before="order", lit="order" if self.in_order
                       else None)

    def redraw_numbers(self):
        """While In order is on: each shape's number (the order they're clicked in) in a
        small accent-coloured circle on its top left corner."""
        c, r = self.canvas, 11
        c.delete("numbers")
        rects = []
        if self.in_order:
            shapes = ([] if self.cleared else self.existing) + self.added
            ink = text_on(self.accent)
            for n, shape in enumerate(shapes, start=1):
                x, y = shapes_box([shape])[:2]
                c.create_oval(x - r, y - r, x + r, y + r, fill=self.accent, outline=self.EDGE,
                              width=2, tags=("numbers", "accent_fill"))
                c.create_text(x, y, text=str(n), fill=ink, tags=("numbers", "accent_ink"),
                              font=("TkDefaultFont", 10 if n < 100 else 8, "bold"))
                rects += rounded_rects(x - r - 1, y - r - 1, 2 * r + 3, 2 * r + 3, r + 1)
        self.regions["numbers"] = rects
        c.tag_raise("numbers")
        c.tag_raise("bar")
        self.show_regions()

    def show_spots(self, plan, gap, most=2500):
        """A small dot in the accent colour on each spot. If they're very close together or
        there are very many, only every nth one each way, so it stays clear (returns n).
        (Each dot is a piece of the window's shape; with thousands of pieces the desktop
        draws it wrongly and slowly, so there are never more than `most`.)"""
        left, top = shapes_box(self.existing)[:2]
        every = max(1, math.ceil(10 / gap))  # dots at least 10 pixels apart
        while True:
            chosen = [(x, y) for y, xs in plan.rows if (y - top) // gap % every == 0
                      for x in xs if (x - left) // gap % every == 0]
            if len(chosen) <= most:
                break
            every += 1
        rects = []
        edge = self.ACCENT_TAGS["accent_edge"][1](self.accent)
        for x, y in chosen:  # an accent dot with a darker edge (shows on any screen)
            self.canvas.create_rectangle(x - 2, y - 2, x + 2, y + 2, fill=self.accent,
                                         outline=edge, tags=("accent_fill", "accent_edge"))
            rects.append((x - 2, y - 2, 5, 5))
        self.regions["spots"] = rects
        return every

    def bar_pressed(self, name):
        if name == "done":
            self.finish()
        elif name == "undo":
            self.undo()
        elif name == "clear":
            self.clear()
        elif name == "order":
            self.in_order = not self.in_order
            self.redraw_numbers()
            self.draw_bar()
        else:
            self.kind = name
            self.corners = []
            self.clear_new()
            self.draw_bar()

    def clear_new(self):
        self.canvas.delete("new")
        self.regions["new"] = []
        self.show_regions()

    def undo(self):
        """Take off the polygon's last corner, or else the last shape drawn (or Clear)."""
        if self.corners:
            self.corners.pop()
            self.redraw_polygon(self.winfo_pointerxy())
            return
        if not self.history:
            return
        step = self.history.pop()
        if step[0] == "add":
            self.added.pop()
        else:  # bring back what Clear took away
            self.added, self.cleared = step[1], step[2]
            self.redraw_existing()
        self.redraw_added()
        self.draw_bar()

    def clear(self):
        """Take every shape away: the area's old ones and the ones drawn this time."""
        if self.corners:
            self.corners = []
            self.clear_new()
        if not self.added and (self.cleared or not self.existing):
            return  # nothing to clear
        self.history.append(("clear", list(self.added), self.cleared))
        self.added, self.cleared = [], True
        self.redraw_existing()
        self.redraw_added()
        self.draw_bar()

    def redraw_existing(self):
        """The area's shapes from before (unless Clear took them away)."""
        self.canvas.delete("existing")
        shown = [] if self.cleared else self.existing
        for shape in shown:
            self.draw_outline(shape, self.OTHER, "existing")
        self.regions["existing"] = [r for s_ in shown for r in outline_rects(s_)]
        self.canvas.tag_raise("added")
        self.redraw_numbers()

    def redraw_added(self):
        self.canvas.delete("added")
        for shape in self.added:
            self.draw_outline(shape, self.NEW, "added")
        self.regions["added"] = [r for s_ in self.added for r in outline_rects(s_)]
        self.redraw_numbers()

    def add(self, shape):
        self.added.append(shape)
        self.history.append(("add",))
        self.clear_new()
        self.redraw_added()
        self.draw_bar()

    def finish(self):
        added, cleared = list(self.added), self.cleared
        self.close()
        if self.on_done:
            self.on_done(added, cleared, self.in_order)

    # ---- the mouse ----
    def press(self, event):
        # (a menu button works when it's let go of, like any button, so the release never
        # lands on the window underneath once Done has closed this)
        self.bar_down = self.on_bar(event)
        if self.bar_down:
            self.start = None
            return
        if self.kind != "polygon":
            self.start = (event.x_root, event.y_root)

    def drag(self, event):
        if self.start is None:
            return
        self.canvas.delete("new")
        shape = self.shape_from(event)
        self.regions["new"] = []
        if shape:
            self.draw_outline(shape, self.NEW, "new")
            left, top, right, bottom = shapes_box([shape])
            label_y = bottom + 22 if bottom + 44 < self.height else top - 22
            label = self.canvas.create_text((left + right) / 2, label_y, fill="#ffffff",
                                            text=f"{right - left} × {bottom - top}",
                                            font=("TkDefaultFont", 12, "bold"), tags="new")
            x1, y1, x2, y2 = self.canvas.bbox(label)
            self.canvas.create_rectangle(x1 - 6, y1 - 3, x2 + 6, y2 + 3, fill=self.PANEL,
                                         outline="", tags="new")
            self.canvas.tag_raise(label)
            self.regions["new"] = outline_rects(shape) + [(x1 - 6, y1 - 3, x2 - x1 + 13,
                                                           y2 - y1 + 7)]
        self.show_regions()

    def release(self, event):
        down, self.bar_down = self.bar_down, None
        if down or self.on_bar(event):
            if down and down == self.on_bar(event):
                self.bar_pressed(down)
            return
        if self.kind == "polygon":
            self.add_corner(event)
            return
        if self.start is None:
            return
        shape = self.shape_from(event)
        self.start = None
        if shape is None:
            self.clear_new()  # just a click, not a shape: keep waiting
            return
        left, top, right, bottom = shapes_box([shape])
        if min(right - left, bottom - top) < 2:
            self.clear_new()
            return
        self.add(shape)

    def shape_from(self, event):
        (x1, y1), x2, y2 = self.start, event.x_root, event.y_root
        if event.state & 0x1 and self.kind in ("rectangle", "circle"):  # Shift: even sides
            side = max(abs(x2 - x1), abs(y2 - y1))
            x2 = x1 + side * (1 if x2 >= x1 else -1)
            y2 = y1 + side * (1 if y2 >= y1 else -1)
        if self.kind == "triangle":
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)
            middle = (left + right) // 2
            points = ([middle, top, left, bottom, right, bottom] if y2 >= y1
                      else [left, top, right, top, middle, bottom])  # dragged up: points down
        else:
            points = [x1, y1, x2, y2]
        return clean_shape({"type": self.kind, "points": points})

    # ---- polygons: click the corners ----
    def add_corner(self, event):
        point = (event.x_root, event.y_root)
        if self.corners and self.corners[-1] == point:
            return  # (the second click of a double-click)
        self.corners.append(point)
        self.redraw_polygon(point)

    def follow(self, event):
        if self.kind == "polygon" and self.corners:
            self.redraw_polygon((event.x_root, event.y_root))

    def redraw_polygon(self, pointer):
        c = self.canvas
        c.delete("new")
        points = self.corners + [tuple(pointer)]
        line = [v for point in points for v in point]
        if len(line) >= 4:
            c.create_line(*line, fill=self.EDGE, width=5, tags="new")
            c.create_line(*line, fill=self.NEW, width=2, tags="new")
        for x, y in self.corners:
            c.create_oval(x - 5, y - 5, x + 5, y + 5, fill=self.NEW, outline=self.EDGE,
                          width=2, tags="new")
        self.regions["new"] = (line_rects(points) if len(points) > 1 else []) + [
            (x - 6, y - 6, 13, 13) for x, y in self.corners]
        c.tag_raise("bar")
        self.show_regions()

    def finish_polygon(self):
        if self.kind != "polygon":
            return
        shape = clean_shape({"type": "polygon",
                             "points": [v for point in self.corners for v in point]})
        if shape is None:
            return  # needs at least 3 corners
        if len(self.corners) == 3:
            shape["type"] = "triangle"
        self.corners = []
        self.add(shape)


class MacroRecorder(ScreenLayer):
    """The Macros menu: a see-through layer over the whole screen (see ScreenLayer) for
    choosing where a macro clicks. Click anywhere with the left, right or middle button to
    add that click there. Each click shows as a circle in the accent colour with its
    letter and number: L1 is a left click and the first click, R2 a right click and the
    second, and so on. Drag a circle to move it. Clear takes every click away, Undo takes
    back the last thing done, and Done (or Esc / Enter) finishes.
    show_only=True just shows the clicks (click to close).
    on_done(clicks) gets the macro's clicks when it closes."""

    R = 14           # the circles' radius
    MOVE_FROM = 5    # pixels: dragging a circle further than this moves it

    def __init__(self, root, clicks, on_done=None, accent="#4a8fd9", show_only=False):
        super().__init__(root, accent)
        self.clicks = [dict(c) for c in clicks]
        self.on_done = on_done
        self.history = []   # what Undo takes back: a copy of the clicks before each change
        self.down = None    # (button, x, y, index of the circle pressed on, or None)
        self.dragged = False
        self.redraw_clicks()
        if show_only:
            n = len(self.clicks)
            self.draw_message(f"The macro's {n} {'click' if n == 1 else 'clicks'}, in order"
                              "  ·  Click or press Esc to close")
            for number in (1, 2, 3):
                self.bind_mouse(**{f"ButtonRelease_{number}": lambda e: self.close()})
            self.bind("<Escape>", lambda e: self.close())
        else:
            self.draw_bar()
            for number in (1, 2, 3):
                self.bind_mouse(**{f"ButtonPress_{number}": self.press,
                                   f"B{number}_Motion": self.drag,
                                   f"ButtonRelease_{number}": self.release})
            self.bind("<BackSpace>", lambda e: self.undo())
            for key in ("<Escape>", "<Return>", "<KP_Enter>"):
                self.bind(key, lambda e: self.finish())
        self.show_now()

    # ---- drawing ----
    def spot_of(self, i):
        """Where click i's circle goes: on its spot, or beside it if an earlier click is
        on the same spot (a double click, say), so every label can be read."""
        click = self.clicks[i]
        same = sum(1 for c in self.clicks[:i]
                   if abs(c["x"] - click["x"]) <= 2 and abs(c["y"] - click["y"]) <= 2)
        return click["x"] + same * (2 * self.R + 4), click["y"]

    def redraw_clicks(self):
        c, r = self.canvas, self.R
        c.delete("clicks")
        rects = []
        font = ("TkDefaultFont", 10, "bold")
        small = ("TkDefaultFont", 8, "bold")
        ink = text_on(self.accent)
        # the arrows first, so the circles go over their ends (and leave room for the circles
        # in the window's shape)
        per_circle = len(rounded_rects(0, 0, 2 * r + 3, 2 * r + 3, r + 1))
        rects += self.draw_arrows(self.SHAPE_PIECES_MAX - per_circle * len(self.clicks))
        for i, click in enumerate(self.clicks):
            x, y = self.spot_of(i)
            c.create_oval(x - r, y - r, x + r, y + r, fill=self.accent, outline=self.EDGE,
                          width=2, tags=("clicks", "accent_fill"))
            label = macro_label(i, click)
            c.create_text(x, y, text=label, font=font if len(label) <= 3 else small,
                          fill=ink, tags=("clicks", "accent_ink"))
            rects += rounded_rects(x - r - 1, y - r - 1, 2 * r + 3, 2 * r + 3, r + 1)
        self.regions["clicks"] = rects
        c.tag_raise("bar")
        self.show_regions()

    ARROW_HEAD = (16, 9)    # the arrowheads' length and half width
    SHAPE_PIECES_MAX = 4000  # more pieces of the window's shape than this and the desktop
                             # draws it wrongly (see WindowShape): very many long arrows
                             # would need more, so the last ones aren't drawn

    def draw_arrows(self, most):
        """An arrow from each click's circle to the next one's (1 to 2, 2 to 3...), in the
        accent colour with a dark edge. Returns the rectangles that show them (at most
        `most`)."""
        c, rects = self.canvas, []
        length, half = self.ARROW_HEAD
        for i in range(len(self.clicks) - 1):
            (xa, ya), (xb, yb) = self.spot_of(i), self.spot_of(i + 1)
            d = math.hypot(xb - xa, yb - ya)
            gap = self.R + 5  # from just outside one circle to just outside the next
            if d < 2 * gap + length + 4:
                continue  # (too close together for an arrow to show)
            ux, uy = (xb - xa) / d, (yb - ya) / d
            start = (xa + ux * gap, ya + uy * gap)
            tip = (xb - ux * gap, yb - uy * gap)
            base = (tip[0] - ux * length, tip[1] - uy * length)
            head = [tip[0], tip[1], base[0] - uy * half, base[1] + ux * half,
                    base[0] + uy * half, base[1] - ux * half]
            line = [start, (base[0] + ux * 2, base[1] + uy * 2)]
            new = self.line_rects(line) + self.triangle_rects(head)
            if len(rects) + len(new) > most:
                break
            rects += new
            flat = [v for point in line for v in point]
            c.create_line(*flat, fill=self.EDGE, width=7, tags="clicks")
            c.create_line(*flat, fill=self.accent, width=3, tags=("clicks", "accent_fill"))
            c.create_polygon(head, fill=self.accent, outline=self.EDGE, width=2,
                             tags=("clicks", "accent_fill"))
        return rects

    @staticmethod
    def line_rects(points, pad=4, step=5):
        """Fewer rectangles than line_rects() for one thick line (7 pixels): squares along
        it, with squares in the same row (or column) joined into one, so a flat line
        needs very few."""
        (xa, ya), (xb, yb) = points
        flat = abs(xb - xa) >= abs(yb - ya)
        n = max(1, int(math.hypot(xb - xa, yb - ya) / step))
        size, rects = 2 * pad + 1, []
        for i in range(n + 1):
            x = int(round(xa + (xb - xa) * i / n)) - pad
            y = int(round(ya + (yb - ya) * i / n)) - pad
            if rects:
                lx, ly, lw, lh = rects[-1]
                if flat and y == ly:  # same row: make the last one longer
                    left = min(lx, x)
                    rects[-1] = (left, ly, max(lx + lw, x + size) - left, lh)
                    continue
                if not flat and x == lx:  # same column
                    top = min(ly, y)
                    rects[-1] = (lx, top, lw, max(ly + lh, y + size) - top)
                    continue
            rects.append((x, y, size, size))
        return rects

    @staticmethod
    def triangle_rects(points):
        """Rows of rectangles covering a triangle and a 2-pixel edge round it."""
        triangle = {"type": "triangle", "points": points}
        ys = points[1::2]
        top, bottom = math.floor(min(ys)), math.ceil(max(ys))
        rects = []
        for y in range(top - 2, bottom + 3):
            for a, b in shape_spans(triangle, min(max(y, top), bottom)):
                rects.append((math.floor(a) - 2, y, math.ceil(b - a) + 5, 1))
        return rects

    def draw_bar(self):
        n = len(self.clicks)
        hint = "Click where it should click (left, right or middle button)"
        if n:
            hint += "  ·  drag a circle to move it"
        hint += f"  ·  {n} {'click' if n == 1 else 'clicks'}"
        if n >= MACRO_MAX:
            hint += " (the most it can have)"
        hint += "  ·  Done or Esc to finish"
        self.draw_menu(["clear", "undo", "done"],
                       {"clear": "Clear", "undo": "Undo", "done": "Done"}, hint)

    def bar_pressed(self, name):
        if name == "done":
            self.finish()
        elif name == "undo":
            self.undo()
        elif name == "clear" and self.clicks:
            self.change(self.clicks.clear)

    # ---- changes ----
    def change(self, how):
        """Make a change to the clicks that Undo can take back."""
        self.history.append([dict(c) for c in self.clicks])
        how()
        self.redraw_clicks()
        self.draw_bar()

    def undo(self):
        if self.history:
            self.clicks = self.history.pop()
            self.redraw_clicks()
            self.draw_bar()

    def finish(self):
        clicks = list(self.clicks)
        self.close()
        if self.on_done:
            self.on_done(clicks)

    # ---- the mouse ----
    def circle_at(self, x, y):
        """The click whose circle is under the mouse (the top one), or None."""
        for i in reversed(range(len(self.clicks))):
            cx, cy = self.spot_of(i)
            if math.hypot(x - cx, y - cy) <= self.R + 2:
                return i
        return None

    def press(self, event):
        # (a menu button works when it's let go of, like any button, so the release never
        # lands on the window underneath once Done has closed this)
        on_bar = self.on_bar(event)
        if on_bar or self.down is not None or self.bar_down:
            if on_bar and event.num == 1 and self.down is None:
                self.bar_down = on_bar
            return
        x, y = event.x_root, event.y_root
        self.down = (event.num, x, y, self.circle_at(x, y))
        self.dragged = False

    def drag(self, event):
        if self.down is None or self.down[3] is None:
            return
        _button, x0, y0, i = self.down
        dx, dy = event.x_root - x0, event.y_root - y0
        if not self.dragged and math.hypot(dx, dy) <= self.MOVE_FROM:
            return
        if not self.dragged:  # starting to move it: Undo puts it back
            self.history.append([dict(c) for c in self.clicks])
            self.dragged = True
        was = self.history[-1][i]  # where it was before the drag
        self.clicks[i]["x"], self.clicks[i]["y"] = was["x"] + dx, was["y"] + dy
        self.redraw_clicks()

    def release(self, event):
        if self.bar_down and event.num == 1:
            name, self.bar_down = self.bar_down, None
            if name == self.on_bar(event):
                self.bar_pressed(name)
            return
        if self.down is None or self.down[0] != event.num:
            return
        number, x, y, _i = self.down
        self.down = None
        if self.dragged:
            self.dragged = False
            self.draw_bar()
            return
        if self.on_bar(event) or len(self.clicks) >= MACRO_MAX:
            return  # (let go on the menu: not a click)
        button = {1: "Left", 2: "Middle", 3: "Right"}[number]
        self.change(lambda: self.clicks.append({"button": button, "x": x, "y": y}))


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
        keep_above(self, parent)
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
        scroll = RoundedScrollbar(body, command=self.text.yview)
        scroll.set_palette(p)
        scroll.grid(row=1, column=1, sticky="ns", padx=(4, 0))
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


def keep_above(popup, parent):
    """A pop-up window stays in front of the app, even when the app is kept on top
    (Keep window on top, or mini mode): otherwise it could open hidden behind it."""
    popup.transient(parent)
    try:
        if parent.attributes("-topmost"):
            popup.attributes("-topmost", True)
    except tk.TclError:
        pass


class SmallDialog(tk.Toplevel):
    """A small window with a message, an optional name box, and buttons.

    With `name` (the starting text) it shows a text box; ok(text) is called with what was
    typed and returns an error message to show, or None to close. Without it, it's just a
    message with an OK button."""

    def __init__(self, parent, title, message, palette, ok_text="OK", name=None, ok=None):
        super().__init__(parent)
        p = palette
        self.ok = ok
        self.title(title)
        self.configure(bg=p["bg"])
        self.resizable(False, False)
        keep_above(self, parent)
        body = tk.Frame(self, bg=p["bg"], padx=18, pady=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        tk.Label(body, text=message, bg=p["bg"], fg=p["fg"], wraplength=340, justify="left",
                 anchor="w").grid(row=0, column=0, columnspan=2, sticky="ew")
        self.name = None
        if name is not None:
            self.name = tk.StringVar(value=name)
            entry = RoundedEntry(body, self.name, on_enter=self.confirm, width=340)
            entry.set_palette(p)
            entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            entry.entry.select_range(0, "end")
            self.after(50, entry.entry.focus_set)
        self.message = tk.Label(body, text="", bg=p["bg"], fg=p["muted"], anchor="w",
                                wraplength=340, justify="left")
        self.message.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.message.grid_remove()  # only shown when there's something to say
        buttons = []
        if name is not None:
            buttons.append(RoundedButton(body, "Cancel", self.destroy, height=34))
        done = RoundedButton(body, ok_text, self.confirm, height=34, selectable=True, accent=True)
        buttons.append(done)
        for column, button in enumerate(buttons):
            button.set_palette(p)
            button.grid(row=3, column=column, columnspan=2 if len(buttons) == 1 else 1,
                        sticky="ew", pady=(12, 0),
                        padx=0 if len(buttons) == 1 else ((0, 5) if column == 0 else (5, 0)))
        done.set_selected(True)
        self.bind("<Escape>", lambda e: self.destroy())
        if name is None:
            self.bind("<Return>", lambda e: self.confirm())
        # in the middle of the app window
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.focus_force()

    def confirm(self):
        problem = self.ok(self.name.get() if self.name else None) if self.ok else None
        if problem:
            self.message.configure(text=problem)
            self.message.grid()
        else:
            self.destroy()


def render_cap(image, w, h, top, color, bg_color, samples=4):
    """Draw one rounded end of a scroll bar thumb (a half circle `w` wide, `h` tall) into
    a PhotoImage, with smooth edges. `top` picks the upper or the lower end."""
    bg = [int(bg_color[i:i + 2], 16) for i in (1, 3, 5)]
    fg = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    r = w / 2
    cy = h if top else 0  # the circle's centre is where the cap meets the straight part
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            hits = 0
            for sy in range(samples):
                for sx in range(samples):
                    px = x + (sx + 0.5) / samples
                    py = y + (sy + 0.5) / samples
                    if (px - r) ** 2 + (py - cy) ** 2 <= r * r:
                        hits += 1
            a = hits / samples ** 2
            row.append("#%02x%02x%02x" % tuple(round(b + (f - b) * a) for b, f in zip(bg, fg)))
        rows.append("{" + " ".join(row) + "}")
    image.put(" ".join(rows))


class RoundedScrollbar(tk.Canvas):
    """A thin scroll bar with a rounded (pill-shaped) handle. It gets a little wider and
    darker while the mouse is over it. Works like ttk.Scrollbar: give it `command`
    (e.g. a canvas's yview) and set the scrolled widget's yscrollcommand to its `set`."""

    WIDTH = 10        # room it takes up
    THIN, WIDE = 6, 8  # handle width normally / with the mouse over it
    MIN_LENGTH = 28   # the handle never gets shorter than this
    GAP = 1           # space above and below the handle

    def __init__(self, parent, command):
        super().__init__(parent, width=self.WIDTH, highlightthickness=0, bd=0)
        self.command = command
        self.palette = None
        self.first, self.last = 0.0, 1.0
        self.hover = False
        self.drag_offset = None  # where on the handle it was grabbed, while dragging
        self.caps = {}  # (width, colour, bg) -> (top image, bottom image)
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", lambda e: self.set_hover(True))
        self.bind("<Leave>", lambda e: self.set_hover(False))
        self.bind("<ButtonPress-1>", self.press)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.configure(bg=palette["bg"])
        self.caps.clear()
        self.redraw()

    def set_hover(self, on):
        self.hover = on
        self.redraw()

    def handle(self):
        """Top and bottom of the handle, in pixels."""
        h = self.winfo_height() - 2 * self.GAP
        span = max(0.0, min(1.0, self.last - self.first))
        length = min(h, max(self.MIN_LENGTH, span * h))
        room = h - length
        top = room * self.first / (1 - span) if span < 1 else 0
        top = self.GAP + max(0, min(room, top))
        return top, top + length

    def press(self, event):
        top, bottom = self.handle()
        if top <= event.y <= bottom:
            self.drag_offset = event.y - top
        else:  # clicked above or below the handle: go one page that way
            self.command("scroll", -1 if event.y < top else 1, "pages")
        self.redraw()

    def drag(self, event):
        if self.drag_offset is None:
            return
        top, bottom = self.handle()
        room = self.winfo_height() - 2 * self.GAP - (bottom - top)
        if room <= 0:
            return
        span = self.last - self.first
        place = (event.y - self.drag_offset - self.GAP) / room
        self.command("moveto", max(0.0, min(1.0, place)) * (1 - span))

    def release(self, event):
        self.drag_offset = None
        x, y = event.x, event.y
        self.hover = 0 <= x < self.winfo_width() and 0 <= y < self.winfo_height()
        self.redraw()

    def cap_images(self, width, color, bg):
        key = (width, color, bg)
        if key not in self.caps:
            h = width // 2
            images = []
            for top in (True, False):
                image = tk.PhotoImage(width=width, height=h)
                render_cap(image, width, h, top, color, bg)
                images.append(image)
            self.caps[key] = tuple(images)
        return self.caps[key]

    def redraw(self):
        self.delete("all")
        if not self.palette or self.winfo_height() < 2 * self.MIN_LENGTH:
            return
        p = self.palette
        active = self.hover or self.drag_offset is not None
        width = self.WIDE if active else self.THIN
        # easy to spot on both light and dark pages, and a bit stronger under the mouse
        color = (mix_color(p["muted"], p["fg"], 0.35) if active
                 else mix_color(p["border"], p["muted"], 0.6))
        top, bottom = round(self.handle()[0]), round(self.handle()[1])
        x = (self.winfo_width() - width) // 2
        cap = width // 2
        top_cap, bottom_cap = self.cap_images(width, color, p["bg"])
        self.create_image(x, top, image=top_cap, anchor="nw")
        self.create_rectangle(x, top + cap, x + width, bottom - cap,
                              fill=color, outline="")
        self.create_image(x, bottom - cap, image=bottom_cap, anchor="nw")


class ScrollArea(ttk.Frame):
    """A page area that scrolls when its contents are taller than the window. Put things in
    `self.inner`. The thin scroll bar only shows when it's needed; the mouse wheel works
    anywhere over the area."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, yscrollincrement=1)
        self.bar = RoundedScrollbar(self, command=self.bar_moved)
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.palette = None
        self.bar_job = None  # see update_scroll
        self.glide_job = None    # the mouse wheel's smooth scrolling, see glide_by
        self.glide_target = 0.0  # where it's heading (pixels from the top)
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
        try:
            if event.widget.winfo_toplevel() is not self.winfo_toplevel():
                return  # over a dropdown list or another window, not this page
        except (AttributeError, tk.TclError):
            return
        if any(isinstance(w, DropdownPopup) for w in self.winfo_toplevel().winfo_children()):
            return  # a dropdown list is open: leave the page where it is
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self.glide_by(-self.WHEEL_STEP)
        else:
            self.glide_by(self.WHEEL_STEP)

    WHEEL_STEP = 60   # pixels per notch of the mouse wheel
    GLIDE_MS = 10     # time between frames of the glide

    def bar_moved(self, *args):
        """The scroll bar was dragged or clicked: that wins over any wheel glide."""
        if self.glide_job is not None:
            self.after_cancel(self.glide_job)
            self.glide_job = None
        self.canvas.yview(*args)

    def glide_by(self, pixels):
        """Scroll smoothly: each frame covers part of the way left, so it starts quick and
        eases to a stop. Turning the wheel again while it moves adds on to where it's heading."""
        height = self.inner.winfo_reqheight()
        most = max(0, height - self.canvas.winfo_height())
        now = self.canvas.yview()[0] * height
        start = self.glide_target if self.glide_job is not None else now
        self.glide_target = min(max(start + pixels, 0), most)
        if self.glide_job is None:
            self.glide_step()

    def glide_step(self):
        height = max(1, self.inner.winfo_reqheight())
        now = self.canvas.yview()[0] * height
        left = self.glide_target - now
        if abs(left) < 1:
            self.canvas.yview_moveto(self.glide_target / height)
            self.glide_job = None
            return
        step = left * 0.3
        if abs(step) < 1:
            step = 1 if left > 0 else -1
        self.canvas.yview_moveto((now + step) / height)
        if abs(self.canvas.yview()[0] * height - now) < 0.5:
            self.glide_job = None  # can't go any further (e.g. the page got shorter)
            return
        self.glide_job = self.after(self.GLIDE_MS, self.glide_step)

    def set_palette(self, palette):
        self.palette = palette
        self.canvas.configure(bg=palette["bg"])
        self.bar.set_palette(palette)


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


class Pointer:
    """Moves the mouse pointer for replays and set click spots, in a way games understand.

    Games that lock the mouse (first-person cameras, like Roblox) turn the camera by how
    far the mouse *moves*, and ignore where the pointer is. So move_by() sends real mouse
    movement, and place() puts the pointer on a spot without sending any movement (if it
    did, the game would see the jump as one huge flick and spin the camera)."""

    def __init__(self):
        self.display = None
        self.root = None
        self.broken = False  # no X connection: fall back to pynput
        self.fallback = None

    def connect(self):
        if self.display is None and not self.broken:
            try:
                from Xlib import display as xdisplay
                from Xlib.ext import xtest  # noqa: F401  (makes sure it's there)
                self.display = xdisplay.Display()
                self.root = self.display.screen().root
            except Exception as err:
                print(f"Moving the mouse the simple way ({err})")
                self.broken = True
                self.fallback = mouse.Controller()
        return self.display

    def move_by(self, dx, dy):
        if not dx and not dy:
            return
        if self.connect() is None:
            self.fallback.move(dx, dy)
            return
        from Xlib import X
        from Xlib.ext import xtest
        xtest.fake_input(self.display, X.MotionNotify, detail=1, x=int(dx), y=int(dy))
        self.display.sync()

    def position(self):
        """Where the pointer is now."""
        if self.connect() is None:
            return tuple(int(v) for v in self.fallback.position)
        reply = self.root.query_pointer()
        return reply.root_x, reply.root_y

    def click_at(self, x, y, button, count, back):
        """Jump to x, y, click `button` (1 left, 2 middle, 3 right) `count` times, and jump
        back to `back`, all in one go. One connection keeps them in order, so it only has
        to wait once at the end (much quicker than waiting after each step). Returns False
        if it can't (then click the slower way)."""
        if self.connect() is None:
            return False
        from Xlib import X
        from Xlib.ext import xtest
        self.root.warp_pointer(int(x), int(y))
        for _ in range(count):
            xtest.fake_input(self.display, X.ButtonPress, button)
            xtest.fake_input(self.display, X.ButtonRelease, button)
        self.root.warp_pointer(int(back[0]), int(back[1]))
        self.display.sync()
        return True

    def place(self, x, y):
        if self.connect() is None:
            self.fallback.position = (x, y)
            return
        self.root.warp_pointer(int(x), int(y))
        # wait until it has really moved: clicks go through a different connection, and
        # could otherwise land before the pointer gets there
        self.display.sync()


class RawMotion:
    """Hears how far the mouse itself moves (X11 "raw motion"), not just where the pointer
    is. When a game locks the mouse it keeps the pointer still, or it gets stuck at the edge
    of the screen, so its position stops changing; the raw movement still comes through.
    Our own fake movement (from the "XTEST" device) is ignored.

    on_move(dx, dy) and on_idle() are called on this listener's own thread."""

    def __init__(self, on_move, on_idle):
        self.on_move = on_move
        self.on_idle = on_idle
        self.display = None
        self.devices = {}  # device id -> True if its movement should be recorded
        self.running = False

    def start(self):
        """Start listening. Returns False if this computer can't do it."""
        try:
            from Xlib import display as xdisplay
            from Xlib.ext import xinput
            self.display = xdisplay.Display()
            if not self.display.has_extension("XInputExtension"):
                raise RuntimeError("no XInput extension")
            # Say we speak XInput 2.2: from 2.1 on, raw movement keeps coming while a
            # game has grabbed the mouse (with 2.0 the game gets it all to itself)
            xinput.XIQueryVersion(display=self.display.display,
                                  opcode=self.display.display.get_extension_major(xinput.extname),
                                  major_version=2, minor_version=2)
            self.display.screen().root.xinput_select_events(
                [(xinput.AllMasterDevices, xinput.RawMotionMask)])
            self.load_devices()
            self.display.flush()
        except Exception as err:
            print(f"Recording mouse movement by position only ({err})")
            self.close()
            return False
        self.running = True
        threading.Thread(target=self.run, daemon=True).start()
        return True

    def stop(self):
        self.running = False  # the thread notices within a few milliseconds

    def close(self):
        if self.display is not None:
            try:
                self.display.close()
            except Exception:
                pass
            self.display = None

    def load_devices(self):
        from Xlib.ext import xinput
        self.devices = {}
        for dev in self.display.xinput_query_device(xinput.AllDevices).devices:
            name = dev.name.decode(errors="replace") if isinstance(dev.name, bytes) else dev.name
            axes = {c.number: c.mode for c in dev.classes if c.type == xinput.ValuatorClass}
            # Only real mice/touchpads: not our own fake input, and not tablets or touch
            # screens, which report where you touch rather than how far you moved
            self.devices[dev.deviceid] = ("XTEST" not in name
                                          and axes.get(0) == 0 and axes.get(1) == 0)

    def run(self):
        import select
        from Xlib.ext import xinput
        try:
            while self.running:
                select.select([self.display], [], [], 0.01)
                while self.running and self.display.pending_events():
                    event = self.display.next_event()
                    if getattr(event, "evtype", None) == xinput.RawMotion:
                        self.handle(event.data)
                self.on_idle()
        except Exception as err:
            print(f"Stopped listening to raw mouse movement: {err}")
        finally:
            self.close()

    def handle(self, data):
        """Read one raw motion event: which device, and its x/y movement."""
        import struct
        source, mask_len = struct.unpack_from("=HH", data, 10)
        if source not in self.devices:
            self.load_devices()  # a mouse was plugged in
            self.devices.setdefault(source, False)  # (only look it up once)
        if not self.devices.get(source):
            return
        mask = int.from_bytes(data[22:22 + 4 * mask_len], "little")
        axes = [i for i in range(32 * mask_len) if mask >> i & 1]
        # after the mask: each axis's processed value, then each axis's raw value
        # (8 bytes each: a whole number, then a fraction out of 2**32)
        start = 22 + 4 * mask_len + 8 * len(axes)
        moved = {}
        for n, axis in enumerate(axes):
            whole, frac = struct.unpack_from("=iI", data, start + 8 * n)
            moved[axis] = whole + frac / 2 ** 32
        dx, dy = moved.get(0, 0.0), moved.get(1, 0.0)
        if dx or dy:
            self.on_move(dx, dy)


class AutoClicker:
    SYNTHETIC_WINDOW = 0.03  # seconds: presses this soon after our own click/press are ours
    REPEAT_WINDOW = 0.2      # seconds: the same key again this soon is a duplicate/held key
    MOVE_TOLERANCE = 10      # pixels: auto stop ignores mouse wobbles smaller than this
    QUICK_REPEAT = 0.1       # seconds: the same key/button again this soon is recorded once

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Clicker")
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(*MIN_SIZE)
        # See-through while it's laid out, so it appears all at once (see reveal). Tk can
        # only do that once the window exists on screen, so it's done the moment it appears.
        self.root.bind("<Map>", self.hide_until_ready, add="+")
        self.set_window_icon()

        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self.pointer = Pointer()  # moves the pointer during replays (see Pointer)
        self.replay_pos = None    # where the replay last put the pointer
        self.running = threading.Event()   # set while clicking/pressing/replaying
        self.stopped = threading.Event()   # set by stop(), wakes the worker from its wait
        self.shutdown = threading.Event()
        self.events = queue.Queue()
        self.settings = {}
        self.clicks = 0
        self.armed = False  # True during start delay or while running
        self.started_at = 0.0     # when clicking began (for "stop after a set time")
        self.round_widgets = []  # every custom-drawn widget, so the theme can reach them
        self.subtitles_to_fit = []  # see fit_subtitles
        self.quick_exit = False     # see on_close (main() turns it on)
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
        self.home_pos = None      # where area clicks put the mouse back to (see tap)
        self.own_windows = []     # where the app's own windows are (see note_own_windows)
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
        # mouse movement waiting to be recorded (one "move" at most every move_sample)
        self.move_sample = ACCURACY["High"]  # seconds, set by the accuracy when recording
        self.motion_lock = threading.RLock()
        self.raw_motion = None        # RawMotion listener, while recording movement
        self.record_pos = None        # where the pointer is
        self.record_dx = self.record_dy = 0.0  # how far the mouse moved since the last move
        self.record_moved = False     # something above changed since the last move
        self.record_pressed = set()   # buttons/keys pressed since recording began
        self.record_skipped = set()   # pressed again too quickly: left out, with their release
        self.record_last_press = {}   # input code -> when it was last recorded as pressed
        self.record_keep_repeats = False
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
        self.area = list(saved["area"])            # the shapes "Click across an area" clicks
        self.area_plan = None                      # AreaPlan for self.area, see area_plan_now
        self.shape_rows = []                       # the Areas page's list of shapes
        self.clear_shapes_job = None               # "Sure?" on Clear all, see clear_shapes
        self.area_choice = tk.StringVar(value=next(iter(list_areas()), ""))  # saved areas list
        self.area_name = tk.StringVar()            # the "Save these shapes as" box
        self.macro = list(saved["macro"])          # the macro's clicks, in order
        self.click_rows = []                       # the Macros page's list of clicks
        self.clear_macro_job = None                # "Sure?" on Clear all, see clear_macro
        self.macro_choice = tk.StringVar(value=next(iter(list_macros()), ""))
        self.macro_name = tk.StringVar()           # the "Save these clicks as" box
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
        if on_wayland():
            self.root.after(600, self.warn_wayland)
        # look up the monitors now, so the first dropdown opens straight away
        threading.Thread(target=screen_areas, daemon=True).start()
        if self.check_updates.get():
            self.root.after(4000, self.look_for_update)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll()
        self.root.after(0, self.reveal)

    REVEAL_SETTLE_MS = 120  # how long to let the layout settle once the window is on screen

    def hide_until_ready(self, event):
        if event.widget is self.root and not getattr(self, "revealed", False):
            self.revealed = True
            if not self.mini.get():
                self.set_alpha(0.0)

    def reveal(self, waited=0):
        """Show the window (it starts see-through) once it's on screen and everything in it
        is laid out and drawn, so the buttons don't pop in one by one."""
        if self.mini.get():
            return  # mini mode fades itself in once it's ready (see apply_mini)
        if not getattr(self, "revealed", False) and waited < 5000:
            self.root.after(20, lambda: self.reveal(waited + 20))
            return
        self.root.update_idletasks()
        self.root.after(self.REVEAL_SETTLE_MS,
                        lambda: (self.root.update_idletasks(), self.set_alpha(1.0)))

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
        self.font_title = tkfont.Font(family=family, size=FONT_SIZE + 5, weight="bold")
        self.font_brand = tkfont.Font(family=family, size=FONT_SIZE + 1, weight="bold")
        self.font_section = tkfont.Font(family=family, size=FONT_SIZE + 1, weight="bold")
        self.font_caption = tkfont.Font(family=family, size=FONT_SIZE - 1, weight="bold")
        self.font_badge_small = tkfont.Font(family=family, size=FONT_SIZE - 3, weight="bold")
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
        self.area_on = tk.BooleanVar(value=saved["area_on"] and not saved["location_on"])
        self.area_gap = tk.IntVar(value=saved["area_gap"])
        self.area_return = tk.BooleanVar(value=saved["area_return"])
        self.area_in_order = tk.BooleanVar(value=saved["area_in_order"])
        self.multi_location = tk.BooleanVar(value=saved["multi_location"])
        self.hold = tk.BooleanVar(value=saved["hold"])
        # Macros
        self.macro_wait = tk.DoubleVar(value=saved["macro_wait"])
        self.macro_delay = tk.DoubleVar(value=saved["macro_delay"])
        self.macro_loop = tk.BooleanVar(value=saved["macro_loop"])
        self.macro_limit_on = tk.BooleanVar(value=saved["macro_limit_on"])
        self.macro_limit = tk.IntVar(value=saved["macro_limit"])
        self.macro_return = tk.BooleanVar(value=saved["macro_return"])
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
        self.record_repeats = tk.BooleanVar(value=saved["record_repeats"])
        self.record_accuracy = tk.StringVar(value=saved["record_accuracy"])
        self.replay_speed = tk.DoubleVar(value=saved["replay_speed"])
        # Profiles
        self.profile_name = tk.StringVar()
        self.profile_choice = tk.StringVar(value=next(iter(list_profiles()), ""))
        self.profile_hotkey = tk.StringVar(value="")  # hotkey of the chosen profile
        # Settings
        self.hotkey = tk.StringVar(value=saved["hotkey"])
        self.location_key = tk.StringVar(value=saved["location_key"])
        self.record_key = tk.StringVar(value=saved["record_key"])
        self.draw_key = tk.StringVar(value=saved["draw_key"])
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
        self.countdown = tk.BooleanVar(value=saved["countdown"])
        self.check_updates = tk.BooleanVar(value=saved["check_updates"])
        self.newer_version = None  # (tag, page) once a newer release has been found
        self.begin_at = 0.0  # when the start delay ends (for the countdown)
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
            "replay_speed": self.replay_speed,
            "record_keys_only": self.record_keys_only, "record_moves": self.record_moves,
            "record_repeats": self.record_repeats, "record_accuracy": self.record_accuracy,
            "multi_location": self.multi_location,
            "area_on": self.area_on, "area_gap": self.area_gap,
            "area_return": self.area_return, "area_in_order": self.area_in_order,
            "macro_wait": self.macro_wait, "macro_delay": self.macro_delay,
            "macro_loop": self.macro_loop, "macro_limit_on": self.macro_limit_on,
            "macro_limit": self.macro_limit, "macro_return": self.macro_return,
        }

        # Apply the starting colours instantly (no animation on launch)
        self.style.theme_use("clam")
        self.apply_palette(build_palette(saved["dark_mode"], saved["accent"]))

        self.hotkey.trace_add("write", lambda *_: self.refresh_button())
        self.location_key.trace_add("write", lambda *_: self.refresh_location())
        self.record_key.trace_add("write", lambda *_: self.refresh_recording_info())
        self.draw_key.trace_add("write", lambda *_: self.refresh_draw_button())
        self.on_top.trace_add("write", lambda *_: self.apply_on_top())
        self.badge_show.trace_add("write", lambda *_: (self.refresh_running(),
                                                        self.show_optional_rows(),
                                                        self.save_settings()))
        self.badge_corner.trace_add("write", lambda *_: (self.refresh_running(),
                                                          self.save_settings()))
        self.profile_choice.trace_add("write", lambda *_: self.show_profile_hotkey())
        self.finish_sound.trace_add("write", lambda *_: self.save_settings())
        self.countdown.trace_add("write", lambda *_: (self.refresh_running(),
                                                       self.save_settings()))
        self.check_updates.trace_add("write", lambda *_: self.save_settings())
        self.text_size.trace_add("write", lambda *_: (self.apply_text_size(), self.save_settings()))
        self.profile_hotkey.trace_add("write", lambda *_: self.on_profile_hotkey_set())
        for var in (self.location_on, self.multi_location):
            var.trace_add("write", lambda *_: self.refresh_location())
        # Click at a set location and Click across an area can't both be on
        self.location_on.trace_add("write", lambda *_: self.location_on.get()
                                   and self.area_on.get() and self.area_on.set(False))
        self.area_on.trace_add("write", lambda *_: self.area_on.get()
                               and self.location_on.get() and self.location_on.set(False))
        for var in (self.area_on, self.area_gap, self.area_in_order):
            var.trace_add("write", lambda *_: self.refresh_area())
        for var in (self.macro_wait, self.macro_loop, self.macro_limit_on, self.macro_limit):
            var.trace_add("write", lambda *_: self.refresh_macro())
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
        pages = (("clicker", "Mouse"), ("areas", "Areas"), ("macros", "Macros"),
                 ("keyboard", "Keyboard"), ("recording", "Profiles"), ("settings", "Settings"))
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
        self.build_areas_page(self.pages["areas"])
        self.build_macros_page(self.pages["macros"])
        self.build_keyboard_page(self.pages["keyboard"])
        self.build_recording_page(self.pages["recording"])
        self.build_settings_page(self.pages["settings"])
        self.mini_frame = ttk.Frame(self.root, padding=MINI_MARGIN, style="Edge.TFrame")
        self.build_mini_view(self.mini_frame)
        self.fit_subtitles()

        for var in (self.click_delay_on, self.limit_on, self.time_limit_on, self.location_on,
                    self.multi_location, self.hold, self.kb_limit_on, self.kb_time_limit_on,
                    self.kb_hold, self.replay_loop, self.replay_limit_on, self.record_keys_only,
                    self.record_moves, self.area_on, self.macro_loop, self.macro_limit_on):
            var.trace_add("write", lambda *_: self.show_optional_rows())
        self.show_optional_rows()

        self.show_page()
        self.refresh_profile_list()
        self.refresh_button()
        self.refresh_location()
        self.refresh_area()
        self.refresh_macro()
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

    def fit_subtitles(self):
        """Give each row's grey text room for the box next to it (see card_row)."""
        def width(box):
            # A box's width is known straight away, except a frame of buttons, which only
            # knows once the whole window is laid out (slow): add up its buttons instead
            kids = box.winfo_children()
            if box.winfo_reqwidth() > 1 or not kids:
                return box.winfo_reqwidth()
            return sum(width(k) for k in kids) + 10 * (len(kids) - 1)

        for row, box, subtitle, has_switch in self.subtitles_to_fit:
            wrap = max(200, 400 - width(box) - (48 if has_switch else 0))
            subtitle.configure(wraplength=wrap)
            row.parts["wrap"] = wrap
        self.subtitles_to_fit = []

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

    def make_combo(self, parent, variable, values, width=FIELD_WIDTH, max_items=None):
        combo = self.register(RoundedCombo(parent, variable, values, width=width))
        combo.max_items = max_items  # (fewer than all of them: the list scrolls)
        return combo

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
        # (8: the label's own padding sits outside its wrap width)
        label.master.bind("<Configure>", lambda e: label.configure(
            wraplength=max(150, min(most, e.width - reserve - 8))), add="+")
        return label

    def button_group(self, parent, buttons):
        """Small buttons side by side, for the end of a card row."""
        frame = tk.Frame(parent, bd=0, highlightthickness=0, bg=self.palette["card"])
        self.card_frames.append(frame)
        for i, (text, command, *width) in enumerate(buttons):  # (text, command[, width])
            self.make_button(frame, text, command, height=28, width=(width or [64])[0]).grid(
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
                # (worked out in fit_subtitles once everything is built: measuring each box
                # now would lay out the whole window again for every row)
                self.subtitles_to_fit.append((row, box, subtitle_label, variable is not None))

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
        # (measured with the label's own font: making a new font object for it is slow)
        width = int(title.tk.call("font", "measure", title.cget("font") or "TkDefaultFont",
                                  title.cget("text")))
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
            ("Clicks per second", lambda p: self.make_spin(p, self.cps, 0.1, MAX_CPS, 1),
             lambda: clicking() and not self.click_delay_on.get()),
            ("Wait (seconds)", lambda p: self.make_spin(p, self.click_delay, 0.001, 3600, 0.5),
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
        # Click across an area: the shapes are set up on the Areas page
        _, self.area_hint, _ = self.card_row(
            card, "Click across an area", self.area_on, subtitle="",
            value=lambda p: self.button_group(p, [("Edit", lambda: self.go_to("areas"))]),
            show=clicking)

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

    def build_areas_page(self, frame):
        """Shapes drawn on the screen; the mouse clicker clicks every spot inside them."""
        sub = self.page_body(frame, "Areas")
        draw = self.draw_btn = self.make_button(sub, "Draw shapes", self.draw_new_shape,
                                                height=FIELD_HEIGHT + 4, selectable=True,
                                                accent=True)
        draw.set_selected(True)  # the main thing to press here: in the accent colour
        self.refresh_draw_button()
        draw.grid(row=1, column=0, sticky="ew")
        self.flow_label(ttk.Label(
            sub, style="Muted.TLabel", justify="left", wraplength=500,
            text="Opens a menu at the top of your screen (its key works anywhere, even in a "
                 "game): pick Rectangle, Circle, Triangle or Polygon and draw on the screen, as "
                 "many as you like, then press Done. "
                 "Every spot inside your shapes gets clicked, row by row.")).grid(
            row=2, column=0, sticky="w", pady=(6, 0))

        # the shapes so far, each with a Remove button (see refresh_shape_list)
        ttk.Label(sub, text="Shapes", style="Caption.TLabel").grid(
            row=3, column=0, sticky="w", pady=(14, 5))
        self.shapes_card = self.register(Card(sub))
        self.shapes_card.grid(row=4, column=0, sticky="ew")
        shape_buttons = ttk.Frame(sub)
        shape_buttons.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        shape_buttons.columnconfigure(0, weight=1)
        shape_buttons.columnconfigure(1, weight=1)
        self.make_button(shape_buttons, "Show spots", self.show_spots,
                         height=FIELD_HEIGHT).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.clear_shapes_btn = self.make_button(shape_buttons, "Clear all", self.clear_shapes,
                                                 height=FIELD_HEIGHT)
        self.clear_shapes_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        card = self.card_section(sub, 6, "Clicking")
        _, self.area_info, _ = self.card_row(card, "Click across this area", self.area_on,
                                             subtitle="")
        self.card_row(card, "Gap between clicks (pixels)",
                      subtitle="Smaller means more clicks, closer together",
                      value=lambda p: self.make_spin(p, self.area_gap, AREA_GAP_MIN,
                                                     AREA_GAP_MAX, 1))
        self.card_row(card, "Put the mouse back after each click", self.area_return,
                      subtitle="It jumps to each spot, clicks and jumps straight back, so the "
                               "mouse stays where you left it and you can keep using it")
        self.card_row(card, "In order", self.area_in_order,
                      subtitle="Click every spot in shape 1, then shape 2, and so on, instead "
                               "of all the shapes together row by row. Also on the drawing menu.")
        # ---- saving areas, the same way as profiles ----
        self.libraries = {}
        self.build_saved_section(sub, 8, "area", "Save these shapes as", "Area name",
                                 "Saved areas", "No areas yet", self.area_choice,
                                 self.area_name, list_areas, area_path, read_area, write_area,
                                 current=lambda: ((self.area, self.area_gap_value(),
                                                   bool(self.area_in_order.get()))
                                                  if self.area else None),
                                 apply=self.apply_area, empty="Add a shape first",
                                 folder=areas_dir)

        self.area_toggle_btn = self.make_button(frame, "", self.toggle, height=42,
                                                selectable=True, accent=True)
        self.area_toggle_btn.grid(row=2, column=0, sticky="ew", pady=(14, 0))

    def build_saved_section(self, sub, row, kind, save_text, placeholder, list_text,
                            none_yet, choice, name, names, path, read, write, current, apply,
                            empty, folder):
        """The bottom of the Areas and Macros pages: save what's there now under a name,
        then load, rename, duplicate or delete saved ones (like profiles). Uses grid rows
        `row` to `row + 4`. How each kind is read and written goes in self.libraries."""
        ttk.Label(sub, text=save_text).grid(row=row, column=0, sticky="w", pady=(16, 4))
        save_row = ttk.Frame(sub)
        save_row.grid(row=row + 1, column=0, sticky="ew", pady=(0, 10))
        save_row.columnconfigure(0, weight=1)
        self.register(RoundedEntry(save_row, name, placeholder,
                                   on_enter=lambda: self.save_saved(kind))).grid(
            row=0, column=0, sticky="ew")
        self.make_button(save_row, "Save", lambda: self.save_saved(kind), height=FIELD_HEIGHT,
                         width=90).grid(row=0, column=1, padx=(10, 0))
        ttk.Label(sub, text=list_text).grid(row=row + 2, column=0, sticky="w", pady=(0, 4))
        load_row = ttk.Frame(sub)
        load_row.grid(row=row + 3, column=0, sticky="ew")
        combo = self.make_combo(load_row, choice, names())
        combo.placeholder = none_yet
        combo.grid(row=0, column=0, columnspan=4, sticky="ew")
        actions = [("Load", self.load_saved), ("Rename", self.rename_saved),
                   ("Duplicate", self.duplicate_saved), ("Delete", self.delete_saved)]
        for column, (text, command) in enumerate(actions):
            load_row.columnconfigure(column, weight=1, uniform=f"{kind}_buttons")
            button = self.make_button(load_row, text, lambda c=command: c(kind),
                                      height=FIELD_HEIGHT, width=70)
            button.grid(row=1, column=column, sticky="ew", pady=(8, 0),
                        padx=(0 if column == 0 else 5, 0 if column == 3 else 5))
        where = ttk.Frame(sub)
        where.grid(row=row + 4, column=0, sticky="ew", pady=(8, 0))
        where.columnconfigure(0, weight=1)
        where_label = self.flow_label(
            ttk.Label(where, text="", style="Muted.TLabel", justify="left", wraplength=360),
            reserve=130, most=360)  # leaves room for the Open folder button
        where_label.grid(row=0, column=0, sticky="w")
        self.make_button(where, "Open folder", lambda: self.open_folder(folder()),
                         height=FIELD_HEIGHT, width=110).grid(row=0, column=1, padx=(10, 0))
        self.libraries[kind] = {
            "a": "an area" if kind == "area" else f"a {kind}",  # "Type an area name first"
            "choice": choice, "name": name, "list": names, "path": path, "read": read,
            "write": write, "current": current, "apply": apply, "empty": empty,
            "combo": combo, "delete_btn": button, "delete_job": None, "where": where_label}

    def build_macros_page(self, frame):
        """A macro: clicks set on the screen, clicked one after another in order."""
        sub = self.page_body(frame, "Macros")
        record = self.make_button(sub, "Record clicks", self.record_macro,
                                  height=FIELD_HEIGHT + 4, selectable=True, accent=True)
        record.set_selected(True)  # the main thing to press here: in the accent colour
        record.grid(row=1, column=0, sticky="ew")
        self.flow_label(ttk.Label(
            sub, style="Muted.TLabel", justify="left", wraplength=500,
            text="Opens a menu at the top of your screen: click anywhere with the left, right "
                 "or middle mouse button to add a click there, as many as you like, then "
                 "press Done. They're clicked one after another, in order: L1 is a left click "
                 "and the first one, R2 a right click and the second.")).grid(
            row=2, column=0, sticky="w", pady=(6, 0))

        # the clicks so far, in order, each with a Remove button (see refresh_click_list)
        ttk.Label(sub, text="Clicks", style="Caption.TLabel").grid(
            row=3, column=0, sticky="w", pady=(14, 5))
        self.clicks_card = self.register(Card(sub))
        self.clicks_card.grid(row=4, column=0, sticky="ew")
        click_buttons = ttk.Frame(sub)
        click_buttons.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        click_buttons.columnconfigure(0, weight=1)
        click_buttons.columnconfigure(1, weight=1)
        self.make_button(click_buttons, "Show clicks", self.show_macro,
                         height=FIELD_HEIGHT).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.clear_macro_btn = self.make_button(click_buttons, "Clear all", self.clear_macro,
                                                height=FIELD_HEIGHT)
        self.clear_macro_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        card = self.card_section(sub, 6, "Playing")
        _, self.macro_info, _ = self.card_row(
            card, "Wait between clicks (seconds)", subtitle="",
            value=lambda p: self.make_spin(p, self.macro_wait, MACRO_WAIT_MIN, MACRO_WAIT_MAX,
                                           0.1))
        self.card_row(card, "Start delay (seconds)",
                      value=lambda p: self.make_spin(p, self.macro_delay, 0, 60, 1))
        self.card_row(card, "Play on a loop", self.macro_loop,
                      subtitle="Start again from the first click after the last one")
        self.card_row(card, "Stop after a number of plays", self.macro_limit_on,
                      value=lambda p: self.make_spin(p, self.macro_limit, 1, 1000000, 1),
                      value_show=self.macro_limit_on.get, show=self.macro_loop.get)
        self.card_row(card, "Put the mouse back after each click", self.macro_return,
                      subtitle="It jumps to each spot, clicks and jumps straight back, so the "
                               "mouse stays where you left it and you can keep using it")
        self.build_saved_section(sub, 8, "macro", "Save these clicks as", "Macro name",
                                 "Saved macros", "No macros yet", self.macro_choice,
                                 self.macro_name, list_macros, macro_path, read_macro,
                                 write_macro,
                                 current=lambda: ((self.macro, self.macro_wait_value())
                                                  if self.macro else None),
                                 apply=self.apply_macro, empty="Record some clicks first",
                                 folder=macros_dir)

        self.macro_toggle_btn = self.make_button(frame, "", self.toggle, height=42,
                                                 selectable=True, accent=True)
        self.macro_toggle_btn.grid(row=2, column=0, sticky="ew", pady=(14, 0))

    def build_keyboard_page(self, frame):
        sub = self.page_body(frame, "Keyboard")
        pressing = lambda: not self.kb_hold.get()

        self.field_columns(sub, 2, [
            ("Key to press",
             lambda p: self.make_key_chooser(p, self.kb_key, "Keyboard clicker",
                                             is_keyboard_key, combos=True),
             None),
            ("Presses per second", lambda p: self.make_spin(p, self.kb_cps, 0.1, MAX_CPS, 1), pressing),
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
        self.profile_combo = self.make_combo(load_row, self.profile_choice, list_profiles())
        self.profile_combo.placeholder = "No profiles yet"
        self.profile_combo.grid(row=0, column=0, columnspan=4, sticky="ew")
        actions = [("Load", self.load_profile), ("Rename", self.rename_profile),
                   ("Duplicate", self.duplicate_profile), ("Delete", self.delete_profile)]
        for column, (text, command) in enumerate(actions):
            load_row.columnconfigure(column, weight=1, uniform="profile_buttons")
            button = self.make_button(load_row, text, command, height=FIELD_HEIGHT, width=70)
            button.grid(row=1, column=column, sticky="ew", pady=(8, 0),
                        padx=(0 if column == 0 else 5, 0 if column == 3 else 5))
        self.delete_btn = button

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
        self.card_row(card, "Accuracy",
                      subtitle="How smoothly mouse movement is recorded. Higher is smoother "
                               "but makes bigger profiles",
                      value=lambda p: self.make_combo(p, self.record_accuracy, list(ACCURACY),
                                                      width=KEY_FIELD_WIDTH, max_items=4),
                      show=lambda: not self.record_keys_only.get() and self.record_moves.get())
        self.card_row(card, "Keep quick repeats", self.record_repeats,
                      subtitle="When off, the same key or button pressed twice within "
                               f"{self.QUICK_REPEAT:g} seconds is only recorded once")

        card = self.card_section(sub, 13, "Playing it back")
        self.card_row(card, "Loop", self.replay_loop, subtitle="Keep playing until you stop it")
        self.card_row(card, "Stop after a number of plays", self.replay_limit_on,
                      value=lambda p: self.make_spin(p, self.replay_limit, 1, 100000, 1),
                      value_show=self.replay_limit_on.get, show=self.replay_loop.get)
        self.card_row(card, "Speed", subtitle="2 is twice as fast, 0.5 is half speed",
                      value=lambda p: self.make_spin(p, self.replay_speed, SPEED_MIN,
                                                     SPEED_MAX, 0.25))

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
            ("CPS", lambda p: self.make_spin(p, self.cps, 0.1, MAX_CPS, 1),
             lambda: clicking() and not self.click_delay_on.get()),
            ("Wait (s)", lambda p: self.make_spin(p, self.click_delay, 0.001, 3600, 0.5),
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
            ("Draw shapes key",
             lambda p: self.make_key_chooser(p, self.draw_key, "Draw shapes"), None),
        ], columns=4)
        self.flow_label(ttk.Label(
            sub, text="Click a box, then press a key or mouse button. Esc cancels.\n"
                      "In the app, Ctrl+1 to Ctrl+6 switch pages and Ctrl+Tab goes to the "
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
        self.card_row(card, "Start countdown", self.countdown,
                      subtitle="Count down the start delay (3, 2, 1) on the badge and in this window")
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
        _, self.areas_where_card, _ = self.card_row(
            card, "Areas folder", subtitle="",
            value=lambda p: self.button_group(p, [
                ("Open", lambda: self.open_folder(AREAS_DIR)),
                ("Move", lambda: self.move_folder("areas"))]))
        _, self.macros_where_card, _ = self.card_row(
            card, "Macros folder", subtitle="",
            value=lambda p: self.button_group(p, [
                ("Open", lambda: self.open_folder(MACROS_DIR)),
                ("Move", lambda: self.move_folder("macros"))]))

        card = self.card_section(sub, 10, "About")
        _, self.version_text, _ = self.card_row(
            card, f"Auto Clicker v{APP_VERSION}", subtitle="",
            value=lambda p: self.button_group(p, [("GitHub page", self.open_github, 100)]))
        self.card_row(card, "Check for updates", self.check_updates,
                      subtitle="Looks on GitHub for a newer version when the app opens",
                      value=lambda p: self.button_group(p, [
                          ("Check now", lambda: self.look_for_update(quiet=False), 84)]))
        self.refresh_version_text()

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
        if not self.menu_is_vertical() and not self.mini_shown:
            self.set_bar_height(self.bar_height)  # (a wider bar: the window keeps room for it)
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
        """Ctrl+1 to Ctrl+6 go to a page; Ctrl+Tab / Ctrl+Shift+Tab go to the next / previous."""
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
        elif name == "areas":
            self.refresh_saved_list("area")
        elif name == "macros":
            self.refresh_saved_list("macro")
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
                          (self.area_toggle_btn, "mouse"),
                          (self.macro_toggle_btn, "macro"),
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
            what = {"mouse": "mouse clicker", "macro": "macro", "keyboard": "keyboard clicker",
                    "replay": "recording"}[self.active_mode]
            return False, "Ready", f"{input_name(self.hotkey.get())} starts the {what}"
        s = self.settings
        title = s.get("title", "Running")
        if not self.running.is_set():
            title = self.starting_text()
        return True, title, s.get("details", "")

    def starting_text(self):
        """During the start delay: "Starting in 3" counting down (or "Starting in 5s")."""
        if self.countdown.get():
            left = max(1, math.ceil(self.begin_at - time.monotonic() - 0.001))
            return f"Starting in {left}"
        return f"Starting in {self.settings.get('delay', 0):g}s"

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
            if s["speed"] != 1:
                parts.append(f"{s['speed']:g}x speed")
        elif s["mode"] == "macro":
            title = "Playing macro"
            n = len(s["macro"])
            plays = {0: "on a loop", 1: "once"}.get(s["plays"], f"{s['plays']} times")
            parts = [f"{n} {'click' if n == 1 else 'clicks'}", plays,
                     f"every {s['interval']:g}s"]
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
            if s.get("area"):
                parts.append(f"area of {s['area'].count:,} spots")
            elif spots > 1:
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
        if s.get("mode") == "macro":
            n, plays = len(s["macro"]), s["plays"]
            if self.clicks:
                parts.append(f"click {(self.clicks - 1) % n + 1} of {n}")
                if plays != 1:
                    play = (self.clicks - 1) // n + 1
                    parts.append(f"play {play} of {plays}" if plays else f"play {play}")
        elif s.get("limit"):
            parts.append(f"{self.clicks} of {s['limit']} {s['unit'][1]}")
        if s.get("time_limit"):
            elapsed = time.monotonic() - self.started_at if self.running.is_set() else 0
            parts.append(f"{clock(max(0.0, s['time_limit'] - elapsed))} left")
        if s.get("area") and self.clicks:
            count = s["area"].count
            parts.append(f"spot {(self.clicks - 1) % count + 1:,} of {count:,}")
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

    def warn_wayland(self):
        SmallDialog(self.root, "Wayland session",
                    "You're using a Wayland session, where Auto Clicker can't click or press "
                    "keys in most apps.\n\nTo use it, log out, click the gear icon at the "
                    "bottom right of the login screen, choose the option with \"Xorg\" in its "
                    "name, then log in again.", self.palette)

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
        for window in self.root.winfo_children():
            if isinstance(window, ScreenLayer):  # the Areas or Macros menu, if it's open
                window.set_accent(p["accent"])
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
            in_use = code in self.app_keys()
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
                "area": list(self.area),
                "macro": list(self.macro),
                "recording": self.recording,
                "hotkey": self.hotkey.get(),
                "location_key": self.location_key.get(),
                "record_key": self.record_key.get(),
                "draw_key": self.draw_key.get(),
                "auto_stop": bool(self.auto_stop.get()),
                "always_on_top": bool(self.on_top.get()),
                "mini_mode": bool(self.mini.get()),
                "mini_position": list(self.mini_position),
                "sidebar_side": self.sidebar_side.get(),
                "active_mode": self.active_mode,
                "badge_show": self.badge_show.get(),
                "badge_corner": self.badge_corner.get(),
                "finish_sound": bool(self.finish_sound.get()),
                "countdown": bool(self.countdown.get()),
                "check_updates": bool(self.check_updates.get()),
                "text_size": self.text_size.get(),
                "sidebar_width": self.sidebar_width,
                "bar_height": self.bar_height,
                "dark_mode": bool(self.dark.get()),
                "accent": self.accent.get(),
            })
            for name in ("limit", "kb_limit", "macro_limit"):
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
            "record_key": self.record_key, "draw_key": self.draw_key,
            "auto_stop": self.auto_stop, "always_on_top": self.on_top, "mini_mode": self.mini,
            "badge_show": self.badge_show, "badge_corner": self.badge_corner,
            "sidebar_side": self.sidebar_side,
            "finish_sound": self.finish_sound, "countdown": self.countdown,
            "check_updates": self.check_updates,
            "text_size": self.text_size,
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

    def app_keys(self):
        """The keys the app itself uses (start/stop, set location, record, draw shapes)."""
        return (self.hotkey.get(), self.location_key.get(), self.record_key.get(),
                self.draw_key.get())

    def profile_hotkey_allowed(self, code):
        return is_valid_input(code) and code not in self.app_keys()

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

    def chosen_profile(self):
        """The profile picked in the list, or None (with a message) if there isn't one."""
        name = self.profile_choice.get()
        if not name or not profile_path(name).exists():
            self.status.config(text="Pick a profile first")
            self.refresh_profile_list()
            return None
        return name

    def check_new_name(self, typed, old=None):
        """(name, problem): the profile name to use, or why it can't be used."""
        name = safe_profile_name(typed or "")
        if not name:
            return None, "Type a name first."
        taken = [n for n in list_profiles() if n.lower() == name.lower() and n != old]
        if taken:
            return None, f"There's already a profile called {taken[0]}."
        return name, None

    def rename_profile(self):
        old = self.chosen_profile()
        if old is None:
            return

        def ok(typed):
            new, problem = self.check_new_name(typed, old)
            if problem:
                return problem
            if new == old:
                return None
            ok_read, recording = read_profile(old)
            if not ok_read or not write_profile(new, recording, read_profile_hotkey(old)):
                return f"Couldn't rename {old}."
            if new.lower() != old.lower():  # (same file if only the capitals changed)
                try:
                    profile_path(old).unlink()
                except OSError:
                    pass
            if self.recording_name == old:
                self.recording_name = new
                self.save_current_recording()
                self.refresh_recording_info()
            self.refresh_profile_list(select=new)
            self.status.config(text=f"Renamed {old} to {new}")
            return None

        SmallDialog(self.root, "Rename profile", f"New name for {old}:", self.palette,
                    ok_text="Rename", name=old, ok=ok)

    def duplicate_profile(self):
        old = self.chosen_profile()
        if old is None:
            return
        suggestion, n = f"{old} copy", 2
        while profile_path(suggestion).exists():
            suggestion, n = f"{old} copy {n}", n + 1

        def ok(typed):
            new, problem = self.check_new_name(typed)
            if problem:
                return problem
            ok_read, recording = read_profile(old)
            # the copy has no hotkey: one key can only play one profile
            if not ok_read or not write_profile(new, recording, None):
                return f"Couldn't copy {old}."
            self.refresh_profile_list(select=new)
            self.status.config(text=f"Copied {old} to {new}")
            return None

        SmallDialog(self.root, "Duplicate profile", f"Name for the copy of {old}:",
                    self.palette, ok_text="Duplicate", name=suggestion, ok=ok)

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

    # ---------------- Updates ----------------
    def refresh_version_text(self):
        if self.newer_version:
            text = f"{self.newer_version[0]} is out: open the GitHub page to get it"
        else:
            text = "Made with AI (Claude). Free and open source (MIT licence)."
        self.version_text.configure(text=text)

    def look_for_update(self, quiet=True):
        """Ask GitHub for its newest release, on a background thread (the answer comes back
        through the event queue, see poll). quiet: only say something if there's an update."""
        if not quiet:
            self.status.config(text="Checking for updates...")

        def check():
            try:
                tag, page = latest_release()
                self.events.put(("update", tag, page, quiet))
            except Exception as err:
                print(f"Couldn't check for updates: {err}")
                self.events.put(("update", None, None, quiet))

        threading.Thread(target=check, daemon=True).start()

    def got_update_answer(self, tag, page, quiet):
        if tag is None:
            if not quiet:
                self.status.config(text="Couldn't check for updates (no internet?)")
            return
        newest, ours = version_numbers(tag), version_numbers(APP_VERSION)
        if newest and ours and newest > ours:
            self.newer_version = (tag, page)
            self.refresh_version_text()
            self.status.config(text=f"{tag} is out: see Settings > About")
        elif not quiet:
            self.status.config(text=f"You have the newest version (v{APP_VERSION})")

    def open_github(self):
        page = self.newer_version[1] if self.newer_version else GITHUB_PAGE
        try:
            subprocess.Popen(["xdg-open", page], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            self.status.config(text="Couldn't open the web page")

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
        self.areas_where_card.config(text=short_path(AREAS_DIR))
        self.libraries["area"]["where"].config(
            text=f"An area is a set of saved shapes. Each one is a .txt file in "
                 f"{short_path(areas_dir())}.")
        self.macros_where_card.config(text=short_path(MACROS_DIR))
        self.libraries["macro"]["where"].config(
            text=f"A macro is a set of saved clicks. Each one is a .txt file in "
                 f"{short_path(macros_dir())}.")

    def move_folder(self, kind):
        """Move the settings, profiles, areas or macros folder somewhere else (Settings >
        Storage)."""
        global SETTINGS_PATH, PROFILES_DIR, AREAS_DIR, MACROS_DIR
        current = {"settings": SETTINGS_PATH.parent, "profiles": PROFILES_DIR,
                   "areas": AREAS_DIR, "macros": MACROS_DIR}[kind]
        marker = {"settings": SETTINGS_MARKER, "profiles": PROFILES_MARKER,
                  "areas": AREAS_MARKER, "macros": MACROS_MARKER}[kind]
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
            target = chosen / {"settings": "Auto Clicker settings",
                               "profiles": "Auto Clicker profiles",
                               "areas": "Auto Clicker areas",
                               "macros": "Auto Clicker macros"}[kind]
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
        elif kind == "profiles":
            PROFILES_DIR = target
            mark_folder(target, PROFILES_MARKER, "profiles")
        elif kind == "areas":
            AREAS_DIR = target
            mark_folder(target, AREAS_MARKER, "saved areas")
            self.refresh_saved_list("area")
        else:
            MACROS_DIR = target
            mark_folder(target, MACROS_MARKER, "saved macros")
            self.refresh_saved_list("macro")
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
        self.record_exclude = {*self.app_keys(), "key:esc", *self.profile_hotkeys}
        self.record_keys = bool(self.record_keys_only.get())
        self.record_movement = bool(self.record_moves.get()) and not self.record_keys
        self.record_from_button = from_button
        self.recording_buf = []
        self.record_pressed = set()
        self.record_skipped = set()
        self.record_last_press = {}
        self.record_keep_repeats = bool(self.record_repeats.get())
        self.move_sample = ACCURACY.get(self.record_accuracy.get(), ACCURACY["High"])
        with self.motion_lock:
            self.record_last_move = 0.0
            self.record_dx = self.record_dy = 0.0
            self.record_moved = False
            try:
                x, y = self.mouse.position
                self.record_pos = (int(x), int(y))
            except Exception:
                self.record_pos = None
        if self.record_movement:
            self.raw_motion = RawMotion(lambda dx, dy: self.note_motion(dx=dx, dy=dy),
                                        self.flush_motion_later)
            if not self.raw_motion.start():
                self.raw_motion = None  # positions only, like before
        self.record_t0 = time.monotonic()
        self.recording_active = True
        self.status.config(text="Recording...")
        self.refresh_recording_info()

    def stop_recording(self, from_button=False):
        self.flush_motion()
        self.recording_active = False
        if self.raw_motion is not None:
            self.raw_motion.stop()
            self.raw_motion = None
        actions = list(self.recording_buf)
        self.recording_buf = []

        def in_window(action):
            if action[1] not in ("move", "press", "release", "scroll") or not self.record_rect:
                return False
            x, y = action[{"move": 2, "press": 3, "release": 3, "scroll": 4}[action[1]]:][:2]
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
        with self.motion_lock:
            if action[0] != "move":
                self.flush_motion()  # the movement before a click comes before the click
            t = round(time.monotonic() - self.record_t0, 3)
            self.recording_buf.append([t, *action])

    def note_motion(self, x=None, y=None, dx=0.0, dy=0.0):
        """The pointer moved to x, y, and/or the mouse moved dx, dy (from RawMotion).
        Recorded as a "move" at most every move_sample seconds (see ACCURACY)."""
        if not (self.recording_active and self.record_movement):
            return
        with self.motion_lock:
            if x is not None:
                self.record_pos = (int(x), int(y))
            self.record_dx += dx
            self.record_dy += dy
            self.record_moved = True
            if time.monotonic() - self.record_last_move >= self.move_sample:
                self.flush_motion()

    def flush_motion_later(self):
        """RawMotion's idle check: record movement that's been waiting long enough."""
        if self.record_moved and time.monotonic() - self.record_last_move >= self.move_sample:
            self.flush_motion()

    def flush_motion(self):
        """Record the movement waiting since the last "move", if there is any."""
        with self.motion_lock:
            if not self.record_moved or self.record_pos is None:
                return
            self.record_moved = False
            self.record_last_move = time.monotonic()
            x, y = self.record_pos
            if self.raw_motion is None:
                self.record_event("move", x, y)
                return
            dx, dy = round(self.record_dx), round(self.record_dy)
            self.record_dx -= dx  # keep the leftover fraction for next time
            self.record_dy -= dy
            last = next((a for a in reversed(self.recording_buf) if a[1] == "move"), None)
            if dx or dy or last is None or last[2:4] != [x, y]:
                self.record_event("move", x, y, dx, dy)

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
                speed = min(max(float(self.replay_speed.get()), SPEED_MIN), SPEED_MAX)
                self.settings = {
                    "mode": "replay", "hold": False, "actions": actions, "plays": plays,
                    "speed": speed,
                    "label": label, "limit": 0, "time_limit": 0,
                    "delay": 0.0, "locations": None, "codes": set(),
                }
            elif mode == "macro":
                if not self.macro:
                    self.status.config(text="Record some clicks first")
                    return False
                clicks = [(BUTTONS[c["button"]], c["x"], c["y"]) for c in self.macro]
                if not self.macro_loop.get():
                    plays = 1
                elif self.macro_limit_on.get():
                    plays = max(1, int(self.macro_limit.get()))
                else:
                    plays = 0  # forever
                self.settings = {
                    "mode": "macro", "hold": False, "macro": clicks, "plays": plays,
                    "codes": {input_code(button) for button, _x, _y in clicks},
                    "count": 1,
                    "interval": self.macro_wait_value(),
                    "limit": plays * len(clicks),  # 0: never stop
                    "time_limit": 0,
                    "delay": min(max(0.0, float(self.macro_delay.get())), 60.0),
                    "locations": None,
                    "area_return": bool(self.macro_return.get()),
                    "unit": ("click", "clicks"),
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
                    "interval": 1.0 / min(max(0.1, float(self.kb_cps.get())), MAX_CPS),
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
                    interval = max(1.0 / MAX_CPS, float(self.click_delay.get()))
                else:
                    interval = 1.0 / min(max(0.1, float(self.cps.get())), MAX_CPS)
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
                                  if self.location_on.get() and self.locations
                                  and not self.area_on.get() else None),
                    # every spot in the area's shapes, see AreaPlan
                    "area": self.area_plan_now() if self.area_on.get() and not hold else None,
                    "area_box": shapes_box(self.area) if self.area else None,
                    "area_return": bool(self.area_return.get()),
                    "unit": ("click", "clicks"),
                }
            # replays move the mouse themselves, so auto stop would stop them straight away
            self.settings["auto_stop"] = bool(self.auto_stop.get()) and mode != "replay"
        except (tk.TclError, ValueError, KeyError):
            self.status.config(text="Invalid setting. Check the numbers.")
            return False
        if (mode == "mouse" and self.area_on.get() and not self.settings["hold"]
                and not self.settings.get("area")):
            self.status.config(text="Add a shape on the Areas page first")
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

    # ---------------- Areas ----------------
    def area_gap_value(self):
        try:
            return min(max(int(self.area_gap.get()), AREA_GAP_MIN), AREA_GAP_MAX)
        except (tk.TclError, ValueError):
            return DEFAULTS["area_gap"]

    def area_plan_now(self):
        """The AreaPlan for the current shapes and gap (worked out again only if they change)."""
        key = (json.dumps(self.area), self.area_gap_value(), bool(self.area_in_order.get()))
        if self.area_plan is None or self.area_plan[0] != key:
            self.area_plan = (key, AreaPlan(self.area, key[1], key[2]) if self.area else None)
        return self.area_plan[1]

    def refresh_area(self):
        plan = self.area_plan_now()
        if not self.area:
            mouse = "No shapes yet: press Edit to draw some."
            info = "No shapes yet: add one above."
        else:
            n = len(self.area)
            info = (f"{n} {'shape' if n == 1 else 'shapes'}, {plan.count:,} "
                    f"{'spot' if plan.count == 1 else 'spots'}, "
                    f"{self.area_gap_value()} px apart")
            if n > 1 and self.area_in_order.get():
                info += ", one shape after another"
            mouse = info + ". Press Edit to change them."
            info += ". The mouse clicker clicks them while this is on."
        self.area_hint.config(text=mouse)
        self.area_info.config(text=info)
        self.refresh_shape_list()

    def refresh_shape_list(self):
        """One row per shape on the Areas page, each with a Remove button."""
        self.shape_rows = self.fill_list(
            self.shapes_card, self.shape_rows, "No shapes yet",
            [(str(i + 1) if self.area_in_order.get() else None, describe_shape(shape),
              lambda n=i: self.remove_shape(n)) for i, shape in enumerate(self.area)])

    def fill_list(self, card, old_rows, empty, items):
        """Fill a card with one row per item (the shapes on the Areas page, the clicks on
        the Macros page): (badge, words, remove), where badge is a ClickBadge's label or
        None. Takes the old rows away first. Returns the new rows."""
        body = card.body
        for widget in old_rows:  # take the old rows away (and stop theming them)
            for part in [widget] + widget.winfo_children():
                for group in (self.round_widgets, self.card_frames, self.dividers):
                    if part in group:
                        group.remove(part)
            widget.destroy()
        rows = []
        p = self.palette
        if not items:
            label = ttk.Label(body, text=empty, style="CardMuted.TLabel")
            label.grid(row=0, column=0, sticky="w", padx=10, pady=10)
            self.repaint_soon()
            return [label]
        for i, (badge, words, remove) in enumerate(items):
            if i:
                line = tk.Frame(body, height=1, bd=0, highlightthickness=0, bg=p["divider"])
                line.grid(row=2 * i - 1, column=0, sticky="ew", padx=10)
                self.dividers.append(line)
                rows.append(line)
            row = tk.Frame(body, bd=0, highlightthickness=0, bg=p["card"])
            row.grid(row=2 * i, column=0, sticky="ew", padx=10)
            self.card_frames.append(row)
            column = 0
            if badge:
                self.register(ClickBadge(row, badge, self.font_caption, self.font_badge_small),
                              surface="card").grid(row=0, column=0, padx=(0, 10), pady=5)
                column = 1
            row.columnconfigure(column, weight=1)
            ttk.Label(row, text=words, style="Card.TLabel").grid(
                row=0, column=column, sticky="w", pady=8)
            self.default_surface = "card"
            try:
                self.make_button(row, "Remove", remove, height=28, width=70).grid(
                    row=0, column=column + 1, padx=(10, 0))
            finally:
                self.default_surface = "page"
            rows.append(row)
        self.repaint_soon()  # everything below the list moved: redraw it, no leftover bits
        return rows

    def refresh_draw_button(self):
        self.draw_btn.set_text(f"Draw shapes ({input_name(self.draw_key.get())})")

    def draw_new_shape(self):
        if any(isinstance(w, ScreenLayer) for w in self.root.winfo_children()):
            return  # already drawing (or the Macros menu is open)
        # (starts on the shape drawn last; the menu at the top switches it)
        kind = self.area[-1]["type"] if self.area else "rectangle"
        ShapeDrawer(self.root, kind, self.area, on_done=self.add_shapes,
                    accent=self.palette["accent"], in_order=bool(self.area_in_order.get()))

    def add_shapes(self, shapes, cleared=False, in_order=None):
        """The shapes drawn on the screen (any number, from its menu). cleared: its Clear
        button took the area's old shapes away, so the area is just these now. in_order:
        its In order switch."""
        if in_order is not None and in_order != self.area_in_order.get():
            self.area_in_order.set(in_order)  # (saves and refreshes, see below)
            if not shapes and not cleared:
                self.save_settings()
                self.status.config(text="In order " + ("on" if in_order else "off"))
                return
        if not shapes and not cleared:
            return
        if cleared:
            self.area = list(shapes)
        else:
            self.area.extend(shapes)
        if self.area:
            self.area_on.set(True)
        self.refresh_area()
        self.save_settings()
        n = len(shapes)
        added = (f"a {SHAPE_NAMES[shapes[0]['type']].lower()}" if n == 1
                 else f"{n} shapes" if n else "")
        self.status.config(text=(f"Cleared, then added {added}" if cleared and n
                                 else "Shapes cleared" if cleared else f"Added {added}"))

    def remove_shape(self, index):
        if 0 <= index < len(self.area):
            removed = self.area.pop(index)
            self.refresh_area()
            self.save_settings()
            self.status.config(text=f"Removed the {SHAPE_NAMES[removed['type']].lower()}")

    def clear_shapes(self):
        if not self.area:
            return
        if self.clear_shapes_job is None:
            # first press: ask to press again, so the shapes aren't lost by accident
            self.clear_shapes_btn.set_text("Sure?")
            self.clear_shapes_job = self.root.after(3000, self.disarm_clear_shapes)
            return
        self.disarm_clear_shapes()
        self.area = []
        self.refresh_area()
        self.save_settings()
        self.status.config(text="Shapes cleared")

    def disarm_clear_shapes(self):
        if self.clear_shapes_job is not None:
            self.root.after_cancel(self.clear_shapes_job)
            self.clear_shapes_job = None
        self.clear_shapes_btn.set_text("Clear all")

    def show_spots(self):
        plan = self.area_plan_now()
        if plan is None or not plan.count:
            self.status.config(text="Add a shape first")
            return
        ShapeDrawer(self.root, None, self.area, plan=plan, gap=self.area_gap_value(),
                    accent=self.palette["accent"], in_order=bool(self.area_in_order.get()))

    def refresh_area_list(self, select=None):
        self.refresh_saved_list("area", select)

    def apply_area(self, shapes, gap, in_order=False):
        """Use a saved area's shapes (Load)."""
        self.area = [dict(shape) for shape in shapes]
        self.area_gap.set(gap)
        self.area_in_order.set(in_order)
        self.area_on.set(True)
        self.refresh_area()
        self.save_settings()

    # ---------------- Macros ----------------
    def macro_wait_value(self):
        try:
            return min(max(float(self.macro_wait.get()), MACRO_WAIT_MIN), MACRO_WAIT_MAX)
        except (tk.TclError, ValueError):
            return DEFAULTS["macro_wait"]

    def refresh_macro(self):
        if not hasattr(self, "macro_info"):
            return  # (still building the window)
        n = len(self.macro)
        if not n:
            info = "No clicks yet: press Record clicks to add some."
        else:
            wait = self.macro_wait_value()
            info = f"{n} {'click' if n == 1 else 'clicks'}, one every {wait:g}s"
            if not self.macro_loop.get():
                info += ", played once"
            elif self.macro_limit_on.get():
                try:
                    plays = max(1, int(self.macro_limit.get()))
                    info += f", played {plays} {'time' if plays == 1 else 'times'}"
                except (tk.TclError, ValueError):
                    pass
            else:
                info += ", on a loop"
        self.macro_info.config(text=info)
        self.refresh_click_list()

    def refresh_click_list(self):
        """One row per click on the Macros page, in order: its circle (L1, R2...), where it
        is, and a Remove button."""
        self.click_rows = self.fill_list(
            self.clicks_card, self.click_rows, "No clicks yet",
            [(macro_label(i, click), f"{click['button']} click at {click['x']}, {click['y']}",
              lambda n=i: self.remove_click(n)) for i, click in enumerate(self.macro)])

    def record_macro(self):
        if any(isinstance(w, ScreenLayer) for w in self.root.winfo_children()):
            return  # the Areas or Macros menu is already open
        if self.armed:
            self.stop()  # (its clicks would land on the menu)
        MacroRecorder(self.root, self.macro, on_done=self.macro_recorded,
                      accent=self.palette["accent"])

    def macro_recorded(self, clicks):
        """The clicks from the Macros menu (Done)."""
        if clicks == self.macro:
            return
        self.macro = clicks
        self.refresh_macro()
        self.save_settings()
        n = len(clicks)
        self.status.config(text=f"Macro has {n} {'click' if n == 1 else 'clicks'}" if n
                           else "Clicks cleared")

    def remove_click(self, index):
        if 0 <= index < len(self.macro):
            removed = self.macro.pop(index)
            self.refresh_macro()
            self.save_settings()
            self.status.config(text=f"Removed {macro_label(index, removed)}")

    def clear_macro(self):
        if not self.macro:
            return
        if self.clear_macro_job is None:
            # first press: ask to press again, so the clicks aren't lost by accident
            self.clear_macro_btn.set_text("Sure?")
            self.clear_macro_job = self.root.after(3000, self.disarm_clear_macro)
            return
        self.disarm_clear_macro()
        self.macro = []
        self.refresh_macro()
        self.save_settings()
        self.status.config(text="Clicks cleared")

    def disarm_clear_macro(self):
        if self.clear_macro_job is not None:
            self.root.after_cancel(self.clear_macro_job)
            self.clear_macro_job = None
        self.clear_macro_btn.set_text("Clear all")

    def show_macro(self):
        if not self.macro:
            self.status.config(text="Record some clicks first")
            return
        if any(isinstance(w, ScreenLayer) for w in self.root.winfo_children()):
            return
        if self.armed:
            self.stop()  # (its clicks would close it straight away)
        MacroRecorder(self.root, self.macro, accent=self.palette["accent"], show_only=True)

    def apply_macro(self, clicks, wait):
        """Use a saved macro's clicks (Load)."""
        self.macro = [dict(click) for click in clicks]
        self.macro_wait.set(wait)
        self.refresh_macro()
        self.save_settings()

    # ---------------- Saved areas and macros ----------------
    # Kept like profiles: one .txt file each, in their own folder. self.libraries says how
    # to read and write each kind (see build_saved_section).
    def refresh_saved_list(self, kind, select=None):
        lib = self.libraries[kind]
        names = lib["list"]()
        lib["combo"].set_values(names)
        if select is not None:
            lib["choice"].set(select)
        elif lib["choice"].get() not in names:
            lib["choice"].set(names[0] if names else "")

    def chosen_saved(self, kind):
        """The saved area / macro picked in the list, or None (with a message) if there
        isn't one."""
        lib = self.libraries[kind]
        name = lib["choice"].get()
        if not name or not lib["path"](name).exists():
            self.status.config(text=f"Pick a saved {kind} first")
            self.refresh_saved_list(kind)
            return None
        return name

    def load_saved(self, kind):
        lib = self.libraries[kind]
        name = self.chosen_saved(kind)
        if name is None:
            return
        found = lib["read"](name)
        if not found:
            self.status.config(text=f"Couldn't read {name}")
            return
        lib["apply"](*found)
        self.status.config(text=f"Loaded {name}")

    def save_saved(self, kind):
        lib = self.libraries[kind]
        current = lib["current"]()
        if current is None:
            self.status.config(text=lib["empty"])
            return
        name = safe_profile_name(lib["name"].get())
        if not name:
            self.status.config(text=f"Type {lib['a']} name first")
            return
        updating = lib["path"](name).exists()
        if not lib["write"](name, *current):
            self.status.config(text=f"Couldn't save the {kind}")
            return
        self.refresh_saved_list(kind, select=name)
        lib["name"].set("")
        self.root.focus_set()
        self.status.config(text=f"Updated {name}" if updating else f"Saved {name}")

    def check_new_saved_name(self, kind, typed, old=None):
        """(name, problem): the name to use, or why it can't be used."""
        lib = self.libraries[kind]
        name = safe_profile_name(typed or "")
        if not name:
            return None, "Type a name first."
        taken = [n for n in lib["list"]() if n.lower() == name.lower() and n != old]
        if taken:
            return None, f"There's already {lib['a']} called {taken[0]}."
        return name, None

    def rename_saved(self, kind):
        lib = self.libraries[kind]
        old = self.chosen_saved(kind)
        if old is None:
            return

        def ok(typed):
            new, problem = self.check_new_saved_name(kind, typed, old)
            if problem:
                return problem
            if new == old:
                return None
            found = lib["read"](old)
            if not found or not lib["write"](new, *found):
                return f"Couldn't rename {old}."
            if new.lower() != old.lower():  # (same file if only the capitals changed)
                try:
                    lib["path"](old).unlink()
                except OSError:
                    pass
            self.refresh_saved_list(kind, select=new)
            self.status.config(text=f"Renamed {old} to {new}")
            return None

        SmallDialog(self.root, f"Rename {kind}", f"New name for {old}:", self.palette,
                    ok_text="Rename", name=old, ok=ok)

    def duplicate_saved(self, kind):
        lib = self.libraries[kind]
        old = self.chosen_saved(kind)
        if old is None:
            return
        suggestion, n = f"{old} copy", 2
        while lib["path"](suggestion).exists():
            suggestion, n = f"{old} copy {n}", n + 1

        def ok(typed):
            new, problem = self.check_new_saved_name(kind, typed)
            if problem:
                return problem
            found = lib["read"](old)
            if not found or not lib["write"](new, *found):
                return f"Couldn't copy {old}."
            self.refresh_saved_list(kind, select=new)
            self.status.config(text=f"Copied {old} to {new}")
            return None

        SmallDialog(self.root, f"Duplicate {kind}", f"Name for the copy of {old}:",
                    self.palette, ok_text="Duplicate", name=suggestion, ok=ok)

    def delete_saved(self, kind):
        lib = self.libraries[kind]
        name = self.chosen_saved(kind)
        if name is None:
            return
        if lib["delete_job"] is None:
            # first press: ask to press again, so nothing is deleted by accident
            lib["delete_btn"].set_text("Sure?")
            lib["delete_job"] = self.root.after(3000, lambda: self.disarm_delete_saved(kind))
            return
        self.disarm_delete_saved(kind)
        try:
            lib["path"](name).unlink()
        except OSError:
            self.status.config(text=f"Couldn't delete {name}")
            return
        self.refresh_saved_list(kind)
        self.status.config(text=f"Deleted {name}")

    def disarm_delete_saved(self, kind):
        lib = self.libraries[kind]
        if lib["delete_job"] is not None:
            self.root.after_cancel(lib["delete_job"])
            lib["delete_job"] = None
        lib["delete_btn"].set_text("Delete")

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
            self.begin_at = time.monotonic() + delay
            self.status.config(text=self.starting_text() + "...")
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
        self.home_pos = None  # where "Put the mouse back" returns it to, see tap
        self.note_own_windows()
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
        elif s["mode"] == "macro":  # the macro's clicks, one after another
            button, x, y = s["macro"][self.clicks % len(s["macro"])]
            if not self.on_own_window((x, y)):  # (never click the auto clicker itself)
                self.click_spot(s, (x, y), button)
        elif s.get("area"):  # every spot in the area, one after another
            spot = s["area"].point(self.clicks)
            if not self.on_own_window(spot):  # (it would press its own buttons)
                self.click_spot(s, spot, s["button"])
        else:
            if s["locations"]:  # one spot, or several clicked in turn
                self.pointer.place(*s["locations"][self.clicks % len(s["locations"])])
            self.mouse.click(s["button"], s["count"])

    def click_spot(self, s, spot, button):
        """Click on a spot (areas and macros). With "Put the mouse back" on, it jumps there,
        clicks, and jumps straight back to where your mouse was."""
        if not s.get("area_return"):
            self.pointer.place(*spot)
            self.mouse.click(button, s["count"])
            return
        home = self.pointer.position()
        if (s.get("auto_stop") and self.home_pos is not None
                and math.hypot(home[0] - self.home_pos[0], home[1] - self.home_pos[1])
                > self.MOVE_TOLERANCE):
            self.events.put("moved")  # you moved it since the last click
        self.home_pos = home
        if not self.pointer.click_at(*spot, button.value, s["count"], home):
            self.pointer.place(*spot)
            self.mouse.click(button, s["count"])
            self.pointer.place(*home)

    def on_own_window(self, spot):
        """True if a spot is on one of the app's own windows (see note_own_windows)."""
        x, y = spot
        return any(left <= x < right and top <= y < bottom
                   for left, top, right, bottom in self.own_windows)

    def note_own_windows(self):
        """Where the app's windows are on screen (main window, badge, pop-ups), so area
        clicking can leave them alone. Kept up to date by poll, read by the click thread."""
        rects = []
        for window in [self.root] + [w for w in self.root.winfo_children()
                                     if isinstance(w, tk.Toplevel)]:
            try:
                if (window.winfo_viewable() and not isinstance(window, ScreenLayer)
                        and window.winfo_width() > 1):
                    x, y = window.winfo_rootx(), window.winfo_rooty()
                    rects.append((x - 4, y - 40 if window is self.root else y - 4,
                                  x + window.winfo_width() + 4,
                                  y + window.winfo_height() + 4))  # (with its title bar)
            except tk.TclError:
                pass
        self.own_windows = rects

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
                    self.pointer.place(*s["locations"][0])
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
            self.replay_pos = None
            for action in s["actions"]:
                wait = began + action[0] / s["speed"] - time.monotonic()
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
                x, y = action[2], action[3]
                if len(action) == 6:  # how far the mouse moved: what games turn with
                    dx, dy = action[4], action[5]
                elif self.replay_pos is not None:  # older recordings: work it out
                    dx, dy = x - self.replay_pos[0], y - self.replay_pos[1]
                else:
                    dx = dy = 0
                self.pointer.move_by(dx, dy)
                self.place_pointer(x, y)
            elif kind == "scroll":
                self.place_pointer(action[4], action[5])
                self.mouse.scroll(action[2], action[3])
            elif kind in ("press", "release"):
                button = mouse.Button[action[2][6:]]
                self.place_pointer(action[3], action[4])
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

    def place_pointer(self, x, y):
        """Put the pointer on a spot (without sending movement a game would turn with)."""
        self.pointer.place(x, y)
        self.replay_pos = (x, y)

    def click_loop(self):
        due = None      # when the next click is due (see below)
        run = None      # the run it belongs to (a new start begins a new timetable)
        while not self.shutdown.is_set():
            if not self.running.wait(timeout=0.1):
                continue
            s = self.settings
            if s is not run:
                run, due = s, None

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

            # Clicks keep to a timetable: each one is due `interval` after the one before,
            # however long the clicking itself took, so the speed is what you set (waiting
            # the whole interval after each click would always run a little slow)
            now = time.perf_counter()
            if due is None or now - due > 0.25:
                due = now  # starting, or the computer was busy for a while: don't rush
            self.tap(s)
            self.clicks += 1

            limit = s["limit"]
            if limit and self.clicks >= limit:
                self.running.clear()
                self.events.put("limit")
                continue

            due += s["interval"]
            wait = due - time.perf_counter()
            if wait > 0:
                self.stopped.wait(wait)  # returns early if stopped

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
            # (skip key repeat while it's held down)
            if code not in self.record_pressed and code not in self.record_skipped:
                if self.quick_repeat(code):
                    self.record_skipped.add(code)
                else:
                    self.record_pressed.add(code)
                    self.record_event("kpress", code)
        self.events.put(("input", code, time.monotonic()))

    def on_key_release(self, key):
        code = input_code(key)
        if code in self.record_skipped:
            self.record_skipped.discard(code)  # its press was left out, so leave this out too
        elif self.recording_active and code in self.record_pressed:
            self.record_pressed.discard(code)
            self.record_event("krelease", code)
        if self.capturing is not None and code in MODIFIER_OF:
            self.events.put(("release", code, time.monotonic()))

    def quick_repeat(self, code):
        """While recording: True if this press should be left out, because the same key or
        button was pressed very shortly before (unless "Keep quick repeats" is on)."""
        now = time.monotonic()
        last = self.record_last_press.get(code)
        if not self.record_keep_repeats and last is not None and now - last < self.QUICK_REPEAT:
            return True
        self.record_last_press[code] = now
        return False

    def on_mouse(self, x, y, button, pressed):
        code = input_code(button)
        if self.recording_active and not self.record_keys and code not in self.record_exclude:
            if pressed:
                if self.quick_repeat(code):
                    self.record_skipped.add(code)
                else:
                    self.record_pressed.add(code)
                    self.record_event("press", code, int(x), int(y))
            elif code in self.record_skipped:
                self.record_skipped.discard(code)
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
        self.note_motion(x=x, y=y)
        # Auto stop: notice when you move the mouse away while it's clicking
        if not self.running.is_set() or not self.settings.get("auto_stop"):
            return
        if ((self.settings.get("area") or self.settings.get("mode") == "macro")
                and self.settings.get("area_return")):
            return  # (the mouse is put back after each click: click_spot notices you moving it)
        # Clicking an area moves the mouse all over it: only leaving the area counts
        if self.settings.get("area"):
            (left, top, right, bottom), t = self.settings["area_box"], self.MOVE_TOLERANCE
            if not (left - t <= x <= right + t and top - t <= y <= bottom + t):
                self.events.put("moved")
            return
        # With set spots the app moves the mouse there itself, so measure from those;
        # otherwise measure from where the mouse was when clicking began.
        spots = (self.settings.get("locations")
                 or [(x_, y_) for _b, x_, y_ in self.settings.get("macro") or []]
                 or ([self.anchor] if self.anchor else []))
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
                and code not in self.app_keys()):
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
        elif code == self.draw_key.get() and not self.recording_active:
            self.draw_new_shape()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event == "limit" and self.settings.get("mode") == "macro":
                    plays = self.settings["plays"]
                    self.stop("Macro finished" if plays == 1 else f"Done: played {plays} times")
                    self.play_finish_sound()
                elif event == "limit":
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
                elif event[0] == "update":
                    self.got_update_answer(*event[1:])
                elif event[0] == "release":
                    self.capture_release(event[1])
                else:
                    self.handle_input(event[1], event[2])
        except queue.Empty:
            pass
        # Keep the floating card's progress (count, time left, countdown) up to date
        counting = self.armed and not self.running.is_set() and self.countdown.get()
        if counting:
            text = self.starting_text() + "..."
            if self.status.cget("text") != text:
                self.status.config(text=text)
        if (self.badge is not None and self.badge.showing and (self.progress_text() or counting)
                and time.monotonic() - self.last_badge_update >= 0.25):
            self.last_badge_update = time.monotonic()
            self.refresh_running()
        # Stop after a set time
        limit = self.settings.get("time_limit")
        if self.running.is_set() and limit and time.monotonic() - self.started_at >= limit:
            self.stop(f"Done: {limit:g} {'second' if limit == 1 else 'seconds'}")
            self.play_finish_sound()
        if self.running.is_set() and (self.settings.get("area")
                                      or self.settings.get("mode") == "macro"):
            self.note_own_windows()
        self.poll_job = self.root.after(50, self.poll)

    def on_close(self):
        if self.shutdown.is_set():
            return  # already closing (e.g. asked to quit twice)
        if self.recording_active:
            self.stop_recording()  # keep what was recorded so far
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
        # Taking hundreds of widgets apart takes Tk a second or two, so vanish first...
        for window in [self.root] + [w for w in self.root.winfo_children()
                                      if isinstance(w, tk.Toplevel)]:
            try:
                window.withdraw()
            except tk.TclError:
                pass
        self.root.update_idletasks()
        self.root.update()  # (sends the "hide" to the screen now)
        if self.quick_exit:
            # ...and then don't take them apart at all: everything is saved and stopped, so
            # main() just ends the program (the system clears the window away instantly)
            self.root.quit()
        else:
            self.root.destroy()


def main():
    if "--write-icons" in sys.argv:
        write_icons()
        return
    found = resolve_locations()  # where settings and profiles are (and if they were moved)
    # Don't connect to the input method (ibus): it's only for typing languages like Chinese,
    # and when it's busy or stuck it makes the app take many seconds to open
    modifiers = os.environ.get("XMODIFIERS")
    os.environ["XMODIFIERS"] = "@im=none"
    root = tk.Tk(className=APP_CLASS)  # window class the dock uses to find the app entry
    if modifiers is None:  # (put it back for anything the app opens, like the file manager)
        os.environ.pop("XMODIFIERS", None)
    else:
        os.environ["XMODIFIERS"] = modifiers
    try:
        root.tk.call("tk", "useinputmethods", 0)
    except tk.TclError:
        pass
    app = AutoClicker(root)
    if found:
        app.status.config(text="Found your moved " + " and ".join(found)
                                + (" folders" if len(found) > 1 else " folder"))
    # When something asks the app to quit (like install.sh updating it), close it the same
    # way as the window's close button: settings are saved and nothing is left held down.
    signal.signal(signal.SIGTERM, lambda *_: root.after(0, app.on_close))
    app.quick_exit = True
    root.mainloop()
    if app.shutdown.is_set():  # closed properly (settings saved, nothing held down)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


if __name__ == "__main__":
    main()
