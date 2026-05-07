"""In-memory session store. Pod restart clears all sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from prompt_loader import load_prompt

SESSION_STORE: dict[str, dict] = {}
# Key: session_id (str)
# Value: {
#   user_id: str | None,
#   username: str | None,
#   role: str | None,
#   accessible_docids: set[str],   ← cached at identify time, re-loaded on re-identify
#   created_at: datetime | None,
#   last_active: datetime,
#   identified: bool
# }

SESSION_TTL = timedelta(hours=8)  # session expires after 8 hours of inactivity


def _is_expired(session: dict) -> bool:
    return datetime.now(timezone.utc) - session["last_active"] > SESSION_TTL


def create_session() -> tuple[str, str]:
    """Create a new unidentified session. Returns (session_id, greeting_prompt)."""
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        "user_id": None,
        "username": None,
        "role": None,
        "accessible_docids": set(),
        "created_at": None,
        "last_active": datetime.now(timezone.utc),
        "identified": False,
    }
    return session_id, load_prompt("session_identity")


def identify_session(
    session_id: str,
    user_id: str,
    username: str,
    role: str,
    accessible_docids: set[str],
) -> None:
    """Bind a validated username to the session and cache their accessible docids."""
    now = datetime.now(timezone.utc)
    SESSION_STORE[session_id].update(
        {
            "user_id": user_id,
            "username": username,
            "role": role,
            "accessible_docids": accessible_docids,
            "created_at": now,
            "last_active": now,
            "identified": True,
        }
    )


def touch_session(session_id: str) -> None:
    if session_id in SESSION_STORE:
        SESSION_STORE[session_id]["last_active"] = datetime.now(timezone.utc)


def get_session(session_id: str) -> dict | None:
    """Return the session if it exists and has not expired, otherwise None."""
    session = SESSION_STORE.get(session_id)
    if session is None:
        return None
    if _is_expired(session):
        del SESSION_STORE[session_id]
        return None
    return session


def get_user_id(session_id: str) -> str | None:
    session = get_session(session_id)
    return session["user_id"] if session else None


def get_cached_accessible_docids(session_id: str) -> set[str]:
    """Return the accessible docids cached at identify time. No DB call."""
    session = get_session(session_id)
    return session["accessible_docids"] if session else set()


def is_first_session_today(session_id: str) -> bool:
    """True if no other identified session for this user was created today (UTC)."""
    current = get_session(session_id)
    if not current or not current["user_id"]:
        return True
    today = datetime.now(timezone.utc).date()
    user_id = current["user_id"]
    for sid, s in list(SESSION_STORE.items()):
        if sid == session_id:
            continue
        if _is_expired(s):
            del SESSION_STORE[sid]
            continue
        if s.get("user_id") == user_id and s.get("created_at"):
            if s["created_at"].date() == today:
                return False
    return True
