import os
from core.logger import log_event

# Primary authorized users — extend as needed
AUTHORIZED_USERS: set[str] = {
    "admin",
    os.getenv("ADMIN_USER", "jesse_martinez_jr"),
}


def authenticate(user: str) -> bool:
    """Return True if the user is in the authorized set."""
    result = user in AUTHORIZED_USERS
    log_event(f"[AUTH] User '{user}' → {'GRANTED' if result else 'DENIED'}")
    return result


def add_user(user: str):
    """Dynamically add an authorized user."""
    AUTHORIZED_USERS.add(user)
    log_event(f"[AUTH] Added user: {user}")


def remove_user(user: str):
    """Remove an authorized user."""
    AUTHORIZED_USERS.discard(user)
    log_event(f"[AUTH] Removed user: {user}")
