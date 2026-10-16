"""
CRSMCPAI Alpha - Quantum & Post-Quantum Video Engines (crs.engines.video_pq)

Extends the PQ video patterns with higher tiers:
- QUANTUM tier: gradient mesh backgrounds, particle field animation,
  plasma/fractal interference patterns (all as 24-bit BMP frames).
- POST-QUANTUM tier: multi-layer alpha compositing, crossfade transitions,
  geometric HUD overlays (grids, waveforms, frame reticles),
  animated GIF clip assembly from quantum frames.

Crash-proof guarantees:
- Standard library only (struct, math)
- NO FastAPI / web imports
- NO module-level I/O, deterministic (integer seeds only)
- All functions defensive: bad input returns safe defaults, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import struct
import math

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
MAX_FRAME_W = 320
MAX_FRAME_H = 240
MAX_CLIP_W = 160
MAX_CLIP_H = 120
MAX_CLIP_FRAMES = 10


def _clamp_int(v, lo, hi, default=None):
    try:
        i = int(v)
    except Exception:
        return default if default is not None else lo
    return max(lo, min(hi, i))


def _clamp_rgb(c):
    try:
        r, g, b = c
        return (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))
    except Exception:
        return (0, 0, 0)


def _blank(w, h, color=(0, 0, 0)):
    c = _clamp_rgb(color)
    return [[c for _ in range(w)] for _ in range(h)]


def _pixels_to_bmp(pixels):
    """Encode a h x w RGB pixel grid to 24-bit BMP bytes."""
    try:
        h = len(pixels)
        w = len(pixels[0]) if h else 0
        if w <= 0 or h <= 0:
            return b""
        row_size = ((w * 3 + 3) // 4) * 4
        padding = row_size - w * 3
        img = bytearray()
        for y in range(h - 1, -1, -1):
            row = pixels[y]
            for x in range(w):
                r, g, b = _clamp_rgb(row[x] if x < len(row) else (0, 0, 0))
                img.extend((b, g, r))
            img.extend(b"\x00" * padding)
        file_size = 54 + len(img)
        header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 54)
        dib = struct.pack("<IIIHHIIIIII", 40, w, h, 1, 24, 0, len(img), 0, 0, 0, 0)
        return header + dib + bytes(img)
    except Exception:
        return b""


def _bmp_to_pixels(data):
    """Decode 24-bit BMP bytes to (w, h, pixel grid). Returns (0,0,[]) on failure."""
    try:
        if not isinstance(data, (bytes, bytearray)) or len(data) < 54:
            return (0, 0, [])
        if data[0:2] != b"BM":
            return (0, 0, [])
        w = struct.unpack("<I", data[18:22])[0]
        h = struct.unpack("<I", data[22:26])[0]
        bpp = struct.unpack("<H", data[28:30])[0]
        offset = struct.unpack("<I", data[10:14])[0]
        if bpp != 24 or w <= 0 or h <= 0 or w > 4096 or h > 4096:
            return (0, 0, [])
        row_size = ((w * 3 + 3) // 4) * 4
        pixels = []
        for y in range(h):
            row = []
            base = offset + (h - 1 - y) * row_size
            for x in range(w):
                i = base + x * 3
                b, g, r = data[i], data[i + 1], data[i + 2]
                row.append((r, g, b))
            pixels.append(row)
        return (w, h, pixels)
    except Exception:
        return (0, 0, [])


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


def generate_quantum_gradient_mesh_frame(width, height, color_a=(20, 40, 90),
                                         color_b=(150, 60, 180), shift_factor=0.0):
    """Bi-directional gradient mesh with sinusoidal distortion. Returns BMP bytes."""
    try:
        w = _clamp_int(width, 1, MAX_FRAME_W, 160)
        h = _clamp_int(height, 1, MAX_FRAME_H, 120)
        ca = _clamp_rgb(color_a)
        cb = _clamp_rgb(color_b)
        try:
            shift = float(shift_factor)
        except Exception:
            shift = 0.0
        shift = max(0.0, min(1.0, shift))
        pixels = []
        for y in range(h):
            row = []
            ny = y / max(h - 1, 1)
            for x in range(w):
                nx = x / max(w - 1, 1)
                wave_ = 0.5 + 0.5 * math.sin(2 * math.pi * (nx + ny + shift * 2.0))
                t = (nx * 0.6 + ny * 0.4 + wave_ * 0.35) / 1.35
                t = max(0.0, min(1.0, t))
                r = int(ca[0] + (cb[0] - ca[0]) * t)
                g = int(ca[1] + (cb[1] - ca[1]) * t)
                b = int(ca[2] + (cb[2] - ca[2]) * t)
                row.append((r, g, b))
            pixels.append(row)
        return _pixels_to_bmp(pixels)
    except Exception:
        return b""


def generate_quantum_particle_field_frame(width, height, num_particles=100,
                                          seed=1, frame_index=0):
    """Deterministic particle starfield with motion trails. Returns BMP bytes."""
    try:
        w = _clamp_int(width, 1, MAX_FRAME_W, 160)
        h = _clamp_int(height, 1, MAX_FRAME_H, 120)
        try:
            n = int(num_particles)
        except Exception:
            n = 100
        n = max(0, min(n, 500))
        try:
            fi = int(frame_index)
        except Exception:
            fi = 0
        pixels = _blank(w, h, (2, 3, 10))
        rng = _lcg((int(seed) if isinstance(seed, int) else 1) * 100003 + fi * 7919)
        for _ in range(n):
            px = int(next(rng) * w)
            py = int(next(rng) * h)
            bright = 0.4 + next(rng) * 0.6
            vx = (next(rng) - 0.5) * 4.0
            vy = (next(rng) - 0.5) * 4.0
            hue = next(rng)
            if hue < 0.5:
                col = (int(200 * bright), int(220 * bright), 255)
            elif hue < 0.8:
                col = (255, int(200 * bright), int(150 * bright))
            else:
                col = (int(170 * bright), 255, int(220 * bright))
            # head + short trail
            for t_step in range(3):
                tx = int(px - vx * t_step)
                ty = int(py - vy * t_step)
                if 0 <= tx < w and 0 <= ty < h:
                    fade = bright * (1.0 - t_step * 0.3)
                    pr, pg, pb = pixels[ty][tx]
                    pixels[ty][tx] = (
                        min(255, int(pr + col[0] * fade * 0.5)),
                        min(255, int(pg + col[1] * fade * 0.5)),
                        min(255, int(pb + col[2] * fade * 0.5)),
                    )
        return _pixels_to_bmp(pixels)
    except Exception:
        return b""


def generate_quantum_plasma_frame(width, height, scale=0.08, time_step=0.0):
    """Demoscene plasma via summed sine interference. Returns BMP bytes."""
    try:
        w = _clamp_int(width, 1, MAX_FRAME_W, 160)
        h = _clamp_int(height, 1, MAX_FRAME_H, 120)
        try:
            sc = float(scale)
        except Exception:
            sc = 0.08
        sc = max(0.001, min(sc, 1.0))
        try:
            tt = float(time_step)
        except Exception:
            tt = 0.0
        pixels = []
        for y in range(h):
            row = []
            for x in range(w):
                v = (math.sin(x * sc + tt)
                     + math.sin(y * sc * 1.3 - tt * 0.7)
                     + math.sin((x + y) * sc * 0.7 + tt * 0.5)
                     + math.sin(math.sqrt(x * x + y * y) * sc * 1.1 - tt))
                v = v / 4.0  # -1..1
                t = (v + 1.0) / 2.0
                # indigo -> cyan -> magenta ramp
                if t < 0.5:
                    k = t * 2.0
                    r, g, b = int(20 + 40 * k), int(10 + 200 * k), int(80 + 120 * k)
                else:
                    k = (t - 0.5) * 2.0
                    r, g, b = int(60 + 195 * k), int(210 - 60 * k), int(200 - 40 * k)
                row.append((r, g, b))
            pixels.append(row)
        return _pixels_to_bmp(pixels)
    except Exception:
        return b""


def composite_video_layers(base_frame, overlay_frame, alpha=0.5):
    """Alpha-blend two BMP frames. Returns BMP bytes (base dimensions)."""
    try:
        try:
            a = float(alpha)
        except Exception:
            a = 0.5
        a = max(0.0, min(1.0, a))
        bw, bh, bp = _bmp_to_pixels(base_frame)
        ow, oh, op = _bmp_to_pixels(overlay_frame)
        if not bp or not op:
            return base_frame if bp else b""
        out = []
        for y in range(bh):
            row = []
            for x in range(bw):
                br, bg, bb = bp[y][x]
                or_, og, ob = op[y % oh][x % ow]
                row.append((
                    int(br * (1 - a) + or_ * a),
                    int(bg * (1 - a) + og * a),
                    int(bb * (1 - a) + ob * a),
                ))
            out.append(row)
        return _pixels_to_bmp(out)
    except Exception:
        try:
            return base_frame if isinstance(base_frame, (bytes, bytearray)) else b""
        except Exception:
            return b""


def apply_crossfade_transition(frame_a, frame_b, step=0, total_steps=10):
    """Crossfade between two BMP frames at step/total_steps. Returns BMP bytes."""
    try:
        try:
            s = int(step)
        except Exception:
            s = 0
        try:
            total = int(total_steps)
        except Exception:
            total = 10
        total = max(1, total)
        s = max(0, min(s, total))
        return composite_video_layers(frame_a, frame_b, s / total)
    except Exception:
        return b""


def render_geometric_hud_overlay(width, height, frame_index=0, color=(0, 255, 180)):
    """Transparent-style HUD: reticle, grid, waveform strip. Returns BMP bytes
    with black background (composite over content with composite_video_layers)."""
    try:
        w = _clamp_int(width, 1, MAX_FRAME_W, 160)
        h = _clamp_int(height, 1, MAX_FRAME_H, 120)
        col = _clamp_rgb(color)
        try:
            fi = int(frame_index)
        except Exception:
            fi = 0
        pixels = _blank(w, h, (0, 0, 0))
        cx, cy = w // 2, h // 2
        # reticle
        rr = min(w, h) // 4
        for deg in range(0, 360, 4):
            rad = math.radians(deg)
            x = int(cx + rr * math.cos(rad))
            y = int(cy + rr * math.sin(rad))
            if 0 <= x < w and 0 <= y < h:
                pixels[y][x] = col
        # crosshair
        for x in range(max(0, cx - rr - 4), min(w, cx + rr + 5)):
            pixels[cy][x] = col
        for y in range(max(0, cy - rr - 4), min(h, cy + rr + 5)):
            pixels[y][cx] = col
        # grid
        for x in range(0, w, max(8, w // 10)):
            for y in range(h):
                if pixels[y][x] == (0, 0, 0):
                    pixels[y][x] = (col[0] // 4, col[1] // 4, col[2] // 4)
        # waveform strip at bottom
        strip_y = h - h // 6
        for x in range(w):
            v = math.sin(x * 0.15 + fi * 0.3) * math.sin(x * 0.05 - fi * 0.15)
            yy = int(strip_y + v * (h // 12))
            if 0 <= yy < h:
                pixels[yy][x] = col
        return _pixels_to_bmp(pixels)
    except Exception:
        return b""


def _lzw_compress(pixels, min_code_size):
    """Minimal LZW compressor for GIF data (mirrors pq_video pattern)."""
    try:
        clear = 1 << min_code_size
        eoi = clear + 1
        table = {bytes([i]): i for i in range(clear)}
        next_code = eoi + 1
        code_size = min_code_size + 1
        out_bits = []

        def emit(code, size):
            for b in range(size):
                out_bits.append((code >> b) & 1)

        emit(clear, code_size)
        prefix = b""
        for px in pixels:
            cur = prefix + bytes([px])
            if cur in table:
                prefix = cur
            else:
                emit(table[prefix], code_size)
                if next_code < 4096:
                    table[cur] = next_code
                    next_code += 1
                    if next_code >= (1 << code_size) and code_size < 12:
                        code_size += 1
                else:
                    emit(clear, code_size)
                    table = {bytes([i]): i for i in range(clear)}
                    next_code = eoi + 1
                    code_size = min_code_size + 1
                prefix = bytes([px])
        if prefix:
            emit(table[prefix], code_size)
        emit(eoi, code_size)
        data = bytearray()
        cur = 0
        nbits = 0
        for bit in out_bits:
            cur |= bit << nbits
            nbits += 1
            if nbits == 8:
                data.append(cur)
                cur = 0
                nbits = 0
        if nbits:
            data.append(cur)
        return bytes(data)
    except Exception:
        return b""


def _quantize_frame(pixels, palette):
    idx = []
    for row in pixels:
        for (r, g, b) in row:
            best, bi = None, 0
            for i, (pr, pg, pb) in enumerate(palette):
                d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                if best is None or d < best:
                    best, bi = d, i
            idx.append(bi)
    return idx


def _web_palette():
    pal = []
    for r in (0, 51, 102, 153, 204, 255):
        for g in (0, 51, 102, 153, 204, 255):
            for b in (0, 51, 102, 153, 204, 255):
                pal.append((r, g, b))
                if len(pal) >= 256:
                    return pal
    return pal


def generate_pq_animated_gif_clip(width, height, frames, pattern="plasma", seed=1):
    """Assemble an animated GIF from quantum pattern frames.

    pattern: plasma | particles | gradient. Returns GIF bytes.
    """
    try:
        w = _clamp_int(width, 1, MAX_CLIP_W, 160)
        h = _clamp_int(height, 1, MAX_CLIP_H, 120)
        try:
            nf = int(frames)
        except Exception:
            nf = 4
        nf = max(1, min(nf, MAX_CLIP_FRAMES))
        pat = str(pattern).lower() if isinstance(pattern, str) else "plasma"
        if pat not in ("plasma", "particles", "gradient"):
            pat = "plasma"
        palette = _web_palette()
        pal_bytes = b"".join(bytes((r, g, b)) for r, g, b in palette)

        gif = bytearray()
        gif.extend(b"GIF89a")
        gif.extend(struct.pack("<HH", w, h))
        gif.extend(b"\xf7\x00\x00")  # GCT flag, 256 colors, bg 0
        gif.extend(pal_bytes)
        # Netscape loop extension (infinite)
        gif.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")

        for f in range(nf):
            if pat == "plasma":
                bmp = generate_quantum_plasma_frame(w, h, 0.08, f * 0.6)
            elif pat == "particles":
                bmp = generate_quantum_particle_field_frame(w, h, 80, seed, f)
            else:
                bmp = generate_quantum_gradient_mesh_frame(
                    w, h, (10, 20, 60), (160, 80, 200), f / max(nf - 1, 1))
            _, _, px = _bmp_to_pixels(bmp)
            if not px:
                continue
            idx = _quantize_frame(px, palette)
            comp = _lzw_compress(idx, 8)
            gif.extend(b"\x21\xf9\x04\x00\x0a\x00\x00\x00")  # GCE: 10cs delay
            gif.extend(b"\x2c")
            gif.extend(struct.pack("<HHHH", 0, 0, w, h))
            gif.extend(b"\x00\x08")  # no local table, min code 8
            for i in range(0, len(comp), 255):
                chunk = comp[i:i + 255]
                gif.append(len(chunk))
                gif.extend(chunk)
            gif.append(0)
        gif.append(0x3B)
        return bytes(gif)
    except Exception:
        return b""


def module_status():
    return {
        "module": "crs.engines.video_pq",
        "status": "ACTIVE",
        "tiers": ["QUANTUM", "POST_QUANTUM"],
        "genesis": GENESIS_HASH[:16],
        "limits": {"frame_max": [MAX_FRAME_W, MAX_FRAME_H],
                   "clip_max": [MAX_CLIP_W, MAX_CLIP_H, MAX_CLIP_FRAMES]},
        "functions": [
            "generate_quantum_gradient_mesh_frame",
            "generate_quantum_particle_field_frame",
            "generate_quantum_plasma_frame",
            "composite_video_layers",
            "apply_crossfade_transition",
            "render_geometric_hud_overlay",
            "generate_pq_animated_gif_clip",
        ],
    }
