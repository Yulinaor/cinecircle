"""Database engine and connectivity checks (SQLAlchemy Core + psycopg 3)."""

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated, Any, Literal

import sqlalchemy as sa
from fastapi import Depends, Request
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import OperationalError

from cinecircle_api.auth import Claims, CurrentUser

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


class _Open:
    """How many user transactions a request has open: a cell the context variable points at."""

    count = 0


_OPEN: ContextVar[_Open | None] = ContextVar("open_user_transactions", default=None)


async def request_scope() -> None:
    """Dependency: give the request its cell for `in_user_transaction`.

    An async dependency runs in the request's own context, while sync dependencies and handlers
    run in worker threads on copies of it. A copy keeps pointing at the same cell, but a value set
    from inside a worker thread would be lost with its copy, so the cell is made here.
    """
    _OPEN.set(_Open())


RequestScope = Annotated[None, Depends(request_scope)]


def in_user_transaction() -> bool:
    """True while the current request has a `user_transaction` open (a probe for tests: TMDB and
    OMDb must never be called from in here, plan Global Constraints)."""
    cell = _OPEN.get()
    return cell is not None and cell.count > 0


@contextmanager
def user_transaction(request: Request, claims: Claims) -> Iterator[Connection]:
    """One transaction running as the signed-in user, so RLS filters every query in it.

    Commits when the block ends and rolls back when it raises. Role and claims are
    transaction-local, so nothing leaks to the next request on the pooled connection.

    A commit()/rollback() inside the block is not an escape hatch: SQLAlchemy refuses any
    further statement inside the `begin()` block, so nothing can run later as postgres.

    A sync handler that calls this directly needs no `RequestScope`: the handler and the sync code
    it calls run in one context copy, and the first call there makes its own cell for
    `in_user_transaction`. `RequestScope` matters for `UserDb`, whose transaction opens in a
    dependency while the handler runs in another context copy.
    """
    cell = _OPEN.get()
    if cell is None:  # outside a request (a script, a test): this context gets its own cell
        cell = _Open()
        _OPEN.set(cell)
    with request.app.state.engine.begin() as conn:
        act_as(conn, claims.raw)
        cell.count += 1
        try:
            yield conn
        finally:
            cell.count -= 1


def user_session(
    request: Request, claims: CurrentUser, _scope: RequestScope
) -> Iterator[Connection]:
    """One `user_transaction` per request, for the handler to use as `UserDb`."""
    with user_transaction(request, claims) as conn:
        yield conn


# scope="function": the dependency ends (commit included) before the response is sent, so a
# failed commit becomes an error response instead of a success the client already received.
UserDb = Annotated[Connection, Depends(user_session, scope="function")]
