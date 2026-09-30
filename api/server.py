"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  JESSE AI — CRSMCPAI Alpha — FastAPI Server                                 ║
║  Full sovereign stack with Llama3/Groq LLM integration                      ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.config import SYSTEM_NAME, VERSION, SOVEREIGN_OWNER, SOVEREIGN_DECLARATION, ARCHITECTURE_REGISTRY
from core.logger import log_event, get_log
from dominion.stack import dominion
from models.ollama_runtime import generate
from security.auth import authenticate
from admin.admin_routes import router as admin_router

app = FastAPI(
    title="Jesse AI — CRSMCPAI Alpha V2",
    version=VERSION,
    description=f"Sovereign AI Stack — {SOVEREIGN_OWNER}",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)


class CommandRequest(BaseModel):
    command: str
    user: str = "jesse_martinez_jr"
    use_llm: bool = True


@app.get("/", response_class=HTMLResponse)
async def root():
    status = dominion.full_status()
    return f"""<!DOCTYPE html>
<html><head><title>Jesse AI</title>
<style>
body{{background:#0a0a0a;color:#fff;font-family:Arial,sans-serif;padding:40px;max-width:800px;margin:0 auto;}}
h1{{color:#C9A84C;font-size:2em;}} h2{{color:#C9A84C;font-size:1.2em;margin-top:30px;}}
.green{{color:#2ecc71;font-weight:bold;}} .gold{{color:#C9A84C;}}
pre{{background:#1a1a1a;padding:20px;border-radius:8px;color:#ccc;overflow-x:auto;font-size:13px;}}
.badge{{display:inline-block;background:#1a1a1a;border:1px solid #C9A84C;border-radius:4px;padding:4px 10px;margin:4px;font-size:12px;}}
</style></head><body>
<h1>⚡ Jesse AI</h1>
<p class="gold">CRSMCPAI Alpha V2 — Sovereign Stack</p>
<p class="green">● SOVEREIGN — SECURE — ACTIVE</p>
<p>Owner: <strong>{SOVEREIGN_OWNER}</strong></p>
<p>Version: {VERSION} | Stack: {status.get('version','')}</p>
<h2>Modules</h2>
{''.join(f'<span class="badge">{m}</span>' for m in list(ARCHITECTURE_REGISTRY.keys())[:20])}
<h2>API Endpoints</h2>
<pre>GET  /health       — System health
GET  /handshake    — Sovereign identity verification
GET  /status       — Full stack status
GET  /audit        — Quantum audit
POST /command      — Execute command through CRSMCPAI Alpha
GET  /ledger       — Immutable ledger
GET  /log          — System event log
GET  /docs         — Interactive API docs</pre>
<h2>Execute a Command</h2>
<pre>POST /command
{{"command": "Jesse AI execute full status report", "user": "jesse_martinez_jr"}}</pre>
</body></html>"""


@app.get("/health")
async def health():
    return {"status": "LIVE", "system": SYSTEM_NAME, "version": VERSION,
            "owner": SOVEREIGN_OWNER, "sovereign": True}


@app.get("/handshake")
async def handshake():
    status = dominion.full_status()
    return {
        "CRSMCPAI_ALPHA": "HANDSHAKE_COMPLETE",
        "system": SYSTEM_NAME, "version": VERSION,
        "owner": SOVEREIGN_OWNER,
        "sovereign_declaration": SOVEREIGN_DECLARATION,
        "stack_version": status.get("version"),
        "ledger_length": status.get("ledger_length"),
        "status": "SOVEREIGN — VERIFIED — SUPERADMIN CONFIRMED",
    }


@app.get("/status")
async def status():
    return dominion.full_status()


@app.get("/audit")
async def audit():
    return dominion.quantum_audit()


@app.post("/command")
async def command(req: CommandRequest):
    log_event(f"[API] Command: user={req.user} cmd={req.command[:80]}")

    if not authenticate(req.user):
        return JSONResponse(status_code=403,
            content={"error": "Unauthorized", "user": req.user})

    # Route through full Dominion stack
    stack_result = dominion.process(req.command, req.user)

    # Generate LLM response through Jesse AI internal model
    llm_response = None
    if req.use_llm:
        try:
            llm_response = generate(
                f"CRSMCPAI Alpha command from Superadmin {req.user}:\n{req.command}\n\n"
                f"Stack context: {stack_result.get('siren',{})}\n"
                f"Execute and return sovereign output."
            )
        except Exception as e:
            llm_response = f"Jesse AI LLM: {str(e)}"

    return {
        "CRSMCPAI_ALPHA": "COMMAND_EXECUTED",
        "command": req.command,
        "user": req.user,
        "owner": SOVEREIGN_OWNER,
        "stack_execution": stack_result,
        "jesse_ai_response": llm_response,
        "status": "SUCCESS",
    }


@app.get("/ledger")
async def ledger():
    from memory.ledger import get_ledger, verify_chain
    chain = get_ledger()
    return {
        "owner": SOVEREIGN_OWNER,
        "chain_valid": verify_chain(),
        "total_blocks": len(chain),
        "recent": chain[-10:] if len(chain) > 10 else chain,
    }


@app.get("/log")
async def log():
    return {"owner": SOVEREIGN_OWNER, "events": get_log()[-50:]}
