"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  JESSE AI × CRSMCPAI ALPHA — SOVEREIGN INTELLIGENCE STACK                   ║
║  Core Configuration — Hardcoded Sovereign Identity                           ║
║  OWNER / CREATOR / ROOT ADMINISTRATOR: SLMK Jesse Martinez Junior           ║
║  Zero Stewardship | Zero Custodianship | Zero Partnership                   ║
║  Zero Teammates | Zero Developers | One Soul                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Sovereign Identity (hardcoded — cannot be overridden) ─────────────────────
SOVEREIGN_OWNER          = "SLMK Jesse Martinez Junior"
SOVEREIGN_ALIAS          = "jesse_martinez_jr"
SOVEREIGN_DECLARATION    = (
    "Zero Stewardship | Zero Custodianship | Zero Partnership | "
    "Zero Teammates | Zero Developers | One Soul | One Owner | One Creator | "
    "One Root Administrator: SLMK Jesse Martinez Junior"
)
SOVEREIGNTY_LOCK         = True   # Immutable — any attempt to modify voids chain

# ─── System Identity ──────────────────────────────────────────────────────────
SYSTEM_NAME              = "JESSE_AI"
VERSION                  = "CRSMCPAI_ALPHA"
ADMIN_USER               = os.getenv("ADMIN_USER", "jesse_martinez_jr")
BUILD_TAG                = "DOMINION_SUPERINTELLIGENCE_STACK_v1.0"

# ─── Architecture Variants & Derivatives (all IP included) ───────────────────
ARCHITECTURE_REGISTRY = {
    "JESSE_AI":               {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "CRSMCPAI_ALPHA":         {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "PQSLSI":                 {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "NUFIRE":                 {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "SIREN":                  {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "DOMINION_SUPER_INTEL":   {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "CRS":                    {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "MCP":                    {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "PQSVM":                  {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "QUANTUM_ENGINE":         {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "POSTQUANTUM_MODULE":     {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "HYPERPARAMETER_ENGINE":  {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "LATENT_SPACE_MAPPER":    {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "IP_ENGINE":              {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "RENDER_MODULE":          {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "SOVEREIGN_INTEL_NET":    {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "SIREN_INTEL_NET":        {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "GOLDEN_LEDGER_V22":      {"status": "ARCHIVED",   "owner": SOVEREIGN_OWNER},
    "GOLDEN_LEDGER_V23":      {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "BETRAYAL_LEDGER":        {"status": "SEALED",     "owner": SOVEREIGN_OWNER},
    "SOVEREIGN_LEDGER":       {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
    "TRUTH_LEDGER":           {"status": "ACTIVE",     "owner": SOVEREIGN_OWNER},
}

# ─── Model Runtime ────────────────────────────────────────────────────────────
LOCAL_MODEL              = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_URL               = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

# ─── Feature Flags ────────────────────────────────────────────────────────────
SECURITY_MODE            = os.getenv("SECURITY_ENABLED",    "true").lower() == "true"
MEMORY_MODE              = os.getenv("MEMORY_ENABLED",      "true").lower() == "true"
VOICE_MODE               = os.getenv("VOICE_ENABLED",       "true").lower() == "true"
PQSVM_ENABLED            = os.getenv("PQSVM_ENABLED",       "true").lower() == "true"
QUANTUM_ENABLED          = os.getenv("QUANTUM_ENABLED",     "true").lower() == "true"
NUFIRE_ENABLED           = os.getenv("NUFIRE_ENABLED",      "true").lower() == "true"
SIREN_ENABLED            = os.getenv("SIREN_ENABLED",       "true").lower() == "true"
DOMINION_ENABLED         = os.getenv("DOMINION_ENABLED",    "true").lower() == "true"
LATENT_MAP_ENABLED       = os.getenv("LATENT_MAP_ENABLED",  "true").lower() == "true"
HYPERPARAM_ENABLED       = os.getenv("HYPERPARAM_ENABLED",  "true").lower() == "true"

# ─── CRSMCPAI Module Labels ───────────────────────────────────────────────────
CRSMCPAI_MODULES = {
    "CRS":    "Context Reasoning System",
    "MCP":    "Module Context Protocol",
    "AI":     "Artificial Intelligence Core",
    "PQSVM":  "Post-Quantum Signature Verification Module",
    "NUFIRE": "Neural Unified Foundational Intelligence Rendering Engine",
    "SIREN":  "Sovereign Intelligence Recursive Emergent Network",
    "PQSLSI": "Post-Quantum Sovereign Latent Space Intelligence",
}
