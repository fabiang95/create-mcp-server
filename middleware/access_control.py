"""Access control: group membership resolution and 403 enforcement."""
from __future__ import annotations

from middleware.session import get_user_id, get_cached_accessible_docids


class AccessDeniedError(Exception):
    """Raised when a user has no access to any document in a candidate set."""


def resolve_access(session_id: str, target_docids: list[str]) -> list[str]:
    """
    Given a session_id and a list of candidate docids,
    return only the docids the user can access.
    Raises AccessDeniedError if result is empty.
    """
    user_id = get_user_id(session_id)
    if not user_id:
        raise AccessDeniedError("Session is not identified. Please provide your username first.")

    accessible = get_accessible_docids(session_id)
    allowed = [d for d in target_docids if d in accessible]
    if not allowed:
        raise AccessDeniedError("No accessible documents for this query.")
    return allowed


def get_accessible_docids(session_id: str) -> set[str]:
    """Return the accessible docids for this session from the in-memory cache."""
    return get_cached_accessible_docids(session_id)
