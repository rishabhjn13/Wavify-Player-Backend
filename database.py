from contextlib import contextmanager
import os
import sqlite3
from config import DB_FILE, SEEDS_DIR
from utils.logger import get_logger

logger = get_logger(__name__)
def init_db():
    """
    Initialize the database and run all seed migrations in order.
    Raises on failure so the caller (lifespan) can abort startup cleanly.
    """
    logger.info("Connecting to database at: %s", DB_FILE)
    _ensure_seeds_dir()
    
    
    conn = sqlite3.connect(DB_FILE)

    try:
        _configure_connection(conn)
        _run_seeds(conn, cursor=conn.cursor())
        conn.commit()
        logger.info("Database initialisation complete.")
    except Exception:
        conn.rollback()
        logger.critical("Database initialisation failed — rolling back.", exc_info=True)
        raise  # Let main.py lifespan abort startup
    finally:
        conn.close()


def _ensure_seeds_dir() -> None:
    if not os.path.exists(SEEDS_DIR):
        os.makedirs(SEEDS_DIR)
        logger.info("Created seeds directory: %s", SEEDS_DIR)


def _configure_connection(conn: sqlite3.Connection) -> None:
    """Apply performance and safety PRAGMAs to a connection."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Better concurrency
    conn.execute("PRAGMA foreign_keys=ON")    # Enforce FK constraints
    conn.execute("PRAGMA synchronous=NORMAL") # Faster writes, still safe with WAL
    
def _run_seeds(conn: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
    sql_files = sorted(f for f in os.listdir(SEEDS_DIR) if f.endswith(".sql"))

    if not sql_files:
        logger.warning("No .sql seed files found in: %s", SEEDS_DIR)
        return

    for sql_file in sql_files:
        file_path = os.path.join(SEEDS_DIR, sql_file)
        logger.info("Running seed: %s", sql_file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                cursor.executescript(f.read())
                logger.info("Seed OK: %s", sql_file)
        except sqlite3.Error as e:
            # Re-raise with context so the caller knows which file broke
            raise RuntimeError(f"Failed to execute seed '{sql_file}': {e}") from e


def get_db() -> sqlite3.Connection:
    """
    Return a configured connection for use in a single request.
    Prefer get_db_ctx() context manager to ensure the connection is closed.
    """
    conn = sqlite3.connect(DB_FILE)
    _configure_connection(conn)
    return conn

@contextmanager
def get_db_ctx():
    """
    Context manager for safe, scoped DB access:

        with get_db_ctx() as db:
            db.execute(...)

            Commits on success, rolls back on error, always closes.
    """
    conn = sqlite3.connect(DB_FILE)
    _configure_connection(conn)
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("DB error — rolled back transaction: %s", e, exc_info=True)
        raise
    finally:
        conn.close()