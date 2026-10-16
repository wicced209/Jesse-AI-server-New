"""
CRSMCPAI Alpha - PQ Audio Engine (Real Generation)
Real PCM audio synthesis. Tone generation, song composition.
Built to supreme hyper immaculate God mode standards.
Tier: PQ (stepped down from PQS per superadmin directive).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import wave
import struct
import math
import base64
import io

pq_audio_router = APIRouter(prefix="/pq-audio", tags=["pq-audio"])
SAMPLE_RATE = 44100
MAX_SONG_SEC = 120.0

# Equal-temperament note map, C4..B5 (A4 = 440 Hz)
_NOTE_OFFSETS = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
                 "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
                 "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def _note_freq(name: str) -> float:
    """Convert note name like 'C4' or 'F#5' to Hz (A4=440)."""
    name = name.strip()
    if len(name) < 2:
        raise ValueError(f"Bad note name: {name}")
    if name[1] in ("#", "b"):
        pitch, octave_s = name[:2], name[2:]
    else:
        pitch, octave_s = name[:1], name[1:]
    if pitch not in _NOTE_OFFSETS:
        raise ValueError(f"Unknown pitch: {pitch}")
    octave = int(octave_s)
    if not (4 <= octave <= 5):
        raise ValueError(f"Octave out of range C4-B5: {name}")
    midi = 12 * (octave + 1) + _NOTE_OFFSETS[pitch]
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _note_table():
    table = {}
    for pitch in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]:
        for octave in (4, 5):
            n = f"{pitch}{octave}"
            table[n] = round(_note_freq(n), 2)
    return table


def _tone_wav(freq_hz: float, duration_sec: float) -> bytes:
    n = int(SAMPLE_RATE * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        for i in range(n):
            t = i / SAMPLE_RATE
            env = min(1.0, i / (SAMPLE_RATE * 0.01), (n - i) / (SAMPLE_RATE * 0.05))
            val = int(32767 * 0.5 * env * math.sin(2 * math.pi * freq_hz * t))
            w.writeframes(struct.pack("<h", val))
    return buf.getvalue()


def _noise_burst(duration_sec: float, seed: int = 7) -> list:
    """Deterministic hi-hat style noise burst (LCG pseudo-noise, highpassed)."""
    n = int(SAMPLE_RATE * duration_sec)
    x = seed
    out = []
    prev = 0.0
    for _ in range(n):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        white = (x / 0x7FFFFFFF) * 2.0 - 1.0
        hp = white - prev  # crude highpass for hat-like sizzle
        prev = white
        env = max(0.0, 1.0 - (_ / max(n, 1)))
        out.append(hp * env * 0.35)
    return out


def _compose_wav(title: str, tempo_bpm: float, melody: list) -> tuple:
    """Mix melody + bass + hi-hat into PCM16 WAV bytes. Returns (wav_bytes, duration_sec)."""
    beat = 60.0 / max(20.0, min(240.0, tempo_bpm))
    events = []
    total_beats = 0.0
    for pair in melody:
        name, beats = pair[0], float(pair[1])
        beats = max(0.0625, min(16.0, beats))
        events.append((_note_freq(name), total_beats * beat, beats * beat))
        total_beats += beats
    total_sec = min(total_beats * beat, MAX_SONG_SEC)
    n = int(SAMPLE_RATE * total_sec)
    mix = [0.0] * n

    def _add(samples, start_sec, gain=1.0):
        s0 = int(start_sec * SAMPLE_RATE)
        for i, v in enumerate(samples):
            j = s0 + i
            if j >= n:
                break
            mix[j] += v * gain

    # Melody: sine + 2nd harmonic with ADSR-ish envelope
    for freq, start, dur in events:
        if start >= total_sec:
            break
        m = int(SAMPLE_RATE * min(dur, total_sec - start))
        attack = int(SAMPLE_RATE * 0.01)
        release = int(SAMPLE_RATE * 0.05)
        seg = []
        for i in range(m):
            t = i / SAMPLE_RATE
            env = min(1.0, i / max(attack, 1), (m - i) / max(release, 1))
            v = (math.sin(2 * math.pi * freq * t)
                 + 0.3 * math.sin(4 * math.pi * freq * t)) * env * 0.4
            seg.append(v)
        _add(seg, start)

    # Bass: root pitch one octave down, half notes across the song
    roots = []
    for freq, start, dur in events:
        root = freq / 2.0
        if root not in roots:
            roots.append(root)
    if not roots:
        roots = [110.0]
    half = beat * 2.0
    t = 0.0
    ri = 0
    while t < total_sec:
        root = roots[ri % len(roots)]
        m = int(SAMPLE_RATE * min(half, total_sec - t))
        seg = [0.5 * math.sin(2 * math.pi * root * (i / SAMPLE_RATE))
               * min(1.0, i / max(int(SAMPLE_RATE * 0.02), 1)) for i in range(m)]
        _add(seg, t, gain=0.8)
        t += half
        ri += 1

    # Hi-hat: noise bursts on eighth notes
    eighth = beat / 2.0
    burst = _noise_burst(min(0.05, eighth))
    t = 0.0
    while t < total_sec:
        _add(burst, t, gain=0.6)
        t += eighth

    # Normalize and pack
    peak = max((abs(v) for v in mix), default=1.0)
    scale = 0.9 / peak if peak > 0.9 else 1.0
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        for v in mix:
            w.writeframes(struct.pack("<h", int(max(-1.0, min(1.0, v * scale)) * 32767)))
    return buf.getvalue(), round(total_sec, 2)


@pq_audio_router.get("/status")
async def pq_audio_status():
    return JSONResponse(content={
        "engine": "PQ Audio Engine", "tier": "PQ",
        "status": "ACTIVE", "sample_rate": SAMPLE_RATE,
        "capabilities": ["tone synthesis", "song composition",
                         "melody/harmony/rhythm layers",
                         "WAV output", "base64 delivery"]})


@pq_audio_router.post("/tone")
async def pq_audio_tone(request: dict):
    freq = float(request.get("frequency_hz", 440.0))
    dur = min(float(request.get("duration_sec", 1.0)), 30.0)
    wav_bytes = _tone_wav(freq, dur)
    return JSONResponse(content={
        "frequency_hz": freq, "duration_sec": dur,
        "format": "WAV/PCM16/mono/44100",
        "audio_base64": base64.b64encode(wav_bytes).decode()})


@pq_audio_router.get("/notes")
async def pq_audio_notes():
    return JSONResponse(content={
        "range": "C4-B5", "tuning": "A4=440 equal temperament",
        "notes": _note_table()})


@pq_audio_router.post("/compose")
async def pq_audio_compose(request: dict):
    title = str(request.get("title", "untitled"))
    tempo = float(request.get("tempo_bpm", 120.0))
    melody = request.get("melody", [["C4", 1], ["E4", 1], ["G4", 2]])
    if not isinstance(melody, list) or not melody:
        return JSONResponse(status_code=400,
                            content={"error": "melody must be a non-empty list of [note, beats]"})
    try:
        wav_bytes, duration = _compose_wav(title, tempo, melody)
    except (ValueError, KeyError, TypeError, IndexError) as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid melody: {e}"})
    return JSONResponse(content={
        "title": title, "tempo_bpm": tempo,
        "duration_sec": duration, "format": "WAV/PCM16/mono/44100",
        "layers": ["melody", "bass", "hi-hat"],
        "audio_base64": base64.b64encode(wav_bytes).decode()})
