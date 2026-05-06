import sqlite3
import sqlite_vec
from config import MOCK_STORE_DB, CHUNKS_VEC_DB


def init_db() -> None:
    """Create tables that may not exist yet (e.g. interactions). Safe to call on every startup."""
    with get_rw_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                interaction_id  TEXT PRIMARY KEY,
                entity_a_id     TEXT NOT NULL,
                entity_b_id     TEXT NOT NULL,
                date            TEXT,
                type            TEXT,
                description     TEXT,
                sentiment       REAL,
                source_docid    TEXT,
                source_event_id TEXT
            )
            """
        )
        conn.commit()


def get_db() -> sqlite3.Connection:
    """Read-only connection to mock_store.db with sqlite-vec loaded."""
    conn = sqlite3.connect(f"file:{MOCK_STORE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def get_rw_db() -> sqlite3.Connection:
    """Read-write connection — used ONLY for interests and sessions tables."""
    conn = sqlite3.connect(MOCK_STORE_DB)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def get_vec_db() -> sqlite3.Connection:
    """Read-only connection to chunks_vec.db."""
    conn = sqlite3.connect(f"file:{CHUNKS_VEC_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn
