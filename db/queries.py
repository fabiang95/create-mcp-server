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
            "SELECT user_id, username, role FROM user_access WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id, username, role, accessible_docids FROM user_access WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


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
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
    return dict(row) if row else None


def search_events_fts(description: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT e.*
            FROM events e
            JOIN events_fts fts ON e.rowid = fts.rowid
            WHERE events_fts MATCH ?
              AND e.confidence >= ?
            ORDER BY fts.rank
            """,
            (description, EVENT_CONFIDENCE_THRESHOLD),
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
    if universe:
        clauses.append("universe = ?")
        params.append(universe)
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
        rows = conn.execute(
            """
            SELECT e.*
            FROM events e
            JOIN entity_events ee ON e.event_id = ee.event_id
            WHERE ee.entity_id = ?
            """,
            (entity_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# entities
# ---------------------------------------------------------------------------

def get_entity(entity_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM entities WHERE entity_id = ?", (entity_id,)
        ).fetchone()
    return dict(row) if row else None


def search_entities_fts(description: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT en.*
            FROM entities en
            JOIN entities_fts fts ON en.rowid = fts.rowid
            WHERE entities_fts MATCH ?
            ORDER BY fts.rank
            """,
            (description,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_entities_filtered(universe: str | None, entity_type: str | None) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if universe:
        clauses.append("universe = ?")
        params.append(universe)
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
    clauses = ["summaries_fts MATCH ?"]
    params: list[Any] = [query]

    if universe:
        clauses.append("s.universe = ?")
        params.append(universe)
    if themes:
        for theme in themes:
            clauses.append("s.themes LIKE ?")
            params.append(f"%{theme}%")

    where = " AND ".join(clauses)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT s.*
            FROM summaries s
            JOIN summaries_fts fts ON s.rowid = fts.rowid
            WHERE {where}
            ORDER BY fts.rank
            LIMIT ?
            """,
            params + [top_n * 5],  # over-fetch then filter in Python
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

def get_valid_interests(user_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM interests WHERE user_id = ? AND valid = 1", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_interests(user_id: str) -> dict[str, list[dict]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM interests WHERE user_id = ?", (user_id,)
        ).fetchall()
    valid = [dict(r) for r in rows if r["valid"] == 1]
    stale = [dict(r) for r in rows if r["valid"] == 0]
    return {"valid": valid, "stale": stale}


def insert_interest(
    user_id: str,
    interest_text: str,
    staleness_type: str,
    staleness_threshold: int,
    valid: int,
) -> None:
    with get_rw_db() as conn:
        conn.execute(
            """
            INSERT INTO interests
                (user_id, interest_text, staleness_type, staleness_threshold, valid, last_validated)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, interest_text) DO UPDATE SET
                staleness_type = excluded.staleness_type,
                staleness_threshold = excluded.staleness_threshold,
                valid = excluded.valid,
                last_validated = excluded.last_validated
            """,
            (user_id, interest_text, staleness_type, staleness_threshold, valid),
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
    """Return all interactions between two entities restricted to accessible docs, ordered by date asc."""
    if not accessible_docids:
        return []
    placeholders = ",".join("?" * len(accessible_docids))
    params: list = [entity_a_id, entity_b_id, entity_b_id, entity_a_id] + list(accessible_docids)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM interactions
            WHERE ((entity_a_id = ? AND entity_b_id = ?)
                OR (entity_a_id = ? AND entity_b_id = ?))
              AND source_docid IN ({placeholders})
            ORDER BY date ASC
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]
