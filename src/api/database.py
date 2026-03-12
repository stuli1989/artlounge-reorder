"""Database connection management for FastAPI routes."""
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config.settings import DATABASE_URL

# Connection pool: reuse connections instead of creating new TCP connections per request
_pool = ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    dsn=DATABASE_URL,
    cursor_factory=RealDictCursor,
)


@contextmanager
def get_db():
    """Get a pooled database connection with RealDictCursor (returns dicts not tuples)."""
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        conn.rollback()  # Ensure no uncommitted state leaks back to pool
        _pool.putconn(conn)
