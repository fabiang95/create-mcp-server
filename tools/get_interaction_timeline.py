"""get_interaction_timeline MCP tool."""
from __future__ import annotations

import json

from middleware.access_control import get_accessible_docids
from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import get_entity, search_entities_fts, get_interactions


def _resolve_entity(
    entity_id: str,
    description: str,
) -> tuple[dict | None, list[dict] | None]:
    """
    Returns (entity, None)         — one clear match
    Returns (None, clarify_list)   — multiple matches
    Returns (None, None)           — not found
    """
    if entity_id:
        entity = get_entity(entity_id)
        return (entity, None) if entity else (None, None)
    resolved = search_entities_fts(description)
    if not resolved:
        return None, None
    if len(resolved) == 1:
        return resolved[0], None
    return None, [
        {
            "entity_id": e["entity_id"],
            "name": e.get("name", ""),
            "type": e.get("type", ""),
            "universe": e.get("universe", ""),
        }
        for e in resolved
    ]


def register(mcp):
    @mcp.tool()
    def get_interaction_timeline(
        session_id: str,
        entity_a: str = "",
        desc_a: str = "",
        entity_b: str = "",
        desc_b: str = "",
    ) -> str:
        """
        Return the full chronological interaction history between two characters.
        Shows how their relationship evolved over time with dates, interaction types,
        sentiment scores, and source documents.
        Use when the user wants to trace a relationship arc or identify turning points.
        """
        touch_session(session_id)
        trace("get_interaction_timeline", session_id, entity_a=entity_a, entity_b=entity_b)

        if not (entity_a or desc_a):
            return "Please provide an entity_id or description for the first character."
        if not (entity_b or desc_b):
            return "Please provide an entity_id or description for the second character."

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        accessible = get_accessible_docids(user_id)

        # Resolve entity A
        a, a_clarify = _resolve_entity(entity_a, desc_a)
        if a_clarify:
            return (
                "Multiple characters matched the first description. Please clarify by entity_id:\n"
                + json.dumps(a_clarify, indent=2)
            )
        if not a:
            return "No matching character found for the first entity in your accessible corpus."

        # Resolve entity B
        b, b_clarify = _resolve_entity(entity_b, desc_b)
        if b_clarify:
            return (
                "Multiple characters matched the second description. Please clarify by entity_id:\n"
                + json.dumps(b_clarify, indent=2)
            )
        if not b:
            return "No matching character found for the second entity in your accessible corpus."

        interactions = get_interactions(a["entity_id"], b["entity_id"], accessible)

        results = [
            {
                "interaction_id": i.get("interaction_id"),
                "date": i.get("date"),
                "type": i.get("type"),
                "description": i.get("description"),
                "sentiment": i.get("sentiment"),
                "source_docid": i.get("source_docid"),
                "source_event_id": i.get("source_event_id"),
            }
            for i in interactions
        ]

        return json.dumps(results, indent=2)
