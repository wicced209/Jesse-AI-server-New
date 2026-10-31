from core.logger import log_event

# The ONLY authorized user is the sovereign owner, Jesse Martinez
# Junior. There is no generic, fallback, or secondary identity.
#
# Cut on 2026-10-31 at Jesse's direct order ("make sure I'm the only
# one; everything else blacklisted and fully cut out"): this set
# previously also accepted the literal username "admin", and the
# admin routes defaulted their identity header to "admin", which
# together left the admin read surface open to any caller who knew
# the address. Both are removed. The dynamic add/remove user
# functions are removed as well — nothing called them, and no
# mechanism to grant access should exist outside a deliberate code
# change by the owner.
AUTHORIZED_USERS: set[str] = {
    "jesse_martinez_jr",
}


def authenticate(user: str) -> bool:
    """Return True only for the sovereign owner."""
    result = user in AUTHORIZED_USERS
    log_event(f"[AUTH] User '{user}' → {'GRANTED' if result else 'DENIED'}")
    return result
