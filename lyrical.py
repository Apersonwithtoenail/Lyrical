#!/usr/bin/env python3
import json, os, re, shutil, subprocess, sys, time
import urllib.parse, urllib.request

LRCLIB_GET    = "https://lrclib.net/api/get"
LRCLIB_SEARCH = "https://lrclib.net/api/search"
RESET = "\033[0m"
BOLD  = "\033[1m"

SHOW_ALBUM_ART = True
ART_WIDTH      = 22
ART_HEIGHT     = 8
ART_TOOL       = "timg"

CURRENT_COLOR = "\033[1;92m"

def color_for(d):
    if d == 1: return "\033[38;5;250m"
    if d == 2: return "\033[38;5;245m"
    if d == 3: return "\033[38;5;240m"
    return "\033[38;5;238m"

def fmt_time(s):
    if s is None: return "0:00"
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"

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
    a, t, al, ln, art = p[:5]
    if not t: return None
    try: dur = int(ln) / 1_000_000
    except ValueError: dur = None
    return a, t, al, dur, art

def fetch_lyrics(artist, title, album, dur):
    params = {"artist_name": artist, "track_name": title}
    if album: params["album_name"] = album
    if dur:   params["duration"]   = str(int(dur))
    try:
        req = urllib.request.Request(LRCLIB_GET + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": "Lyrical/2.1"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
        return d.get("syncedLyrics") or d.get("plainLyrics")
    except Exception: pass
    try:
        q = urllib.parse.urlencode({"q": f"{artist} {title}"})
        req = urllib.request.Request(LRCLIB_SEARCH + "?" + q,
                                     headers={"User-Agent": "Lyrical/2.1"})
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
    parts = []
    for i in range(total):
        if i < filled:
            f = i / max(1, total - 1)
            c = "\033[38;5;82m" if f < 0.5 else ("\033[38;5;226m" if f < 0.8 else "\033[38;5;203m")
            parts.append(f"{c}\u2588{RESET}")
        else:
            parts.append("\033[38;5;238m\u2591\033[0m")
    return "".join(parts)

def cline(s, cols):
    pad = max(0, (cols - vlen(s)) // 2)
    return " " * pad + s

def build(artist, title, lyrics, synced, idx, pos, dur, art, cols, rows):
    lines = []
    lines.append(cline(f"{BOLD}{artist} \u2014 {title}{RESET}", cols))
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

    # lyrics fill remaining rows. current line sits at row (top_of_lyrics + 3)
    top_of_lyrics = len(lines)
    avail = rows - top_of_lyrics
    if idx < 0:
        show = min(len(lyrics), avail)
        start = 0
    else:
        CURR_ROW_FROM_TOP = 3
        start = max(0, idx - CURR_ROW_FROM_TOP)
        show = min(len(lyrics) - start, avail)

    for i in range(start, start + show):
        _, txt = lyrics[i]
        if synced and i == idx:
            line = f"{CURRENT_COLOR}\u25b6  {txt}  \u25c0{RESET}"
        else:
            d = abs(i - idx) if idx >= 0 else 1
            line = f"{color_for(d)}{txt}{RESET}"
        lines.append(cline(line, cols))

    return lines

def write_frame(lines, cols, rows):
    """Absolute cursor positioning. No newlines → no scrollback growth."""
    out = ["\033[?25l"]  # hide cursor
    for i in range(rows):
        row = i + 1
        out.append(f"\033[{row};1H\033[K")   # move to row, clear it
        if i < len(lines):
            out.append(lines[i])
    out.append("\033[?25h")  # show cursor
    sys.stdout.write("".join(out))
    sys.stdout.flush()

def enter_alt():
    sys.stdout.write("\033[?1049h\033[H\033[2J")
    sys.stdout.flush()

def exit_alt():
    sys.stdout.write("\033[?1049l\033[?25h")
    sys.stdout.flush()

def main():
    cache, art_cache = {}, {}
    key = None
    synced, lyrics = False, []
    art_lines = None
    last_key = None

    while True:
        track = current_track()
        if not track:
            if last_key != "idle":
                cols, rows = shutil.get_terminal_size((80, 24))
                write_frame(["", "  No MPRIS player detected.", "  Start music in mpv / VLC / Rhythmbox."], cols, rows)
                last_key = "idle"
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
            last_key = None

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
            k = (idx, int(pos), artist, title, cols, rows)
            if k != last_key:
                write_frame(build(artist, title, lyrics, synced, idx, pos, dur, art_lines, cols, rows), cols, rows)
                last_key = k
        else:
            k = f"nl_{artist}_{title}"
            if last_key != k:
                cols, rows = shutil.get_terminal_size((80, 24))
                write_frame([f"  {artist} \u2014 {title}", "", "  No lyrics found."], cols, rows)
                last_key = k

        time.sleep(0.2)

if __name__ == "__main__":
    try:
        enter_alt()
        main()
    except KeyboardInterrupt:
        pass
    finally:
        exit_alt()
