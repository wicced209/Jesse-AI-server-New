"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  JESSE AI × CRSMCPAI ALPHA — DOMINION SUPERINTELLIGENCE STACK               ║
║  Main Entry Point                                                            ║
║  OWNER: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from core.config   import SYSTEM_NAME, VERSION, SOVEREIGN_OWNER, SOVEREIGN_DECLARATION
from core.logger   import log_event
from dominion.stack import dominion


BANNER = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   ██ ███████ ███████ ███████ ███████      █████  ██                         ║
║   ██ ██      ██      ██      ██          ██   ██ ██                         ║
║   ██ █████   ███████ ███████ █████       ███████ ██                         ║
║██ ██ ██          ██      ██ ██          ██   ██ ██                         ║
║ ████  ███████ ███████ ███████ ███████      ██   ██ ██                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  System  : {SYSTEM_NAME:<65}║
║  Version : {VERSION:<65}║
║  Owner   : {SOVEREIGN_OWNER:<65}║
╠══════════════════════════════════════════════════════════════════════════════╣
║  {SOVEREIGN_DECLARATION[:76]:<76}║
╚══════════════════════════════════════════════════════════════════════════════╝

Modules Online: CRSMCPAI | PQSVM | PQSLSI | NUFIRE | SIREN | DOMINION
                HYPERPARAMETER ENGINE | LATENT SPACE MAPPER | QUANTUM AUDIT
                SOVEREIGN LEDGER | TRUTH LEDGER | BETRAYAL LEDGER | GOLDEN LEDGER V22/V23

Type 'status'  — full stack status
Type 'audit'   — run quantum audit of all IP/engines/modules
Type 'exit'    — shutdown
"""


def main():
    print(BANNER)
    log_event(f"[BOOT] {SYSTEM_NAME} {VERSION} — Dominion Stack live")

    while True:
        try:
            user_input = input("\nJesse Dominion >> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Dominion] Shutting down. Sovereign.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            log_event("[SHUTDOWN] Sovereign shutdown")
            print("[Dominion] Shutting down. Sovereign.")
            break

        if user_input.lower() == "status":
            import json
            print(json.dumps(dominion.full_status(), indent=2))
            continue

        if user_input.lower() == "audit":
            import json
            print(json.dumps(dominion.quantum_audit(), indent=2))
            continue

        result = dominion.process(user_input)
        import json
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
