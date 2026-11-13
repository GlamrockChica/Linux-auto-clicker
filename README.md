# Pengclick

A simple, good-looking auto clicker for Linux, with a penguin. It clicks the mouse or presses a key for you,
and can record and replay what you do.

## Features

- **Mouse clicker:** clicks per second (or a set wait between clicks), left/right/middle
  button, single/double/triple clicks, hold the button down, click at a set spot or at
  several spots in turn
- **Areas:** draw rectangles, circles, triangles and polygons on the screen (as many as you
  like) and it clicks every spot inside them, a set number of pixels apart, row by row.
  The mouse jumps to each spot and straight back, so you can keep using it. The screen
  stays visible while you draw. Turn on **In order** to click one shape after another
  (each shape shows its number). Preview the spots, and save, rename or duplicate
  areas like profiles
- **Macros:** click on the screen with the left, right or middle button to set where it
  clicks, then it clicks them one after another, in order. Each click shows as a circle
  in your accent colour, like L1 (a left click, the first one) or R2 (a right click, the
  second), with arrows from each click to the next. Drag a circle to move it. Set the
  wait between clicks, play once, a number of times or on a loop, and save, rename or
  duplicate macros like profiles
- **Keyboard clicker:** presses a key or key combo (like Ctrl+C) over and over, or holds it
- **Record and replay:** record your mouse and keyboard, then play it back
  - once, a set number of times or on a loop, at any speed (half speed, twice as fast...)
  - choose how smoothly mouse movement is recorded, from Lowest to Ultra
  - works in games that lock the mouse (like first-person Roblox): the camera turns the
    same way it did when you recorded
  - save recordings as profiles, each with its own hotkey; rename, duplicate or share them
    (they're plain text files)
- **Stops by itself** after a number of clicks or a set time, or when you move the mouse
- **Mini mode:** a small rounded panel that stays on top of other windows
- **Badge:** a small card in the corner of the screen showing what's running, and
  counting down the start delay (3, 2, 1)
- Light and dark mode, accent colours, text sizes, and a menu you can move to any side
- A penguin icon holding your own mouse pointer (it's read from your cursor theme when you
  install)
- Tells you when a new version is out on GitHub

## Requirements

- Linux with an **X11** session (Zorin OS and many others use X11 by default).
  The clicking doesn't work on Wayland sessions.
- Python 3 with Tk, and git

## Install

On Ubuntu, Zorin OS, Linux Mint and similar, open a terminal and run:

```bash
sudo apt install python3-venv python3-tk git
```

```bash
git clone https://github.com/GlamrockChica/Linux-auto-clicker.git
```

```bash
cd Linux-auto-clicker && ./install.sh
```

(Or download the zip from GitHub, unzip it, open a terminal in the folder and run
`./install.sh`.)

The installer builds the app, adds **Pengclick** to your app list and starts it.
It needs an internet connection the first time, to download its two Python packages
(`pynput` and `pyinstaller`).

## Update

The app tells you when a new version is out (it checks GitHub when it opens; you can turn
that off in **Settings → About**). To update, get the new version, then run the installer
again. It closes the app, rebuilds it and starts it again. Your settings and profiles are kept.

```bash
cd Linux-auto-clicker && git pull && ./install.sh
```

## Keys

| Key | What it does |
|-----|--------------|
| F6  | Start / stop |
| F7  | Set the click location (when "Click at a set location" is on) |
| F8  | Start / stop recording |
| F9  | Draw shapes for an area (works anywhere, even in a game) |
| Esc | Stops everything |
| Ctrl+1 to Ctrl+6 | Switch pages (Ctrl+Tab goes to the next one) |

In Settings you can change F6 to F9 to another key or a mouse button.

## Where things are kept

- Settings: `~/.config/autoclicker/`
- Profiles: `~/.config/autoclicker/profiles/`, one `.txt` file per profile
- Saved areas: `~/.config/autoclicker/areas/`, one `.txt` file per area
- Saved macros: `~/.config/autoclicker/macros/`, one `.txt` file per macro

All four folders can be moved from **Settings → Storage**.

A profile file is plain text, one input per line, for example:

```
{profile:"hi"}
{[0],kpress:"h"}
{[0.1],krelease:"h"}
{[0.4],kpress:"i"}
{[0.1],krelease:"i"}
```

The number in `[ ]` is the wait in seconds since the line before.

## Uninstall

In the folder you installed from, run:

```bash
./uninstall.sh
```

It removes the app, its menu entry and its icons, then asks whether to delete your settings,
profiles, areas and macros too (they're kept unless you answer **y**).

## Please use it fairly

Many online games don't allow auto clickers. Only use it where it's allowed.

## Licence

MIT. See [LICENSE](LICENSE).
