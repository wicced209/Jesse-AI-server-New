"""
Golden Ledger versions 23 through 27, rebuilt on the V28 pattern.
Owner: SLMK Jesse Martinez Junior
V28 remains the live primary (memory/ledger.py + golden_ledger.json).
These are versioned working ledgers.
"""
from .versioned import GoldenLedgerVersioned, LEDGERS, ledger_status

__all__ = ["GoldenLedgerVersioned", "LEDGERS", "ledger_status"]
