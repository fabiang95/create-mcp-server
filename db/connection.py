import sqlite3
import sqlite_vec
from config import MOCK_STORE_DB, CHUNKS_VEC_DB


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
