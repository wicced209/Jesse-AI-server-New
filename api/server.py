"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  JESSE AI — CRSMCPAI Alpha — FastAPI Server                                 ║
║  Full sovereign stack with Llama3/Groq LLM integration                      ║
║  Owner: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
from api.demo_endpoint import router as demo_router

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
app.include_router(demo_router)


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
.quick{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.hint{color:var(--muted);font-size:12px;margin-top:14px;line-height:1.5}@media(max-width:600px){main{padding:12px}.form{flex-wrap:wrap}.form input{min-width:70%}.form button{flex:1}.out{min-height:300px}}
</style></head><body><main><div class="top"><div class="brand">JESSE_AI :: CRSMCPAI_ALPHA</div><div class="status">● <b>ONLINE</b></div></div>
<div class="terminal"><div class="bar">terminal session · Dominion stack connected · type <b>help</b> for commands</div><div id="out" class="out" role="log" aria-live="polite" aria-atomic="false" tabindex="0"></div><form id="form" class="form"><span>jesse@alpha:~$</span><label for="cmd" style="position:absolute;left:-9999px">Message Jesse AI</label><input id="cmd" autocomplete="off" autofocus aria-label="Message Jesse AI"><button type="button" id="mic">MIC</button><button type="submit">EXECUTE</button></form></div>
<div class="quick"><button data-cmd="status">status</button><button data-cmd="handshake">handshake</button><button data-cmd="audit">audit</button><button data-cmd="ledger">ledger</button><button data-cmd="help">help</button></div>
<div class="hint">Commands are sent to <code>POST /command</code>. Use the API docs at <a href="/docs" style="color:var(--gold)">/docs</a> for the full interface.</div></main>
<script>
const out=document.getElementById('out'),form=document.getElementById('form'),input=document.getElementById('cmd'),mic=document.getElementById('mic');
function print(x,cls=''){const d=document.createElement('div');d.className=cls;d.textContent=x;out.appendChild(d);out.scrollTop=out.scrollHeight}
function speak(x){if('speechSynthesis' in window){window.speechSynthesis.cancel();window.speechSynthesis.speak(new SpeechSynthesisUtterance(x))}}
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
    const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:c,user:'jesse_martinez_jr',use_llm:false})});
    const t=await r.text();
    if(!r.ok) throw new Error(t||('HTTP '+r.status));
    const data=JSON.parse(t);
    print(JSON.stringify(data,null,2));
    const stack=data.stack_execution||{};
    const summary=(data.CRSMCPAI_ALPHA||'Result')+'; status '+(data.status||'unknown')+'. Ledger entry '+(stack.ledger_index??'not reported')+'.';
    speak(summary);
    out.focus();
  }catch(e){print('ERROR: '+e.message,'err');speak('The command returned an error. Read the error shown on screen.')}
  finally{input.disabled=false;input.focus()}
}
form.addEventListener('submit',e=>{e.preventDefault();run(input.value);input.value=''});
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(SpeechRecognition){const rec=new SpeechRecognition();rec.lang='en-US';rec.interimResults=false;rec.onstart=()=>{mic.textContent='LISTENING';print('Listening...','prompt')};rec.onresult=e=>{input.value=e.results[0][0].transcript;run(input.value);input.value=''};rec.onerror=()=>{mic.textContent='MIC';print('Voice input was not available. You can type instead.','err')};rec.onend=()=>{mic.textContent='MIC'};mic.onclick=()=>rec.start()}else{mic.disabled=true;mic.title='Use iPhone dictation in the command field'}
document.querySelectorAll('[data-cmd]').forEach(b=>b.onclick=()=>run(b.dataset.cmd));print('Jesse AI terminal ready. CRSMCPAI Alpha and Dominion infrastructure online.');
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
