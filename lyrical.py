#!/usr/bin/env python3
import json, os, re, shutil, subprocess, sys, time
import urllib.parse, urllib.request

LRCLIB_GET    = "https://lrclib.net/api/get"
LRCLIB_SEARCH = "https://lrclib.net/api/search"
RESET = "\033[0m"
BOLD  = "\033[1m"

SHOW_ALBUM_ART = True
ART_WIDTH      = 24
ART_HEIGHT     = 10
ART_TOOL       = "timg"

CURRENT_COLOR = "\033[1;92m"
CURR_OFFSET   = 3        # how many lines above the highlighted line

def color_for(d):
    if d == 1: return "\033[38;5;250m"
    if d == 2: return "\033[38;5;245m"
    if d == 3: return "\033[38;5;240m"
    return "\033[38;5;238m"

def fmt_time(sec):
    if sec is None: return "0:00"
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None

def current_track():
    out = run(["playerctl", "metadata", "--format",
               "{{artist}}|||{{title}}|||{{album}}|||{{mpris:length}}|||{{mpris:artUrl}}"])
    if not out: return None
    p = out.split("|||")
    if len(p) < 5: return None
    artist, title, album, length, art = p[:5]
    if not title: return None
    dur = None
    try: dur = int(length) / 1_000_000
    except ValueError: pass
    return artist, title, album, dur, art

def fetch_lyrics(artist, title, album, dur):
    params = {"artist_name": artist, "track_name": title}
    if album: params["album_name"] = album
    if dur:   params["duration"]   = str(int(dur))
    try:
        req = urllib.request.Request(LRCLIB_GET + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": "Lyrical/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
        return d.get("syncedLyrics") or d.get("plainLyrics")
    except Exception: pass
    try:
        q = urllib.parse.urlencode({"q": f"{artist} {title}"})
        req = urllib.request.Request(LRCLIB_SEARCH + "?" + q,
                                     headers={"User-Agent": "Lyrical/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.load(r)
        if res: return res[0].get("syncedLyrics") or res[0].get("plainLyrics")
    except Exception: pass
    return None

def parse_lrc(text):
    if not text: return False, []
    lines = []
    for line in text.splitlines():
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line)
        if m:
            t = int(m.group(1)) * 60 + float(m.group(2))
            txt = m.group(3).strip()
            if txt: lines.append((t, txt))
    if lines: return True, lines
    return False, [(0, l.strip()) for l in text.splitlines() if l.strip()]

ANSI = re.compile(r"\033\[[0-9;]*m")
def vlen(s): return len(ANSI.sub("", s))

def render_art(art_url):
    if not SHOW_ALBUM_ART or not art_url or not shutil.which(ART_TOOL):
        return None
    path = art_url
    if path.startswith("file://"):
        path = urllib.parse.unquote(path[7:])
    if not os.path.exists(path): return None
    try:
        if ART_TOOL == "timg":
            cmd = ["timg", "-g", f"{ART_WIDTH}x{ART_HEIGHT}", "--upscale", path]
        else:
            cmd = ["chafa", "--size", f"{ART_WIDTH}x{ART_HEIGHT}",
                   "--animate", "off", "--symbols", "block+border+space", "--stretch", path]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        lines = [l.rstrip("\r") for l in out.rstrip("\n").split("\n") if l.strip()]
        if not lines: return None
        w = max(vlen(l) for l in lines)
        return [l + " " * (w - vlen(l)) for l in lines]
    except Exception:
        return None

def gradient_bar(filled, total):
    out = []
    for i in range(total):
        if i < filled:
            f = i / max(1, total - 1)
            c = "\033[38;5;82m" if f < 0.5 else ("\033[38;5;226m" if f < 0.8 else "\033[38;5;203m")
            out.append(f"{c}\u2588{RESET}")
        else:
            out.append("\033[38;5;238m\u2591\033[0m")
    return "".join(out)

def cline(s, cols):
    pad = max(0, (cols - vlen(s)) // 2)
    return " " * pad + s

def build(artist, title, lyrics, synced, idx, pos, dur, art, cols, rows):
    lines = []
    lines.append(cline(f"{BOLD}{artist} \u2014 {title}{RESET}", cols))
    lines.append("")
    if art:
        bw = max(vlen(l) for l in art)
        pad = max(0, (cols - bw) // 2)
        for al in art:
            lines.append(" " * pad + al)
    if dur and pos is not None:
        bw  = min(cols - 4, 60)
        fil = int(bw * min(pos / dur, 1.0))
        lines.append(cline(gradient_bar(fil, bw), cols))
        lines.append(cline(f"\033[38;5;245m{fmt_time(pos)} / {fmt_time(dur)}{RESET}", cols))
    lines.append("")  # single gap before lyrics

    # lyrics: current line sits at fixed row = len(lines) + CURR_OFFSET
    start = max(0, idx - CURR_OFFSET) if idx >= 0 else 0
    remaining = rows - len(lines) - CURR_OFFSET
    if remaining < 1: remaining = 1
    end = min(len(lyrics), start + remaining) if idx >= 0 else min(len(lyrics), remaining)

    for i in range(start, end):
        _, txt = lyrics[i]
        if synced and i == idx:
            line = f"{CURRENT_COLOR}\u25b6  {txt}  \u25c0{RESET}"
        else:
            d = abs(i - idx) if idx >= 0 else 1
            line = f"{color_for(d)}{txt}{RESET}"
        lines.append(cline(line, cols))

    while len(lines) < rows:
        lines.append("")
    return lines[:rows]

def write_frame(lines):
    # cursor home + overwrite each line, clearing to EOL. No full-screen wipe.
    buf = ["\033[H"]
    for i, l in enumerate(lines):
        buf.append(l + "\033[K")
        if i < len(lines) - 1:
            buf.append("\n")
    sys.stdout.write("".join(buf))
    sys.stdout.flush()

def main():
    cache, art_cache = {}, {}
    key = None
    synced, lyrics = False, []
    art_lines = None
    last_frame_key = None

    while True:
        track = current_track()
        if not track:
            if last_frame_key != "idle":
                sys.stdout.write("\033[H\033[2JNo MPRIS player detected.\nStart music in mpv / VLC / Rhythmbox.\n")
                sys.stdout.flush()
                last_frame_key = "idle"
            time.sleep(1)
            continue

        artist, title, album, dur, art_url = track
        nk = (artist, title, album)
        if nk != key:
            if nk not in cache:
                cache[nk] = fetch_lyrics(artist, title, album, dur)
            synced, lyrics = parse_lrc(cache[nk])
            if art_url not in art_cache:
                art_cache[art_url] = render_art(art_url)
            art_lines = art_cache[art_url]
            key = nk

        pos_s = run(["playerctl", "position"])
        try: pos = float(pos_s) if pos_s else 0.0
        except ValueError: pos = 0.0

        idx = -1
        if synced:
            for i, (t, _) in enumerate(lyrics):
                if t <= pos: idx = i
                else: break

        if lyrics:
            cols, rows = shutil.get_terminal_size((80, 24))
            # redraw only when the current line or the second changes
            frame_key = (idx, int(pos), artist, title)
            if frame_key != last_frame_key:
                write_frame(build(artist, title, lyrics, synced, idx, pos, dur, art_lines, cols, rows))
                last_frame_key = frame_key
        else:
            if last_frame_key != f"nl_{artist}_{title}":
                sys.stdout.write(f"\033[H\033[2J{artist} \u2014 {title}\n\nNo lyrics found.\n")
                sys.stdout.flush()
                last_frame_key = f"nl_{artist}_{title}"

        time.sleep(0.2)

if __name__ == "__main__":
    main()
