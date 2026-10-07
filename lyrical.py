#!/usr/bin/env python3
import json, os, re, shutil, subprocess, sys, time
import urllib.parse, urllib.request

LRCLIB_GET    = "https://lrclib.net/api/get"
LRCLIB_SEARCH = "https://lrclib.net/api/search"
RESET = "\033[0m"
BOLD  = "\033[1m"

SHOW_ALBUM_ART = True
ART_WIDTH      = 24
ART_HEIGHT     = 12
ART_TOOL       = "timg"

CURRENT_COLOR = "\033[1;92m"

def color_for(distance):
    if distance == 1: return "\033[38;5;250m"
    if distance == 2: return "\033[38;5;245m"
    if distance == 3: return "\033[38;5;240m"
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
    if not out:
        return None
    parts = out.split("|||")
    if len(parts) < 5:
        return None
    artist, title, album, length, art = parts[:5]
    if not title:
        return None
    duration = None
    try:
        duration = int(length) / 1_000_000
    except ValueError:
        pass
    return artist, title, album, duration, art

def fetch_lyrics(artist, title, album, duration):
    params = {"artist_name": artist, "track_name": title}
    if album:    params["album_name"] = album
    if duration: params["duration"]   = str(int(duration))
    url = LRCLIB_GET + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Lyrical/1.4"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        return data.get("syncedLyrics") or data.get("plainLyrics")
    except Exception:
        pass
    q = urllib.parse.urlencode({"q": f"{artist} {title}"})
    try:
        req = urllib.request.Request(LRCLIB_SEARCH + "?" + q,
                                     headers={"User-Agent": "Lyrical/1.4"})
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

ANSI_RE = re.compile(r"\033\[[0-9;]*m")
def visible_len(s):
    return len(ANSI_RE.sub("", s))

def render_art(art_url):
    if not SHOW_ALBUM_ART or not art_url:
        return None
    if not shutil.which(ART_TOOL):
        return None
    path = art_url
    if path.startswith("file://"):
        path = urllib.parse.unquote(path[7:])
    if not os.path.exists(path):
        return None
    try:
        if ART_TOOL == "timg":
            cmd = ["timg", "-g", f"{ART_WIDTH}x{ART_HEIGHT}", "--upscale", path]
        else:
            cmd = ["chafa", "--size", f"{ART_WIDTH}x{ART_HEIGHT}",
                   "--animate", "off", "--symbols", "block+border+space",
                   "--stretch", path]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        lines = [l.rstrip("\r") for l in out.rstrip("\n").split("\n") if l.strip()]
        if not lines:
            return None
        widths = [visible_len(l) for l in lines]
        max_w = max(widths)
        return [l + " " * (max_w - w) for l, w in zip(lines, widths)]
    except Exception:
        return None

def gradient_bar(filled, total):
    out = []
    for i in range(total):
        if i < filled:
            frac = i / max(1, total - 1)
            if frac < 0.5:   c = "\033[38;5;82m"
            elif frac < 0.8: c = "\033[38;5;226m"
            else:            c = "\033[38;5;203m"
            out.append(f"{c}\u2588{RESET}")
        else:
            out.append("\033[38;5;238m\u2591\033[0m")
    return "".join(out)

def build_frame(artist, title, lyrics, synced, idx, pos, duration,
                art_lines, cols, rows):
    out = []
    title_str = f"{BOLD}{artist} \u2014 {title}{RESET}"
    pad = max(0, (cols - visible_len(title_str)) // 2)
    out.append(" " * pad + title_str)
    out.append("")

    if art_lines:
        block_w = max(visible_len(l) for l in art_lines)
        pad = max(0, (cols - block_w) // 2)
        for line in art_lines:
            out.append(" " * pad + line)

    if duration and pos is not None:
        bar_w  = min(cols - 4, 60)
        filled = int(bar_w * min(pos / duration, 1.0))
        bar    = gradient_bar(filled, bar_w)
        pad    = max(0, (cols - bar_w) // 2)
        out.append(" " * pad + bar)
        time_str = f"\033[38;5;245m{fmt_time(pos)} / {fmt_time(duration)}{RESET}"
        pad = max(0, (cols - visible_len(time_str)) // 2)
        out.append(" " * pad + time_str)

    art_rows = len(art_lines) if art_lines else 0
    half = max(3, (rows - 5 - art_rows) // 2)
    if idx < 0:
        start, end, cur = 0, min(len(lyrics), half * 2), -1
    else:
        start = max(0, idx - half)
        end   = min(len(lyrics), idx + half + 1)
        cur   = idx

    for i in range(start, end):
        _, txt = lyrics[i]
        if synced and i == cur:
            line = f"{CURRENT_COLOR}\u25b6  {txt}  \u25c0{RESET}"
        else:
            d = abs(i - cur) if cur >= 0 else 1
            line = f"{color_for(d)}{txt}{RESET}"
        pad = max(0, (cols - visible_len(line)) // 2)
        out.append(" " * pad + line)

    while len(out) < rows:
        out.append("")
    out = out[:rows]
    return "\033[H\033[2J" + "\n".join(out)

def main():
    cache = {}
    art_cache = {}
    key   = None
    synced, lyrics = False, []
    art_lines = None
    last = None

    while True:
        track = current_track()
        if not track:
            if last != "__idle__":
                sys.stdout.write("\033[H\033[2JNo MPRIS player detected.\n"
                                 "Start music in mpv / VLC / Rhythmbox.\n")
                sys.stdout.flush()
                last = "__idle__"
            time.sleep(1)
            continue

        artist, title, album, duration, art_url = track
        new_key = (artist, title, album)

        if new_key != key:
            if new_key not in cache:
                cache[new_key] = fetch_lyrics(artist, title, album, duration)
            synced, lyrics = parse_lrc(cache[new_key])
            if art_url not in art_cache:
                art_cache[art_url] = render_art(art_url)
            art_lines = art_cache[art_url]
            key = new_key

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
            cols, rows = shutil.get_terminal_size((80, 24))
            frame = build_frame(artist, title, lyrics, synced, idx,
                                pos, duration, art_lines, cols, rows)
            if frame != last:
                sys.stdout.write(frame)
                sys.stdout.flush()
                last = frame
        else:
            msg = f"__nl_{artist}_{title}__"
            if last != msg:
                sys.stdout.write(f"\033[H\033[2J{artist} \u2014 {title}\n\nNo lyrics found.\n")
                sys.stdout.flush()
                last = msg

        time.sleep(0.2)

if __name__ == "__main__":
    main()
