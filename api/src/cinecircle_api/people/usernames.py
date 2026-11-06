"""Username rules (the database CHECK is the last line of defence; this gives clean errors)."""

import re

USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,30}$")
RESERVED = frozenset({"me", "search"})  # would collide with /me and /users/search


def normalize_username(raw: str) -> str:
    """Strip and lower-case; raise ValueError("reserved") or ValueError("invalid")."""
    username = raw.strip().lower()
    if username in RESERVED:
        raise ValueError("reserved")
    # fullmatch: `$` alone would also accept a trailing newline.
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("invalid")
    return username
