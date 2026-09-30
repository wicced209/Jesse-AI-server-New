import pyttsx3
from core.logger import log_event

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 170)    # words per minute
        _engine.setProperty("volume", 1.0)
        log_event("[TTS] Engine initialized")
    return _engine


def speak(text: str):
    """Convert text to speech and play it immediately."""
    log_event(f"[TTS] Speaking: {text[:60]}...")
    engine = _get_engine()
    engine.say(text)
    engine.runAndWait()


def set_voice_rate(rate: int = 170):
    """Adjust speech rate (words per minute)."""
    _get_engine().setProperty("rate", rate)
