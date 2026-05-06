"""In-memory session store. Pod restart clears all sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from prompt_loader import load_prompt

SESSION_STORE: dict[str, dict] = {}
# Key: session_id (str)
# Value: {
#   user_id: str | None,
#   username: str | None,
#   role: str | None,
#   created_at: datetime | None,
#   last_active: datetime,
#   identified: bool
# }


def create_session() -> tuple[str, str]:
    """Create a new unidentified session. Returns (session_id, greeting_prompt)."""
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        "user_id": None,
        "username": None,
        "role": None,
        "created_at": None,
        "last_active": datetime.now(timezone.utc),
        "identified": False,
    }
    return session_id, load_prompt("session_identity")


def identify_session(session_id: str, user_id: str, username: str, role: str) -> None:
    """Bind a validated username to the session."""
    now = datetime.now(timezone.utc)
    SESSION_STORE[session_id].update(
        {
            "user_id": user_id,
            "username": username,
            "role": role,
            "created_at": now,
            "last_active": now,
            "identified": True,
        }
    )


def touch_session(session_id: str) -> None:
    if session_id in SESSION_STORE:
        SESSION_STORE[session_id]["last_active"] = datetime.now(timezone.utc)


def get_session(session_id: str) -> dict | None:
    return SESSION_STORE.get(session_id)


def get_user_id(session_id: str) -> str | None:
    session = SESSION_STORE.get(session_id)
    return session["user_id"] if session else None


def is_first_session_today(session_id: str) -> bool:
    """True if no other identified session for this user was created today (UTC)."""
    current = SESSION_STORE.get(session_id)
    if not current or not current["user_id"]:
        return True
    today = datetime.now(timezone.utc).date()
    user_id = current["user_id"]
    for sid, s in SESSION_STORE.items():
        if sid == session_id:
            continue
        if s.get("user_id") == user_id and s.get("created_at"):
            if s["created_at"].date() == today:
                return False
    return True
