"""
CRSMCPAI Alpha - Output Watermark (anti-distillation build 4)

Marks public demo answers so harvested copies can be proven ours.

Method (deliberately narrow and screen-reader safe):
- The only variation points are contraction choices: "do not" vs
  "don't", "it is" vs "it's", and a short list of true equivalents.
  Both forms read naturally, mean exactly the same thing, and are
  spoken identically in sense by a screen reader. No punctuation
  tricks, no spacing tricks, no invisible characters, no synonym
  swaps that could shift meaning. If it cannot be heard safely, it
  is not used - the demo law.
- Which form appears at each site is chosen by a keyed hash of the
  answer's skeleton (the text with every site normalized to a
  placeholder). A verbatim harvested copy preserves the pattern;
  verification re-derives the expected pattern from the skeleton
  and compares the choices actually present.
- Honest limits: light editing erodes the mark; a short answer with
  fewer than 3 sites is left unmarked. The mark is provenance
  evidence, not DRM. It never blocks, alters meaning, or punishes.

Key: CRS_WATERMARK_KEY from the environment when set; otherwise an
ephemeral per-boot key. Either way only a hash commitment of the
key is sealed (WATERMARK_KEY_COMMITMENT); the key itself is never
stored or sealed. With an ephemeral key, verification covers
outputs produced during the same boot - stated plainly in status.
"""

import hashlib
import hmac as hmac_mod
import os
import re
import secrets

_seal_fn = None

PAIRS = [
    ("do not", "don't"),
    ("does not", "doesn't"),
    ("did not", "didn't"),
    ("cannot", "can't"),
    ("could not", "couldn't"),
    ("would not", "wouldn't"),
    ("should not", "shouldn't"),
    ("is not", "isn't"),
    ("are not", "aren't"),
    ("it is", "it's"),
    ("that is", "that's"),
    ("there is", "there's"),
    ("you are", "you're"),
    ("we are", "we're"),
    ("you will", "you'll"),
    ("it will", "it'll"),
]

_PATTERNS = []
for a, b in PAIRS:
    for form, other in ((a, b), (b, a)):
        _PATTERNS.append((re.compile(r"\b" + re.escape(form) + r"\b",
                                     re.IGNORECASE), form, other))

_key = None
_key_source = None
_commitment_sealed = False
_marked_count = 0
_unmarked_count = 0


def set_seal_fn(fn):
    global _seal_fn
    _seal_fn = fn


def _seal(event):
    if _seal_fn is None:
        return
    try:
        _seal_fn(event)
    except Exception:
        pass


def _ensure_key():
    global _key, _key_source, _commitment_sealed
    if _key is not None:
        return
    env = os.environ.get("CRS_WATERMARK_KEY", "")
    if env:
        _key = env.encode()
        _key_source = "environment"
    else:
        _key = secrets.token_bytes(32)
        _key_source = "ephemeral_per_boot"
    if not _commitment_sealed:
        _commitment_sealed = True
        _seal({"event": "WATERMARK_KEY_COMMITMENT",
               "key_commitment": hashlib.sha3_512(_key).hexdigest(),
               "key_source": _key_source})


def _sites(text):
    """Ordered (start, end, chosen_form, alternate_form) matches,
    skipping anything inside a URL or code span."""
    found = []
    for pat, form, other in _PATTERNS:
        for m in pat.finditer(text):
            token_zone = text[max(0, m.start() - 12):m.end() + 4]
            if "://" in token_zone or "`" in token_zone:
                continue
            found.append((m.start(), m.end(), m.group(0), other))
    found.sort()
    # drop overlaps (first wins)
    out, last_end = [], -1
    for s in found:
        if s[0] >= last_end:
            out.append(s)
            last_end = s[1]
    return out


def _skeleton(text, sites):
    parts, prev = [], 0
    for s, e, _, _ in sites:
        parts.append(text[prev:s])
        parts.append("\x00SITE\x00")
        prev = e
    parts.append(text[prev:])
    return "".join(parts)


def _expected_bits(skeleton, n):
    digest = hmac_mod.new(_key, skeleton.encode(),
                          hashlib.sha256).digest()
    bits = []
    i = 0
    while len(bits) < n:
        for byte in digest:
            for shift in range(7, -1, -1):
                bits.append((byte >> shift) & 1)
        i += 1
        digest = hmac_mod.new(_key, (skeleton + str(i)).encode(),
                              hashlib.sha256).digest()
    return bits[:n]


def _match_case(original, replacement):
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def mark(text):
    """Apply the keyed contraction pattern. Returns the (possibly
    unchanged) text."""
    global _marked_count, _unmarked_count
    _ensure_key()
    if not text:
        return text
    sites = _sites(text)
    if len(sites) < 3:
        _unmarked_count += 1
        return text
    bits = _expected_bits(_skeleton(text, sites), len(sites))
    parts, prev = [], 0
    for (s, e, current, other), bit in zip(sites, bits):
        parts.append(text[prev:s])
        # bit 0 keeps the long form, bit 1 the contracted form;
        # "current" is whichever form the draft already had.
        long_form = current if current.lower() in (
            p[0] for p in PAIRS) else other
        short_form = other if long_form == current else current
        chosen = short_form if bit == 1 else long_form
        parts.append(_match_case(current, chosen))
        prev = e
    parts.append(text[prev:])
    _marked_count += 1
    return "".join(parts)


def verify(text):
    """Check a candidate text for our mark."""
    _ensure_key()
    sites = _sites(text or "")
    if len(sites) < 3:
        return {"marked": False, "sites": len(sites), "matched": 0,
                "ratio": 0.0,
                "reason": "too_few_sites"}
    bits = _expected_bits(_skeleton(text, sites), len(sites))
    matched = 0
    for (_, _, current, _), bit in zip(sites, bits):
        is_short = "'" in current
        if (bit == 1) == is_short:
            matched += 1
    ratio = matched / len(sites)
    return {"marked": bool(len(sites) >= 4 and ratio >= 0.85),
            "sites": len(sites), "matched": matched,
            "ratio": round(ratio, 3),
            "reason": "pattern_match" if ratio >= 0.85 else "no_match"}


def watermark_status():
    _ensure_key()
    return {
        "ok": True,
        "module": "output_watermark",
        "key_source": _key_source,
        "sites_per_scheme": "contraction choices only",
        "answers_marked_this_boot": _marked_count,
        "answers_unmarked_too_short": _unmarked_count,
        "honesty": "Provenance evidence, not DRM: light editing "
                   "erodes the mark, answers with fewer than 3 "
                   "contraction sites are left unmarked, and with an "
                   "ephemeral key verification covers this boot's "
                   "outputs. The mark never changes meaning and is "
                   "fully screen-reader safe.",
    }
