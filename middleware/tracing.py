"""Structured tool-call tracing. Logs to stdout and logs/tools.log."""
from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path

from middleware.session import get_session

# --- logger setup ---
_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_logger = logging.getLogger("mcp.tools")
_logger.setLevel(logging.INFO)

if not _logger.handlers:
    _fmt = logging.Formatter("%(message)s")

    # rotating file — 5 MB per file, keep 3
    _fh = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "tools.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _fh.setFormatter(_fmt)

    _sh = logging.StreamHandler()
    _sh.setFormatter(_fmt)

    _logger.addHandler(_fh)
    _logger.addHandler(_sh)


def trace(tool_name: str, session_id: str, **params) -> None:
    """
    Emit one JSON log line per tool call.
    Call at the top of every tool handler, after touch_session().
    """
    session = get_session(session_id) or {}
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "session_id": session_id,
        "user": session.get("username") or session.get("user_id") or "unidentified",
        "role": session.get("role"),
        "params": {k: v for k, v in params.items() if v not in (None, "", [])},
    }
    _logger.info(json.dumps(record))
