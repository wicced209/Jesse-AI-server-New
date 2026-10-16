"""
CRSMCPAI Alpha - Quantum & Post-Quantum Audio Engines (crs.engines.audio_pq)

Extends the PQ audio synthesis patterns with higher tiers:
- QUANTUM tier: additive harmonic overtone synthesis, ADSR envelopes,
  pseudo-stereo widening for richer soundstage.
- POST-QUANTUM tier: feedback-delay reverb, chorus detune (LFO),
  layered pad textures.

Crash-proof guarantees:
- Standard library only (wave, struct, math, io)
- NO FastAPI / web imports
- NO module-level I/O, deterministic (no randomness)
- All functions defensive: bad input returns safe defaults, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import wave
import struct
import math
import io

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
SAMPLE_RATE = 44100
MAX_DURATION_SEC = 120.0
MAX_SAMPLES = int(SAMPLE_RATE * MAX_DURATION_SEC)


def _clamp(v, lo, hi):
    try:
        f = float(v)
    except Exception:
        return lo
    if f != f:  # NaN
        return lo
    return max(lo, min(hi, f))


def generate_adsr_envelope(num_samples, sample_rate=44100,
                           attack=0.01, decay=0.1, sustain=0.7, release=0.1):
    """ADSR amplitude curve, one multiplier per sample in [0.0, 1.0]."""
    try:
        n = int(num_samples)
    except Exception:
        return []
    if n <= 0:
        return []
    n = min(n, MAX_SAMPLES)
    try:
        sr = int(sample_rate)
    except Exception:
        sr = SAMPLE_RATE
    if sr <= 0:
        sr = SAMPLE_RATE
    a = max(0.0, _clamp(attack, 0.0, 10.0))
    d = max(0.0, _clamp(decay, 0.0, 10.0))
    s = _clamp(sustain, 0.0, 1.0)
    r = max(0.0, _clamp(release, 0.0, 10.0))
    a_n = int(a * sr)
    d_n = int(d * sr)
    r_n = int(r * sr)
    env = []
    for i in range(n):
        if i < a_n and a_n > 0:
            env.append(i / a_n)
        elif i < a_n + d_n and d_n > 0:
            env.append(1.0 - (1.0 - s) * ((i - a_n) / d_n))
        elif i < n - r_n:
            env.append(s)
        elif r_n > 0:
            env.append(max(0.0, s * ((n - i) / r_n)))
        else:
            env.append(s)
    return env


def synthesize_quantum_tone(frequency, duration_sec, harmonics=None, sample_rate=44100):
    """Additive synthesis: fundamental + harmonic overtone weights.

    harmonics: list of amplitude weights, index 0 = fundamental.
    Returns mono samples in [-1.0, 1.0].
    """
    try:
        freq = float(frequency)
    except Exception:
        return []
    if freq <= 0 or freq > 20000:
        return []
    try:
        dur = float(duration_sec)
    except Exception:
        return []
    if dur <= 0:
        return []
    dur = min(dur, MAX_DURATION_SEC)
    try:
        sr = int(sample_rate)
    except Exception:
        sr = SAMPLE_RATE
    if sr <= 0:
        sr = SAMPLE_RATE
    if not isinstance(harmonics, (list, tuple)) or not harmonics:
        harmonics = [1.0, 0.5, 0.25]
    weights = [_clamp(w, 0.0, 1.0) for w in harmonics[:16]]
    total = sum(weights) or 1.0
    n = min(int(sr * dur), MAX_SAMPLES)
    out = [0.0] * n
    for i in range(n):
        t = i / sr
        v = 0.0
        for h, w in enumerate(weights):
            v += w * math.sin(2.0 * math.pi * freq * (h + 1) * t)
        out[i] = v / total
    return out


def apply_stereo_widening(mono_samples, width_factor=0.3):
    """Split mono into pseudo-stereo L/R with slight delay offset.

    Returns (left, right) sample lists.
    """
    try:
        if not isinstance(mono_samples, (list, tuple)):
            return ([], [])
        width = _clamp(width_factor, 0.0, 1.0)
        mono = [float(x) for x in mono_samples[:MAX_SAMPLES]]
        n = len(mono)
        if n == 0:
            return ([], [])
        delay = max(1, int(n * 0.001 * width * 10))  # small offset, scaled by width
        delay = min(delay, n - 1) if n > 1 else 0
        left = list(mono)
        right = [0.0] * n
        for i in range(n):
            src = mono[i - delay] if i >= delay else 0.0
            right[i] = mono[i] * (1.0 - width * 0.5) + src * (width * 0.5)
        return (left, right)
    except Exception:
        return ([], [])


def apply_feedback_delay(samples, delay_samples, feedback=0.4):
    """Simple feedback delay (echo/reverb). feedback must be < 1.0."""
    try:
        if not isinstance(samples, (list, tuple)):
            return []
        fb = _clamp(feedback, 0.0, 0.95)
        try:
            d = int(delay_samples)
        except Exception:
            return list(samples)
        buf = [float(x) for x in samples[:MAX_SAMPLES]]
        n = len(buf)
        if d <= 0 or d >= n or n == 0:
            return buf
        out = list(buf)
        for i in range(d, n):
            out[i] = buf[i] + out[i - d] * fb
            if out[i] > 1.0:
                out[i] = 1.0
            elif out[i] < -1.0:
                out[i] = -1.0
        return out
    except Exception:
        try:
            return list(samples)
        except Exception:
            return []


def apply_chorus_detune(samples, sample_rate=44100, depth=0.002, rate=1.5):
    """Chorus via LFO-modulated delay mixed with dry signal."""
    try:
        if not isinstance(samples, (list, tuple)):
            return []
        try:
            sr = int(sample_rate)
        except Exception:
            sr = SAMPLE_RATE
        if sr <= 0:
            sr = SAMPLE_RATE
        dep = _clamp(depth, 0.0, 0.02)
        rt = _clamp(rate, 0.0, 20.0)
        buf = [float(x) for x in samples[:MAX_SAMPLES]]
        n = len(buf)
        if n == 0:
            return []
        base_delay = int(sr * 0.015)  # 15 ms base
        mod_amp = int(sr * dep)
        out = [0.0] * n
        for i in range(n):
            lfo = math.sin(2.0 * math.pi * rt * (i / sr))
            var_delay = base_delay + int(lfo * mod_amp)
            j = i - var_delay
            wet = buf[j] if j >= 0 else 0.0
            mixed = buf[i] * 0.6 + wet * 0.4
            out[i] = max(-1.0, min(1.0, mixed))
        return out
    except Exception:
        try:
            return list(samples)
        except Exception:
            return []


def export_wav_bytes(mono_or_left, right=None, sample_rate=44100):
    """Export samples to 16-bit WAV bytes. Mono if right is None, else stereo."""
    try:
        try:
            sr = int(sample_rate)
        except Exception:
            sr = SAMPLE_RATE
        if sr <= 0:
            sr = SAMPLE_RATE
        left = [max(-1.0, min(1.0, float(x))) for x in (mono_or_left or [])[:MAX_SAMPLES]]
        stereo = right is not None
        if stereo:
            r = [max(-1.0, min(1.0, float(x))) for x in (right or [])[:MAX_SAMPLES]]
            n = min(len(left), len(r))
            left, r = left[:n], r[:n]
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(2 if stereo else 1)
            w.setsampwidth(2)
            w.setframerate(sr)
            if stereo:
                for a, b in zip(left, r):
                    w.writeframes(struct.pack("<hh", int(a * 32767), int(b * 32767)))
            else:
                for a in left:
                    w.writeframes(struct.pack("<h", int(a * 32767)))
        return buf.getvalue()
    except Exception:
        return b""


def synthesize_pad_chord(frequencies, duration_sec, sample_rate=44100):
    """Post-quantum tier: layered pad from a chord with slow ADSR + chorus."""
    try:
        if not isinstance(frequencies, (list, tuple)) or not frequencies:
            return []
        layers = []
        for f in frequencies[:8]:
            tone = synthesize_quantum_tone(f, duration_sec, [1.0, 0.4, 0.2, 0.1],
                                           sample_rate)
            if tone:
                layers.append(tone)
        if not layers:
            return []
        n = max(len(l) for l in layers)
        mixed = [0.0] * n
        for layer in layers:
            for i, v in enumerate(layer):
                mixed[i] += v / len(layers)
        env = generate_adsr_envelope(n, sample_rate, attack=duration_sec * 0.3,
                                     decay=duration_sec * 0.2, sustain=0.8,
                                     release=duration_sec * 0.3)
        mixed = [v * e for v, e in zip(mixed, env)]
        return apply_chorus_detune(mixed, sample_rate)
    except Exception:
        return []


def module_status():
    return {
        "module": "crs.engines.audio_pq",
        "status": "ACTIVE",
        "tiers": ["QUANTUM", "POST_QUANTUM"],
        "genesis": GENESIS_HASH[:16],
        "functions": [
            "generate_adsr_envelope",
            "synthesize_quantum_tone",
            "apply_stereo_widening",
            "apply_feedback_delay",
            "apply_chorus_detune",
            "synthesize_pad_chord",
            "export_wav_bytes",
        ],
    }
