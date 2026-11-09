"""Voice routes — Groq Whisper transcription + Orpheus speech
(2026-11-09, Muse).

WHY: the held voice wrappers (voice/whisper_input.py,
voice/tts_output.py) are local-model wrappers that were never wired
into a live route, so SOLVA 014/015 honestly reported not
integrated. Groq serves both directions from the same account key
the relay voice already uses, and both models are on this account's
verified roster (pulled from the account 2026-11-07):

  transcription  whisper-large-v3        (whisper-large-v3-turbo also listed)
  speech         canopylabs/orpheus-v1-english

API shapes verified against Groq's own documentation, fetched
2026-11-09:
  - Transcription: POST https://api.groq.com/openai/v1/audio/transcriptions
    (OpenAI-compatible, multipart file + model) —
    https://console.groq.com/docs/speech-to-text
  - Speech: POST https://api.groq.com/openai/v1/audio/speech with
    JSON {model, input, voice, response_format}; Orpheus input is
    limited to 200 characters and the only supported format is
    "wav" — https://console.groq.com/docs/text-to-speech/orpheus
    and https://console.groq.com/docs/text-to-speech
    English voices include autumn, diana, hannah, austin, daniel,
    troy; "autumn" is used as the default here.

Transport follows models/ollama_runtime.py: stdlib urllib with a
Bearer Authorization header and a browser User-Agent. The endpoint
URLs can be overridden by environment (GROQ_TRANSCRIBE_URL,
GROQ_SPEECH_URL) so tests can point the same request-building code
at a local stub.

HONESTY RULES: no key configured, no audio, empty text, or text
over the Orpheus limit all return an honest error JSON. A Groq HTTP
error is reported with its status — a transcript or audio file is
never fabricated.

Routes (wired in api/server.py the way api/hud.py is wired):
  GET  /voice/status
  POST /voice/transcribe   multipart form field "file"
  POST /voice/speak        JSON {"text": ..., "voice": optional}

Owner: SLMK Jesse Martinez Junior.
"""
import io
import json
import os
import urllib.error
import urllib.request
import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, Response

voice_router = APIRouter(prefix="/voice", tags=["voice"])

TRANSCRIBE_MODEL = "whisper-large-v3"
SPEECH_MODEL = "canopylabs/orpheus-v1-english"
SPEECH_DEFAULT_VOICE = "autumn"
SPEECH_MAX_CHARS = 200
_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _transcribe_url() -> str:
    return os.environ.get(
        "GROQ_TRANSCRIBE_URL",
        "https://api.groq.com/openai/v1/audio/transcriptions")


def _speech_url() -> str:
    return os.environ.get(
        "GROQ_SPEECH_URL", "https://api.groq.com/openai/v1/audio/speech")


def _api_key() -> str:
    # Read at call time, not import time, so a key placed into the
    # process environment is honored and tests can control it.
    return os.environ.get("GROQ_API_KEY", "")


def build_multipart(audio_bytes: bytes, filename: str,
                    content_type: str = "application/octet-stream",
                    model: str = TRANSCRIBE_MODEL) -> tuple:
    """Build the exact multipart body sent to Groq. Returns
    (body_bytes, content_type_header). Pure function — unit-tested."""
    boundary = "----jesseai" + uuid.uuid4().hex
    buf = io.BytesIO()
    def _field(name, value):
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(str(value).encode() + b"\r\n")
    _field("model", model)
    _field("response_format", "json")
    buf.write(f"--{boundary}\r\n".encode())
    buf.write((f'Content-Disposition: form-data; name="file"; '
               f'filename="{filename}"\r\n').encode())
    buf.write(f"Content-Type: {content_type}\r\n\r\n".encode())
    buf.write(audio_bytes + b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "audio.wav",
                           content_type: str = "application/octet-stream",
                           api_key: str = None, url: str = None,
                           urlopen_fn=None) -> dict:
    """Transcribe audio bytes through Groq Whisper. Returns a result
    dict; on any failure the dict carries ok=False and an error —
    never a fabricated transcript."""
    key = _api_key() if api_key is None else api_key
    if not key:
        return {"ok": False, "transcribed": False,
                "error": "groq_not_configured",
                "detail": "GROQ_API_KEY is not set in this process; "
                          "no transcription was attempted"}
    if not audio_bytes:
        return {"ok": False, "transcribed": False, "error": "empty_audio",
                "detail": "no audio bytes were supplied"}
    body, ctype = build_multipart(audio_bytes, filename, content_type)
    req = urllib.request.Request(
        url or _transcribe_url(), data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": ctype, "User-Agent": _USER_AGENT})
    opener = urlopen_fn or urllib.request.urlopen
    try:
        with opener(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return {"ok": False, "transcribed": False,
                "error": f"groq_http_{exc.code}", "detail": detail}
    except Exception as exc:
        return {"ok": False, "transcribed": False,
                "error": f"{type(exc).__name__}", "detail": str(exc)[:300]}
    text = data.get("text")
    if not isinstance(text, str):
        return {"ok": False, "transcribed": False,
                "error": "groq_unexpected_response",
                "detail": f"response keys: {sorted(data)[:10]}"}
    return {"ok": True, "transcribed": True, "text": text,
            "model": TRANSCRIBE_MODEL, "language": data.get("language"),
            "duration": data.get("duration")}


def synthesize_speech_bytes(text: str, voice: str = SPEECH_DEFAULT_VOICE,
                            api_key: str = None, url: str = None,
                            urlopen_fn=None) -> dict:
    """Synthesize speech through Groq Orpheus. On success returns
    {ok: True, audio_bytes, content_type}; on failure an honest
    error dict — never fabricated audio."""
    key = _api_key() if api_key is None else api_key
    if not key:
        return {"ok": False, "error": "groq_not_configured",
                "detail": "GROQ_API_KEY is not set in this process; "
                          "no synthesis was attempted"}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty_text",
                "detail": "no text was supplied"}
    if len(text) > SPEECH_MAX_CHARS:
        return {"ok": False, "error": "text_too_long",
                "detail": f"Orpheus accepts at most {SPEECH_MAX_CHARS} "
                          f"characters per request; got {len(text)}"}
    payload = json.dumps({"model": SPEECH_MODEL, "input": text,
                          "voice": voice or SPEECH_DEFAULT_VOICE,
                          "response_format": "wav"}).encode()
    req = urllib.request.Request(
        url or _speech_url(), data=payload, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": _USER_AGENT})
    opener = urlopen_fn or urllib.request.urlopen
    try:
        with opener(req, timeout=60) as resp:
            audio = resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return {"ok": False, "error": f"groq_http_{exc.code}", "detail": detail}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}",
                "detail": str(exc)[:300]}
    if not audio:
        return {"ok": False, "error": "groq_empty_audio",
                "detail": "Groq returned an empty body"}
    return {"ok": True, "audio_bytes": audio, "content_type": "audio/wav",
            "model": SPEECH_MODEL, "voice": voice or SPEECH_DEFAULT_VOICE,
            "chars": len(text)}


def voice_status() -> dict:
    configured = bool(_api_key())
    return {
        "transcribe": {"route": "POST /voice/transcribe",
                       "provider": "Groq (OpenAI-compatible audio endpoint)",
                       "model": TRANSCRIBE_MODEL, "configured": configured},
        "speak": {"route": "POST /voice/speak",
                  "provider": "Groq Orpheus",
                  "model": SPEECH_MODEL, "configured": configured,
                  "max_chars_per_request": SPEECH_MAX_CHARS,
                  "response_format": "wav"},
    }


@voice_router.get("/status")
def voice_status_route():
    return voice_status()


@voice_router.post("/transcribe")
async def voice_transcribe(file: UploadFile = File(None)):
    if file is None:
        return JSONResponse(status_code=400, content={
            "ok": False, "transcribed": False, "error": "no_audio_file",
            "detail": "multipart form field 'file' is required"})
    audio = await file.read()
    if not audio:
        return JSONResponse(status_code=400, content={
            "ok": False, "transcribed": False, "error": "empty_audio",
            "detail": "the uploaded file contained no bytes"})
    result = transcribe_audio_bytes(
        audio, filename=file.filename or "audio.wav",
        content_type=file.content_type or "application/octet-stream")
    if not result["ok"]:
        code = 503 if result["error"] == "groq_not_configured" else 502
        return JSONResponse(status_code=code, content=result)
    return result


@voice_router.post("/speak")
def voice_speak(request: dict = None):
    body = request or {}
    result = synthesize_speech_bytes(
        str(body.get("text") or ""), voice=str(body.get("voice") or SPEECH_DEFAULT_VOICE))
    if not result["ok"]:
        code = (503 if result["error"] == "groq_not_configured"
                else 400 if result["error"] in ("empty_text", "text_too_long")
                else 502)
        return JSONResponse(status_code=code,
                            content={k: v for k, v in result.items()
                                     if k != "audio_bytes"})
    return Response(content=result["audio_bytes"],
                    media_type=result["content_type"],
                    headers={"X-Voice-Model": result["model"],
                             "X-Voice-Voice": result["voice"]})
