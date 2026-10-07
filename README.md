# Lyrical

Terminal live lyrics for any MPRIS player — Spotify, mpv, VLC Rhythmbox, anything `playerctl` can see.

Synced lyrics from [LRCLIB](https://lrclib.net) (no API key needed). Centered layout, progress bar, fading context lines, steady highlight on the current line.

## Requirements

- `playerctl` — `sudo apt install playerctl`
- `python3`

## Install

```
git clone https://github.com/Apersonwithtoenail/Lyrical.git
cd Lyrical
cp Lyrical.py ~/bin/live_lyrics.py
chmod +x ~/bin/live_lyrics.py
```

Make sure `~/bin` is on your `PATH` (it usually already is on Kali).

## Run

Play something in any MPRIS-compatible player, then:

```
python3 ~/bin/live_lyrics.py
```

## Controls

- **Ctrl-C** — quit

## How it works

1. Polls `playerctl` for the current track
2. Looks up the track on LRCIB (exact match, falls back to fuzzy)
3. If synced lyrics exist, renders them line-by-line with a progress bar
4. Fades older lines, highlights the active one

## License

MIT
