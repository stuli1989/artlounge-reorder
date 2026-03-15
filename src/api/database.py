"""Database connection management for FastAPI routes."""
import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

# Connection pool: reuse connections instead of creating new TCP connections per request
# Add connect_timeout for faster failure detection
_dsn = DATABASE_URL
if "?" not in _dsn:
    _dsn += "?connect_timeout=5"
else:
    _dsn += "&connect_timeout=5"

try:
    _pool = ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        dsn=_dsn,
        cursor_factory=RealDictCursor,
    )
except Exception as e:
    logger.error("Failed to create connection pool: %s", e)
    _pool = None


@contextmanager
def get_db():
    """Get a pooled database connection with RealDictCursor (returns dicts not tuples)."""
    if _pool is None:
        raise RuntimeError("Database connection pool not initialized")
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        try:
            conn.rollback()  # Ensure no uncommitted state leaks back to pool
        except Exception:
            _pool.putconn(conn, close=True)
        else:
            _pool.putconn(conn)
