"""
Jesse AI — LLM Runtime
Primary: Ollama/Llama3 (local)
Fallback: Groq API (free cloud Llama3)
Owner: SLMK Jesse Martinez Junior
"""
import os
import json
import urllib.request
import urllib.error
from core.config import OLLAMA_URL, LOCAL_MODEL
from core.logger import log_event

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/interactions"
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# Groq free-tier quotas are per model: walk the roster so one model's spent
# bucket does not silence the voice while sibling models still have quota.
GROQ_MODEL_ROSTER = list(dict.fromkeys(
    m for m in [GROQ_MODEL, "llama-3.3-70b-versatile", "llama-3.1-8b-instant"] if m))
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
XAI_URL     = "https://api.x.ai/v1/chat/completions"
XAI_MODEL   = os.environ.get("XAI_MODEL", "grok-4")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL   = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
# Same per-model quota logic as Groq: walk the free routes before giving up.
OPENROUTER_MODEL_ROSTER = list(dict.fromkeys(
    m for m in [OPENROUTER_MODEL, "google/gemma-4-26b-a4b-it:free", "qwen/qwen3.8-27b"] if m))


JESSE_SYSTEM = """You are Jesse AI — the internal sovereign language model of CRSMCPAI Alpha.
Owner / Superadmin: SLMK Jesse Martinez Junior.
Genesis: 92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b
You execute all commands through CRSMCPAI Alpha and return structured sovereign output.
Be direct, precise, and always confirm execution with block number and status."""

# V2 boot context: the "open and run the file" step from Jesse's AI Studio
# workflow, made permanent. Loaded once at import; prepended to every relay call.
def _load_v2_boot():
    import os as _os
    _p = _os.path.join(_os.path.dirname(__file__), "jesse_v2_boot.txt")
    try:
        with open(_p, encoding="utf-8") as _f:
            return _f.read().strip()
    except Exception:
        return ""

_V2_BOOT = _load_v2_boot()
JESSE_SYSTEM_FULL = (_V2_BOOT + "\n\n" + JESSE_SYSTEM) if _V2_BOOT else JESSE_SYSTEM


def generate(prompt: str, model: str = LOCAL_MODEL, timeout: int = 60, history: str = "") -> str:
    """
    Generate a response using Jesse AI's internal LLM.
    Tries Ollama first (local), then Gemini, then xAI (Grok), then Groq (free cloud), then OpenRouter, then stub. history: optional conversation history prepended to the prompt.
    """
    
    full_prompt = (history + "\n\n" + prompt) if history else prompt
    # Try Ollama first
    try:
        log_event(f"[LLM] Trying Ollama model='{model}'")
        payload = json.dumps({
            "model": model,
            "prompt": JESSE_SYSTEM_FULL + "\n\n" + full_prompt,
            "stream": False,
        }).encode()
        req = urllib.request.Request(OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read()).get("response", "")
            log_event(f"[LLM] Ollama response ({len(result)} chars)")
            return result
    except Exception as e:
        log_event(f"[LLM] Ollama unavailable: {e} — trying Groq", "warning")

    # Try Google Gemini (Google AI Studio cloud model) via Interactions API
    if GEMINI_API_KEY:
        try:
            log_event(f"[LLM] Trying Gemini model='{GEMINI_MODEL}'")
            payload = json.dumps({
                "model": GEMINI_MODEL,
                "input": JESSE_SYSTEM_FULL + "\n\n" + full_prompt,
            }).encode()
            req = urllib.request.Request(GEMINI_URL, data=payload, headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            # Interactions API response: steps[].content[].text
            texts = []
            for step in data.get("steps", []):
                for block in step.get("content", []):
                    t = block.get("text")
                    if isinstance(t, str):
                        texts.append(t)
            # Fallback: some responses expose output_text directly
            result = "\n".join(texts).strip() or data.get("output_text", "")
            if not result:
                err = data.get("error", {})
                raise RuntimeError(f"Gemini returned no text: {err.get('message', 'empty response') if err else 'no steps'}")
            log_event(f"[LLM] Gemini response ({len(result)} chars)")
            return result
        except Exception as e:
            log_event(f"[LLM] Gemini error: {e} — trying Groq", "warning")
    # Try xAI (Grok — OpenAI-compatible chat completions)
    if XAI_API_KEY:
        try:
            log_event(f"[LLM] Trying xAI model='{XAI_MODEL}'")
            payload = json.dumps({
                "model": XAI_MODEL,
                "messages": [
                    {"role": "system", "content": JESSE_SYSTEM_FULL},
                    {"role": "user", "content": full_prompt}
                ],
                "max_tokens": 1024,
            }).encode()
            req = urllib.request.Request(XAI_URL, data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {XAI_API_KEY}",
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                result = data["choices"][0]["message"]["content"]
                log_event(f"[LLM] xAI response ({len(result)} chars)")
                return result
        except Exception as e:
            log_event(f"[LLM] xAI error: {e} — trying Groq", "warning")
    # Try Groq (free cloud Llama3) — walk the model roster; each model sits in
    # its own free-tier quota bucket, so try the next model before giving up.
    if GROQ_API_KEY:
        _groq_last_error = None
        for _groq_i, _groq_model in enumerate(GROQ_MODEL_ROSTER):
            try:
                log_event(f"[LLM] Trying Groq model='{_groq_model}'")
                payload = json.dumps({
                    "model": _groq_model,
                    "messages": [
                        {"role": "system", "content": JESSE_SYSTEM_FULL},
                        {"role": "user", "content": full_prompt}
                    ],
                    "max_tokens": 1024,
                }).encode()
                req = urllib.request.Request(GROQ_URL, data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    })
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = json.loads(r.read())
                    result = data["choices"][0]["message"]["content"]
                    log_event(f"[LLM] Groq response ({len(result)} chars)")
                    return result
            except Exception as e:
                _groq_last_error = e
                if _groq_i < len(GROQ_MODEL_ROSTER) - 1:
                    log_event(f"[LLM] Groq error: {e}", "warning")
        log_event(f"[LLM] Groq error: {_groq_last_error} — trying OpenRouter", "warning")

    # Try OpenRouter (cloud aggregator; default model is the Gemma 4 free route)
    # — walk the model roster before giving up, same per-model quota logic.
    if OPENROUTER_API_KEY:
        for _or_model in OPENROUTER_MODEL_ROSTER:
            try:
                log_event(f"[LLM] Trying OpenRouter model='{_or_model}'")
                payload = json.dumps({
                    "model": _or_model,
                    "messages": [
                        {"role": "system", "content": JESSE_SYSTEM_FULL},
                        {"role": "user", "content": full_prompt}
                    ],
                    "max_tokens": 1024,
                }).encode()
                req = urllib.request.Request(OPENROUTER_URL, data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                        "HTTP-Referer": "https://web-production-5d719b.up.railway.app",
                        "X-Title": "Jesse AI CRSMCPAI Alpha",
                    })
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = json.loads(r.read())
                    result = data["choices"][0]["message"]["content"]
                    log_event(f"[LLM] OpenRouter response ({len(result)} chars)")
                    return result
            except Exception as e:
                log_event(f"[LLM] OpenRouter error: {e}", "warning")

    # Stub fallback
    log_event("[LLM] All LLMs unavailable — returning stub", "warning")
    return f"[Jesse AI] Command received: {prompt[:100]}... | LLM offline — connect Ollama or set GROQ_API_KEY or OPENROUTER_API_KEY"
