"""Orchestrates the 6-step RAG query pipeline."""
from __future__ import annotations

import httpx

from config import OLLAMA_URL, CHAT_MODEL, CHAT_MAX_TOKENS, TOP_K_CHUNKS
from middleware.access_control import resolve_access, AccessDeniedError
from middleware.session import get_user_id
from prompt_loader import load_prompt
from rag.rerank import boost_by_interests
from rag.retrieval import retrieve_chunks, assemble_context


def run_rag_pipeline(
    question: str,
    candidate_docids: list[str],
    session_id: str,
) -> dict:
    """
    Steps 2-6 of the RAG pipeline.
    Step 1 (index lookup / candidate selection) is the caller's responsibility.

    Returns {"answer": str, "sources": list[dict]}.
    Raises AccessDeniedError if no accessible docs remain after filtering.
    """
    # Step 2 — access filter
    allowed_docids = resolve_access(session_id, candidate_docids)

    # Step 3 — interest boost re-ranking
    user_id = get_user_id(session_id)
    ranked_docids = boost_by_interests(allowed_docids, user_id)

    # Step 4 — chunk retrieval
    chunks = retrieve_chunks(question, ranked_docids, k=TOP_K_CHUNKS)
    if not chunks:
        return {
            "answer": "No relevant content found in the accessible corpus for this query.",
            "sources": [],
        }

    # Step 5 — context assembly
    context, sources = assemble_context(chunks)

    # Step 6 — LLM answer (local Ollama)
    answer = _generate_answer(question, context, sources)
    return {"answer": answer, "sources": sources}


def _generate_answer(question: str, context: str, sources: list[dict]) -> str:
    source_list = "\n".join(
        [f"- {s['title']} ({s['file_path']})" for s in sources]
    )
    prompt = load_prompt(
        "rag_answer",
        context=context,
        question=question,
        source_list=source_list,
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
