"""Database engine and connectivity checks (SQLAlchemy Core + psycopg 3)."""

import json
from collections.abc import Iterator, Mapping
from typing import Annotated, Any, Literal

import sqlalchemy as sa
from fastapi import Depends, Request
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import OperationalError

from cinecircle_api.auth import CurrentUser

DbStatus = Literal["ok", "unreachable", "schema_missing"]

_SCHEMA_EXISTS = sa.text("SELECT 1 FROM pg_namespace WHERE nspname = 'app'")
_SET_ROLE = sa.text("SET LOCAL ROLE authenticated")
_SET_CLAIMS = sa.text("SELECT set_config('request.jwt.claims', :claims, true)")
# auth.uid() reads request.jwt.claim.sub first and falls back to request.jwt.claims->>'sub', so a
# stale session-level value on a pooled connection would win. Shadow it for this transaction.
_SET_SUB = sa.text("SELECT set_config('request.jwt.claim.sub', :sub, true)")


def make_engine(database_url: str) -> Engine:
    """Create a lazy engine: no connection is opened until first use."""
    return sa.create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def check_db(engine: Engine) -> DbStatus:
    try:
        with engine.connect() as conn:
            found = conn.scalar(_SCHEMA_EXISTS)
    except OperationalError:
        return "unreachable"
    return "ok" if found else "schema_missing"


def act_as(conn: Connection, claims: Mapping[str, Any]) -> None:
    """Run the rest of this transaction as the signed-in user, so Postgres RLS applies.

    Both settings are transaction-local: they end at commit or rollback, so call this inside
    the transaction that runs the user's queries (spec 02 §5.2).
    """
    conn.execute(_SET_ROLE)
    conn.execute(_SET_CLAIMS, {"claims": json.dumps(dict(claims))})
    conn.execute(_SET_SUB, {"sub": str(claims.get("sub", ""))})


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def user_session(request: Request, claims: CurrentUser) -> Iterator[Connection]:
    """One transaction per request, running as the signed-in user so RLS filters every query.

    Commits when the handler returns and rolls back when it raises. Role and claims are
    transaction-local, so nothing leaks to the next request on the pooled connection.

    A commit()/rollback() inside the handler is not an escape hatch: SQLAlchemy refuses any
    further statement inside the `begin()` block, so nothing can run later as postgres.
    """
    with request.app.state.engine.begin() as conn:
        act_as(conn, claims.raw)
        yield conn


# scope="function": the dependency ends (commit included) before the response is sent, so a
# failed commit becomes an error response instead of a success the client already received.
UserDb = Annotated[Connection, Depends(user_session, scope="function")]
