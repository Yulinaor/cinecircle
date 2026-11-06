"""People tables under RLS: cards, details, settings, follows and their notifications.

Gal = owner, Dana = approved follower, Noa = stranger, Ron = pending (see conftest `people`).
Every query runs as the user through `as_user`, i.e. exactly as the API will run it.
"""

import psycopg.errors
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, ProgrammingError

from cinecircle_api.db import act_as
from tests.integration.conftest import GAL_BIO, as_user, claims_for

pytestmark = pytest.mark.integration

PEOPLE_TABLES = ["profiles", "profile_details", "user_settings", "follows", "notifications"]
_ACCEPT_RON = (
    "UPDATE app.follows SET status = 'accepted' WHERE follower_id = :r AND followee_id = :g"
)
_RON_ROW = (
    "SELECT status, responded_at FROM app.follows WHERE follower_id = :r AND followee_id = :g"
)


def scalar(conn: sa.Connection, sql: str, **params):
    return conn.scalar(sa.text(sql), params)


def run(conn: sa.Connection, sql: str, **params) -> sa.CursorResult:
    return conn.execute(sa.text(sql), params)


def assert_permission_denied(exc: pytest.ExceptionInfo, table: str) -> None:
    """Refused by GRANTs (no privilege on the table or column), not by a policy."""
    assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege)
    assert f"permission denied for table {table}" in str(exc.value.orig)


def assert_rls_refused(exc: pytest.ExceptionInfo, table: str) -> None:
    assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege)
    assert f'new row violates row-level security policy for table "{table}"' in str(exc.value.orig)


def notifications_of(conn: sa.Connection) -> list[tuple[str, str]]:
    """The current user's notifications as (type, actor username), sorted."""
    rows = run(
        conn,
        "SELECT n.type, p.username FROM app.notifications n"
        " JOIN app.profiles p ON p.id = n.actor_id"
        " WHERE n.recipient_id = auth.uid() ORDER BY 1, 2",
    )
    return [tuple(r) for r in rows]


# ----- reading ---------------------------------------------------------------------------------


def test_any_signed_in_user_reads_every_card(people, engine):
    for user in people.values():
        with as_user(engine, user) as conn:
            assert scalar(conn, "SELECT count(*) FROM app.profiles") == 4


def test_details_owner_and_approved_follower_only(people, engine):
    gal = people["gal"]
    for key, sees in {"gal": True, "dana": True, "noa": False, "ron": False}.items():
        with as_user(engine, people[key]) as conn:
            rows = run(conn, "SELECT bio FROM app.profile_details WHERE user_id = :g", g=gal.id)
            assert rows.scalars().all() == ([GAL_BIO] if sees else []), key


def test_follow_rows_visible_only_to_the_two_people(people, engine):
    gal = people["gal"]
    for key, expected in {"gal": 2, "dana": 1, "ron": 1, "noa": 0}.items():
        with as_user(engine, people[key]) as conn:
            count = scalar(
                conn, "SELECT count(*) FROM app.follows WHERE followee_id = :g", g=gal.id
            )
            assert count == expected, key


def test_settings_owner_only(people, engine):
    for user in people.values():
        with as_user(engine, user) as conn:
            assert run(conn, "SELECT user_id FROM app.user_settings").scalars().all() == [user.id]


def test_triggers_create_notifications(people, engine):
    expected = {
        "gal": [("follow_request", "dana"), ("follow_request", "ron")],
        "dana": [("follow_accepted", "gal")],
        "noa": [],
        "ron": [],
    }
    for key, notes in expected.items():
        with as_user(engine, people[key]) as conn:
            assert notifications_of(conn) == notes, key


def test_notifications_recipient_only(people, engine):
    gal = people["gal"]
    for key in ("dana", "noa"):
        with as_user(engine, people[key]) as conn:
            count = scalar(
                conn, "SELECT count(*) FROM app.notifications WHERE recipient_id = :g", g=gal.id
            )
            assert count == 0, key


def test_anon_reads_nothing(people, engine):
    for table in PEOPLE_TABLES:
        with engine.connect() as conn, pytest.raises(ProgrammingError) as exc:
            run(conn, "SET LOCAL ROLE anon")
            run(conn, f"SELECT * FROM app.{table}")
        assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege), table
    # Not just the schema lock: anon holds no privilege on the tables themselves either.
    with engine.connect() as conn:
        for table in PEOPLE_TABLES:
            held = scalar(
                conn,
                "SELECT has_table_privilege('anon', CAST(:t AS regclass),"
                " 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')",
                t=f"app.{table}",
            )
            assert held is False, table


# Exact GRANTs for `authenticated` (plan P6): table-level SELECT / DELETE, column-level writes.
GRANTS = {  # table: (insert columns, update columns, delete)
    "profiles": (
        {"id", "username", "display_name", "avatar_url"},
        {"display_name", "avatar_url"},
        False,
    ),
    "profile_details": ({"user_id", "bio"}, {"bio"}, False),
    "user_settings": ({"user_id", "locale"}, {"locale"}, False),
    "follows": ({"follower_id", "followee_id"}, {"status"}, True),
    "notifications": (set(), {"read_at"}, False),
}


@pytest.mark.parametrize("table", PEOPLE_TABLES)
def test_authenticated_grants_are_exact(people, engine, table):
    insert_cols, update_cols, delete = GRANTS[table]
    with engine.connect() as conn:

        def columns_with(priv: str) -> set[str]:
            rows = run(
                conn,
                "SELECT attname FROM pg_attribute"
                " WHERE attrelid = CAST(:t AS regclass) AND attnum > 0 AND NOT attisdropped"
                " AND has_column_privilege('authenticated', attrelid, attnum, :p)",
                t=f"app.{table}",
                p=priv,
            )
            return set(rows.scalars())

        def table_priv(priv: str) -> bool:
            return scalar(
                conn,
                "SELECT has_table_privilege('authenticated', CAST(:t AS regclass), :p)",
                t=f"app.{table}",
                p=priv,
            )

        assert table_priv("SELECT") is True
        assert columns_with("INSERT") == insert_cols
        assert columns_with("UPDATE") == update_cols
        assert table_priv("INSERT") is False  # never the whole table: only the columns above
        assert table_priv("UPDATE") is False
        assert table_priv("DELETE") is delete
        assert table_priv("TRUNCATE, REFERENCES, TRIGGER") is False


# ----- writing past the rules ------------------------------------------------------------------


def test_cannot_request_follow_as_someone_else(people, engine):
    with as_user(engine, people["noa"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(
            conn,
            "INSERT INTO app.follows (follower_id, followee_id) VALUES (:r, :g)",
            r=people["ron"].id,
            g=people["gal"].id,
        )
    assert_rls_refused(exc, "follows")


def test_cannot_insert_accepted_follow(people, engine):
    with as_user(engine, people["noa"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(
            conn,
            "INSERT INTO app.follows (follower_id, followee_id, status)"
            " VALUES (:n, :g, 'accepted')",
            n=people["noa"].id,
            g=people["gal"].id,
        )
    assert_permission_denied(exc, "follows")


def test_follower_cannot_accept_own_request(people, engine):
    ron, gal = people["ron"], people["gal"]
    with as_user(engine, ron) as conn:
        result = run(conn, _ACCEPT_RON, r=ron.id, g=gal.id)
        assert result.rowcount == 0
        assert scalar(conn, "SELECT status FROM app.follows WHERE follower_id = :r", r=ron.id) == (
            "pending"
        )


def test_followee_cannot_rewrite_follower_id(people, engine):
    with as_user(engine, people["gal"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(
            conn,
            "UPDATE app.follows SET follower_id = :n WHERE follower_id = :r",
            n=people["noa"].id,
            r=people["ron"].id,
        )
    assert_permission_denied(exc, "follows")


def test_accepted_cannot_go_back_to_pending(people, engine):
    with as_user(engine, people["gal"]) as conn, pytest.raises(IntegrityError) as exc:
        run(
            conn,
            "UPDATE app.follows SET status = 'pending' WHERE follower_id = :d",
            d=people["dana"].id,
        )
    assert isinstance(exc.value.orig, psycopg.errors.CheckViolation)
    assert "follow status cannot change from accepted to pending" in str(exc.value.orig)


def test_cannot_insert_notification(people, engine):
    for key in ("gal", "noa"):
        with as_user(engine, people[key]) as conn, pytest.raises(ProgrammingError) as exc:
            run(
                conn,
                "INSERT INTO app.notifications (recipient_id, actor_id, type)"
                " VALUES (:me, :g, 'follow_accepted')",
                me=people[key].id,
                g=people["gal"].id,
            )
        assert_permission_denied(exc, "notifications")


def test_cannot_update_another_profile(people, engine):
    gal = people["gal"]
    with as_user(engine, people["noa"]) as conn:
        result = run(
            conn, "UPDATE app.profiles SET display_name = 'hacked' WHERE id = :g", g=gal.id
        )
        assert result.rowcount == 0
        assert (
            scalar(conn, "SELECT display_name FROM app.profiles WHERE id = :g", g=gal.id) == "Gal"
        )


# ----- follow lifecycle ------------------------------------------------------------------------


def test_accept_twice_one_notification(people, engine):
    gal, ron = people["gal"], people["ron"]
    ids = {"r": ron.id, "g": gal.id}
    # First accept is committed, so the second runs in a later transaction (a later now()).
    with engine.begin() as conn:
        act_as(conn, claims_for(gal))
        assert run(conn, _ACCEPT_RON, **ids).rowcount == 1
        first = run(conn, _RON_ROW, **ids).one()
    assert first.status == "accepted" and first.responded_at is not None

    with as_user(engine, gal) as conn:
        run(conn, _ACCEPT_RON, **ids)  # no error
        assert tuple(run(conn, _RON_ROW, **ids).one()) == tuple(first)
    with as_user(engine, ron) as conn:
        assert notifications_of(conn) == [("follow_accepted", "gal")]


def test_cancel_deletes_request_notification(people, engine):
    gal, ron = people["gal"], people["ron"]
    with as_user(engine, ron) as conn:
        deleted = run(conn, "DELETE FROM app.follows WHERE follower_id = :r", r=ron.id)
        assert deleted.rowcount == 1
        act_as(conn, claims_for(gal))
        assert notifications_of(conn) == [("follow_request", "dana")]


def test_decline_then_request_again(people, engine):
    gal, ron = people["gal"], people["ron"]
    request_ids = (
        "SELECT id FROM app.notifications"
        " WHERE recipient_id = :g AND actor_id = :r AND type = 'follow_request'"
    )
    with as_user(engine, gal) as conn:
        [old_id] = run(conn, request_ids, g=gal.id, r=ron.id).scalars().all()
        declined = run(conn, "DELETE FROM app.follows WHERE follower_id = :r", r=ron.id)
        assert declined.rowcount == 1

        act_as(conn, claims_for(ron))
        run(
            conn,
            "INSERT INTO app.follows (follower_id, followee_id) VALUES (:r, :g)",
            r=ron.id,
            g=gal.id,
        )
        rows = run(conn, "SELECT status FROM app.follows WHERE follower_id = :r", r=ron.id)
        assert rows.scalars().all() == ["pending"]

        act_as(conn, claims_for(gal))
        [new_id] = run(conn, request_ids, g=gal.id, r=ron.id).scalars().all()
        assert new_id != old_id


def test_self_follow_rejected(people, engine):
    gal = people["gal"]
    with as_user(engine, gal) as conn, pytest.raises(IntegrityError) as exc:
        run(conn, "INSERT INTO app.follows (follower_id, followee_id) VALUES (:g, :g)", g=gal.id)
    assert isinstance(exc.value.orig, psycopg.errors.CheckViolation)
    assert exc.value.orig.diag.constraint_name == "follows_check"
