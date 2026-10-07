#!/usr/bin/env python3
import json, os, re, shutil, select, subprocess, sys, termios, time, tty
import urllib.parse, urllib.request

# ---------- paths / defaults ----------
CFG_DIR  = os.path.expanduser("~/.config/lyrical")
CFG_PATH = os.path.join(CFG_DIR, "config.json")
CACHE_DIR = os.path.expanduser("~/.cache/lyrical")
CACHE_PATH = os.path.join(CACHE_DIR, "lyrics.json")

DEFAULTS = {
    "show_album_art": True,
    "art_width": 22,
    "art_height": 8,
    "art_tool": "timg",
    "current_color": "\033[1;92m",
    "timing_offset": 0.0,
}

# ---------- ANSI ----------
RESET = "\033[0m"
BOLD  = "\033[1m"
ANSI  = re.compile(r"\033\[[0-9;]*m")

def vlen(s): return len(ANSI.sub("", s))

# ---------- config ----------
def load_cfg():
    os.makedirs(CFG_DIR, exist_ok=True)
    if not os.path.exists(CFG_PATH):
        with open(CFG_PATH, "w") as f:
            json.dump(DEFAULTS, f, indent=2)
        return dict(DEFAULTS)
    try:
        with open(CFG_PATH) as f:
            cfg = json.load(f)
        for k, v in DEFAULTS.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return dict(DEFAULTS)

def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# ---------- cache ----------
def load_cache():
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache):
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

# ---------- terminal ----------
def setup_raw():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ICANON | termios.ECHO)
    new[6][termios.VMIN] = 0
    new[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, new)
    return old

def restore_term(old):
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, old)
    except Exception:
        pass

def get_key():
    if select.select([sys.stdin], [], [], 0)[0]:
        try:
            return sys.stdin.read(1)
        except Exception:
            return None
    return None

def enter_alt():
    sys.stdout.write("\033[?1049h\033[H\033[2J\033[?25l")
    sys.stdout.flush()

def exit_alt():
    sys.stdout.write("\033[?1049l\033[?25h")
    sys.stdout.flush()

# ---------- helpers ----------
def fmt_time(s):
    if s is None: return "0:00"
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"

def color_for(d):
    if d == 1: return "\033[38;5;250m"
    if d == 2: return "\033[38;5;245m"
    if d == 3: return "\033[38;5;240m"
    return "\033[38;5;238m"

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None

# ---------- metadata ----------
BRACKETS = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
NOISE    = re.compile(r"\b(feat\.?|ft\.?|featuring|prod\.?|remaster(ed)?|remix|version|edit|official|video|audio|lyric[s]?|hd|hq|explicit)\b", re.I)

def clean(s):
    if not s: return s
    s = BRACKETS.sub("", s)
    s = NOISE.sub("", s)
    s = re.sub(r"\s*-\s*$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" -")

# ---------- player ----------
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

# ---------- lyrics fetch ----------
def fetch_lyrics(artist, title, album, dur, cache):
    ck = f"{artist}|{title}|{album}"
    if ck in cache:
        return cache[ck], True

    # Strategy 1: exact match with cleaned names
    params = {"artist_name": clean(artist), "track_name": clean(title)}
    if album: params["album_name"] = clean(album)
    if dur:   params["duration"]   = str(int(dur))
    try:
        req = urllib.request.Request(
            "https://lrclib.net/api/get?" + urllib.parse.urlencode(params),
            headers={"User-Agent": "Lyrical/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.load(r)
        text = d.get("syncedLyrics") or d.get("plainLyrics")
        if text:
            cache[ck] = text
            return text, False
    except Exception:
        pass

    # Strategy 2: fuzzy search with cleaned names
    try:
        q = urllib.parse.urlencode({"q": f"{clean(artist)} {clean(title)}"})
        req = urllib.request.Request(
            "https://lrclib.net/api/search?" + q,
            headers={"User-Agent": "Lyrical/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            res = json.load(r)
        if res:
            text = res[0].get("syncedLyrics") or res[0].get("plainLyrics")
            if text:
                cache[ck] = text
                return text, False
    except Exception:
        pass

    # Strategy 3: title only
    try:
        q = urllib.parse.urlencode({"q": clean(title)})
        req = urllib.request.Request(
            "https://lrclib.net/api/search?" + q,
            headers={"User-Agent": "Lyrical/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            res = json.load(r)
        if res:
            text = res[0].get("syncedLyrics") or res[0].get("plainLyrics")
            if text:
                cache[ck] = text
                return text, False
    except Exception:
        pass

    cache[ck] = ""
    return None, False

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

# ---------- album art ----------
def render_art(art_url, cfg):
    if not cfg["show_album_art"] or not art_url: return None
    tool = cfg["art_tool"]
    if not shutil.which(tool): return None
    path = art_url
    if path.startswith("file://"):
        path = urllib.parse.unquote(path[7:])
    if not os.path.exists(path): return None
    try:
        if tool == "timg":
            cmd = ["timg", "-g", f"{cfg['art_width']}x{cfg['art_height']}",
                   "--upscale", path]
        else:
            cmd = ["chafa", "--size", f"{cfg['art_width']}x{cfg['art_height']}",
                   "--animate", "off", "--symbols", "block+border+space",
                   "--stretch", path]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        lines = [l.rstrip("\r") for l in out.rstrip("\n").split("\n") if l.strip()]
        if not lines: return None
        w = max(vlen(l) for l in lines)
        return [l + " " * (w - vlen(l)) for l in lines]
    except Exception:
        return None

# ---------- rendering ----------
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

def build(artist, title, lyrics, synced, idx, pos, dur, art, cfg, cols, rows, status=""):
    lines = []
    header = f"{BOLD}{artist} \u2014 {title}{RESET}"
    if status:
        header += f"  \033[38;5;245m[{status}]{RESET}"
    lines.append(cline(header, cols))

    if art:
        bw = max(vlen(l) for l in art)
        pad = max(0, (cols - bw) // 2)
        for al in art:
            lines.append(" " * pad + al)

    if dur and pos is not None:
        bw  = min(cols - 4, 60)
        fil = int(bw * min(pos / dur, 1.0))
        lines.append(cline(gradient_bar(fil, bw), cols))
        lines.append(cline(
            f"\033[38;5;245m{fmt_time(pos)} / {fmt_time(dur)}  "
            f"\u00b7 offset {cfg['timing_offset']:+.2f}s{RESET}", cols))

    top_of_lyrics = len(lines)
    avail = rows - top_of_lyrics - 1  # -1 for help bar
    if avail < 3: avail = 3

    if idx < 0:
        show = min(len(lyrics), avail)
        start = 0
    else:
        start = max(0, idx - 3)
        show  = min(len(lyrics) - start, avail)

    for i in range(start, start + show):
        _, txt = lyrics[i]
        if synced and i == idx:
            line = f"{cfg['current_color']}\u25b6  {txt}  \u25c0{RESET}"
        else:
            d = abs(i - idx) if idx >= 0 else 1
            line = f"{color_for(d)}{txt}{RESET}"
        lines.append(cline(line, cols))

    while len(lines) < rows - 1:
        lines.append("")

    # help bar at bottom
    help_str = "\033[38;5;240m  q quit   [ ] offset   a art   r reload  \033[0m"
    lines.append(cline(help_str, cols))
    return lines

def write_frame(lines, cols, rows):
    out = ["\033[?25l"]
    for i in range(rows):
        out.append(f"\033[{i+1};1H\033[K")
        if i < len(lines):
            out.append(lines[i])
    out.append("\033[?25h")
    sys.stdout.write("".join(out))
    sys.stdout.flush()

def write_status(lines, cols, rows):
    write_frame(lines, cols, rows)

# ---------- main ----------
def main():
    cfg = load_cfg()
    cache = load_cache()
    art_cache = {}

    key = None
    synced, lyrics = False, []
    art_lines = None
    raw_lyric_text = None
    loading = False
    load_started = 0.0
    last_key = None

    while True:
        # ---- handle keys ----
        k = get_key()
        if k:
            if k in ("q", "\x03", "\x1b"):  # q, Ctrl-C, ESC
                break
            elif k == "[":
                cfg["timing_offset"] -= 0.25
                save_cfg(cfg)
                last_key = None
            elif k == "]":
                cfg["timing_offset"] += 0.25
                save_cfg(cfg)
                last_key = None
            elif k == "a":
                cfg["show_album_art"] = not cfg["show_album_art"]
                save_cfg(cfg)
                art_lines = None if not cfg["show_album_art"] else art_cache.get(key, None)
                last_key = None
            elif k == "r":
                ck = f"{key[0]}|{key[1]}|{key[2]}" if key else None
                if ck and ck in cache:
                    del cache[ck]
                key = None
                last_key = None

        # ---- track ----
        track = current_track()
        if not track:
            idle = ["", "  No MPRIS player detected.",
                    "  Start music in mpv / VLC / Rhythmbox.",
                    "", "  q to quit"]
            cols, rows = shutil.get_terminal_size((80, 24))
            if last_key != "idle":
                write_frame(idle, cols, rows)
                last_key = "idle"
            time.sleep(0.15)
            continue

        artist, title, album, dur, art_url = track
        nk = (artist, title, album)

        if nk != key:
            key = nk
            synced, lyrics = False, []
            raw_lyric_text = None
            loading = True
            load_started = time.time()
            last_key = None
            # render loading state
            cols, rows = shutil.get_terminal_size((80, 24))
            write_frame(["", f"  {artist} \u2014 {title}",
                         "", "  Searching LRCLIB\u2026"], cols, rows)
            # fetch
            raw_lyric_text, _ = fetch_lyrics(artist, title, album, dur, cache)
            save_cache(cache)
            synced, lyrics = parse_lrc(raw_lyric_text)
            loading = False

        if art_lines is None and cfg["show_album_art"] and art_url:
            if art_url not in art_cache:
                art_cache[art_url] = render_art(art_url, cfg)
            art_lines = art_cache[art_url]

        # ---- position ----
        pos_s = run(["playerctl", "position"])
        try: pos = float(pos_s) if pos_s else 0.0
        except ValueError: pos = 0.0
        pos = max(0.0, pos + cfg["timing_offset"])

        idx = -1
        if synced:
            for i, (t, _) in enumerate(lyrics):
                if t <= pos: idx = i
                else: break

        # ---- render ----
        cols, rows = shutil.get_terminal_size((80, 24))
        if lyrics:
            k = (idx, int(pos), cfg["show_album_art"],
                 cfg["timing_offset"], artist, title, cols, rows)
            if k != last_key:
                frame = build(artist, title, lyrics, synced, idx, pos, dur,
                              art_lines if cfg["show_album_art"] else None,
                              cfg, cols, rows)
                write_frame(frame, cols, rows)
                last_key = k
        else:
            msg = ["", f"  {artist} \u2014 {title}", "",
                   "  No lyrics found for this track.",
                   "  Press r to retry, q to quit."]
            k = f"nl_{artist}_{title}"
            if last_key != k:
                write_frame(msg, cols, rows)
                last_key = k

        time.sleep(0.08)

# ---------- entry ----------
if __name__ == "__main__":
    old_term = None
    try:
        enter_alt()
        old_term = setup_raw()
        main()
    except KeyboardInterrupt:
        pass
    finally:
        if old_term is not None:
            restore_term(old_term)
        exit_alt()
