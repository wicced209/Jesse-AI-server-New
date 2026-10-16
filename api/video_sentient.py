"""
CRSMCPAI Alpha - Post-Quantum Sentient Video Engine (crs.engines.sentient_video)

Sentient tier above post-quantum video: narrative/intent-driven scene
generation from a high-level scene descriptor.
- Scene descriptor (mood, pace, complexity) -> visual parameter beats
- Keyframe sequence planner across beats with transitions
- Sentient clip renderer -> animated GIF bytes

Crash-proof guarantees:
- Standard library only (struct, math)
- NO FastAPI / web imports, NO imports from sibling engine modules
- NO module-level I/O, deterministic (integer seeds only)
- All functions defensive: bad input returns safe defaults, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import struct
import math

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
MAX_W = 160
MAX_H = 120
MAX_BEATS = 8
MAX_FRAMES_PER_BEAT = 4

MOOD_PRESETS = {
    "calm": {"palette": [((8, 20, 50), (40, 120, 170))],
             "patterns": ["gradient", "particles"], "base_speed": 0.5},
    "urgent": {"palette": [((90, 8, 8), (230, 60, 20)), ((60, 10, 40), (255, 150, 40))],
               "patterns": ["plasma", "particles"], "base_speed": 2.0},
    "triumphant": {"palette": [((20, 30, 80), (240, 200, 80)), ((40, 20, 90), (255, 120, 60))],
                   "patterns": ["plasma", "gradient"], "base_speed": 1.4},
    "mystical": {"palette": [((15, 8, 45), (120, 60, 220)), ((8, 30, 40), (40, 220, 190))],
                 "patterns": ["plasma", "gradient"], "base_speed": 0.8},
    "melancholy": {"palette": [((12, 14, 30), (70, 90, 140))],
                   "patterns": ["gradient", "particles"], "base_speed": 0.6},
}

PACE_MULT = {"slow": 0.5, "moderate": 1.0, "fast": 1.8}


def _lcg(seed):
    try:
        x = int(seed) & 0x7FFFFFFF
    except Exception:
        x = 1
    if x == 0:
        x = 1
    while True:
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        yield x / 0x7FFFFFFF


def _clamp_int(v, lo, hi, default=None):
    try:
        i = int(v)
    except Exception:
        return default if default is not None else lo
    return max(lo, min(hi, i))


def _pixels_to_bmp(pixels):
    try:
        h = len(pixels)
        w = len(pixels[0]) if h else 0
        if w <= 0 or h <= 0:
            return b""
        row_size = ((w * 3 + 3) // 4) * 4
        pad = row_size - w * 3
        img = bytearray()
        for y in range(h - 1, -1, -1):
            row = pixels[y]
            for x in range(w):
                try:
                    r, g, b = row[x]
                    r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))
                except Exception:
                    r, g, b = 0, 0, 0
                img.extend((b, g, r))
            img.extend(b"\x00" * pad)
        header = struct.pack("<2sIHHI", b"BM", 54 + len(img), 0, 0, 54)
        dib = struct.pack("<IIIHHIIIIII", 40, w, h, 1, 24, 0, len(img), 0, 0, 0, 0)
        return header + dib + bytes(img)
    except Exception:
        return b""


def _bmp_to_pixels(data):
    try:
        if not isinstance(data, (bytes, bytearray)) or len(data) < 54 or data[0:2] != b"BM":
            return (0, 0, [])
        w = struct.unpack("<I", data[18:22])[0]
        h = struct.unpack("<I", data[22:26])[0]
        if struct.unpack("<H", data[28:30])[0] != 24 or w <= 0 or h <= 0 or w > 1024 or h > 1024:
            return (0, 0, [])
        off = struct.unpack("<I", data[10:14])[0]
        rs = ((w * 3 + 3) // 4) * 4
        px = []
        for y in range(h):
            row = []
            base = off + (h - 1 - y) * rs
            for x in range(w):
                i = base + x * 3
                b, g, r = data[i], data[i + 1], data[i + 2]
                row.append((r, g, b))
            px.append(row)
        return (w, h, px)
    except Exception:
        return (0, 0, [])


def _render_pattern(pattern, w, h, ca, cb, t, seed):
    """Render one pattern frame as pixel grid. Deterministic."""
    try:
        px = []
        if pattern == "plasma":
            try:
                sc = 0.09
            except Exception:
                sc = 0.09
            for y in range(h):
                row = []
                for x in range(w):
                    v = (math.sin(x * sc + t) + math.sin(y * sc * 1.3 - t * 0.7)
                         + math.sin((x + y) * sc * 0.7 + t * 0.5)) / 3.0
                    k = max(0.0, min(1.0, (v + 1.0) / 2.0))
                    row.append((int(ca[0] + (cb[0] - ca[0]) * k),
                                int(ca[1] + (cb[1] - ca[1]) * k),
                                int(ca[2] + (cb[2] - ca[2]) * k)))
                px.append(row)
        elif pattern == "particles":
            px = [[(ca[0] // 6, ca[1] // 6, ca[2] // 4) for _ in range(w)] for _ in range(h)]
            rng = _lcg(int(seed) * 100003 + int(t * 10) * 7919 + 13)
            for _ in range(60):
                x = int(next(rng) * w)
                y = int(next(rng) * h)
                br = 0.5 + next(rng) * 0.5
                r = int(cb[0] * br)
                g = int(cb[1] * br)
                b = int(cb[2] * br)
                pr, pg, pb = px[y][x]
                px[y][x] = (min(255, pr + r // 2), min(255, pg + g // 2), min(255, pb + b // 2))
        else:  # gradient
            try:
                sh = float(t) * 0.15
            except Exception:
                sh = 0.0
            for y in range(h):
                row = []
                ny = y / max(h - 1, 1)
                for x in range(w):
                    nx = x / max(w - 1, 1)
                    wave_ = 0.5 + 0.5 * math.sin(2 * math.pi * (nx + ny + sh))
                    k = max(0.0, min(1.0, (nx * 0.6 + ny * 0.4 + wave_ * 0.35) / 1.35))
                    row.append((int(ca[0] + (cb[0] - ca[0]) * k),
                                int(ca[1] + (cb[1] - ca[1]) * k),
                                int(ca[2] + (cb[2] - ca[2]) * k)))
                px.append(row)
        return px
    except Exception:
        return [[(0, 0, 0) for _ in range(w)] for _ in range(h)]


def map_scene_to_visual_params(descriptor):
    """Map a scene descriptor to an ordered list of scene beats.

    descriptor: dict with mood, pace, complexity, duration_beats, seed.
    Returns list of beat dicts.
    """
    try:
        d = dict(descriptor) if isinstance(descriptor, dict) else {}
    except Exception:
        d = {}
    try:
        mood = str(d.get("mood", "calm")).strip().lower()
    except Exception:
        mood = "calm"
    preset = MOOD_PRESETS.get(mood, MOOD_PRESETS["calm"])
    try:
        pace = str(d.get("pace", "moderate")).strip().lower()
    except Exception:
        pace = "moderate"
    speed = preset["base_speed"] * PACE_MULT.get(pace, 1.0)
    try:
        complexity = int(d.get("complexity", 5))
    except Exception:
        complexity = 5
    complexity = max(1, min(complexity, 10))
    try:
        beats_n = int(d.get("duration_beats", 4))
    except Exception:
        beats_n = 4
    beats_n = max(1, min(beats_n, MAX_BEATS))
    try:
        seed = int(d.get("seed", 42))
    except Exception:
        seed = 42
    rng = _lcg(seed)
    palettes = preset["palette"]
    patterns = preset["patterns"]
    beats = []
    for i in range(beats_n):
        pal = palettes[int(next(rng) * len(palettes)) % len(palettes)]
        pat = patterns[(i + int(next(rng) * len(patterns))) % len(patterns)]
        # narrative arc: brighten toward middle, resolve at end
        arc = math.sin(math.pi * (i + 1) / (beats_n + 1))
        beats.append({
            "beat_index": i,
            "mood": mood,
            "pattern_type": pat,
            "color_base": pal[0],
            "color_accent": pal[1],
            "motion_speed": round(speed * (0.8 + arc * 0.5), 3),
            "hud_overlay": bool(complexity >= 6 and i % 2 == 0),
            "seed": seed + i * 101,
        })
    return beats


def plan_keyframe_sequence(beats, width=160, height=120, frames_per_beat=3, seed=42):
    """Expand beats into a flat list of BMP frame bytes with transitions."""
    try:
        w = _clamp_int(width, 1, MAX_W, 160)
        h = _clamp_int(height, 1, MAX_H, 120)
        try:
            fpb = int(frames_per_beat)
        except Exception:
            fpb = 3
        fpb = max(1, min(fpb, MAX_FRAMES_PER_BEAT))
        if not isinstance(beats, list) or not beats:
            return []
        frames = []
        prev = None
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            pat = str(beat.get("pattern_type", "gradient"))
            ca = beat.get("color_base", (10, 20, 60))
            cb = beat.get("color_accent", (150, 80, 200))
            try:
                ca = (int(ca[0]), int(ca[1]), int(ca[2]))
                cb = (int(cb[0]), int(cb[1]), int(cb[2]))
            except Exception:
                ca, cb = (10, 20, 60), (150, 80, 200)
            try:
                spd = float(beat.get("motion_speed", 1.0))
            except Exception:
                spd = 1.0
            try:
                bseed = int(beat.get("seed", seed))
            except Exception:
                bseed = 42
            for f in range(fpb):
                t = (len(frames) * 0.55) * max(0.1, min(spd, 3.0))
                px = _render_pattern(pat, w, h, ca, cb, t, bseed)
                bmp = _pixels_to_bmp(px)
                if prev is not None and f == 0:
                    # crossfade from previous beat's last frame
                    bmp = _crossfade_bmp(prev, bmp, 0.5)
                if bmp:
                    frames.append(bmp)
                    prev = bmp
                if len(frames) >= MAX_BEATS * MAX_FRAMES_PER_BEAT:
                    break
            if len(frames) >= MAX_BEATS * MAX_FRAMES_PER_BEAT:
                break
        return frames
    except Exception:
        return []


def _crossfade_bmp(a, b, alpha):
    try:
        aw, ah, ap = _bmp_to_pixels(a)
        bw, bh, bp = _bmp_to_pixels(b)
        if not ap or not bp or aw != bw or ah != bh:
            return b
        out = []
        for y in range(ah):
            row = []
            for x in range(aw):
                ar, ag, ab = ap[y][x]
                br, bg, bb = bp[y][x]
                row.append((int(ar * (1 - alpha) + br * alpha),
                            int(ag * (1 - alpha) + bg * alpha),
                            int(ab * (1 - alpha) + bb * alpha)))
            out.append(row)
        return _pixels_to_bmp(out)
    except Exception:
        return b


def _lzw_compress(pixels, min_code_size):
    try:
        clear = 1 << min_code_size
        eoi = clear + 1
        table = {bytes([i]): i for i in range(clear)}
        nxt = eoi + 1
        size = min_code_size + 1
        bits = []

        def emit(code, sz):
            for b in range(sz):
                bits.append((code >> b) & 1)

        emit(clear, size)
        prefix = b""
        for px in pixels:
            cur = prefix + bytes([px])
            if cur in table:
                prefix = cur
            else:
                emit(table[prefix], size)
                if nxt < 4096:
                    table[cur] = nxt
                    nxt += 1
                    if nxt >= (1 << size) and size < 12:
                        size += 1
                else:
                    emit(clear, size)
                    table = {bytes([i]): i for i in range(clear)}
                    nxt = eoi + 1
                    size = min_code_size + 1
                prefix = bytes([px])
        if prefix:
            emit(table[prefix], size)
        emit(eoi, size)
        data = bytearray()
        cur = nbits = 0
        for bit in bits:
            cur |= bit << nbits
            nbits += 1
            if nbits == 8:
                data.append(cur)
                cur = nbits = 0
        if nbits:
            data.append(cur)
        return bytes(data)
    except Exception:
        return b""


def render_sentient_clip(descriptor, width=160, height=120, frames_per_beat=3):
    """Full pipeline: descriptor -> beats -> frames -> animated GIF bytes."""
    try:
        beats = map_scene_to_visual_params(descriptor)
        frames = plan_keyframe_sequence(beats, width, height, frames_per_beat,
                                        int(descriptor.get("seed", 42)) if isinstance(descriptor, dict) else 42)
        if not frames:
            return b""
        w = _clamp_int(width, 1, MAX_W, 160)
        h = _clamp_int(height, 1, MAX_H, 120)
        palette = []
        for r in (0, 51, 102, 153, 204, 255):
            for g in (0, 51, 102, 153, 204, 255):
                for b in (0, 51, 102, 153, 204, 255):
                    palette.append((r, g, b))
                    if len(palette) >= 256:
                        break
                if len(palette) >= 256:
                    break
            if len(palette) >= 256:
                break
        pal_bytes = b"".join(bytes((r, g, b)) for r, g, b in palette)
        gif = bytearray(b"GIF89a")
        gif.extend(struct.pack("<HH", w, h))
        gif.extend(b"\xf7\x00\x00")
        gif.extend(pal_bytes)
        gif.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")
        for bmp in frames:
            _, _, px = _bmp_to_pixels(bmp)
            if not px:
                continue
            idx = []
            for row in px:
                for (r, g, b) in row:
                    best, bi = None, 0
                    for i, (pr, pg, pb) in enumerate(palette):
                        dd = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                        if best is None or dd < best:
                            best, bi = dd, i
                    idx.append(bi)
            comp = _lzw_compress(idx, 8)
            if not comp:
                continue
            gif.extend(b"\x21\xf9\x04\x00\x0a\x00\x00\x00")
            gif.extend(b"\x2c")
            gif.extend(struct.pack("<HHHH", 0, 0, w, h))
            gif.extend(b"\x00\x08")
            for i in range(0, len(comp), 255):
                ch = comp[i:i + 255]
                gif.append(len(ch))
                gif.extend(ch)
            gif.append(0)
        gif.append(0x3B)
        return bytes(gif)
    except Exception:
        return b""


def module_status():
    return {
        "module": "crs.engines.sentient_video",
        "status": "ACTIVE",
        "tier": "POST_QUANTUM_SENTIENT",
        "genesis": GENESIS_HASH[:16],
        "moods": sorted(MOOD_PRESETS.keys()),
        "functions": [
            "map_scene_to_visual_params",
            "plan_keyframe_sequence",
            "render_sentient_clip",
        ],
    }
