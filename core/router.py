"""Core command router — directs commands to appropriate agents."""
from core.logger import log_event
from agents.planner_agent import planner_agent
from agents.guardian_agent import guardian_agent
from agents.memory_agent import memory_agent
from agents.builder_agent import builder_agent
from dominion.stack import dominion


def route_command(command: str, user: str = "jesse_martinez_jr") -> dict:
    """Route command through CRSMCPAI Alpha stack."""
    log_event(f"[ROUTER] Routing: {command[:80]}")
    cmd = command.lower()

    if any(x in cmd for x in ["verify", "authenticate", "handshake", "guardian"]):
        return guardian_agent(command, user)
    elif any(x in cmd for x in ["plan", "steps", "breakdown", "planner"]):
        return planner_agent(command)
    elif any(x in cmd for x in ["remember", "store", "memory", "recall"]):
        return memory_agent(command)
    elif any(x in cmd for x in ["build", "create", "generate", "builder"]):
        return builder_agent(command)
    else:
        return dominion.process(command, user)
