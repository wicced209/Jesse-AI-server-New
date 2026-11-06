"""
CRS steganography tooling — image encode / decode tied to coloured books and ledgers.
Owner: SLMK Jesse Martinez Junior
Stdlib-only LSB-style payload embedding in PPM (no external image libs required).
"""
import hashlib
import os
import struct
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event

BASE = os.path.dirname(__file__)
OUT = os.path.join(BASE, "out")
os.makedirs(OUT, exist_ok=True)


def _bytes_to_bits(data: bytes):
    for b in data:
        for i in range(8):
            yield (b >> (7 - i)) & 1


def _bits_to_bytes(bits):
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits):
                byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return bytes(out)


class CRSStego:
    MODULE_ID = "crs_steganography"
    OWNER = SOVEREIGN_OWNER

    def __init__(self):
        log_event(f"[{self.MODULE_ID}] initialized — PPM LSB, stdlib only")

    def status(self):
        return {
            "module": self.MODULE_ID,
            "owner": self.OWNER,
            "status": "LIVE",
            "format": "PPM (P6) LSB",
            "tied_to": ["coloured_books", "ledgers", "CRS"],
        }

    def encode(self, payload: bytes, width: int = 64, height: int = 64, label: str = "crs") -> dict:
        """Embed payload length-prefixed into a PPM image via LSB of RGB bytes."""
        header = struct.pack(">I", len(payload)) + payload
        bits = list(_bytes_to_bits(header))
        need = len(bits)
        capacity = width * height * 3
        if need > capacity:
            return {"ok": False, "error": f"payload too large for {width}x{height}"}
        # Generate carrier from genesis + label for determinism
        seed = hashlib.sha3_256(f"{label}|{self.OWNER}".encode()).digest()
        pixels = bytearray()
        for i in range(capacity):
            pixels.append(seed[i % len(seed)])
        for i, bit in enumerate(bits):
            pixels[i] = (pixels[i] & 0xFE) | bit
        path = os.path.join(OUT, f"{label}_{int(time.time())}.ppm")
        with open(path, "wb") as f:
            f.write(f"P6\n{width} {height}\n255\n".encode())
            f.write(pixels)
        return {
            "ok": True,
            "path": path,
            "payload_len": len(payload),
            "width": width,
            "height": height,
            "owner": self.OWNER,
        }

    def decode(self, path: str) -> dict:
        with open(path, "rb") as f:
            # Skip PPM header (3 lines)
            f.readline()
            f.readline()
            f.readline()
            data = f.read()
        bits = [(b & 1) for b in data]
        raw = _bits_to_bytes(bits)
        if len(raw) < 4:
            return {"ok": False, "error": "too short"}
        length = struct.unpack(">I", raw[:4])[0]
        payload = raw[4:4 + length]
        return {
            "ok": True,
            "payload": payload,
            "payload_len": length,
            "payload_hex": payload.hex(),
            "owner": self.OWNER,
        }


crs_stego = CRSStego()
