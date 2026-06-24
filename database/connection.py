import psycopg2
import psycopg2.extras
import psycopg2.pool
import logging
from config import Config

logger = logging.getLogger(__name__)

# Bug 8 fixed: use a ThreadedConnectionPool instead of a new connection per
# query. minconn=1, maxconn=10 fits comfortably on a t3.micro alongside
# the single-worker / 4-thread Gunicorn deployment.
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=Config.DATABASE_URL,
        )
    return _pool


def get_connection():
    """Return a connection from the thread-safe pool."""
    return _get_pool().getconn()


def release_connection(conn):
    """Return a connection to the pool."""
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


def execute_query(query, params=None, fetch=None):
    """
    Generic query helper.
    fetch: None | 'one' | 'all'
    Returns rows as list-of-dicts (or single dict).
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch == "one":
                result = cur.fetchone()
                conn.commit()
                return dict(result) if result else None
            elif fetch == "all":
                result = cur.fetchall()
                conn.commit()
                return [dict(r) for r in result]
            else:
                conn.commit()
                return None
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"DB error: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)


def init_db():
    """Run schema.sql to create tables (idempotent — IF NOT EXISTS)."""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        sql = f.read()
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        logger.info("Database initialised successfully.")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"DB init error: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)
