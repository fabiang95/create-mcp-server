"""Vector search and chunk assembly."""
from __future__ import annotations

from config import FILE_STORE_PATH
from db.queries import get_chunk_texts, get_summary, get_report, vector_search as _vector_search
from rag.embed import embed


def retrieve_chunks(question: str, docids: list[str], k: int = 6) -> list[dict]:
    """Embed question, run cosine search restricted to docids pool."""
    question_vec = embed(question)
    chunk_ids = _vector_search(question_vec, docids, k)
    return get_chunk_texts(chunk_ids)


def assemble_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    """Build context string and deduplicated source list for prompt."""
    context_parts: list[str] = []
    sources: list[dict] = []
    seen_docids: set[str] = set()

    for chunk in chunks:
        docid = chunk["systemdocid"]
        summary = get_summary(docid) or {}
        title = summary.get("title", docid)
        heading = chunk.get("section_heading", "")
        context_parts.append(f"[{title} | {heading}]\n{chunk['text']}")

        if docid not in seen_docids:
            seen_docids.add(docid)
            sources.append(
                {
                    "systemdocid": docid,
                    "title": title,
                    "file_path": build_file_path(docid),
                    "section_heading": heading,
                }
            )

    context = "\n\n".join(context_parts)
    return context, sources


def build_file_path(systemdocid: str) -> str:
    """Construct local file path from reports table."""
    row = get_report(systemdocid)
    if not row:
        return f"{FILE_STORE_PATH}/{systemdocid}"
    version = row.get("version", "1")
    mongo_id = row.get("mongo_id", systemdocid)
    fmt = row.get("format", "pdf")
    return f"{FILE_STORE_PATH}/{systemdocid}/{version}/M_{mongo_id}.{fmt}"
