"""All SQL queries as named functions. No SQL is written inline in tool or pipeline code."""
from __future__ import annotations

import json
from typing import Any

from db.connection import get_db, get_rw_db, get_vec_db
from config import EVENT_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# user_access
# ---------------------------------------------------------------------------

def get_user(user_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id, role FROM user_access WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["username"] = d["user_id"]
    return d


def get_user_by_username(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id, role, accessible_docids FROM user_access WHERE user_id = ?",
            (username,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["username"] = d["user_id"]
    return d


def get_accessible_docids(user_id: str) -> set[str]:
    """Return the pre-computed set of accessible docids for a user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT accessible_docids FROM user_access WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return set()
    raw = row["accessible_docids"]
    if isinstance(raw, str):
        return set(json.loads(raw))
    return set(raw)


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

def get_event(event_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
    return dict(row) if row else None


def search_events_fts(description: str) -> list[dict]:
    term = f"%{description.lower()}%"
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM events
            WHERE (LOWER(name) LIKE ? OR LOWER(participants) LIKE ? OR LOWER(topics) LIKE ?)
              AND confidence >= ?
            """,
            (term, term, term, EVENT_CONFIDENCE_THRESHOLD),
        ).fetchall()
    return [dict(r) for r in rows]


def list_events_filtered(
    universe: str | None,
    date_from: str | None,
    date_to: str | None,
    participant: str | None,
) -> list[dict]:
    clauses = [f"confidence >= {EVENT_CONFIDENCE_THRESHOLD}"]
    params: list[Any] = []
    # events table has no universe column — ignore this filter
    if universe:
        pass
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    if participant:
        clauses.append("participants LIKE ?")
        params.append(f"%{participant}%")

    where = " AND ".join(clauses)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM events WHERE {where}", params
        ).fetchall()
    return [dict(r) for r in rows]


def get_events_for_entity(entity_id: str) -> list[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT event_ids FROM entities WHERE id = ?", (entity_id,)).fetchone()
    if not row:
        return []
    event_ids = json.loads(row["event_ids"] or "[]")
    if not event_ids:
        return []
    placeholders = ",".join("?" * len(event_ids))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM events WHERE id IN ({placeholders})", event_ids
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# entities
# ---------------------------------------------------------------------------

def get_entity(entity_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
    return dict(row) if row else None


def search_entities_fts(description: str) -> list[dict]:
    term = f"%{description.lower()}%"
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM entities WHERE name_lower LIKE ?",
            (term,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_entities_filtered(universe: str | None, entity_type: str | None) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if entity_type:
        clauses.append("type = ?")
        params.append(entity_type)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_db() as conn:
        rows = conn.execute(f"SELECT * FROM entities {where}", params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# summaries
# ---------------------------------------------------------------------------

def get_summary(systemdocid: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM summaries WHERE systemdocid = ?", (systemdocid,)
        ).fetchone()
    return dict(row) if row else None


def search_summaries_fts(
    query: str,
    accessible_docids: set[str],
    universe: str | None = None,
    themes: list[str] | None = None,
    top_n: int = 10,
) -> list[dict]:
    term = f"%{query.lower()}%"
    clauses = ["(LOWER(title) LIKE ? OR LOWER(summary) LIKE ? OR LOWER(themes) LIKE ?)"]
    params: list[Any] = [term, term, term]

    if themes:
        for theme in themes:
            clauses.append("LOWER(themes) LIKE ?")
            params.append(f"%{theme.lower()}%")

    where = " AND ".join(clauses)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM summaries WHERE {where} LIMIT ?",
            params + [top_n * 5],
        ).fetchall()

    results = [dict(r) for r in rows if r["systemdocid"] in accessible_docids]
    return results[:top_n]


def get_summaries_for_docids(docids: list[str]) -> list[dict]:
    placeholders = ",".join("?" * len(docids))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM summaries WHERE systemdocid IN ({placeholders})", docids
        ).fetchall()
    return [dict(r) for r in rows]


def match_interest_against_summaries(interest_text: str, accessible_docids: set[str]) -> bool:
    """Return True if interest_text matches any accessible summary."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT systemdocid, themes, summary, title FROM summaries"
        ).fetchall()
    for row in rows:
        if row["systemdocid"] not in accessible_docids:
            continue
        themes_raw = row["themes"] or ""
        if interest_text.lower() in themes_raw.lower():
            return True
        if interest_text.lower() in (row["summary"] or "").lower():
            return True
        if interest_text.lower() in (row["title"] or "").lower():
            return True
    return False


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def get_report(systemdocid: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE systemdocid = ?", (systemdocid,)
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# chunks
# ---------------------------------------------------------------------------

def get_chunk_texts(chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" * len(chunk_ids))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM chunks WHERE chunk_id IN ({placeholders})", chunk_ids
        ).fetchall()
    return [dict(r) for r in rows]


def get_chunk_ids_for_docids(docids: list[str]) -> list[str]:
    if not docids:
        return []
    placeholders = ",".join("?" * len(docids))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT chunk_id FROM chunks WHERE systemdocid IN ({placeholders})", docids
        ).fetchall()
    return [r["chunk_id"] for r in rows]


# ---------------------------------------------------------------------------
# interests
# ---------------------------------------------------------------------------

def _normalize_interest(row: dict) -> dict:
    """Map actual DB columns to the field names the rest of the code expects."""
    row = dict(row)
    row["interest_text"] = row.get("interest", "")
    row["valid"] = 1 if row.get("validation_state") == "valid" else 0
    return row


def get_valid_interests(user_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM interests WHERE user_id = ? AND validation_state = 'valid'", (user_id,)
        ).fetchall()
    return [_normalize_interest(r) for r in rows]


def get_all_interests(user_id: str) -> dict[str, list[dict]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM interests WHERE user_id = ?", (user_id,)
        ).fetchall()
    all_rows = [_normalize_interest(r) for r in rows]
    valid = [r for r in all_rows if r["valid"] == 1]
    stale = [r for r in all_rows if r["valid"] == 0]
    return {"valid": valid, "stale": stale}


def insert_interest(
    user_id: str,
    interest_text: str,
    staleness_type: str,
    staleness_threshold: int,
    valid: int,
) -> None:
    import json
    staleness_config = json.dumps({"type": staleness_type, "threshold": staleness_threshold})
    validation_state = "valid" if valid else "stale"
    with get_rw_db() as conn:
        conn.execute(
            "DELETE FROM interests WHERE user_id = ? AND interest = ?",
            (user_id, interest_text),
        )
        conn.execute(
            "INSERT INTO interests (user_id, interest, staleness_config, validation_state) VALUES (?, ?, ?, ?)",
            (user_id, interest_text, staleness_config, validation_state),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# vector search
# ---------------------------------------------------------------------------

def vector_search(question_vec: list[float], docids: list[str], k: int) -> list[str]:
    """Cosine similarity search in chunks_vec.db restricted to the given docids."""
    if not docids:
        return []
    allowed_chunk_ids = get_chunk_ids_for_docids(docids)
    if not allowed_chunk_ids:
        return []

    placeholders = ",".join("?" * len(allowed_chunk_ids))
    vec_bytes = _encode_vec(question_vec)

    with get_vec_db() as conn:
        rows = conn.execute(
            f"""
            SELECT chunk_id, distance
            FROM vectors
            WHERE chunk_id IN ({placeholders})
            ORDER BY vec_distance_cosine(embedding, ?) ASC
            LIMIT ?
            """,
            allowed_chunk_ids + [vec_bytes, k],
        ).fetchall()
    return [r["chunk_id"] for r in rows]


def _encode_vec(vec: list[float]) -> bytes:
    import struct
    return struct.pack(f"{len(vec)}f", *vec)


# ---------------------------------------------------------------------------
# interactions
# ---------------------------------------------------------------------------

def get_interactions(
    entity_a_id: str,
    entity_b_id: str,
    accessible_docids: set[str],
) -> list[dict]:
    """Return interactions between two entities restricted to accessible docs.

    The interactions table stores character names and evidence as a JSON array of
    {docid, chunk_ids, event} objects. We resolve entity IDs to names, then filter
    evidence entries to only those in accessible_docids.
    """
    if not accessible_docids:
        return []

    a = get_entity(entity_a_id)
    b = get_entity(entity_b_id)
    if not a or not b:
        return []

    name_a, name_b = a["name"], b["name"]

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM interactions
            WHERE (character_a = ? AND character_b = ?)
               OR (character_a = ? AND character_b = ?)
            """,
            (name_a, name_b, name_b, name_a),
        ).fetchall()

    results = []
    for row in rows:
        evidence = json.loads(row["evidence"] or "[]")
        accessible_evidence = [e for e in evidence if e.get("docid") in accessible_docids]
        if accessible_evidence:
            results.append({
                "id": row["id"],
                "character_a": row["character_a"],
                "character_b": row["character_b"],
                "evidence": accessible_evidence,
            })
    return results
