"""query_event MCP tool."""
from __future__ import annotations

import json

from middleware.access_control import AccessDeniedError
from middleware.session import touch_session
from middleware.tracing import trace
from db.queries import get_event, search_events_fts
from rag.pipeline import run_rag_pipeline


def register(mcp):
    @mcp.tool()
    def query_event(
        session_id: str,
        question: str,
        event_id: str = "",
        description: str = "",
    ) -> str:
        """
        Answer a question about a specific event in the research corpus —
        what happened, who attended, what was discussed, and what the outcome was.
        Provide either a known event_id OR a natural language description of the event
        (e.g. "the economics conference in Tel Aviv", "the incident at the sandy pit").
        If the description matches multiple events, the tool will return a clarification
        list for the user to choose from. Use list_events to browse all available events.
        """
        touch_session(session_id)
        trace("query_event", session_id, event_id=event_id, description=description, question=question)

        if not event_id and not description:
            return "Please provide either an event_id or a description of the event."

        # --- resolve event ---
        if event_id:
            event = get_event(event_id)
            if not event:
                return "No matching event found in your accessible corpus."
            resolved = [event]
        else:
            resolved = search_events_fts(description)

        if not resolved:
            return "No matching event found in your accessible corpus."

        if len(resolved) > 1:
            clarifications = [
                {
                    "event_id": e["event_id"],
                    "name": e.get("name", ""),
                    "date": e.get("date", ""),
                    "location": e.get("location", ""),
                }
                for e in resolved
            ]
            return (
                "Multiple events matched your description. Please clarify by event_id:\n"
                + json.dumps(clarifications, indent=2)
            )

        event = resolved[0]
        raw_docids = event.get("source_docids") or "[]"
        if isinstance(raw_docids, str):
            candidate_docids = json.loads(raw_docids)
        else:
            candidate_docids = list(raw_docids)

        try:
            result = run_rag_pipeline(question, candidate_docids, session_id)
        except AccessDeniedError:
            return "You do not have access to documents relevant to this query."

        return json.dumps(result, indent=2)
