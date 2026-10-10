# Lyrical

**Terminal live lyrics for any MPRIS player — Spotify, mpv, VLC, Rhythmbox, anything `playerctl` can see.**

Shows synced lyrics for the track currently playing, right in your terminal. Centered layout, gradient progress bar with timestamp, album art via timg/chafa, fading context lines, and a steady highlight on the active line. No API key needed — lyrics come from LRCLIB.

## Features

- Live synced lyrics for any MPRIS-compatible player
- Album art rendered in the terminal (`timg` or `chafa`)
- Gradient progress bar with `m:ss / m:ss` time
- Keyboard controls: timing offset, album-art toggle, reload
- Disk cache — instant lookup when you replay a track
- Config file at `~/.config/lyrical/config.json`
- Smarter track matching (strips feat/ft./remaster/version noise)
- Alt-screen buffer — no scrollback pollution, no flicker
- Auto-reload on track change

## Requirements

- `playerctl` — `sudo apt install playerctl`
- Python 3
- `timg` or `chafa` — optional, for album art

## Install

    git clone https://github.com/Apersonwithtoenail/Lyrical.git
    cd Lyrical
    ./install.sh

Then run:

    lyrical

Uninstall with `./uninstall.sh`.

### Manual

    git clone https://github.com/Apersonwithtoenail/Lyrical.git
    cd Lyrical
    mkdir -p ~/bin
    ln -sf "$PWD/lyrical.py" ~/bin/live_lyrics.py
    chmod +x lyrical.py

## Usage

Play something in any MPRIS-compatible player, then:

    lyrical

## Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Reload lyrics for current track |
| `[` | Nudge timing -0.25s |
| `]` | Nudge timing +0.25s |
| `a` | Toggle album art on/off |
| `Ctrl-C` | Quit |

Timing offset is saved to the config file, so adjustments persist across sessions.

## Configuration

Config lives at `~/.config/lyrical/config.json`.

| Key | Default | Purpose |
|-----|---------|---------|
| `show_album_art` | `true` | Render album art |
| `art_width` | `22` | Art width in columns |
| `art_height` | `8` | Art height in rows |
| `art_tool` | `timg` | `timg` or `chafa` |
| `current_color` | green | ANSI color for active line |
| `timing_offset` | `0.0` | Seconds offset applied to sync |

Lyrics are cached at `~/.cache/lyrical/lyrics.json`.

## How it works

1. Polls `playerctl` for the current track
2. Cleans the title and artist (strips feat., remaster, official video, etc.)
3. Looks the track up on LRCLIB — exact match, then fuzzy, then title-only
4. If synced lyrics exist, renders them with a moving highlight
5. Album art is rendered once per track via `timg`/`chafa` and cached
6. Uses the alternate screen buffer (like `vim`/`htop`) so scrollback stays clean

## Platform status

| Platform | Status |
|----------|--------|
| Linux (MPRIS) | Tested |
| macOS | No MPRIS |
| Windows | No MPRIS |

## License

MIT — see [LICENSE](LICENSE).
