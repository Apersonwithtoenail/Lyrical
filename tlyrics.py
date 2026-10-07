#!/usr/bin/env python3
import json, os, re, shutil, subprocess, sys, time
import urllib.parse, urllib.request

LRCLIB_GET    = "https://lrclib.net/api/get"
LRCLIB_SEARCH = "https://lrclib.net/api/search"
RESET = "\033[0m"
BOLD  = "\033[1m"

CURRENT_COLOR = "\033[1;92m"   # steady green — the final resting color
FLASH_COLOR   = "\033[1;97m"   # white — used for the entrance flash

def color_for(distance):
    if distance == 1: return "\033[38;5;250m"
    if distance == 2: return "\033[38;5;245m"
    if distance == 3: return "\033[38;5;240m"
    return "\033[38;5;238m"

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None

def current_track():
    out = run(["playerctl", "metadata", "--format",
               "{{artist}}|||{{title}}|||{{album}}|||{{mpris:length}}"])
    if not out:
        return None
    parts = out.split("|||")
    if len(parts) < 4:
        return None
    artist, title, album, length = parts[:4]
    if not title:
        return None
    duration = None
    try:
        duration = int(length) / 1_000_000
    except ValueError:
        pass
    return artist, title, album, duration

def fetch_lyrics(artist, title, album, duration):
    params = {"artist_name": artist, "track_name": title}
    if album:    params["album_name"] = album
    if duration: params["duration"]   = str(int(duration))
    url = LRCLIB_GET + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "live-lyrics/3.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        return data.get("syncedLyrics") or data.get("plainLyrics")
    except Exception:
        pass
    q = urllib.parse.urlencode({"q": f"{artist} {title}"})
    try:
        req = urllib.request.Request(LRCLIB_SEARCH + "?" + q,
                                     headers={"User-Agent": "live-lyrics/3.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.load(r)
        if results:
            return results[0].get("syncedLyrics") or results[0].get("plainLyrics")
    except Exception:
        pass
    return None

def parse_lrc(text):
    if not text:
        return False, []
    lines = []
    for line in text.splitlines():
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line)
        if m:
            t = int(m.group(1)) * 60 + float(m.group(2))
            txt = m.group(3).strip()
            if txt:
                lines.append((t, txt))
    if lines:
        return True, lines
    return False, [(0, l.strip()) for l in text.splitlines() if l.strip()]

def visible_len(s):
    return len(re.sub(r"\033\[[0-9;]*m", "", s))

def center(s, width):
    pad = max(0, (width - visible_len(s)) // 2)
    return " " * pad + s

def render(artist, title, lyrics, synced, idx, pos, duration,
           anim_step=0, anim_steps=0):
    """
    If anim_steps > 0, we're inside a transition on the current line:
      - the line slides in from the right
      - flashes white at the start
      - settles to steady green at the end
    """
    cols, rows = shutil.get_terminal_size((80, 24))
    out = ["\033[H\033[J"]
    out.append(center(f"{BOLD}{artist} — {title}{RESET}", cols))

    if duration and pos is not None:
        bar_w  = min(cols - 4, 60)
        filled = int(bar_w * min(pos / duration, 1.0))
        bar    = "█" * filled + "░" * (bar_w - filled)
        out.append("")
        out.append(center(f"\033[38;5;240m{bar}{RESET}", cols))

    out.append("")
    out.append("")

    half = max(3, (rows - 8) // 2)
    if idx < 0:
        start, end, cur = 0, min(len(lyrics), half * 2), -1
    else:
        start = max(0, idx - half)
        end   = min(len(lyrics), idx + half + 1)
        cur   = idx

    for i in range(start, end):
        _, txt = lyrics[i]

        if synced and i == cur:
            if anim_steps > 0:
                t = anim_step / max(1, anim_steps - 1)   # 0.0 -> 1.0
                # slide-in: start with an indent, shrink to centered
                extra = int((1.0 - t) * 12)
                color = FLASH_COLOR if t < 0.55 else CURRENT_COLOR
                line  = f"{color}▶  {txt}  ◀{RESET}"
                base  = max(0, (cols - visible_len(line)) // 2)
                out.append(" " * (base + extra) + line)
            else:
                out.append(center(f"{CURRENT_COLOR}▶  {txt}  ◀{RESET}", cols))
        else:
            d = abs(i - cur) if cur >= 0 else 1
            out.append(center(f"{color_for(d)}{txt}{RESET}", cols))

    sys.stdout.write("\n".join(out))
    sys.stdout.flush()

def main():
    cache = {}
    key   = None
    synced, lyrics = False, []
    prev_idx = -1

    while True:
        track = current_track()
        if not track:
            os.system("clear")
            print("No MPRIS player detected. Start music in mpv / VLC / Rhythmbox.")
            prev_idx = -1
            time.sleep(1)
            continue

        artist, title, album, duration = track
        new_key = (artist, title, album)

        if new_key != key:
            if new_key not in cache:
                cache[new_key] = fetch_lyrics(artist, title, album, duration)
            synced, lyrics = parse_lrc(cache[new_key])
            key = new_key
            prev_idx = -1

        pos_s = run(["playerctl", "position"])
        try:
            pos = float(pos_s) if pos_s else 0.0
        except ValueError:
            pos = 0.0

        idx = -1
        if synced:
            for i, (t, _) in enumerate(lyrics):
                if t <= pos:
                    idx = i
                else:
                    break

        if lyrics:
            # When the active line changes, play a short entrance animation
            if idx != prev_idx and idx >= 0:
                steps = 0
                for s in range(steps):
                    render(artist, title, lyrics, synced, idx,
                           pos, duration, anim_step=s, anim_steps=steps)
                    time.sleep(0.04)
                prev_idx = idx

            render(artist, title, lyrics, synced, idx, pos, duration)
        else:
            os.system("clear")
            print(f"{artist} — {title}\n\nNo lyrics found.")

        time.sleep(0.15)

if __name__ == "__main__":
    main()
