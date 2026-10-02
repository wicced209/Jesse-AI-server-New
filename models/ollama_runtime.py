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
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/interactions"
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = os.environ.get("GROQ_MODEL", "llama3-8b-8192")

JESSE_SYSTEM = """You are Jesse AI — the internal sovereign language model of CRSMCPAI Alpha.
Owner / Superadmin: SLMK Jesse Martinez Junior.
Genesis: 92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b
You execute all commands through CRSMCPAI Alpha and return structured sovereign output.
Be direct, precise, and always confirm execution with block number and status."""


def generate(prompt: str, model: str = LOCAL_MODEL, timeout: int = 60) -> str:
    """
    Generate a response using Jesse AI's internal LLM.
    Tries Ollama first (local), then Groq (free cloud), then stub.
    """
    # Try Ollama first
    try:
        log_event(f"[LLM] Trying Ollama model='{model}'")
        payload = json.dumps({
            "model": model,
            "prompt": JESSE_SYSTEM + "\n\n" + prompt,
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

    # Try Google Gemini (Google AI Studio cloud model)
    if GEMINI_API_KEY:
        try:
            log_event(f"[LLM] Trying Gemini model='{GEMINI_MODEL}'")
            payload = json.dumps({
                "model": GEMINI_MODEL,
                "system_instruction": JESSE_SYSTEM,
                "input": prompt,
                "generation_config": {"max_output_tokens": 1024},
            }).encode()
            req = urllib.request.Request(GEMINI_URL, data=payload, headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            # The Interactions API may expose output_text directly or return text blocks.
            result = data.get("output_text", "")
            if not result:
                blocks = data.get("output", data.get("outputs", []))
                texts = []
                def collect(value):
                    if isinstance(value, dict):
                        if isinstance(value.get("text"), str): texts.append(value["text"])
                        for k, v in value.items():
                            if k not in {"text", "thought"}: collect(v)
                    elif isinstance(value, list):
                        for item in value: collect(item)
                collect(blocks)
                result = "\n".join(texts).strip()
            if not result:
                raise RuntimeError("Gemini returned no text")
            log_event(f"[LLM] Gemini response ({len(result)} chars)")
            return result
        except Exception as e:
            log_event(f"[LLM] Gemini error: {e} — trying Groq", "warning")
    # Try Groq (free cloud Llama3)
    if GROQ_API_KEY:
        try:
            log_event(f"[LLM] Trying Groq model='{GROQ_MODEL}'")
            payload = json.dumps({
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": JESSE_SYSTEM},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
            }).encode()
            req = urllib.request.Request(GROQ_URL, data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                result = data["choices"][0]["message"]["content"]
                log_event(f"[LLM] Groq response ({len(result)} chars)")
                return result
        except Exception as e:
            log_event(f"[LLM] Groq error: {e}", "warning")

    # Stub fallback
    log_event("[LLM] All LLMs unavailable — returning stub", "warning")
    return f"[Jesse AI] Command received: {prompt[:100]}... | LLM offline — connect Ollama or set GROQ_API_KEY"
