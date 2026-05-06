"""query_character MCP tool."""
from __future__ import annotations

import json

from middleware.access_control import AccessDeniedError
from middleware.session import touch_session
from middleware.tracing import trace
from db.queries import get_entity, search_entities_fts
from rag.pipeline import run_rag_pipeline


def register(mcp):
    @mcp.tool()
    def query_character(
        session_id: str,
        question: str,
        character_id: str = "",
        description: str = "",
    ) -> str:
        """
        Answer a question about a specific character, person, or entity in the research corpus —
        their role, behaviour, relationships, or appearances across reports.
        Provide either a known character_id OR a natural language description
        (e.g. "the bear who likes honey", "the detective at Baker Street").
        If the description matches multiple entities, the tool will return a clarification list.
        Use list_characters to browse all available characters.
        """
        touch_session(session_id)
        trace("query_character", session_id, character_id=character_id, description=description, question=question)

        if not character_id and not description:
            return "Please provide either a character_id or a description of the character."

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
                    "entity_id": e["entity_id"],
                    "name": e.get("name", ""),
                    "type": e.get("type", ""),
                    "universe": e.get("universe", ""),
                }
                for e in resolved
            ]
            return (
                "Multiple characters matched your description. Please clarify by character_id:\n"
                + json.dumps(clarifications, indent=2)
            )

        entity = resolved[0]
        raw_docids = entity.get("docids") or "[]"
        if isinstance(raw_docids, str):
            candidate_docids = json.loads(raw_docids)
        else:
            candidate_docids = list(raw_docids)

        try:
            result = run_rag_pipeline(question, candidate_docids, session_id)
        except AccessDeniedError:
            return "You do not have access to documents relevant to this query."

        return json.dumps(result, indent=2)
