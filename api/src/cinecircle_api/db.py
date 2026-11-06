"""Database engine and connectivity checks (SQLAlchemy Core + psycopg 3)."""

import json
from collections.abc import Mapping
from typing import Any, Literal

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import OperationalError

DbStatus = Literal["ok", "unreachable", "schema_missing"]

_SCHEMA_EXISTS = sa.text("SELECT 1 FROM pg_namespace WHERE nspname = 'app'")
_SET_ROLE = sa.text("SET LOCAL ROLE authenticated")
_SET_CLAIMS = sa.text("SELECT set_config('request.jwt.claims', :claims, true)")


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


def get_engine(request: Request) -> Engine:
    return request.app.state.engine
