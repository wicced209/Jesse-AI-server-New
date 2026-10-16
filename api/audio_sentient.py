"""
CRSMCPAI Alpha - Post-Quantum Sentient Audio Engine (crs.engines.sentient_audio)

Sentient tier above post-quantum: emotive, intent-driven synthesis.
- Emotion/intent descriptor -> acoustic parameter mapping
- Deterministic generative melodic motifs (seeded)
- Full emotive arrangement rendering to WAV bytes

Crash-proof guarantees:
- Standard library only (math, struct, wave, io)
- NO FastAPI / web imports
- NO module-level I/O, deterministic (integer seeds only)
- Guarded reuse of api.audio_quantum primitives with local fallbacks
- All functions defensive: bad input returns safe defaults, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import math
import struct
import wave
import io

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
SAMPLE_RATE = 44100
MAX_DURATION_SEC = 120.0

# --- Guarded reuse of quantum-tier primitives (fallbacks if unavailable) ---
try:
    from api.audio_quantum import (  # type: ignore
        synthesize_quantum_tone as _qtone,
        generate_adsr_envelope as _qadsr,
        apply_chorus_detune as _qchorus,
        export_wav_bytes as _qwav,
    )
    _HAS_Q = True
except Exception:
    _HAS_Q = False


def _fallback_tone(freq, dur, harmonics, sr=44100):
    n = max(1, min(int(sr * max(0.01, min(dur, MAX_DURATION_SEC))), SAMPLE_RATE * 10))
    weights = list(harmonics or [1.0])[:8]
    total = sum(weights) or 1.0
    out = []
    for i in range(n):
        t = i / sr
        v = sum(w * math.sin(2.0 * math.pi * freq * (h + 1) * t)
                for h, w in enumerate(weights))
        out.append(max(-1.0, min(1.0, v / total)))
    return out


def _fallback_wav(mono, sr=44100):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for x in mono:
            w.writeframes(struct.pack("<h", int(max(-1.0, min(1.0, x)) * 32767)))
    return buf.getvalue()


def _tone(freq, dur, harmonics, sr=44100):
    try:
        if _HAS_Q:
            return _qtone(freq, dur, harmonics, sr)
    except Exception:
        pass
    return _fallback_tone(freq, dur, harmonics, sr)


def _wav(mono, sr=44100):
    try:
        if _HAS_Q:
            return _qwav(mono, None, sr)
    except Exception:
        pass
    return _fallback_wav(mono, sr)


EMOTION_PROFILES = {
    "calm": {"tempo_bpm": 60.0, "brightness": 0.7, "harmonic_spread": 3,
             "attack_sec": 0.40, "release_sec": 0.80, "chorus_depth": 0.004,
             "scale": [0, 3, 5, 7, 10], "base_note": 220.0},
    "urgent": {"tempo_bpm": 140.0, "brightness": 1.8, "harmonic_spread": 6,
               "attack_sec": 0.02, "release_sec": 0.10, "chorus_depth": 0.012,
               "scale": [0, 2, 3, 5, 7, 8, 10], "base_note": 246.94},
    "triumphant": {"tempo_bpm": 110.0, "brightness": 1.5, "harmonic_spread": 5,
                   "attack_sec": 0.10, "release_sec": 0.40, "chorus_depth": 0.008,
                   "scale": [0, 2, 4, 7, 9], "base_note": 261.63},
    "melancholy": {"tempo_bpm": 70.0, "brightness": 0.6, "harmonic_spread": 4,
                   "attack_sec": 0.30, "release_sec": 0.90, "chorus_depth": 0.006,
                   "scale": [0, 3, 5, 7, 8, 10], "base_note": 196.00},
    "mysterious": {"tempo_bpm": 80.0, "brightness": 1.0, "harmonic_spread": 5,
                   "attack_sec": 0.25, "release_sec": 0.60, "chorus_depth": 0.010,
                   "scale": [0, 1, 5, 6, 10], "base_note": 207.65},
}


def _lcg(seed):
    """Deterministic pseudo-random generator (LCG). Yields floats in [0,1)."""
    try:
        x = int(seed) & 0x7FFFFFFF
    except Exception:
        x = 1
    if x == 0:
        x = 1
    while True:
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        yield x / 0x7FFFFFFF


def map_emotion_to_parameters(emotion):
    """Map an emotion descriptor to synthesis parameters. Falls back to calm."""
    try:
        key = str(emotion).strip().lower() if emotion is not None else "calm"
    except Exception:
        key = "calm"
    profile = EMOTION_PROFILES.get(key, EMOTION_PROFILES["calm"])
    return {
        "emotion": key if key in EMOTION_PROFILES else "calm",
        "tempo_bpm": float(profile["tempo_bpm"]),
        "brightness": float(profile["brightness"]),
        "harmonic_spread": int(profile["harmonic_spread"]),
        "attack_sec": float(profile["attack_sec"]),
        "release_sec": float(profile["release_sec"]),
        "chorus_depth": float(profile["chorus_depth"]),
    }


def generate_melodic_motif(seed, emotion="calm", num_notes=8):
    """Deterministic melodic phrase from seed + emotion. Returns note dicts."""
    try:
        params = map_emotion_to_parameters(emotion)
        try:
            count = int(num_notes)
        except Exception:
            count = 8
        count = max(1, min(count, 64))
        profile = EMOTION_PROFILES.get(params["emotion"], EMOTION_PROFILES["calm"])
        scale = profile["scale"]
        base = float(profile["base_note"])
        tempo = float(params["tempo_bpm"])
        beat = 60.0 / max(20.0, min(tempo, 240.0))
        rng = _lcg(seed)
        notes = []
        degree = 0
        for _ in range(count):
            step = int(next(rng) * 5) - 2  # -2..+2 scale steps
            degree = max(-7, min(14, degree + step))
            semis = scale[degree % len(scale)] + 12 * (degree // len(scale))
            freq = base * (2.0 ** (semis / 12.0))
            dur_choices = [0.5, 0.5, 1.0, 1.0, 1.5, 2.0]
            dur = dur_choices[int(next(rng) * len(dur_choices))] * beat
            vel = 0.5 + next(rng) * 0.5
            notes.append({
                "frequency": round(freq, 2),
                "duration": round(dur, 3),
                "velocity": round(vel, 3),
            })
        return notes
    except Exception:
        return []


def build_sentient_arrangement(seed=1, emotion="calm", duration_sec=4.0):
    """Render a full emotive arrangement to WAV bytes. Never raises."""
    try:
        try:
            dur = float(duration_sec)
        except Exception:
            dur = 4.0
        dur = max(0.5, min(dur, MAX_DURATION_SEC))
        params = map_emotion_to_parameters(emotion)
        n = int(SAMPLE_RATE * dur)
        mix = [0.0] * n
        spread = max(1, min(int(params["harmonic_spread"]), 8))
        harmonics = [1.0 / (h + 1) for h in range(spread)]
        # brighten: boost upper harmonics with brightness factor
        bright = max(0.1, min(params["brightness"], 2.0))
        harmonics = [w * (bright if h > 0 else 1.0) for h, w in enumerate(harmonics)]
        total = sum(harmonics) or 1.0
        harmonics = [w / total for w in harmonics]

        motif = generate_melodic_motif(seed, params["emotion"], num_notes=12)
        if not motif:
            motif = [{"frequency": 440.0, "duration": dur, "velocity": 0.7}]

        # schedule motif across the duration (loop if needed)
        t = 0.0
        idx = 0
        while t < dur and idx < 512:
            note = motif[idx % len(motif)]
            nd = min(float(note["duration"]), dur - t)
            if nd <= 0:
                break
            tone = _tone(float(note["frequency"]), nd, harmonics, SAMPLE_RATE)
            start = int(t * SAMPLE_RATE)
            vel = float(note["velocity"])
            atk = int(float(params["attack_sec"]) * SAMPLE_RATE)
            rel = int(float(params["release_sec"]) * SAMPLE_RATE)
            for i, v in enumerate(tone):
                pos = start + i
                if pos >= n:
                    break
                env = 1.0
                if atk > 0 and i < atk:
                    env = i / atk
                if rel > 0 and i >= len(tone) - rel:
                    env = max(0.0, (len(tone) - i) / rel)
                mix[pos] += v * vel * env * 0.5
            t += nd
            idx += 1

        # gentle chorus for sentient shimmer
        try:
            if _HAS_Q:
                mix = _qchorus(mix, SAMPLE_RATE, depth=float(params["chorus_depth"]),
                               rate=0.8)
        except Exception:
            pass
        mix = [max(-1.0, min(1.0, x)) for x in mix]
        return bytearray(_wav(mix, SAMPLE_RATE))
    except Exception:
        try:
            return bytearray(_wav([0.0] * SAMPLE_RATE, SAMPLE_RATE))
        except Exception:
            return bytearray()


def module_status():
    return {
        "module": "crs.engines.sentient_audio",
        "status": "ACTIVE",
        "tier": "POST_QUANTUM_SENTIENT",
        "genesis": GENESIS_HASH[:16],
        "emotions": sorted(EMOTION_PROFILES.keys()),
        "functions": [
            "map_emotion_to_parameters",
            "generate_melodic_motif",
            "build_sentient_arrangement",
        ],
    }
