"""
CRSMCPAI Alpha - PQ Video Engine (Real Generation)
Real BMP frame and animated GIF clip generation. Pure Python stdlib.
Built to supreme hyper immaculate God mode standards.
Tier: PQ.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import struct
import base64
import math

pq_video_router = APIRouter(prefix="/pq-video", tags=["pq-video"])

MAX_FRAME_W = 320
MAX_FRAME_H = 240
MAX_CLIP_W = 160
MAX_CLIP_H = 120
MAX_CLIP_FRAMES = 10

PALETTE = [
    (0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]
PATTERNS = ("gradient", "checker", "pulse")


def _pattern_color(pattern, x, y, w, h, frame=0):
    if pattern == "checker":
        return PALETTE[7] if ((x // 8) + (y // 8) + frame) % 2 == 0 else PALETTE[0]
    if pattern == "pulse":
        cx, cy = w / 2.0, h / 2.0
        d = math.hypot(x - cx, y - cy)
        band = int((d + frame * 6) / 8) % 2
        return PALETTE[7] if band == 0 else PALETTE[1]
    t = (x + frame * 4) / max(w - 1, 1)
    v = int(255 * t)
    return (v, v, v)


def _frame_bmp(pattern, w, h, frame=0):
    row_size = (w * 3 + 3) // 4 * 4
    pixel_data = bytearray()
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b = _pattern_color(pattern, x, y, w, h, frame)
            row += bytes((b, g, r))
        row += b"\x00" * (row_size - len(row))
        pixel_data += row
    file_size = 54 + len(pixel_data)
    header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 54)
    dib = struct.pack("<IIIHHIIIIII", 40, w, h, 1, 24, 0,
                      len(pixel_data), 2835, 2835, 0, 0)
    return header + dib + bytes(pixel_data)


def _frame_indices(pattern, w, h, frame=0):
    idx = []
    for y in range(h):
        for x in range(w):
            r, g, b = _pattern_color(pattern, x, y, w, h, frame)
            best, best_d = 0, None
            for i, (pr, pg, pb) in enumerate(PALETTE):
                d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
                if best_d is None or d < best_d:
                    best, best_d = i, d
            idx.append(best)
    return idx


def _lzw_compress(pixels, min_code_size):
    clear = 1 << min_code_size
    eoi = clear + 1
    table = {bytes([i]): i for i in range(clear)}
    next_code = eoi + 1
    code_size = min_code_size + 1
    out = []

    def emit(code, size):
        out.append((code, size))

    emit(clear, code_size)
    w = b""
    for p in pixels:
        b = bytes([p])
        wk = w + b
        if wk in table:
            w = wk
        else:
            emit(table[w], code_size)
            if next_code < 4096:
                table[wk] = next_code
                next_code += 1
                if next_code > (1 << code_size) and code_size < 12:
                    code_size += 1
            w = b
    if w:
        emit(table[w], code_size)
    emit(eoi, code_size)

    data = bytearray()
    acc = 0
    nbits = 0
    for code, size in out:
        acc |= code << nbits
        nbits += size
        while nbits >= 8:
            data.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8
    if nbits:
        data.append(acc & 0xFF)
    return bytes(data)


def _clip_gif(pattern, w, h, frames, fps):
    min_code_size = 3
    out = bytearray()
    out += b"GIF89a"
    out += struct.pack("<HHB", w, h, 0xF2) + b"\x00\x00"
    for (r, g, b) in PALETTE:
        out += bytes((r, g, b))
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    delay = max(1, int(round(100 / fps)))
    for f in range(frames):
        out += b"\x21\xf9\x04\x00" + struct.pack("<H", delay) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHH", 0, 0, w, h) + b"\x00"
        pixels = _frame_indices(pattern, w, h, f)
        comp = _lzw_compress(pixels, min_code_size)
        out += bytes([min_code_size])
        for i in range(0, len(comp), 255):
            chunk = comp[i:i + 255]
            out += bytes([len(chunk)]) + chunk
        out += b"\x00"
    out += b"\x3b"
    return bytes(out)


@pq_video_router.get("/status")
async def pq_video_status():
    return JSONResponse(content={
        "engine": "PQ Video Engine", "tier": "PQ",
        "status": "ACTIVE",
        "capabilities": ["BMP frame generation", "animated GIF clips",
                         "patterns: gradient/checker/pulse", "base64 delivery"],
        "limits": {"frame_max": "320x240", "clip_max": "160x120",
                   "clip_frames_max": MAX_CLIP_FRAMES}})


@pq_video_router.post("/frame")
async def pq_video_frame(request: dict):
    w = max(1, min(int(request.get("width", 160)), MAX_FRAME_W))
    h = max(1, min(int(request.get("height", 120)), MAX_FRAME_H))
    pattern = request.get("pattern", "gradient")
    if pattern not in PATTERNS:
        pattern = "gradient"
    bmp = _frame_bmp(pattern, w, h)
    return JSONResponse(content={
        "pattern": pattern, "width": w, "height": h,
        "format": "BMP/24bit",
        "image_base64": base64.b64encode(bmp).decode()})


@pq_video_router.post("/clip")
async def pq_video_clip(request: dict):
    w = max(1, min(int(request.get("width", 160)), MAX_CLIP_W))
    h = max(1, min(int(request.get("height", 120)), MAX_CLIP_H))
    frames = max(1, min(int(request.get("frames", 4)), MAX_CLIP_FRAMES))
    fps = max(1, min(int(request.get("fps", 4)), 30))
    pattern = request.get("pattern", "pulse")
    if pattern not in PATTERNS:
        pattern = "pulse"
    gif = _clip_gif(pattern, w, h, frames, fps)
    return JSONResponse(content={
        "pattern": pattern, "width": w, "height": h,
        "frames": frames, "fps": fps, "format": "GIF89a/animated",
        "clip_base64": base64.b64encode(gif).decode()})
