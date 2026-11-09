# Auto Clicker

A simple, good-looking auto clicker for Linux. It clicks the mouse or presses a key for you,
and can record and replay what you do.

## Features

- **Mouse clicker:** clicks per second (or a set wait between clicks), left/right/middle
  button, single/double/triple clicks, hold the button down, click at a set spot or at
  several spots in turn
- **Keyboard clicker:** presses a key or key combo (like Ctrl+C) over and over, or holds it
- **Record and replay:** record your mouse and keyboard (with a choice of how smoothly mouse
  movement is recorded, from Lowest to Ultra), replay it once, a set number of
  times or on a loop, at any speed (half speed, twice as fast...), and save recordings as
  profiles with their own hotkey (rename, duplicate or share them as text files). Mouse
  movement replays properly in games that lock the mouse (like first-person Roblox),
  so the camera turns the same way it did when you recorded
- **Stops by itself** after a number of clicks or a set time, or when you move the mouse
- **Mini mode:** a small rounded panel that stays on top of other windows
- **Badge:** a small card in the corner of the screen showing what's running, and
  counting down the start delay (3, 2, 1)
- Light and dark mode, accent colours, text sizes, and a menu you can move to any side

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

The installer builds the app, adds **Auto Clicker** to your app list and starts it.
It needs an internet connection the first time, to download its two Python packages
(`pynput` and `pyinstaller`).

## Update

Get the new version, then run the installer again. It closes the app, rebuilds it and
starts it again. Your settings and profiles are kept.

```bash
cd Linux-auto-clicker && git pull && ./install.sh
```

## Keys

| Key | What it does |
|-----|--------------|
| F6  | Start / stop |
| F7  | Set the click location (when "Click at a set location" is on) |
| F8  | Start / stop recording |
| Esc | Stops everything |
| Ctrl+1 to Ctrl+4 | Switch pages (Ctrl+Tab goes to the next one) |

You can change F6, F7 and F8 in Settings, to another key or a mouse button.

## Where things are kept

- Settings: `~/.config/autoclicker/`
- Profiles: `~/.config/autoclicker/profiles/`, one `.txt` file per profile

Both folders can be moved from **Settings → Storage**.

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

```bash
rm -f ~/.local/bin/autoclicker ~/.local/share/applications/autoclicker.desktop
```

```bash
find ~/.local/share/icons -name 'autoclicker*.png' -delete
```

To also delete your settings and profiles:

```bash
rm -rf ~/.config/autoclicker
```

## Please use it fairly

Many online games don't allow auto clickers. Only use it where it's allowed.

## Licence

MIT. See [LICENSE](LICENSE).
