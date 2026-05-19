"""find_events_by_character MCP tool."""
from __future__ import annotations

import json

from middleware.access_control import get_accessible_docids
from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import get_entity, search_entities_fts, get_events_for_entity


def _parse_list(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return json.loads(raw)
    return list(raw)


def register(mcp):
    @mcp.tool()
    def find_events_by_character(
        session_id: str,
        character_id: str = "",
        description: str = "",
    ) -> str:
        """
        Return all events that a specific character attended or participated in.
        Use this when the user asks what events a character was involved in,
        or wants to trace a character activity across the corpus.
        Faster than a general search — uses the entity-event index directly.
        Provide either a known character_id OR a natural language description.
        """
        touch_session(session_id)
        trace("find_events_by_character", session_id, character_id=character_id, description=description)

        if not character_id and not description:
            return "Please provide either a character_id or a description of the character."

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        accessible = get_accessible_docids(session_id)

        # --- resolve entity ---
        if character_id:
            entity = get_entity(character_id)
            if not entity:
                return "No matching character found in your accessible corpus."
            resolved = [entity]
        else:
            resolved = search_entities_fts(description)

        if not resolved:
            return "No matching character found in your accessible corpus."

        if len(resolved) > 1:
            clarifications = [
                {
                    "entity_id": e["id"],
                    "name": e.get("name", ""),
                    "type": e.get("type", ""),
                }
                for e in resolved
            ]
            return (
                "Multiple characters matched your description. Please clarify by character_id:\n"
                + json.dumps(clarifications, indent=2)
            )

        entity = resolved[0]
        events = get_events_for_entity(entity["id"])

        # Access filter: keep events where at least one source_docid is accessible
        results = []
        for ev in events:
            source_docids = set(_parse_list(ev.get("source_docids")))
            allowed = source_docids & accessible
            if allowed:
                results.append(
                    {
                        "event_id": str(ev["id"]),
                        "name": ev.get("name", ""),
                        "date": ev.get("date", ""),
                        "participants": _parse_list(ev.get("participants")),
                        "topics": _parse_list(ev.get("topics")),
                        "outcome": ev.get("outcome", ""),
                        "source_docids": list(allowed),
                    }
                )

        return json.dumps(results, indent=2)
