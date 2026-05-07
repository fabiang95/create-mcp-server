"""query_relationship MCP tool."""
from __future__ import annotations

import json

import httpx

from config import OLLAMA_URL, CHAT_MODEL, CHAT_MAX_TOKENS
from middleware.access_control import get_accessible_docids
from middleware.session import touch_session, get_user_id
from middleware.tracing import trace
from db.queries import get_entity, search_entities_fts, get_summary
from rag.relationships import derive_relationship
from rag.retrieval import build_file_path


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


def _parse_docids(raw) -> set[str]:
    if not raw:
        return set()
    if isinstance(raw, str):
        return set(json.loads(raw))
    return set(raw)


def _build_sources(timeline: list[dict]) -> list[dict]:
    seen: set[str] = set()
    sources: list[dict] = []
    for item in timeline:
        docid = item.get("source_docid")
        if docid and docid not in seen:
            seen.add(docid)
            summary = get_summary(docid) or {}
            sources.append(
                {
                    "systemdocid": docid,
                    "title": summary.get("title", docid),
                    "file_path": build_file_path(docid),
                }
            )
    return sources


def _compose_answer(
    question: str,
    entity_a: dict,
    entity_b: dict,
    derived: dict,
) -> str:
    name_a = entity_a.get("name", entity_a["entity_id"])
    name_b = entity_b.get("name", entity_b["entity_id"])
    timeline_entries = "\n".join(
        f"[{i.get('date', '')}] {i.get('type', '')} — {i.get('description', '')} "
        f"(sentiment: {i.get('sentiment', 'N/A')})"
        for i in derived.get("timeline", [])
    )
    prompt = (
        f"Based on the interaction history between {name_a} and {name_b}, "
        f"answer this question: {question}\n\n"
        f"Relationship data:\n"
        f"- Dominant type: {derived['dominant_type']}\n"
        f"- Overall sentiment: {derived['overall_sentiment']}\n"
        f"- Recent sentiment: {derived['recent_sentiment']}\n"
        f"- Trajectory: {derived['trajectory']}\n"
        f"- Interaction count: {derived['interaction_count']}\n\n"
        f"Interaction timeline:\n{timeline_entries}"
    )
    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": CHAT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": CHAT_MAX_TOKENS},
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"]


def register(mcp):
    @mcp.tool()
    def query_relationship(
        session_id: str,
        question: str,
        entity_a: str = "",
        desc_a: str = "",
        entity_b: str = "",
        desc_b: str = "",
    ) -> str:
        """
        Describe the relationship between two characters including current state,
        historical trajectory, and key turning points.
        Derives the relationship dynamically from all recorded interactions.
        Can detect arcs such as allies turned enemies.
        Provide either known entity_ids or natural language descriptions of both characters.
        """
        touch_session(session_id)
        trace("query_relationship", session_id, entity_a=entity_a, entity_b=entity_b)

        if not (entity_a or desc_a):
            return "Please provide an entity_id or description for the first character."
        if not (entity_b or desc_b):
            return "Please provide an entity_id or description for the second character."

        user_id = get_user_id(session_id)
        if not user_id:
            return "Session is not identified. Please provide your username first."

        accessible = get_accessible_docids(session_id)

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

        # Both entities must have at least one accessible source docid
        if not (_parse_docids(a.get("docids")) & accessible):
            return "You do not have access to documents relevant to this query."
        if not (_parse_docids(b.get("docids")) & accessible):
            return "You do not have access to documents relevant to this query."

        derived = derive_relationship(a["entity_id"], b["entity_id"], accessible)
        if derived.get("status") == "no_interactions":
            return "No recorded interactions between these characters in your accessible corpus."

        answer = _compose_answer(question, a, b, derived)
        sources = _build_sources(derived.get("timeline", []))

        return json.dumps(
            {
                "answer": answer,
                "dominant_type": derived["dominant_type"],
                "overall_sentiment": derived["overall_sentiment"],
                "recent_sentiment": derived["recent_sentiment"],
                "trajectory": derived["trajectory"],
                "interaction_count": derived["interaction_count"],
                "timeline": derived["timeline"],
                "sources": sources,
            },
            indent=2,
        )
