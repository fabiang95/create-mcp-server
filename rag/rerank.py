"""Interest boost re-ranking."""
from __future__ import annotations

from db.queries import get_valid_interests, get_summary


def boost_by_interests(docids: list[str], user_id: str) -> list[str]:
    """Re-rank docids so those matching active interests come first."""
    interests = get_valid_interests(user_id)
    if not interests:
        return docids

    scores: dict[str, int] = {}
    for docid in docids:
        summary_row = get_summary(docid)
        score = 0
        if summary_row:
            themes_raw = (summary_row.get("themes") or "").lower()
            summary_text = (summary_row.get("summary") or "").lower()
            for interest in interests:
                itext = interest["interest_text"].lower()
                if itext in themes_raw:
                    score += 2
                if itext in summary_text:
                    score += 1
        scores[docid] = score

    return sorted(docids, key=lambda d: scores.get(d, 0), reverse=True)
