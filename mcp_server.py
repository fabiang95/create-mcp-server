"""FastAPI + MCP entry point. Mount MCP at /mcp, register all tools."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

from prompt_loader import load_prompt
from middleware.session import (
    create_session,
    identify_session,
    get_session,
    is_first_session_today,
    get_user_id,
)
from middleware.access_control import get_accessible_docids
from middleware.tracing import trace
from db.connection import init_db
from db.queries import get_user_by_username, get_valid_interests, get_all_interests, get_accessible_docids

import tools.query_event as _query_event
import tools.query_character as _query_character
import tools.search as _search
import tools.list_events as _list_events
import tools.list_characters as _list_characters
import tools.find_events_by_character as _find_events_by_char
import tools.set_interest as _set_interest
import tools.get_interests as _get_interests
import tools.query_relationship as _query_relationship
import tools.get_interaction_timeline as _get_interaction_timeline

# Ensure optional tables exist before accepting any requests
init_db()

mcp = FastMCP("create-mcp")

# Register all tools
_query_event.register(mcp)
_query_character.register(mcp)
_search.register(mcp)
_list_events.register(mcp)
_list_characters.register(mcp)
_find_events_by_char.register(mcp)
_set_interest.register(mcp)
_get_interests.register(mcp)
_query_relationship.register(mcp)
_get_interaction_timeline.register(mcp)


# --- Session management tools ---

@mcp.tool()
def start_session() -> dict:
    """
    Begin a new MCP session. Call this once when connecting.
    Returns a session_id and a greeting prompt asking the user to identify themselves.
    """
    session_id, greeting = create_session()
    trace("start_session", session_id)
    return {"session_id": session_id, "message": greeting}


@mcp.tool()
def identify(session_id: str, username: str) -> dict:
    """
    Bind a username to an existing session.
    The username must exist in the user_access table.
    Returns the session opening context (system prompt prefix) once identified.
    """
    user = get_user_by_username(username)
    if not user:
        trace("identify", session_id, username=username, result="not_found")
        return {
            "status": "error",
            "action_required": "re_identify",
            "message": (
                f"Username '{username}' was not found in the system. "
                "The user could not be authenticated. "
                "Please ask the user to provide a valid username and call identify() again."
            ),
        }

    accessible_docids = get_accessible_docids(user["user_id"])
    identify_session(session_id, user["user_id"], username, user["role"], accessible_docids)
    trace("identify", session_id, username=username, role=user["role"], result="ok")
    session = get_session(session_id)
    first_today = is_first_session_today(session_id)

    user_id = user["user_id"]
    all_interests = get_all_interests(user_id)
    valid_interests = all_interests["valid"]

    response: dict = {
        "status": "identified",
        "session_id": session_id,
        "username": username,
        "role": user["role"],
    }

    if first_today and not valid_interests:
        # Prompt user to set interests
        response["message"] = load_prompt("interest_collection")
        response["action_required"] = "set_interests"
    elif first_today and valid_interests:
        # Show existing interests and ask if they want to update
        interest_summary = ", ".join(i["interest_text"] for i in valid_interests)
        response["message"] = (
            f"Welcome back. Your current research interests are: {interest_summary}. "
            "Would you like to update them? (yes/no)"
        )
        response["action_required"] = "confirm_interests"
    else:
        # Subsequent session today — load silently
        interests_str = _format_interests(valid_interests)
        opening = load_prompt(
            "opening_context",
            interests=interests_str,
            username=username,
            role=user["role"],
        )
        response["message"] = opening
        response["action_required"] = None

    return response


@mcp.tool()
def get_opening_context(session_id: str) -> str:
    """
    Return the full system prompt prefix for this session once the user is identified
    and interests are confirmed. Call this after identify() completes successfully.
    """
    trace("get_opening_context", session_id)
    session = get_session(session_id)
    if not session or not session.get("identified"):
        return "Session not identified. Call identify() first."

    user_id = get_user_id(session_id)
    valid_interests = get_valid_interests(user_id)
    interests_str = _format_interests(valid_interests)

    return load_prompt(
        "opening_context",
        interests=interests_str,
        username=session["username"],
        role=session["role"],
    )


def _format_interests(interests: list[dict]) -> str:
    if not interests:
        return "(none set)"
    return "\n".join(f"- {i['interest_text']}" for i in interests)


if __name__ == "__main__":
    import sys
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    mcp.run()
else:
    app = mcp.streamable_http_app()
