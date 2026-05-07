"""search MCP tool — general two-pass search across the corpus."""
from __future__ import annotations

import json

from middleware.access_control import AccessDeniedError, get_accessible_docids
from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import search_summaries_fts
from rag.pipeline import run_rag_pipeline
from rag.rerank import boost_by_interests

_TOP_N_SUMMARIES = 10


def register(mcp):
    @mcp.tool()
    def search(
        session_id: str,
        query: str,
        universe: str = "",
        themes: list[str] | None = None,
    ) -> str:
        """
        General search across the accessible report corpus.
        Use this for broad questions not tied to a specific named event or character —
        for example thematic questions, questions spanning multiple documents,
        or when the user is exploring a topic without knowing specific entity names.
        Searches document summaries first for relevance, then retrieves specific passages.
        Supports optional universe and theme filters.
        """
        touch_session(session_id)
        trace("search", session_id, query=query, universe=universe, themes=themes)

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        accessible = get_accessible_docids(session_id)
        if not accessible:
            return "You do not have access to any documents in this corpus."

        # Pass 1 — coarse filter via FTS on summaries
        candidate_rows = search_summaries_fts(
            query,
            accessible,
            universe=universe or None,
            themes=themes or [],
            top_n=_TOP_N_SUMMARIES,
        )
        candidate_docids = [r["systemdocid"] for r in candidate_rows]

        # Apply interest boost re-ranking across the candidates
        candidate_docids = boost_by_interests(candidate_docids, user_id)

        # Pass 2 (and steps 2-6) — handled inside run_rag_pipeline
        try:
            result = run_rag_pipeline(query, candidate_docids, session_id)
        except AccessDeniedError:
            return "You do not have access to documents relevant to this query."

        return json.dumps(result, indent=2)
