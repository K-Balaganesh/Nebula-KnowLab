"""Database connection and transaction manager with SQLite WAL mode."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.config import DATABASE_PATH

# Thread-local storage for connections
_local = threading.local()


def get_db_connection() -> sqlite3.Connection:
    """Get or create a thread-local SQLite connection with WAL mode enabled."""
    if not hasattr(_local, "connection") or _local.connection is None:
        db_path = Path(DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(db_path),
            timeout=10.0,
            check_same_thread=False,
            isolation_level=None  # Enable autocommit mode so we can manually manage transactions
        )
        conn.row_factory = sqlite3.Row
        # Configure WAL mode and busy timeout for high concurrency
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        _local.connection = conn

    return _local.connection


get_db = get_db_connection


@contextmanager
def transaction(conn: Optional[sqlite3.Connection] = None):
    """Context manager for ACID transaction with BEGIN IMMEDIATE lock."""
    connection = conn or get_db_connection()
    # BEGIN IMMEDIATE acquires a reserved lock immediately, preventing writer starvation and deadlocks
    connection.execute("BEGIN IMMEDIATE;")
    try:
        yield connection
        connection.execute("COMMIT;")
    except Exception:
        connection.execute("ROLLBACK;")
        raise


def init_db(schema_path: Optional[Path] = None) -> None:
    """Initialize database tables using schema.sql."""
    if schema_path is None:
        schema_path = Path(__file__).parent / "schema.sql"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_db_connection()
    conn.executescript(schema_sql)


def execute_query(
    sql: str,
    params: Union[Tuple, List, Dict] = (),
    fetchone: bool = False
) -> Union[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Execute a read query and return dictionary results."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    if fetchone:
        row = cursor.fetchone()
        return dict(row) if row else None
    else:
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def execute_write(sql: str, params: Union[Tuple, List, Dict] = ()) -> int:
    """Execute a single write query and return the last inserted rowid."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return cursor.lastrowid or cursor.rowcount
