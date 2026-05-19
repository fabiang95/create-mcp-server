"""list_events MCP tool."""
from __future__ import annotations

import json

from middleware.access_control import get_accessible_docids
from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import list_events_filtered


def _parse_docids(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return json.loads(raw)
    return list(raw)


def register(mcp):
    @mcp.tool()
    def list_events(
        session_id: str,
        universe: str = "",
        date_from: str = "",
        date_to: str = "",
        participant: str = "",
    ) -> str:
        """
        Return a list of events accessible to the user.
        Use this when the user wants to browse or discover what events exist in the corpus,
        or when they refer to an event by description and you need to find the event_id
        before calling query_event. Results can be filtered by universe, date range,
        or participant name.
        """
        touch_session(session_id)
        trace("list_events", session_id, universe=universe, date_from=date_from, date_to=date_to, participant=participant)

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        accessible = get_accessible_docids(session_id)

        rows = list_events_filtered(
            universe=universe or None,
            date_from=date_from or None,
            date_to=date_to or None,
            participant=participant or None,
        )

        # Post-retrieval access filter
        results = []
        for row in rows:
            source_docids = set(_parse_docids(row.get("source_docids")))
            if source_docids & accessible:
                results.append(
                    {
                        "event_id": str(row["id"]),
                        "name": row.get("name", ""),
                        "date": row.get("date", ""),
                        "location": row.get("location", ""),
                        "participants": _parse_docids(row.get("participants")),
                        "topics": _parse_docids(row.get("topics")),
                        "source_docids": list(source_docids & accessible),
                    }
                )

        return json.dumps(results, indent=2)
