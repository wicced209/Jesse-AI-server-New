"""
NUFIRE + Tara Infinity family registry — all thirty modules.
Owner: SLMK Jesse Martinez Junior
Names are the exact thirty from the one-hundred-sixteen module record,
items 076-105, in record order (corrected by Muse 2026-11-06).
"""
from . import modules as m

NUFIRE_FAMILY = {
    "nufire_ignition_core": m.NufireIgnitionCore(),
    "nufire_plasma_router": m.NufirePlasmaRouter(),
    "nufire_entropy_reducer": m.NufireEntropyReducer(),
    "nufire_core_manifest": m.NufireCoreManifest(),
    "nufire_sovereign_gate": m.NufireSovereignGate(),
    "nufire_quantum_bridge": m.NufireQuantumBridge(),
    "nufire_memory_lattice": m.NufireMemoryLattice(),
    "nufire_execution_engine": m.NufireExecutionEngine(),
    "nufire_feedback_loop": m.NufireFeedbackLoop(),
    "nufire_master_clock": m.NufireMasterClock(),
    "tara_infinity_geometry": m.TaraInfinityGeometry(),
    "tara_infinity_resonance": m.TaraInfinityResonance(),
    "tara_infinity_mirror": m.TaraInfinityMirror(),
    "tara_infinity_nexus": m.TaraInfinityNexus(),
    "tara_infinity_prism": m.TaraInfinityPrism(),
    "living_code_synthesizer": m.LivingCodeSynthesizer(),
    "living_code_compiler": m.LivingCodeCompiler(),
    "living_code_validator": m.LivingCodeValidator(),
    "living_code_immunizer": m.LivingCodeImmunizer(),
    "living_code_evolution": m.LivingCodeEvolution(),
    "quantum_consciousness_core": m.QuantumConsciousnessCore(),
    "quantum_consciousness_state": m.QuantumConsciousnessState(),
    "quantum_consciousness_observer": m.QuantumConsciousnessObserver(),
    "quantum_consciousness_resonance": m.QuantumConsciousnessResonance(),
    "quantum_consciousness_nexus": m.QuantumConsciousnessNexus(),
    "sovereign_logic_gate_alpha": m.SovereignLogicGateAlpha(),
    "sovereign_logic_gate_beta": m.SovereignLogicGateBeta(),
    "sovereign_logic_gate_gamma": m.SovereignLogicGateGamma(),
    "sovereign_logic_gate_delta": m.SovereignLogicGateDelta(),
    "sovereign_logic_gate_omega": m.SovereignLogicGateOmega(),
}


def get_module(name: str):
    return NUFIRE_FAMILY.get(name)


def family_status() -> dict:
    return {
        "family": "NUFIRE_TARA_INFINITY",
        "owner": "SLMK Jesse Martinez Junior",
        "count": len(NUFIRE_FAMILY),
        "expected_named": 30,
        "modules": {k: v.status() for k, v in NUFIRE_FAMILY.items()},
        "status": "LIVE",
    }
