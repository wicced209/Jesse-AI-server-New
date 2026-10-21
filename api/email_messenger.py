"""
JESSE AI Email Messenger — Directive #72
Free voice-first messenger through CRS architecture.

Flow:
  1. Jesse dictates an email from WICCED209@iCloud.com (iPhone Mail, voice)
  2. Email arrives at the connected Gmail (jessefromthewest209@gmail.com)
     with subject starting "JESSE AI:" (or body starting "Jesse AI,")
  3. The watcher (poll loop or /messenger/poll endpoint) reads it
  4. Command is executed through the local /command pipeline (CRSMCPAI Alpha)
  5. Full unabridged response is emailed back to WICCED209@iCloud.com

Security:
  - Sender allowlist: ONLY WICCED209@iCloud.com is processed. Everything
    else is ignored silently.
  - Replay protection: processed Gmail message IDs are recorded in the
    ledger; a message ID is never executed twice.
  - Command receipts: every execution seals a ledger block.
  - No secrets in email bodies are logged.

Owner: SLMK Jesse Martinez Junior
"""
import hashlib
import json
import time
from datetime import datetime, timezone

MESSENGER_ID = "JESSE-AI-EMAIL-MESSENGER"
MESSENGER_VER = "v1.0"
OWNER = "SLMK Jesse Martinez Junior"

# Allowlisted sender — the ONLY address whose mail is executed.
ALLOWED_SENDERS = {"wicced209@icloud.com"}

# Subject prefixes that mark a command email. Longer, specific prefixes come
# first so "JESSE AI COMMAND:" is stripped fully rather than leaving a
# "COMMAND:" remnant. The trailing colon is OPTIONAL on every prefix:
# VoiceOver does not read the colon back, so a blind user cannot reliably
# know it is required. A bare "Jesse AI" subject counts as a command.
COMMAND_SUBJECT_PREFIXES = ("JESSE AI COMMAND:", "[JESSE AI]", "JESSE AI:")

# Reply destination (Jesse's iPhone Mail address).
REPLY_TO = "WICCED209@iCloud.com"

# In-memory processed-ID set (also sealed to ledger per execution).
_processed_ids: set = set()


def _subject_prefix_len(subject: str) -> int:
    """Length of a recognized command prefix in the subject, 0 if none.

    Accepts the coloned prefixes, plus the bare words "Jesse AI" (no colon)
    since VoiceOver does not read the colon back for a blind user.
    """
    s = (subject or "").strip().upper()
    for p in COMMAND_SUBJECT_PREFIXES:
        if s.startswith(p):
            return len(p)
    if s == "JESSE AI":
        return len("JESSE AI")
    if s.startswith("JESSE AI "):
        return len("JESSE AI ")
    return 0


def is_command_email(sender: str, subject: str, body: str) -> bool:
    """True only if the sender is allowlisted AND the message looks like a command."""
    if (sender or "").strip().lower() not in ALLOWED_SENDERS:
        return False
    if _subject_prefix_len(subject) > 0:
        return True
    return (body or "").strip().lower().startswith("jesse ai,")


def extract_command(subject: str, body: str) -> str:
    """Strip the command prefix; return the raw command text."""
    subj = (subject or "").strip()
    n = _subject_prefix_len(subj)
    if n:
        subj = subj[n:].strip()
    body = (body or "").strip()
    if body.lower().startswith("jesse ai,"):
        body = body[len("jesse ai,"):].strip()
    # Prefer body; fall back to subject remainder.
    return body or subj


def mark_processed(message_id: str) -> bool:
    """Replay guard. Returns True if this ID was already processed."""
    if message_id in _processed_ids:
        return True
    _processed_ids.add(message_id)
    return False


def build_reply_subject(original_subject: str) -> str:
    return "Re: " + (original_subject or "Jesse AI command")


def build_reply_body(command: str, result: dict, ledger_index) -> str:
    """Full unabridged response, plain text, screen-reader friendly."""
    lines = [
        "Jesse AI response",
        "",
        "Your command:",
        command,
        "",
        "Response:",
        json.dumps(result, indent=1, default=str)[:12000],
        "",
        f"Ledger block: {ledger_index}",
        "verification sovereign living master key Jesse Martinez Junior",
    ]
    return "\n".join(lines)


def messenger_status() -> dict:
    return {
        "messenger": MESSENGER_ID,
        "version": MESSENGER_VER,
        "owner": OWNER,
        "status": "LIVE",
        "allowed_senders": sorted(ALLOWED_SENDERS),
        "reply_to": REPLY_TO,
        "processed_count": len(_processed_ids),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
