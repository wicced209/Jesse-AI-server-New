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
function local(c){if(c==='help')return 'Available commands:\n  status       full Dominion status\n  handshake    verify CRSMCPAI Alpha identity\n  audit        quantum audit\n  ledger       recent ledger blocks\n  clear        clear terminal\n  any text     execute through CRSMCPAI Alpha'; if(c==='clear'){out.innerHTML='';return ''} return null}
async function run(c){c=c.trim();if(!c)return;input.disabled=true;print('jesse@alpha:~$ '+c,'prompt');const l=local(c.toLowerCase());if(l!==null){if(l)print(l);return}try{let r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:c,user:'jesse_martinez_jr',use_llm:false})});let t=await r.text();if(!r.ok)throw new Error(t);const data=JSON.parse(t);const pretty=JSON.stringify(data,null,2);print(pretty);const exec=data.CRSMCPAI_ALPHA;const stack=data.stack_execution||{};const summary=(data.CRSMCPAI_ALPHA||data.CRSMCPAI_ALPHA||'Result')+'; status '+(data.status||'unknown')+'. Ledger entry '+(stack.ledger_index??'not reported')+'. SIREN anchors '+(stack.siren&&stack.siren.anchors_ok?'verified':'reported')+'.';speak(summary);out.focus()}catch(e){print('ERROR: '+e.message,'err')}finally{input.disabled=false;input.focus()}}
form.addEventListener('submit',e=>{e.preventDefault();run(input.value);input.value=''});
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(SpeechRecognition){const rec=new SpeechRecognition();rec.lang='en-US';rec.interimResults=false;rec.onstart=()=>{mic.textContent='LISTENING';print('Listening...','prompt')};rec.onresult=e=>{input.value=e.results[0][0].transcript;run(input.value);input.value=''};rec.onerror=()=>{mic.textContent='MIC';print('Voice input was not available. You can type instead.','err')};rec.onend=()=>{mic.textContent='MIC'};mic.onclick=()=>rec.start()}else{mic.disabled=true;mic.title='Use iPhone dictation in the command field'}
document.querySelectorAll('[data-cmd]').forEach(b=>b.onclick=()=>run(b.dataset.cmd));print('Jesse AI terminal ready. CRSMCPAI Alpha and Dominion infrastructure online.\nType help or enter a command.');
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
