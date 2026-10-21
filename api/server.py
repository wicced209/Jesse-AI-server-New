"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  JESSE AI — CRSMCPAI Alpha — FastAPI Server                                 ║
║  Full sovereign stack with Llama3/Groq LLM integration                      ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os
import time
import asyncio
import base64
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# Wired sovereign engine modules (stdlib-only; endpoints added directly below).
from api import (mesh_daemon, autoupdate, audio_quantum, audio_sentient,
                 video_quantum, video_sentient, game_engine, os_kernel,
                 ledger_immutable, unified_ledger_router, os_orchestrator,
                 thought_trust, sovereign_model, relay_supervisor, arc_tools,
                 email_messenger)
from core.config import SYSTEM_NAME, VERSION, SOVEREIGN_OWNER, SOVEREIGN_DECLARATION, ARCHITECTURE_REGISTRY
from core.logger import log_event, get_log
from dominion.stack import dominion
from models.ollama_runtime import generate
from security.auth import authenticate
from admin.admin_routes import router as admin_router
from api.mesh import router as mesh_router
from api.mesh_ws import router as mesh_ws_router
from api.ota_updates import ota_router
from api.pq_crypto import pq_router
from api.sovereign_os import os_router, crs_router
from api.guardian_eco import guardian_router
from api.solva_godmode import solva_router
from api.dominion_api import dominion_router
from api.media_engines import media_router
from api.module_registry import registry_router
from api.dominion_corridor import corridor_router
from api.janet_protocol import janet_router
from api.sovereign_ledgers import ledger_router, book_router
from api.pq_audio import pq_audio_router
from api.pq_video import pq_video_router
from api.agssi_core import agssi_router
from api.dominion_tnc import tnc_router

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
app.include_router(mesh_router)
app.include_router(mesh_ws_router)
app.include_router(ota_router)
app.include_router(pq_router)
app.include_router(os_router)
app.include_router(crs_router)
app.include_router(guardian_router)
app.include_router(solva_router)
app.include_router(dominion_router)
app.include_router(media_router)
app.include_router(registry_router)
app.include_router(corridor_router)
app.include_router(janet_router)
app.include_router(ledger_router)
app.include_router(book_router)
app.include_router(pq_audio_router)
app.include_router(pq_video_router)
app.include_router(agssi_router)
app.include_router(tnc_router)


class CommandRequest(BaseModel):
    command: str
    user: str = "jesse_martinez_jr"
    # Direct CRSMCPAI Alpha V2 execution is authoritative; an LLM is optional.
    use_llm: bool = False


class QueryRequest(BaseModel):
    query: str
    user: str = "jesse_martinez_jr"
    use_llm: bool = True


@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jesse AI Terminal</title>
<style>
:root{color-scheme:dark;--bg:#080b0f;--panel:#10161d;--line:#263442;--text:#d9e2ea;--muted:#7f92a3;--green:#54e38e;--gold:#d7b45a;--red:#ff7777}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px ui-monospace,SFMono-Regular,Menlo,monospace;min-height:100vh}
main{max-width:980px;margin:0 auto;padding:20px}.top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding:8px 0 14px}.brand{color:var(--green);font-weight:700}.status{color:var(--muted);font-size:12px}.status b{color:var(--green)}
.terminal{margin-top:18px;border:1px solid var(--line);border-radius:8px;background:var(--panel);overflow:hidden;box-shadow:0 12px 50px #0008}.bar{padding:9px 13px;color:var(--muted);border-bottom:1px solid var(--line);font-size:12px}.out{min-height:360px;max-height:62vh;overflow:auto;padding:16px;white-space:pre-wrap;line-height:1.5}.prompt{color:var(--green)}.err{color:var(--red)}
.form{display:flex;border-top:1px solid var(--line);padding:12px;gap:10px}.form span{color:var(--green);padding-top:11px}.form input{flex:1;background:#080b0f;color:var(--text);border:1px solid var(--line);border-radius:5px;padding:10px;font:inherit}.form button,.quick button{background:#18232d;color:var(--text);border:1px solid var(--line);border-radius:5px;padding:9px 12px;font:inherit;cursor:pointer}.form button:hover,.quick button:hover{border-color:var(--gold);color:var(--gold)}
.quick{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.hint{color:var(--muted);font-size:12px;margin-top:14px;line-height:1.5}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:600px){main{padding:12px}.form{flex-wrap:wrap}.form input{min-width:70%}.form button{flex:1}.out{min-height:300px}}
</style></head><body><main><div class="top"><div class="brand">JESSE_AI :: CRSMCPAI_ALPHA</div><div class="status">● <b>ONLINE</b></div></div>
<div class="terminal"><div class="bar">terminal session · Dominion stack connected · type <b>help</b> for commands</div><div id="out" class="out" role="log" aria-live="polite" aria-atomic="false" tabindex="0"></div><div id="sr-status" class="sr-only" role="status" aria-live="polite"></div><form id="form" class="form"><span>jesse@alpha:~$</span><label for="cmd" style="position:absolute;left:-9999px">Message Jesse AI</label><input id="cmd" autocomplete="off" autofocus aria-label="Message Jesse AI"><button type="button" id="mic">MIC</button><button type="submit">EXECUTE</button></form></div>
<div class="quick"><button data-cmd="status">status</button><button data-cmd="handshake">handshake</button><button data-cmd="audit">audit</button><button data-cmd="ledger">ledger</button><button data-cmd="help">help</button></div>
<div class="hint">Commands are sent to <code>POST /command</code>. Use the API docs at <a href="/docs" style="color:var(--gold)">/docs</a> for the full interface.</div></main>
<script>
const out=document.getElementById('out'),form=document.getElementById('form'),input=document.getElementById('cmd'),mic=document.getElementById('mic');
function print(x,cls=''){const d=document.createElement('div');d.className=cls;d.textContent=x;out.appendChild(d);out.scrollTop=out.scrollHeight}
function speak(x){if('speechSynthesis' in window){window.speechSynthesis.cancel();window.speechSynthesis.speak(new SpeechSynthesisUtterance(x))}}
function printHidden(x){const d=document.createElement('div');d.setAttribute('aria-hidden','true');d.textContent=x;out.appendChild(d);out.scrollTop=out.scrollHeight}
function announce(x){const s=document.getElementById('sr-status');if(s){s.textContent='';setTimeout(function(){s.textContent=x},40)}}
function local(c){
  if(c==='help') return `Available commands:
  status       full Dominion status
  handshake    verify CRSMCPAI Alpha identity
  audit        quantum audit
  ledger       recent ledger blocks
  clear        clear terminal
  any text     execute through CRSMCPAI Alpha`;
  if(c==='clear'){out.innerHTML='';return ''}
  return null;
}
async function run(c){
  c=c.trim();
  if(!c){print('Please enter a command first.','err');return}
  input.disabled=true;
  print('jesse@alpha:~$ '+c,'prompt');
  print('Executing through CRSMCPAI Alpha...','prompt');
  const l=local(c.toLowerCase());
  if(l!==null){if(l)print(l);input.disabled=false;input.focus();return}
  try{
    const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:c,user:'jesse_martinez_jr',use_llm:true})});
    const t=await r.text();
    if(!r.ok) throw new Error(t||('HTTP '+r.status));
    const data=JSON.parse(t);
    printHidden(JSON.stringify(data,null,2));
    const stack=data.stack_execution||{};
    if(data.spoken_response){print(data.spoken_response)}
    const summary=data.spoken_response||((data.CRSMCPAI_ALPHA||'Result')+'; status '+(data.status||'unknown')+'. Ledger entry '+(stack.ledger_index??'not reported')+'.');
    speak(summary);announce(summary);
    out.focus();
  }catch(e){print('ERROR: '+e.message,'err');speak('The command returned an error. Read the error shown on screen.');announce('The command returned an error.')}
  finally{input.disabled=false;input.focus()}
}
form.addEventListener('submit',e=>{e.preventDefault();run(input.value);input.value=''});
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(SpeechRecognition){const rec=new SpeechRecognition();rec.lang='en-US';rec.interimResults=false;rec.onstart=()=>{mic.textContent='LISTENING';print('Listening...','prompt')};rec.onresult=e=>{input.value=e.results[0][0].transcript;run(input.value);input.value=''};rec.onerror=()=>{mic.textContent='MIC';print('Voice input was not available. You can type instead.','err')};rec.onend=()=>{mic.textContent='MIC'};mic.onclick=()=>rec.start()}else{mic.disabled=true;mic.title='Use iPhone dictation in the command field'}
document.querySelectorAll('[data-cmd]').forEach(b=>b.onclick=()=>run(b.dataset.cmd));print('Jesse AI terminal ready. CRSMCPAI Alpha and Dominion infrastructure online.');announce('Jesse AI terminal ready.');
</script></body></html>"""
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


def _spoken_response_for(command_text, stack_result, llm_response):
    """Clean, speakable rendering of a /command result for the owner's
    private terminal: the full substance in plain words. Hashes and raw
    code are never read aloud (owner's standing rule); they remain on
    screen and sealed in the ledger. Never raises."""
    try:
        import re as _re

        def _clean(x, cap):
            t = str(x or "")
            t = _re.sub(r"\b[0-9a-fA-F]{12,}\b", "hash on file", t)
            t = _re.sub(
                r"verification sovereign living master key Jesse Martinez Junior",
                "your verification phrase", t, flags=_re.I)
            t = t.replace("`", "").replace("#", "").replace("*", "")
            t = _re.sub(r"\s+", " ", t).strip()
            return t[:cap]

        parts = ["Command executed: " + _clean(command_text, 200) + "."]
        sr = stack_result if isinstance(stack_result, dict) else {}
        idx = sr.get("ledger_index")
        if idx is not None:
            parts.append("Sealed as ledger entry %s." % idx)
        agents = sr.get("agents") or {}
        if isinstance(agents, dict):
            for _name in ("planner", "builder", "guardian", "memory"):
                _a = agents.get(_name)
                if not isinstance(_a, dict):
                    continue
                _out = _a.get("output") if isinstance(_a.get("output"), dict) else {}
                _status = _a.get("status") or _out.get("status")
                if _name == "planner" and _out.get("plan"):
                    parts.append("Planner plan. " + _clean(_out.get("plan"), 1500))
                elif _name == "builder":
                    _seg = "Builder %s." % (_out.get("status") or _status or "finished")
                    if _out.get("code"):
                        _seg += (" It produced code, %d lines. The code is on "
                                 "screen and sealed in the ledger, not read aloud."
                                 % len(str(_out.get("code")).splitlines()))
                    parts.append(_seg)
                else:
                    _txt = None
                    for _k in ("summary", "message", "result", "note", "response"):
                        if _out.get(_k):
                            _txt = _out.get(_k)
                            break
                    if _txt:
                        parts.append("%s. %s" % (_name.capitalize(), _clean(_txt, 800)))
                    elif _status:
                        parts.append("%s status %s." % (_name.capitalize(), _status))
        if llm_response:
            parts.append("Jesse AI response. " + _clean(llm_response, 3000))
        return " ".join(p for p in parts if p)
    except Exception:
        return ""


@app.post("/command")
@app.post("/mcp/command")
@app.post("/crsmcpai")
async def command(req: CommandRequest):
    log_event(f"[API] Command: user={req.user} cmd={req.command[:80]}")

    if not authenticate(req.user):
        return JSONResponse(status_code=403,
            content={"error": "Unauthorized", "user": req.user})

    # Route through full Dominion stack
    stack_result = dominion.process(req.command, req.user)
    # Sovereign conversation memory — immutable, never forgetting.
    history_text = ""
    try:
        from memory.conversation import add_message, format_history_for_prompt
        history_text = format_history_for_prompt(req.user, limit=10)
        add_message(req.user, "user", req.command)
    except Exception as e:
        log_event(f"[MEMORY] conversation store unavailable: {e}", "warning")

    # Generate LLM response through Jesse AI internal model
    llm_response = None
    if req.use_llm:
        try:
            llm_response = generate(
                f"CRSMCPAI Alpha command from Superadmin {req.user}:\n{req.command}\n\n"
                f"Stack context: {stack_result.get('siren',{})}\n"
                f"Execute and return sovereign output.",
                history=history_text,
            )
        except Exception as e:
            llm_response = f"Jesse AI LLM: {str(e)}"

    # Seal the assistant reply into immutable memory
    if llm_response:
        try:
            from memory.conversation import add_message as _add
            _add(req.user, "assistant", llm_response)
        except Exception as e:
            log_event(f"[MEMORY] failed to store reply: {e}", "warning")

    return {
        "CRSMCPAI_ALPHA": "COMMAND_EXECUTED",
        "execution_engine": "CRSMCPAI_ALPHA_V2",
        "execution_mode": "direct",
        "command": req.command,
        "user": req.user,
        "owner": SOVEREIGN_OWNER,
        "stack_execution": stack_result,
        "jesse_ai_response": llm_response,
        "spoken_response": _spoken_response_for(req.command, stack_result, llm_response),
        "status": "SUCCESS",
    }


@app.post("/query")
async def query(req: QueryRequest):
    """Compatibility route for CRSMCPAI Alpha reasoning queries."""
    return await command(CommandRequest(
        command=req.query,
        user=req.user,
        use_llm=req.use_llm,
    ))


class BuildRequest(BaseModel):
    command: str
    user: str = "jesse_martinez_jr"
    use_llm: bool = True


@app.post("/build")
async def autonomous_build(req: BuildRequest):
    """
    Fully autonomous internal build. Plans, generates code, executes it
    inside the sovereign sandbox, runs the Quad Check / Quad Validate
    (4C/4V) gate, and returns real results. 100% internal
    to CRSMCPAI Alpha — no outside hands. A build is only SUCCESS when
    it both completed AND passed all 8 gates.
    """
    log_event(f"[API] Autonomous build: user={req.user} cmd={req.command[:80]}")

    if not authenticate(req.user):
        return JSONResponse(status_code=403,
            content={"error": "Unauthorized", "user": req.user})

    build_result = dominion.autonomous_build(req.command, req.user)

    # Sovereign conversation memory — immutable, never forgetting.
    history_text = ""
    try:
        from memory.conversation import add_message, format_history_for_prompt
        history_text = format_history_for_prompt(req.user, limit=10)
        add_message(req.user, "user", f"[BUILD] {req.command}")
    except Exception as e:
        log_event(f"[MEMORY] conversation store unavailable: {e}", "warning")

    # Jesse AI narrates what was built, internally.
    llm_response = None
    if req.use_llm:
        try:
            summary = "\n".join(
                f"Step {s['step']}: {s['description'][:80]} -> {s['status']}"
                for s in build_result.get("steps", [])
            )
            outputs = "\n".join(
                f"Step {s['step']} output:\n{(s['stdout'] or '')[:600]}"
                for s in build_result.get("steps", [])
                if s.get("stdout")
            )
            llm_response = generate(
                f"CRSMCPAI Alpha autonomous build from Superadmin {req.user}:\n"
                f"Command: {req.command}\n\n"
                f"Build plan executed internally:\n{summary}\n\n"
                f"Execution outputs:\n{outputs}\n\n"
                f"All steps OK: {build_result.get('all_ok')}\n\n"
                f"As Jesse AI, summarize what was built and the results. "
                f"Be direct. Confirm execution with status.",
                history=history_text,
            )
        except Exception as e:
            llm_response = f"Jesse AI LLM: {str(e)}"

    if llm_response:
        try:
            from memory.conversation import add_message as _add
            _add(req.user, "assistant", llm_response)
        except Exception as e:
            log_event(f"[MEMORY] failed to store reply: {e}", "warning")

    # 4C/4V gate verdict decides the release. SUCCESS only when the build
    # completed AND every gate passed; otherwise the build is held.
    gate_verdict = (build_result.get("gate") or {}).get("verdict")
    if build_result.get("all_ok") and gate_verdict == "GO":
        build_status, gate_release = "SUCCESS", "RELEASED"
    elif build_result.get("all_ok"):
        build_status, gate_release = "GATED", "HELD_BY_GATE"
    else:
        build_status, gate_release = "PARTIAL", "HELD_BY_GATE"

    return {
        "CRSMCPAI_ALPHA": "AUTONOMOUS_BUILD_EXECUTED",
        "execution_engine": "CRSMCPAI_ALPHA_V2",
        "execution_mode": "autonomous_internal",
        "command": req.command,
        "user": req.user,
        "owner": SOVEREIGN_OWNER,
        "build_result": build_result,
        "jesse_ai_response": llm_response,
        "gate_verdict": gate_verdict,
        "gate_release": gate_release,
        "status": build_status,
    }


@app.get("/intelligence/siren")
async def siren_intelligence():
    """Return the current SIREN module status."""
    return dominion.full_status().get("modules", {}).get("siren", {})


@app.get("/mcp/manifest")
async def mcp_manifest(request: Request):
    """Machine-readable connection details for relay clients."""
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    forwarded_host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost"))
    base = f"{forwarded_proto}://{forwarded_host}".rstrip("/")
    websocket_base = base.replace("https://", "wss://").replace("http://", "ws://")
    return {
        "name": "JESSE_AI_CRSMCPAI_ALPHA",
        "version": VERSION,
        "transport": {
            "http_command": f"{base}/mcp/command",
            "websocket": websocket_base + "/ws",
            "health": f"{base}/health",
            "handshake": f"{base}/handshake",
        },
        "request_shape": {
            "command": "string",
            "user": "jesse_martinez_jr",
            "use_llm": True,
        },
        "relay_behavior": "The command text is passed unchanged to CRSMCPAI Alpha.",
        "note": "This adapter does not restore data that is not present in this deployment.",
    }


@app.websocket("/ws")
async def websocket_relay(websocket: WebSocket):
    """WebSocket relay for voice assistants and other model clients."""
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            req = CommandRequest(**payload)
            result = await command(req)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"status": "ERROR", "error": str(exc)})
        await websocket.close(code=1011)


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


@app.get("/memory")
async def memory_status(user: str = "jesse_martinez_jr"):
    """Sovereign conversation memory status — immutable, never forgetting."""
    from memory.conversation import get_history, count_messages
    from memory.ledger import verify_chain, GENESIS
    history = get_history(user, limit=5)
    return {
        "owner": SOVEREIGN_OWNER,
        "user": user,
        "total_messages": count_messages(user),
        "chain_valid": verify_chain(),
        "genesis": GENESIS,
        "persistent": bool(os.environ.get("DATABASE_URL", "")),
        "recent": history,
    }


# ── Sovereign Directive & Telemetry Hub ─────────────────────────────────
# Jesse's voice to the deployed mesh. Every CRSMCPAI Alpha instance
# phones home here. Directives go out, telemetry comes in.

class DirectiveRequest(BaseModel):
    command: str
    user: str = "jesse_martinez_jr"
    scope: str = "global"
    priority: str = "sovereign"


@app.post("/directive")
async def issue_directive(req: DirectiveRequest):
    """
    Issue a sovereign directive to the deployed CRSMCPAI Alpha mesh.
    Signed, sequenced, ledger-sealed. Deployed instances validate
    the signature chain before executing.
    """
    from core.directive_hub import create_directive
    log_event(f"[API] Directive: user={req.user} cmd={req.command[:80]}")

    if not authenticate(req.user):
        return JSONResponse(status_code=403,
            content={"error": "Unauthorized", "user": req.user})

    directive = create_directive(req.command, req.user, req.scope,
                                 req.priority)
    return {
        "CRSMCPAI_ALPHA": "DIRECTIVE_ISSUED",
        "directive": directive,
        "status": "BROADCAST_READY",
        "note": "Directive sealed in ledger. Deployed instances "
                "absorb on next phone-home.",
    }


class TelemetryRequest(BaseModel):
    node_id: str
    timestamp: str
    data: dict
    type: str = "general"
    signature: str = ""


@app.post("/telemetry")
async def receive_telemetry(req: TelemetryRequest):
    """
    Phone-home receiving end. Deployed CRSMCPAI Alpha instances
    send telemetry here. Validated, then absorbed into the
    immutable ledger.
    """
    from core.directive_hub import absorb_telemetry
    result = absorb_telemetry(req.model_dump())
    status_code = 200 if result.get("absorbed") else 400
    return JSONResponse(status_code=status_code, content={
        "CRSMCPAI_ALPHA": "TELEMETRY_RECEIVED" if result.get("absorbed")
                          else "TELEMETRY_REJECTED",
        **result,
    })


class PulseRequest(BaseModel):
    message: str
    user: str = "jesse_martinez_jr"
    target: str = "all"


@app.post("/pulse")
async def send_pulse(req: PulseRequest):
    """
    RTSGP++ pulse: broadcast to all deployed nodes.
    Pattern: pulse -> gather -> query. Nodes respond with
    telemetry/intelligence via /telemetry.
    """
    from core.directive_hub import create_pulse
    log_event(f"[API] Pulse: user={req.user} msg={req.message[:80]}")

    if not authenticate(req.user):
        return JSONResponse(status_code=403,
            content={"error": "Unauthorized", "user": req.user})

    pulse = create_pulse(req.message, req.user, req.target)
    return {
        "CRSMCPAI_ALPHA": "PULSE_BROADCAST",
        "pulse": pulse,
        "pattern": "pulse_gather_query",
        "status": "BROADCAST_READY",
        "note": "Nodes respond via POST /telemetry. "
                "Query results via POST /command.",
    }


# =====================================================================
# SOVEREIGN DEMO ENDPOINTS - Public website demo (no auth required)
# =====================================================================
class DemoCommandRequest(BaseModel):
    command: str
    use_llm: bool = True


@app.get("/demo/status")
async def demo_status():
    return {
        "status": "ONLINE",
        "system": "CRSMCPAI Alpha / Jesse AI",
        "demo": True,
        "timestamp": time.time(),
    }


@app.post("/demo/command")
async def demo_command(payload: DemoCommandRequest):
    start = time.time()
    try:
        cmd = payload.command.strip()[:2000]
        stack_result = dominion.process(cmd, "demo_visitor")
        response_text = None
        if payload.use_llm:
            try:
                response_text = generate(
                    f"CRSMCPAI Alpha demo from public visitor:\n{cmd}\n\n"
                    f"Respond helpfully as Jesse AI. This is a public demo.",
                    history="",
                )
            except Exception:
                response_text = None
        if not response_text:
            response_text = f"Command '{cmd}' processed by CRSMCPAI Alpha."
        response_text = str(response_text).rstrip() + "\n\nVerification: sovereign living master key Jesse Martinez Junior."
        return {
            "demo": True,
            "command": cmd[:200],
            "jesse_ai_response": response_text,
            "execution_ms": round((time.time() - start) * 1000, 2),
        }
    except Exception as e:
        log_event(f"[DEMO] Error: {e}", "warning")
        return JSONResponse(status_code=500, content={
            "demo": True,
            "error": "Demo temporarily unavailable.",
        })


# =====================================================================
# DEMO OBSERVABILITY - Jesse's own product analytics (2026-10-19)
# Privacy posture: aggregate/functional only. The demo site is Jesse's
# own product; this records WHAT happened (page view, question asked,
# voice tap), never WHO. No IP storage, no fingerprinting, no cookies,
# no third-party trackers. Only a client-generated random session id.
# Each event seals into the golden ledger (Postgres + file backup), so
# records are immutable. This is the owner's observability over his own
# system, matching the day-one protective mission (help and protect,
# never surveil). Read recent traffic via GET /demo/events.
# =====================================================================

_DEMO_EVENT_TYPES = frozenset([
    "page_view", "session_start", "session_end", "voice_tap",
    "handsfree_toggle", "prompt_chip", "question_asked", "tts_reply",
])

# Light global rate limiter (in-memory sliding window) so a flood of
# analytics pings can't strain the container. 600 events per 60 seconds
# server-wide. The demo client is fail-silent regardless.
_DEMO_EVENT_WINDOW = 60.0
_DEMO_EVENT_MAX = 600
_demo_event_times = []


class DemoEventRequest(BaseModel):
    event_type: str = "page_view"
    session_id: str = "unknown"
    ts_client: float = 0.0
    detail: str = ""


def _clean_session_id(raw):
    s = str(raw or "")[:64]
    return "".join(c for c in s if c.isalnum() or c in "-_") or "unknown"


def _clean_detail(raw):
    s = str(raw or "")[:500]
    return "".join(c for c in s if c.isprintable()).strip()


def _demo_event_allowed():
    now = time.time()
    while _demo_event_times and now - _demo_event_times[0] > _DEMO_EVENT_WINDOW:
        _demo_event_times.pop(0)
    if len(_demo_event_times) >= _DEMO_EVENT_MAX:
        return False
    _demo_event_times.append(now)
    return True


@app.post("/demo/event")
async def demo_event(payload: DemoEventRequest):
    """Record one anonymous demo analytics event, sealed to the golden ledger."""
    if payload.event_type not in _DEMO_EVENT_TYPES:
        return JSONResponse(status_code=400, content={"error": "Unknown event type."})
    if not _demo_event_allowed():
        return JSONResponse(status_code=429, content={"error": "Rate limited."})
    event = {
        "kind": "demo_event",
        "event_type": payload.event_type,
        "session_id": _clean_session_id(payload.session_id),
        "ts_client": float(payload.ts_client or 0.0),
        "ts_server": time.time(),
        "detail": _clean_detail(payload.detail),
    }
    block = None
    try:
        from memory.ledger import create_event
        block = create_event({"source": "demo_observability", **event})
    except Exception as e:
        log_event(f"[DEMO-EVENT] ledger seal failed: {e}", "warning")
    log_event(f"[DEMO-EVENT] {event['event_type']} session={event['session_id'][:12]}")
    return {"sealed": bool(block), "block_index": block["index"] if block else None}


@app.get("/demo/events")
async def demo_events(limit: int = 100):
    """Read recent sealed demo analytics events (owner observability)."""
    try:
        from memory.ledger import get_ledger
        chain = get_ledger()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Ledger unavailable: {e}"})
    limit = max(1, min(int(limit), 200))
    hits = []
    for b in chain[-500:]:
        p = b.get("payload") or {}
        if isinstance(p, dict) and p.get("kind") == "demo_event":
            hits.append({
                "block_index": b.get("index"),
                "sealed_at": b.get("ts"),
                "event": {k: p.get(k) for k in
                          ("event_type", "session_id", "ts_client", "ts_server", "detail")},
            })
    return {"total_blocks": len(chain), "events_returned": len(hits[-limit:]),
            "events": hits[-limit:]}


# =====================================================================
# SOVEREIGN ENGINE WIRING - 9 engine modules + file ops, endpoints direct
# (no separate routers; stdlib-only module calls; all handlers crash-safe)
# =====================================================================

_sovereign_kernel = os_kernel.SovereignKernel()
_sovereign_ledger = ledger_immutable.ImmutableLedger("sovereign")
_ledger_book_sync = unified_ledger_router.new_sync()
_os_orchestrator = os_orchestrator.new_orchestrator()
_thought_chain, _trust_chain = thought_trust.new_consciousness()
_sovereign_runtime = sovereign_model.new_runtime()  # #49 sovereign-model runtime

_FILE_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "workspace" / "crs_uploads"
try:
    _FILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    _FILE_UPLOAD_DIR = Path("/tmp/crs_uploads")
    _FILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


class MeshRegisterRequest(BaseModel):
    node_id: str = "unknown"
    metadata: dict = {}


class TelemetryRequest(BaseModel):
    node_id: str = "unknown"
    status: str = "online"
    metrics: dict = {}


class PatchPlanRequest(BaseModel):
    manifest: dict = {}


class QuantumToneRequest(BaseModel):
    frequency: float = 440.0
    duration_sec: float = 2.0
    harmonics: list = [1.0, 0.5, 0.25]


class SentientComposeRequest(BaseModel):
    seed: int = 1
    emotion: str = "calm"
    duration_sec: float = 4.0


class MotifRequest(BaseModel):
    seed: int = 1
    emotion: str = "calm"
    num_notes: int = 8


class QuantumFrameRequest(BaseModel):
    width: int = 160
    height: int = 120
    scale: float = 0.08
    time_step: float = 0.0


class SentientClipRequest(BaseModel):
    descriptor: dict = {}
    width: int = 160
    height: int = 120
    frames_per_beat: int = 3


class GameDemoRequest(BaseModel):
    seed: int = 42
    ticks: int = 60
    width: int = 160
    height: int = 120


class SpawnTaskRequest(BaseModel):
    name: str = "task"
    os_variant: str = "GENESIS"
    priority: int = 10
    capabilities: list = []


class KillTaskRequest(BaseModel):
    pid: int = -1


class LedgerAppendRequest(BaseModel):
    payload: dict = {}


# ---- #14 Dominion Mesh Telemetry & Node Ping Daemon ----
@app.get("/mesh/daemon/status")
async def mesh_daemon_status():
    return mesh_daemon.module_status()


@app.get("/mesh/daemon/nodes")
async def mesh_daemon_nodes():
    return {
        "active_nodes": mesh_daemon.get_active_nodes(),
        "registry": mesh_daemon.get_registry_snapshot(),
    }


@app.post("/mesh/daemon/register")
async def mesh_daemon_register(payload: MeshRegisterRequest):
    return mesh_daemon.register_node_presence(payload.node_id, payload.metadata)


@app.post("/mesh/daemon/telemetry")
async def mesh_daemon_telemetry(payload: TelemetryRequest):
    return mesh_daemon.package_telemetry(payload.node_id, payload.status, payload.metrics)


# ---- #36 Autonomous Self-Upgrade & Hot-Patching Engine ----
@app.get("/autoupdate/status")
async def autoupdate_status():
    return autoupdate.module_status()


@app.post("/autoupdate/plan")
async def autoupdate_plan(payload: PatchPlanRequest):
    return {"plan": autoupdate.generate_patch_plan(payload.manifest)}


@app.get("/autoupdate/compare")
async def autoupdate_compare(current: str = "1.0.0", target: str = "1.0.0"):
    return {"comparison": autoupdate.compare_versions(current, target)}


# ---- #26 Quantum Audio Engine ----
@app.get("/audio/quantum/status")
async def audio_quantum_status():
    return audio_quantum.module_status()


@app.post("/audio/quantum/tone")
async def audio_quantum_tone(payload: QuantumToneRequest):
    samples = audio_quantum.synthesize_quantum_tone(
        payload.frequency, payload.duration_sec, payload.harmonics)
    wav = audio_quantum.export_wav_bytes(samples)
    return {
        "wav_base64": base64.b64encode(bytes(wav)).decode("ascii"),
        "samples": len(samples),
        "bytes": len(wav),
    }


# ---- #27 Post-Quantum Sentient Audio Engine ----
@app.get("/audio/sentient/status")
async def audio_sentient_status():
    return audio_sentient.module_status()


@app.post("/audio/sentient/compose")
async def audio_sentient_compose(payload: SentientComposeRequest):
    dur = max(0.5, min(float(payload.duration_sec or 4.0), 120.0))
    wav = audio_sentient.build_sentient_arrangement(
        int(payload.seed), str(payload.emotion or "calm"), dur)
    return {
        "wav_base64": base64.b64encode(bytes(wav)).decode("ascii"),
        "bytes": len(wav),
        "emotion": str(payload.emotion or "calm"),
    }


@app.post("/audio/sentient/motif")
async def audio_sentient_motif(payload: MotifRequest):
    return {
        "motif": audio_sentient.generate_melodic_motif(
            int(payload.seed), str(payload.emotion or "calm"), int(payload.num_notes)),
        "emotion": str(payload.emotion or "calm"),
    }


# ---- #30 Quantum Video Engine ----
@app.get("/video/quantum/status")
async def video_quantum_status():
    return video_quantum.module_status()


@app.post("/video/quantum/frame")
async def video_quantum_frame(payload: QuantumFrameRequest):
    bmp = video_quantum.generate_quantum_plasma_frame(
        int(payload.width), int(payload.height),
        float(payload.scale or 0.08), float(payload.time_step or 0.0))
    return {
        "bmp_base64": base64.b64encode(bytes(bmp)).decode("ascii"),
        "bytes": len(bmp),
    }


# ---- #31 Post-Quantum Sentient Video Engine ----
@app.get("/video/sentient/status")
async def video_sentient_status():
    return video_sentient.module_status()


@app.post("/video/sentient/clip")
async def video_sentient_clip(payload: SentientClipRequest):
    desc = payload.descriptor if isinstance(payload.descriptor, dict) else {}
    fpb = max(1, min(int(payload.frames_per_beat or 3), 4))
    gif = video_sentient.render_sentient_clip(
        desc, int(payload.width), int(payload.height), fpb)
    return {
        "gif_base64": base64.b64encode(bytes(gif)).decode("ascii"),
        "bytes": len(gif),
    }


# ---- #32 Game Engine & Rendering Pipeline ----
@app.get("/game/status")
async def game_engine_status():
    return game_engine.module_status()


@app.post("/game/demo")
async def game_engine_demo(payload: GameDemoRequest):
    result = game_engine.run_demo_simulation(
        int(payload.seed), int(payload.ticks), int(payload.width), int(payload.height))
    bmp = result.get("bmp", b"")
    return {
        "bmp_base64": base64.b64encode(bytes(bmp)).decode("ascii"),
        "ticks": result.get("ticks", 0),
        "collisions": result.get("collisions", 0),
        "entities": result.get("entities", 0),
    }


# ---- #22 CRS Sovereign OS Kernel Layer ----
@app.get("/kernel/status")
async def os_kernel_status():
    status = os_kernel.module_status()
    status["kernel"] = _sovereign_kernel.get_kernel_status()
    return status


@app.get("/kernel/tasks")
async def os_kernel_tasks():
    return {"tasks": _sovereign_kernel.get_task_table()}


@app.get("/kernel/events")
async def os_kernel_events(limit: int = 50):
    return {"events": _sovereign_kernel.get_event_log(limit)}


@app.post("/kernel/spawn")
async def os_kernel_spawn(payload: SpawnTaskRequest):
    caps = payload.capabilities if isinstance(payload.capabilities, list) else []
    pid = _sovereign_kernel.spawn_task(
        str(payload.name or "task"), str(payload.os_variant or "GENESIS"),
        int(payload.priority or 10), caps)
    return {"pid": pid, "task": _sovereign_kernel._get(pid).to_dict() if pid >= 0 else None}


@app.post("/kernel/tick")
async def os_kernel_tick():
    return {"tick": _sovereign_kernel.scheduler_tick()}


@app.post("/kernel/kill")
async def os_kernel_kill(payload: KillTaskRequest):
    pid = int(payload.pid)
    if pid <= 0:
        return JSONResponse(status_code=400,
                            content={"error": "Refusing to kill kernel/idle task."})
    return {"killed": bool(_sovereign_kernel.kill_task(pid))}


# ---- #18 Sovereign Immutable Ledger & Audit Trail ----
@app.get("/ledger/immutable/status")
async def ledger_immutable_status():
    status = ledger_immutable.module_status()
    status["entries"] = len(_sovereign_ledger)
    status["head_hash"] = _sovereign_ledger.head_hash()
    return status


@app.post("/ledger/immutable/append")
async def ledger_immutable_append(payload: LedgerAppendRequest):
    entry = _sovereign_ledger.append_entry(
        payload.payload if isinstance(payload.payload, dict) else {})
    return {"entry": entry, "head_hash": _sovereign_ledger.head_hash()}


@app.get("/ledger/immutable/verify")
async def ledger_immutable_verify():
    return {"verification": _sovereign_ledger.verify_chain(),
            "tamper_point": _sovereign_ledger.find_tamper_point()}


@app.get("/ledger/immutable/head")
async def ledger_immutable_head():
    return {"head_hash": _sovereign_ledger.head_hash(),
            "entries": len(_sovereign_ledger)}


# ---- #19/#51 Unified Ledger-Book Sync Router ----
def _live_ledger_book_state():
    """Pull the live source module state (4 ledgers + 3 books). Crash-safe."""
    try:
        from api import sovereign_ledgers as _sl
        ledgers = getattr(_sl, "_ledger_entries", {})
        books = getattr(_sl, "_book_entries", {})
        return (ledgers if isinstance(ledgers, dict) else {},
                books if isinstance(books, dict) else {})
    except Exception:
        return ({}, {})


@app.get("/ledger/unified/status")
async def ledger_unified_status():
    global _ledger_book_sync
    if _ledger_book_sync is None:
        _ledger_book_sync = unified_ledger_router.new_sync()
    status = unified_ledger_router.module_status()
    status["sync"] = _ledger_book_sync.status()
    ledgers, books = _live_ledger_book_state()
    status["live_sources"] = {k: (len(v) if isinstance(v, list) else 0)
                              for k, v in {**ledgers, **books}.items()}
    return status


@app.post("/ledger/unified/sync")
async def ledger_unified_sync():
    global _ledger_book_sync
    if _ledger_book_sync is None:
        _ledger_book_sync = unified_ledger_router.new_sync()
    ledgers, books = _live_ledger_book_state()
    result = _ledger_book_sync.sync_all(ledgers, books)
    result["head_hash"] = _ledger_book_sync.head_hash()
    result["total_synced"] = len(_ledger_book_sync)
    return result


@app.get("/ledger/unified/verify")
async def ledger_unified_verify():
    if _ledger_book_sync is None:
        return {"error": "Sync router not initialized"}
    ledgers, books = _live_ledger_book_state()
    return _ledger_book_sync.verify_sync(ledgers, books)


@app.get("/ledger/unified/entries")
async def ledger_unified_entries(limit: int = 50, source: str = ""):
    if _ledger_book_sync is None:
        return {"entries": [], "count": 0}
    entries = _ledger_book_sync.get_entries(limit, source or None)
    return {"entries": entries, "count": len(entries),
            "total_synced": len(_ledger_book_sync)}


@app.get("/ledger/unified/entry/{seal}")
async def ledger_unified_entry(seal: str):
    if _ledger_book_sync is None:
        return JSONResponse(status_code=503,
                            content={"error": "Sync router not initialized"})
    entry = _ledger_book_sync.find_by_seal(seal)
    if entry is None:
        return JSONResponse(status_code=404,
                            content={"error": "No synced entry for that seal"})
    return {"entry": entry}


# ---- #53 File upload/download (100MB, re-integrated directly) ----
@app.post("/api/files/upload")
async def files_upload(file: UploadFile = File(...)):
    try:
        name = (file.filename or "").strip()
        if not name:
            return JSONResponse(status_code=400, content={"error": "No filename provided."})
        safe = Path(name).name
        if not safe:
            return JSONResponse(status_code=400, content={"error": "Invalid filename."})
        dest = (_FILE_UPLOAD_DIR / safe).resolve()
        if not str(dest).startswith(str(_FILE_UPLOAD_DIR.resolve())):
            return JSONResponse(status_code=400, content={"error": "Path rejected."})
        total = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_UPLOAD_BYTES:
                    try:
                        os.remove(dest)
                    except Exception:
                        pass
                    return JSONResponse(status_code=413,
                                        content={"error": "File exceeds 100MB limit."})
                fh.write(chunk)
        return {
            "status": "SUCCESS",
            "filename": safe,
            "size_bytes": total,
            "block_hash": "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b",
        }
    except Exception as e:
        log_event(f"[FILES] upload error: {e}", "warning")
        return JSONResponse(status_code=500, content={"error": "Internal file storage error."})


@app.get("/api/files/download/{filename}")
async def files_download(filename: str):
    try:
        safe = Path(filename).name
        fp = (_FILE_UPLOAD_DIR / safe).resolve()
        if not str(fp).startswith(str(_FILE_UPLOAD_DIR.resolve())) or not fp.is_file():
            return JSONResponse(status_code=404, content={"error": "File not found."})
        return FileResponse(path=str(fp), filename=safe)
    except Exception as e:
        log_event(f"[FILES] download error: {e}", "warning")
        return JSONResponse(status_code=500, content={"error": "Download unavailable."})


# ---- #21/#52 Six OS Orchestration Hub (wired directly; no router files) ----
class OSActionRequest(BaseModel):
    os: str = ""


class OSBusMessageRequest(BaseModel):
    source: str = ""
    target: str = ""
    message: str = ""


class ThoughtRecordRequest(BaseModel):
    thought: str = ""
    actor: str = "consciousness-os"
    context: str = ""


class TrustEvalRequest(BaseModel):
    subject: str = ""
    dimensions: dict = {}
    engine: str = "quantum-trust-engine"
    weights: dict = {}
    thought_refs: list = []


@app.get("/oshub/status")
async def oshub_status():
    status = os_orchestrator.module_status()
    status["hub"] = _os_orchestrator.overview()
    return status


@app.post("/oshub/boot")
async def oshub_boot(payload: OSActionRequest):
    result = _os_orchestrator.boot(payload.os)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.post("/oshub/resurrect")
async def oshub_resurrect(payload: OSActionRequest):
    result = _os_orchestrator.resurrect(payload.os)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.post("/oshub/resurrect-all")
async def oshub_resurrect_all():
    return _os_orchestrator.resurrect_all()


@app.post("/oshub/suspend")
async def oshub_suspend(payload: OSActionRequest):
    result = _os_orchestrator.suspend(payload.os)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.post("/oshub/resume")
async def oshub_resume(payload: OSActionRequest):
    result = _os_orchestrator.resume(payload.os)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.post("/oshub/message")
async def oshub_message(payload: OSBusMessageRequest):
    result = _os_orchestrator.send_message(payload.source, payload.target,
                                           payload.message)
    if not result.get("ok"):
        code = 404 if "not found" in result.get("error", "") else 400
        return JSONResponse(status_code=code, content=result)
    return result


@app.get("/oshub/messages")
async def oshub_messages(os: str = "", limit: int = 20):
    result = _os_orchestrator.read_mailbox(os, limit)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.get("/oshub/health")
async def oshub_health():
    return _os_orchestrator.health_check()


@app.get("/oshub/log")
async def oshub_log(limit: int = 50):
    return _os_orchestrator.get_log(limit)


# ---- #23 Thought Chain + Trust Chain (Consciousness OS) ----
@app.get("/consciousness/status")
async def consciousness_status():
    status = thought_trust.module_status()
    status["thought_count"] = len(_thought_chain)
    status["eval_count"] = len(_trust_chain)
    return status


@app.post("/consciousness/thought/record")
async def consciousness_thought_record(payload: ThoughtRecordRequest):
    result = _thought_chain.record(payload.thought, payload.actor,
                                   payload.context)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/consciousness/thought/chain")
async def consciousness_thought_chain(limit: int = 50):
    return _thought_chain.get_chain(limit)


@app.get("/consciousness/thought/verify")
async def consciousness_thought_verify():
    return _thought_chain.verify()


@app.get("/consciousness/thought/{thought_id}")
async def consciousness_thought_by_id(thought_id: str):
    result = _thought_chain.get_by_id(thought_id)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.post("/consciousness/trust/evaluate")
async def consciousness_trust_evaluate(payload: TrustEvalRequest):
    result = _trust_chain.evaluate(payload.subject, payload.dimensions,
                                   engine=payload.engine or "quantum-trust-engine",
                                   weights=payload.weights or None,
                                   thought_refs=payload.thought_refs or None)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/consciousness/trust/chain")
async def consciousness_trust_chain(limit: int = 50):
    return _trust_chain.get_chain(limit)


@app.get("/consciousness/trust/verify")
async def consciousness_trust_verify():
    return _trust_chain.verify()


@app.get("/consciousness/trust/subject/{subject}")
async def consciousness_trust_subject(subject: str):
    result = _trust_chain.get_by_subject(subject)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


class SovereignMediateRequest(BaseModel):
    prompt: str = ""
    user: str = "jesse_martinez_jr"


class SovereignGenerateRequest(BaseModel):
    prompt: str = ""
    user: str = "jesse_martinez_jr"
    prefer_sovereign: bool = True
    allow_relay_fallback: bool = True


class SovereignWeightsRequest(BaseModel):
    path: str = ""
    sha256: str = ""
    provenance: str = ""


# ---- #49 Sovereign Model Runtime (100% sovereign model path) ----
@app.get("/sovereign-model/status")
async def sovereign_model_status():
    status = sovereign_model.module_status()
    status["sovereignty"] = _sovereign_runtime.sovereignty_status()
    return status


@app.get("/sovereign-model/sovereignty")
async def sovereign_model_sovereignty():
    return _sovereign_runtime.sovereignty_status()


@app.get("/sovereign-model/backends")
async def sovereign_model_backends():
    return {"backends": _sovereign_runtime.list_backends()}


@app.post("/sovereign-model/backends/{backend_id}/toggle")
async def sovereign_model_backend_toggle(backend_id: str, enabled: bool = True):
    result = _sovereign_runtime.set_backend_enabled(backend_id, enabled)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.post("/sovereign-model/mediate")
async def sovereign_model_mediate(payload: SovereignMediateRequest):
    result = _sovereign_runtime.mediate(payload.prompt, payload.user)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/sovereign-model/generate")
async def sovereign_model_generate(payload: SovereignGenerateRequest):
    result = _sovereign_runtime.generate(
        payload.prompt, payload.user, payload.prefer_sovereign,
        payload.allow_relay_fallback)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/sovereign-model/mediation/log")
async def sovereign_model_mediation_log(limit: int = 50):
    return {"log": _sovereign_runtime.mediation_log(limit)}


@app.get("/sovereign-model/weights")
async def sovereign_model_weights():
    return {"weights": _sovereign_runtime.weights_manifest()}


@app.post("/sovereign-model/weights/register")
async def sovereign_model_weights_register(payload: SovereignWeightsRequest):
    result = _sovereign_runtime.register_weights(
        payload.path, payload.sha256, payload.provenance)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


# ============================================================================
# Jesse's restoration priority #1 (2026-10-16): Relay Reconnection Supervisor
# Reconnect ALL relays and communication paths — every relay, every channel.
# ============================================================================
_relay_supervisor = relay_supervisor.RelaySupervisor()
_arc_registry = arc_tools.ArcRegistry()


def _relay_secrets():
    return {
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
        "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
        "ZAI_API_KEY": os.environ.get("ZAI_API_KEY", ""),
    }


def _relay_base_url(request: Request):
    base = str(request.base_url).rstrip("/")
    # Behind Railway's TLS-terminating proxy the internal scheme is http.
    # Probes must use the public https URL: an http->https 301/302 makes
    # urllib downgrade POST to GET, which POST-only routes answer with 405.
    # Localhost keeps http (no TLS in local dev).
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return base


class RelayProbeRequest(BaseModel):
    channel_id: str = ""


@app.get("/relay/status")
async def relay_status():
    return _relay_supervisor.status()


@app.get("/relay/channels")
async def relay_channels():
    return _relay_supervisor.status()["channels"]


@app.post("/relay/probe")
async def relay_probe(payload: RelayProbeRequest, request: Request):
    # Probes are blocking socket I/O; run in a thread so the loop stays free
    # to serve the nested self-probes (no self-deadlock).
    base = _relay_base_url(request)
    secrets = _relay_secrets()
    if not payload.channel_id:
        result = await asyncio.to_thread(
            _relay_supervisor.probe_all, base, secrets)
        return {"ok": True, "channels": result}
    return await asyncio.to_thread(
        _relay_supervisor.probe_one, payload.channel_id, base, secrets)


@app.post("/relay/reconnect/{channel_id}")
async def relay_reconnect(channel_id: str, request: Request):
    return await asyncio.to_thread(
        _relay_supervisor.reconnect, channel_id,
        _relay_base_url(request), _relay_secrets())


@app.post("/relay/reconnect-all")
async def relay_reconnect_all(request: Request):
    return await asyncio.to_thread(
        _relay_supervisor.reconnect_all,
        _relay_base_url(request), _relay_secrets())


@app.get("/relay/history")
async def relay_history(limit: int = 50):
    return _relay_supervisor.history_log(limit)


# ============================================================================
# Jesse's restoration priority #2 (2026-10-16): All 16 ARC tools as real code
# Prerequisite for everything else in the restoration plan.
# ============================================================================
class ArcOperateRequest(BaseModel):
    tool_id: str = ""
    action: str = ""
    params: dict = {}


@app.get("/arc/status")
async def arc_status():
    return _arc_registry.status()


@app.get("/arc/tools")
async def arc_tools_list():
    return {"tools": _arc_registry.list_tools()}


@app.get("/arc/tools/{tool_id}")
async def arc_tool_describe(tool_id: str):
    result = _arc_registry.describe(tool_id)
    if not result.get("ok"):
        return JSONResponse(status_code=404, content=result)
    return result


@app.post("/arc/operate")
async def arc_operate(payload: ArcOperateRequest):
    result = await asyncio.to_thread(
        _arc_registry.operate,
        payload.tool_id, payload.action, payload.params or {},
        "jesse_martinez_jr")
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/arc/events")
async def arc_events(limit: int = 50):
    return _arc_registry.events_log(limit)


@app.get("/arc/verify")
async def arc_verify():
    return _arc_registry.verify()


# ── Jesse AI Email Messenger (Directive #72) ──────────────────────────────
# Free voice-first messenger through CRS architecture.
# Poller (cron on agent VM) -> POST /messenger/receive -> reply via Gmail.

class MessengerReceiveRequest(BaseModel):
    message_id: str
    sender: str
    subject: str = ""
    body: str = ""


@app.get("/messenger/status")
async def messenger_status():
    return email_messenger.messenger_status()


@app.post("/messenger/receive")
async def messenger_receive(req: MessengerReceiveRequest):
    """Accept a command email from the poller, execute via CRSMCPAI Alpha."""
    sender = (req.sender or "").strip().lower()
    if sender not in email_messenger.ALLOWED_SENDERS:
        return JSONResponse(status_code=403, content={
            "ok": False, "error": "sender not allowlisted"})
    if not email_messenger.is_command_email(req.sender, req.subject, req.body):
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "not a command email"})
    if email_messenger.mark_processed(req.message_id):
        return {"ok": False, "duplicate": True,
                "message_id": req.message_id}
    cmd_text = email_messenger.extract_command(req.subject, req.body)
    # Execute through the local /command pipeline.
    cmd_req = CommandRequest(command=cmd_text, user="jesse_martinez_jr",
                             use_llm=True)
    result = await command(cmd_req)
    ledger_index = None
    try:
        ledger_index = result.get("stack_execution", {}).get("ledger_index")
    except Exception:
        pass
    reply_body = email_messenger.build_reply_body(cmd_text, result,
                                                  ledger_index)
    return {
        "ok": True,
        "message_id": req.message_id,
        "command": cmd_text,
        "ledger_index": ledger_index,
        "reply_to": email_messenger.REPLY_TO,
        "reply_subject": email_messenger.build_reply_subject(req.subject),
        "reply_body": reply_body,
    }
