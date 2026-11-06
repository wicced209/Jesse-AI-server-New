"""
Five named version-one modules with no prior artifact.
Owner: SLMK Jesse Martinez Junior
"""
from .intent_classifier import IntentClassifier
from .memory_compressor import MemoryCompressor
from .telemetry_streamer import TelemetryStreamer
from .self_healing import SelfHealingRecovery
from .control_plane import ControlPlane

V1_MODULES = {
    "intent_classifier": IntentClassifier(),
    "memory_compressor": MemoryCompressor(),
    "telemetry_streamer": TelemetryStreamer(),
    "self_healing_error_recovery": SelfHealingRecovery(),
    "control_plane": ControlPlane(),
}

def v1_status():
    return {
        "family": "V1_MODULES",
        "owner": "SLMK Jesse Martinez Junior",
        "modules": {k: v.status() for k, v in V1_MODULES.items()},
        "status": "LIVE",
    }
