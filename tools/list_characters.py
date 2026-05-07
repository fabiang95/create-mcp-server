"""list_characters MCP tool."""
from __future__ import annotations

import json

from middleware.access_control import get_accessible_docids
from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import list_entities_filtered


def _parse_list(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return json.loads(raw)
    return list(raw)


def register(mcp):
    @mcp.tool()
    def list_characters(
        session_id: str,
        universe: str = "",
        type: str = "",
    ) -> str:
        """
        Return a list of characters, locations, and organisations accessible to the user.
        Use this when the user wants to know what entities exist in the corpus,
        or when you need a character_id before calling query_character or
        find_events_by_character.
        """
        touch_session(session_id)
        trace("list_characters", session_id, universe=universe, type=type)

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        accessible = get_accessible_docids(session_id)

        rows = list_entities_filtered(
            universe=universe or None,
            entity_type=type or None,
        )

        # Post-retrieval access filter
        results = []
        for row in rows:
            docids = set(_parse_list(row.get("docids")))
            if docids & accessible:
                results.append(
                    {
                        "entity_id": row["entity_id"],
                        "name": row.get("name", ""),
                        "aliases": _parse_list(row.get("aliases")),
                        "type": row.get("type", ""),
                        "universe": row.get("universe", ""),
                        "docids": list(docids & accessible),
                    }
                )

        return json.dumps(results, indent=2)
