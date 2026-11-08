from unittest.mock import patch

import sqlalchemy as sa

from cinecircle_api.db import make_engine


def test_engine_never_prepares_statements():
    # Supavisor's transaction pooler cannot keep server-side prepared statements.
    with patch("cinecircle_api.db.sa.create_engine", wraps=sa.create_engine) as create:
        make_engine("postgresql+psycopg://u:p@127.0.0.1:1/x")
    connect_args = create.call_args.kwargs["connect_args"]
    assert connect_args["prepare_threshold"] is None
    assert connect_args["connect_timeout"] == 3
    assert create.call_args.kwargs["pool_pre_ping"] is True
