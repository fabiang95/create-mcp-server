"""set_interest MCP tool."""
from __future__ import annotations

import json

from middleware.access_control import get_accessible_docids
from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import insert_interest, get_all_interests, match_interest_against_summaries
from config import DEFAULT_STALENESS_TYPE, DEFAULT_STALENESS_THRESHOLD
from prompt_loader import load_prompt


def register(mcp):
    @mcp.tool()
    def set_interest(
        session_id: str,
        interest_text: str,
        staleness_type: str = DEFAULT_STALENESS_TYPE,
        staleness_threshold: int = DEFAULT_STALENESS_THRESHOLD,
    ) -> str:
        """
        Save a research interest for the current user.
        Interests act as re-ranking signals — documents matching the interest are surfaced
        higher in all subsequent queries. Use this when the user expresses a topic they
        want to focus on or follow. Interests persist across sessions.
        """
        touch_session(session_id)
        trace("set_interest", session_id, interest_text=interest_text, staleness_type=staleness_type)

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        accessible = get_accessible_docids(user_id)

        # Validate: does any accessible doc match this interest?
        valid = match_interest_against_summaries(interest_text, accessible)

        insert_interest(
            user_id=user_id,
            interest_text=interest_text,
            staleness_type=staleness_type,
            staleness_threshold=staleness_threshold,
            valid=1 if valid else 0,
        )

        all_interests = get_all_interests(user_id)
        return json.dumps(
            {
                "status": "saved",
                "interest_text": interest_text,
                "valid": valid,
                "current_interests": all_interests,
            },
            indent=2,
        )
