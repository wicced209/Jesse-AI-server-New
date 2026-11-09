"""
CRSMCPAI Alpha — Logic Surface (v1, 2026-11-08, Muse).

HTTP surface for the stack's logic core: the Context Reasoning
System (crsmcpai/context_reasoning.py v2) and the Module Context
Protocol (crsmcpai/module_context_protocol.py v2). The dominion
orchestrator uses both in-process; these routes exist so the logic
layer can be exercised and audited directly — push context, recall
it by meaning, assemble a working context, run a grounded reasoning
pass, list the protocol's modules and handlers, and dispatch a call
through the protocol.

Owner: SLMK Jesse Martinez Junior.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from crsmcpai.context_reasoning import crs
from crsmcpai.module_context_protocol import mcp

router = APIRouter(prefix="/logic", tags=["logic"])


class PushRequest(BaseModel):
    role: str = "user"
    content: str


class QueryRequest(BaseModel):
    query: str


class DispatchRequest(BaseModel):
    handler: str
    payload: dict = {}
    caller: str = ""


@router.post("/crs/push")
def crs_push(req: PushRequest):
    crs.push(req.role, req.content)
    return crs.stats()


@router.get("/crs/context")
def crs_context():
    return {"context": crs.get_context(), "stats": crs.stats()}


@router.post("/crs/retrieve")
def crs_retrieve(req: QueryRequest):
    return {"results": crs.retrieve(req.query)}


@router.post("/crs/assemble")
def crs_assemble(req: QueryRequest):
    return crs.assemble(req.query)


@router.post("/crs/reason")
def crs_reason(req: QueryRequest):
    return crs.reason(req.query)


@router.get("/mcp/modules")
def mcp_modules():
    return {"modules": mcp.list_modules(), "handlers": mcp.list_handlers()}


@router.post("/mcp/dispatch")
def mcp_dispatch(req: DispatchRequest):
    return mcp.dispatch(req.handler, req.payload, req.caller)


@router.get("/mcp/bus")
def mcp_bus(cursor: int = 0):
    return mcp.consume_since(cursor)
