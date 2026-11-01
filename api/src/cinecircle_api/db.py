"""Database engine and connectivity checks (SQLAlchemy Core + psycopg 3)."""

from typing import Literal

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

DbStatus = Literal["ok", "unreachable", "schema_missing"]

_SCHEMA_EXISTS = sa.text("SELECT 1 FROM pg_namespace WHERE nspname = 'app'")


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


def get_engine(request: Request) -> Engine:
    return request.app.state.engine
