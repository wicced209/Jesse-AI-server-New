from core.logger import log_event

# Lazy-load whisper so the system starts even without the model downloaded
_model = None


def _load_model(size: str = "base"):
    global _model
    if _model is None:
        import whisper
        log_event(f"[WHISPER] Loading model: {size}")
        _model = whisper.load_model(size)
        log_event("[WHISPER] Model loaded")
    return _model


def transcribe(audio_file: str, model_size: str = "base") -> str:
    """
    Transcribe an audio file to text using OpenAI Whisper (local).
    Returns the transcribed string.
    """
    model = _load_model(model_size)
    log_event(f"[WHISPER] Transcribing: {audio_file}")
    result = model.transcribe(audio_file)
    text   = result.get("text", "").strip()
    log_event(f"[WHISPER] Transcription complete: {text[:60]}...")
    return text
