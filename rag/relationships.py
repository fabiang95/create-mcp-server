"""Relationship derivation from interactions table — pure computation, no LLM."""
from __future__ import annotations

from collections import Counter

from db.queries import get_interactions


def derive_relationship(
    entity_a_id: str,
    entity_b_id: str,
    accessible_docids: set[str],
) -> dict:
    """
    Compute relationship state from raw interaction records.
    Returns a dict with trajectory, sentiment stats, and the full timeline.
    Returns {"status": "no_interactions"} when no records are found.
    """
    interactions = get_interactions(entity_a_id, entity_b_id, accessible_docids)
    if not interactions:
        return {"status": "no_interactions"}

    sentiments = [i["sentiment"] for i in interactions if i.get("sentiment") is not None]
    if not sentiments:
        sentiments = [0.0]

    recent = sentiments[-3:]
    overall_avg = sum(sentiments) / len(sentiments)
    recent_avg = sum(recent) / len(recent)
    delta = recent_avg - overall_avg

    trajectory = (
        "improving" if delta > 0.1
        else "deteriorating" if delta < -0.1
        else "stable"
    )

    type_counts = Counter(i["type"] for i in interactions if i.get("type"))
    dominant = type_counts.most_common(1)[0][0] if type_counts else None

    return {
        "dominant_type": dominant,
        "overall_sentiment": round(overall_avg, 2),
        "recent_sentiment": round(recent_avg, 2),
        "trajectory": trajectory,
        "interaction_count": len(interactions),
        "timeline": interactions,
    }
