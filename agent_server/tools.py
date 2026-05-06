"""SQL execution helper for querying Databricks Lakebase (managed PostgreSQL)."""

import logging
import threading
import uuid

import psycopg2
import psycopg2.extras
from databricks.sdk import WorkspaceClient

from agent_server.config import (
    LAKEBASE_DB,
    LAKEBASE_DNS,
    LAKEBASE_INSTANCE,
    LAKEBASE_SCHEMA,
)

logger = logging.getLogger(__name__)

_ws = WorkspaceClient()
_lock = threading.Lock()
_conn = None


def _get_token() -> tuple[str, str]:
    """Get a Lakebase database credential and user identity via the REST API."""
    resp = _ws.api_client.do(
        "POST",
        "/api/2.0/database/credentials",
        body={"instance_names": [LAKEBASE_INSTANCE], "request_id": str(uuid.uuid4())},
    )
    token = resp["token"]
    me = _ws.current_user.me()
    return token, me.user_name


def _get_connection() -> psycopg2.extensions.connection:
    """Get or create a psycopg2 connection to Lakebase, refreshing token if needed."""
    global _conn

    if _conn is not None and not _conn.closed:
        try:
            # Quick liveness check
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            logger.debug("Lakebase connection stale, reconnecting")
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None

    token, email = _get_token()
    _conn = psycopg2.connect(
        host=LAKEBASE_DNS,
        port=5432,
        dbname=LAKEBASE_DB,
        user=email,
        password=token,
        sslmode="require",
        options=f"-c search_path={LAKEBASE_SCHEMA}",
    )
    _conn.autocommit = True
    logger.info("Connected to Lakebase at %s", LAKEBASE_DNS)
    return _conn


def _execute_sql(query: str) -> list[dict]:
    """Execute a SQL query against Lakebase and return results as list of dicts."""
    with _lock:
        try:
            conn = _get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                if cur.description is None:
                    # INSERT/CREATE/UPDATE — no result set
                    return []
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except psycopg2.OperationalError:
            # Token expired or connection dropped — reconnect once and retry
            logger.warning("Lakebase connection error, reconnecting and retrying")
            global _conn
            try:
                if _conn is not None:
                    _conn.close()
            except Exception:
                pass
            _conn = None
            conn = _get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                if cur.description is None:
                    return []
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except Exception:
            logger.exception("Lakebase query failed")
            raise
