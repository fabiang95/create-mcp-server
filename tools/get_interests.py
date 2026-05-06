"""get_interests MCP tool."""
from __future__ import annotations

import json

from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import get_all_interests


def register(mcp):
    @mcp.tool()
    def get_interests(session_id: str) -> str:
        """
        Return the current user saved research interests,
        split into valid (currently matching accessible documents)
        and stale (no longer matching). Use this when the user asks
        what interests they have saved or wants to review them before updating.
        """
        touch_session(session_id)
        trace("get_interests", session_id)

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        interests = get_all_interests(user_id)
        return json.dumps(interests, indent=2)
