"""Sovereign command-and-control HUD — the owner's panel.

WHY THIS EXISTS (Jesse, 2026-11-08): a full control panel for the
stack was part of the original design — one surface showing what is
live, what orders are sealed, what the agents are doing, what has
arrived, and what is still open — and it had to be friendly to a
screen reader, because the owner runs everything by voice. The
surviving admin surface was JSON-only status endpoints: fine for
machines, useless as the owner's own eyes.

This module is that panel, rebuilt as a behavior layer over the
live probes that already exist (the same functions the OS family,
networks, kernel-module, fabric, telemetry, and Sentinel surfaces
report from — one truth, many doors):

  GET /hud           the panel itself: semantic HTML, heading
                     structure a screen reader can navigate,
                     auto-refreshing, no scripts required.
  GET /hud/briefing  the same picture as plain sentences, text
                     only — made to be read aloud start to finish.
  GET /hud/state     the assembled picture as JSON.

ACCESS MODEL: the panel shows state — counts, statuses, times,
system names. It shows NO order texts, NO payloads, NO secrets,
and it can change nothing: reading the panel is not authority
(the demo dial: display at maximum, stranger authority zero).
The deep record — full order texts, build code, execution
detail — stays behind the owner-gated oversight routes.

Every section is probed at request time and fails soft: a probe
that errors reports its section as unavailable rather than
breaking the panel.
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

hud_router = APIRouter(prefix="/hud", tags=["hud"])

_PACIFIC = ZoneInfo("America/Los_Angeles")


def _when(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), _PACIFIC).strftime(
            "%I:%M %p Pacific, %B %d")
    except Exception:
        return "time unknown"


def hud_state() -> dict:
    """Assemble the whole picture from live probes, section by
    section, each failing soft to {"unavailable": reason}."""
    state: dict = {"generated_at": _when(time.time())}

    try:
        from memory.ledger import get_ledger, verify_chain
        chain = get_ledger()
        state["ledger"] = {"height": len(chain),
                           "chain_valid": verify_chain(),
                           "head_at": _when(chain[-1]["ts"]) if chain
                           else "no blocks"}
    except Exception as exc:
        state["ledger"] = {"unavailable": str(exc)[:120]}

    try:
        from memory.executions import list_executions
        total, _ = list_executions(1, 0)
        _, rows = list_executions(200, max(0, total - 200))
        by_kind: dict = {}
        for rec in rows:
            by_kind[rec["kind"]] = by_kind.get(rec["kind"], 0) + 1
        latest = list(reversed(rows[-5:]))
        state["orders"] = {
            "total": total, "by_kind": by_kind,
            "latest": [{"id": r["id"], "kind": r["kind"],
                        "sealed_at_block": r.get("ledger_index"),
                        "at": _when(r["ts"])} for r in latest],
        }
    except Exception as exc:
        state["orders"] = {"unavailable": str(exc)[:120]}

    try:
        from api.compute_fabric import hive_state
        hive = hive_state()
        state["hive"] = {
            "participants": len(hive["nodes"]),
            "participants_active": hive["nodes_active"],
            "work": hive["work"],
            "checkins": hive["checkins"]["total"],
            "peers": hive["sync"]["peers"],
        }
    except Exception as exc:
        state["hive"] = {"unavailable": str(exc)[:120]}

    try:
        from api.telemetry_ingest import ingest_status
        tel = ingest_status()
        state["telemetry"] = {
            "sources_total": tel["sources_total"],
            "sources_by_state": tel["sources_by_state"],
            "accepted_batches": tel["accepted_batches"],
            "accepted_events": tel["accepted_events"],
        }
    except Exception as exc:
        state["telemetry"] = {"unavailable": str(exc)[:120]}

    try:
        from api.os_family import family_status
        fam = family_status()["family"]
        state["os_family"] = {
            "passed": [k for k, v in fam.items()
                       if v.get("last_passed") is True],
            "failed": [k for k, v in fam.items()
                       if v.get("last_passed") is False],
            "unchecked": [k for k, v in fam.items()
                          if v.get("last_passed") is None],
            "total": len(fam),
        }
    except Exception as exc:
        state["os_family"] = {"unavailable": str(exc)[:120]}

    try:
        from api.networks import all_networks
        nets = all_networks()["networks"]
        state["networks"] = {
            key: {"live": val["bound_live"],
                  "total": val["declared_modules"]}
            for key, val in nets.items() if "error" not in val}
    except Exception as exc:
        state["networks"] = {"unavailable": str(exc)[:120]}

    try:
        from api.kernel_modules import kernel_module_status
        km = kernel_module_status()
        state["kernel_modules"] = {"live": km["total_live"],
                                    "total": km["total"]}
    except Exception as exc:
        state["kernel_modules"] = {"unavailable": str(exc)[:120]}

    try:
        from api.sentinel import sentinel_engine
        scan = sentinel_engine.scan()
        state["watch"] = {"state": scan["state"],
                          "threat_score": scan["threat_score"],
                          "alerts_active": scan["alerts_active"]}
    except Exception as exc:
        state["watch"] = {"unavailable": str(exc)[:120]}

    return state


def _declared_only(state: dict) -> int:
    total = 0
    nets = state.get("networks", {})
    if "unavailable" not in nets:
        total += sum(v["total"] - v["live"] for v in nets.values())
    km = state.get("kernel_modules", {})
    if "unavailable" not in km:
        total += km["total"] - km["live"]
    return total


def hud_briefing_text() -> str:
    """The panel as plain sentences, in reading order. No hashes,
    no codes, no tables — made to be heard."""
    s = hud_state()
    lines = ["Sovereign command panel.",
             f"Picture taken at {s['generated_at']}."]

    led = s.get("ledger", {})
    if "unavailable" in led:
        lines.append("The Golden Ledger could not be read just now.")
    else:
        lines.append(
            f"The Golden Ledger holds {led['height']} blocks and "
            f"the chain is {'valid' if led['chain_valid'] else 'NOT valid'}. "
            f"The newest block was sealed at {led['head_at']}.")

    orders = s.get("orders", {})
    if "unavailable" in orders:
        lines.append("The orders record could not be read just now.")
    elif orders["total"] == 0:
        lines.append("No orders or executions are on record yet.")
    else:
        kinds = ", ".join(f"{n} {k}" for k, n in
                          sorted(orders["by_kind"].items()))
        lines.append(
            f"There are {orders['total']} executions on record: {kinds}.")
        latest = orders["latest"][0]
        lines.append(
            f"The most recent is execution {latest['id']}, a "
            f"{latest['kind']}, sealed at block "
            f"{latest['sealed_at_block']}, at {latest['at']}.")

    hive = s.get("hive", {})
    if "unavailable" in hive:
        lines.append("The hive picture could not be read just now.")
    else:
        w = hive["work"]
        lines.append(
            f"The hive shows {hive['participants_active']} of "
            f"{hive['participants']} participants active, "
            f"{hive['checkins']} check-ins on record, and work "
            f"orders: {w['total']} total, {w['done']} done, "
            f"{w['pending']} pending, {w['rejected']} rejected.")

    tel = s.get("telemetry", {})
    if "unavailable" in tel:
        lines.append("The telemetry intake could not be read just now.")
    else:
        lines.append(
            f"Telemetry: {tel['sources_total']} sources registered "
            f"this session, {tel['accepted_batches']} batches and "
            f"{tel['accepted_events']} events accepted.")

    fam = s.get("os_family", {})
    if "unavailable" in fam:
        lines.append("The operating system family could not be "
                     "checked just now.")
    elif fam["failed"]:
        lines.append(
            f"Of the {fam['total']} operating systems, "
            f"{len(fam['passed'])} passed their duty checks and "
            f"{len(fam['failed'])} failed: "
            f"{', '.join(fam['failed'])}.")
    elif fam["unchecked"] and not fam["passed"]:
        lines.append(
            f"The {fam['total']} operating systems are dormant "
            f"since the last restart and their duty checks have "
            f"not run yet this session.")
    elif fam["unchecked"]:
        lines.append(
            f"Of the {fam['total']} operating systems, "
            f"{len(fam['passed'])} passed their duty checks; "
            f"{len(fam['unchecked'])} have not been re-checked "
            f"this session.")
    else:
        lines.append(
            f"All {fam['total']} operating systems passed their "
            f"duty checks.")

    nets = s.get("networks", {})
    if "unavailable" not in nets:
        parts = [f"{key}, {v['live']} of {v['total']} live"
                 for key, v in nets.items()]
        lines.append("Networks: " + "; ".join(parts) + ".")

    km = s.get("kernel_modules", {})
    if "unavailable" not in km:
        lines.append(
            f"Kernel modules: {km['live']} of {km['total']} live.")

    watch = s.get("watch", {})
    if "unavailable" not in watch:
        lines.append(
            f"The Sentinel watch reads {watch['state']}, threat "
            f"score {watch['threat_score']}, with "
            f"{watch['alerts_active']} active alerts.")

    declared = _declared_only(s)
    lines.append(
        f"Still open: {declared} declared components are not yet "
        f"bound to live behavior, the trained weights run waits on "
        f"compute, and true lattice cryptography waits on its "
        f"library. End of briefing.")
    return "\n".join(lines)


def hud_page() -> str:
    s = hud_state()
    briefing = hud_briefing_text().split("\n")
    items = "".join(f"<li>{line}</li>" for line in briefing[1:-1])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sovereign Command Panel — Jesse AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<style>
body {{ font-family: system-ui, sans-serif; background: #0b0e13;
color: #e8ecf1; margin: 2rem auto; max-width: 44rem; padding: 0 1rem;
line-height: 1.6; font-size: 1.125rem; }}
h1 {{ font-size: 1.6rem; }} li {{ margin: 0.6rem 0; }}
a {{ color: #8ab8ff; }}
</style>
</head>
<body>
<main>
<h1>Sovereign Command Panel</h1>
<p>{briefing[0]} {briefing[1]}</p>
<ul>
{items}
</ul>
<p>{briefing[-1]}</p>
<p><a href="/hud/briefing">Hear this panel as plain text</a> ·
<a href="/hud/state">Panel data as JSON</a></p>
</main>
</body>
</html>"""


@hud_router.get("")
def hud_home():
    return HTMLResponse(content=hud_page())


@hud_router.get("/briefing")
def hud_briefing():
    return PlainTextResponse(content=hud_briefing_text())


@hud_router.get("/state")
def hud_state_route():
    return JSONResponse(content=hud_state())
