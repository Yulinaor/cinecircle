"""The R5 visibility table (00-rules R5), proved in SQL for the four viewers.

Gal = owner, Dana = approved follower, Noa = stranger, Ron = pending request (sees what a
stranger sees). Every probe runs as the viewer through `as_user`, exactly as the API runs it,
and asks one question: "can this viewer see Gal's item?".
"""

import psycopg.errors
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

from cinecircle_api.stats.repository import MY_CTE
from cinecircle_api.taste.repository import _AGREEMENTS
from tests.integration.conftest import (
    GAL_PRIVATE_OPINION,
    GAL_SHARED_OPINION,
    as_user,
)
from tests.integration.test_people_rls import (
    assert_permission_denied,
    assert_rls_refused,
    run,
    scalar,
)

pytestmark = pytest.mark.integration

VIEWERS = ["gal", "dana", "noa", "ron"]
SEES = {  # R5 row -> viewers who can see Gal's item
    "card": {"gal", "dana", "noa", "ron"},
    "bio": {"gal", "dana"},
    "post_count": {"gal", "dana"},
    "shared_posts": {"gal", "dana"},
    "private_ratings": {"gal"},
    "follow_lists": {"gal"},
    "following_list": {"gal"},
    "wishlist": {"gal"},
    "my_stats": {"gal"},
    "notifications": {"gal"},
    "catalogue": {"gal", "dana", "noa", "ron"},
}
# Phase 3 read paths: the feed and title-page queries, run as each viewer.
FEED_SQL = (
    "SELECT count(*) = 1 FROM app.posts p WHERE p.is_shared AND (p.author_id = auth.uid()"
    " OR p.author_id IN (SELECT followee_id FROM app.follows"
    " WHERE follower_id = auth.uid() AND status = 'accepted'))"
)
TITLE_SQL = "SELECT count(*) = 1 FROM app.posts p WHERE p.title_id = {title}"
SEES |= {
    "home_feed": {"gal", "dana"},  # Gal's shared post appears in the viewer's Home query
    "title_page_shared": {"gal", "dana"},  # ... in the title-page query for title_ids[0]
    "title_page_private": {"gal"},  # Gal's private rating in the title-page query for title_ids[1]
    "private_in_feed": set(),  # Gal's private rating never appears in anyone's Home, Gal's too
}
PROBES = {  # SQL run as the viewer; True when Gal's item is visible
    "card": "SELECT count(*) = 1 FROM app.profiles WHERE id = :gal",
    "bio": "SELECT count(*) = 1 FROM app.profile_details WHERE user_id = :gal",
    "post_count": "SELECT count(*) = 1 FROM app.posts WHERE author_id = :gal AND is_shared",
    "shared_posts": "SELECT count(*) = 1 FROM app.posts WHERE id = :shared",
    "private_ratings": "SELECT count(*) = 1 FROM app.posts WHERE id = :private",
    "follow_lists": (
        "SELECT count(*) > 0 FROM app.follows"
        " WHERE followee_id = :gal AND follower_id <> auth.uid()"
    ),
    "following_list": (
        "SELECT count(*) > 0 FROM app.follows"
        " WHERE follower_id = :gal AND followee_id <> auth.uid()"
    ),
    "wishlist": "SELECT count(*) > 0 FROM app.wishlist_items WHERE owner_id = :gal",
    "my_stats": "SELECT count(*) = 2 FROM app.posts WHERE author_id = :gal",  # whole history
    "notifications": "SELECT count(*) > 0 FROM app.notifications WHERE recipient_id = :gal",
    "catalogue": "SELECT count(*) = 2 FROM app.titles",
}
PROBES |= {
    "home_feed": FEED_SQL + " AND p.id = :shared",
    "title_page_shared": TITLE_SQL.format(title=":title1") + " AND p.id = :shared",
    "title_page_private": TITLE_SQL.format(title=":title2") + " AND p.id = :private",
    "private_in_feed": FEED_SQL + " AND p.id = :private",
}
SEES |= {
    "wishlist_on_title": {"gal"},  # the in_wishlist probe (P5) for title_ids[1]
    "wishlist_rls_only": {"gal"},  # no owner filter at all: RLS alone hides Gal's row
}
PROBES |= {
    "wishlist_on_title": (
        "SELECT EXISTS (SELECT 1 FROM app.wishlist_items w"
        " WHERE w.owner_id = auth.uid() AND w.title_id = :title2)"
    ),
    "wishlist_rls_only": "SELECT count(*) > 0 FROM app.wishlist_items WHERE title_id = :title2",
}
SEES |= {"genre_prefs": {"gal"}, "events": {"gal"}}  # Taste Match inputs and logs (Phase 5)
PROBES |= {
    "genre_prefs": "SELECT count(*) > 0 FROM app.user_genre_prefs WHERE user_id = :gal",
    "events": "SELECT count(*) > 0 FROM app.events WHERE user_id = :gal",
}
SEES |= {"external_reviews": {"gal", "dana", "noa", "ron"}}  # TMDB reviews: catalogue data (P7)
PROBES |= {"external_reviews": "SELECT count(*) = 1 FROM app.external_reviews"}
SEES |= {
    "stats_ratings": {"gal"},  # the My Stats `my` CTE holds only the viewer's own ratings
    "stats_agreement_with_gal": {"dana"},  # Gal is an author in the viewer's agreement rows
}
PROBES |= {
    "stats_ratings": MY_CTE + " SELECT count(*) > 0 FROM my WHERE title_id = :title2",
    # `load_agreements`' statement as is; it needs a rated title in common with Gal.
    "stats_agreement_with_gal": (
        "SELECT count(*) > 0 FROM (" + _AGREEMENTS.text + ") a WHERE a.author_id = :gal"
    ),
}
# Statements run as the viewer, in the probe's transaction, before the probe (rolled back after).
SETUP = {
    "stats_agreement_with_gal": (
        "INSERT INTO app.posts (author_id, title_id, rating, is_shared)"
        " VALUES (auth.uid(), :title1, 7.5, false) ON CONFLICT DO NOTHING"
    ),
}
CONTENT_TABLES = ["posts", "wishlist_items", "user_genre_prefs", "events"]


def test_matrix_covers_every_probe():
    assert SEES.keys() == PROBES.keys()


@pytest.mark.parametrize("row", SEES)
@pytest.mark.parametrize("viewer", VIEWERS)
def test_r5_visibility(row, viewer, people, gal_content, engine):
    params = {
        "gal": people["gal"].id,
        "shared": gal_content.shared_post_id,
        "private": gal_content.private_post_id,
        "title1": gal_content.title_ids[0],
        "title2": gal_content.title_ids[1],
    }
    with as_user(engine, people[viewer]) as conn:
        if row in SETUP:
            conn.execute(sa.text(SETUP[row]), params)
        assert conn.scalar(sa.text(PROBES[row]), params) is (viewer in SEES[row])


@pytest.mark.parametrize("viewer", ["dana", "noa", "ron"])
def test_others_never_see_gals_private_content(viewer, people, gal_content, engine):
    """Opinion text, not just row counts: nothing of the private rating leaks to anyone else."""
    with as_user(engine, people[viewer]) as conn:
        opinions = run(conn, "SELECT opinion FROM app.posts").scalars().all()
        assert GAL_PRIVATE_OPINION not in opinions
        assert opinions == ([GAL_SHARED_OPINION] if viewer == "dana" else [])
        for table, owner_col in (
            ("wishlist_items", "owner_id"),
            ("user_genre_prefs", "user_id"),
            ("events", "user_id"),
        ):
            sql = f"SELECT count(*) FROM app.{table} WHERE {owner_col} = :g"
            assert scalar(conn, sql, g=people["gal"].id) == 0, table


# ----- exact GRANTs for `authenticated` --------------------------------------------------------

POST_COLS = {
    "author_id",
    "title_id",
    "season_number",
    "rating",
    "opinion",
    "contains_spoilers",
    "is_shared",
}
GRANTS = {  # table: (insert columns, update columns, delete); never a whole-table INSERT/UPDATE
    "posts": (
        POST_COLS,
        {"rating", "opinion", "contains_spoilers", "is_shared"},  # updated_at: the trigger's
        True,
    ),
    "wishlist_items": (
        # no added_at (server clock) and no watched_at (the trigger's)
        {"owner_id", "title_id", "source", "source_post_id", "status", "fit_at_save"},
        {"status"},  # watched_at: the trigger's
        True,
    ),
    "user_genre_prefs": ({"user_id", "genre_id"}, set(), True),
    "events": (
        # no id (would run ahead of events_id_seq) and no created_at (server clock)
        {"user_id", "event_type", "title_id", "post_id", "props"},
        set(),
        False,
    ),
}


@pytest.mark.parametrize("table", CONTENT_TABLES)
def test_authenticated_grants_are_exact(engine, table):
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

        def table_priv(priv: str, role: str = "authenticated") -> bool:
            return scalar(
                conn,
                "SELECT has_table_privilege(:r, CAST(:t AS regclass), :p)",
                r=role,
                t=f"app.{table}",
                p=priv,
            )

        assert table_priv("SELECT") is True
        assert columns_with("INSERT") == insert_cols
        assert columns_with("UPDATE") == update_cols
        assert table_priv("INSERT") is False  # only the columns above
        assert table_priv("UPDATE") is False  # never the whole table: only the columns above
        assert table_priv("DELETE") is delete
        assert table_priv("TRUNCATE, REFERENCES, TRIGGER") is False
        for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):  # one at a time: a list means ANY
            assert table_priv(priv, role="service_role") is True, priv


@pytest.mark.parametrize("viewer", VIEWERS)
def test_discover_cache_is_not_readable_by_anyone_signed_in(viewer, people, engine):
    """The Discover list cache is service-only: no viewer can read it, whoever they follow."""
    with as_user(engine, people[viewer]) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, "SELECT count(*) FROM app.discover_cache")
    assert_permission_denied(exc, "discover_cache")


@pytest.mark.parametrize("seq", ["posts_id_seq", "events_id_seq"])
def test_sequence_grants_are_exact(engine, seq):
    with engine.connect() as conn:

        def has(role: str, priv: str) -> bool:
            return scalar(
                conn,
                "SELECT has_sequence_privilege(:r, CAST(:s AS regclass), :p)",
                r=role,
                s=f"app.{seq}",
                p=priv,
            )

        assert has("authenticated", "USAGE") is True
        assert has("authenticated", "SELECT") is False
        assert has("authenticated", "UPDATE") is False
        assert has("anon", "USAGE, SELECT, UPDATE") is False


def test_anon_reads_no_user_content(people, gal_content, engine):
    for table in CONTENT_TABLES:
        with engine.connect() as conn, pytest.raises(ProgrammingError) as exc:
            run(conn, "SET LOCAL ROLE anon")
            run(conn, f"SELECT * FROM app.{table}")
        assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege), table
    with engine.connect() as conn:
        for table in CONTENT_TABLES:
            held = scalar(
                conn,
                "SELECT has_table_privilege('anon', CAST(:t AS regclass),"
                " 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')",
                t=f"app.{table}",
            )
            assert held is False, table


# ----- writing past the rules ------------------------------------------------------------------

_INSERT_POST = (
    "INSERT INTO app.posts (author_id, title_id, rating, is_shared) VALUES (:a, :t, 7.5, true)"
)


def test_cannot_write_as_someone_else(people, gal_content, engine):
    gal, dana, noa = people["gal"], people["dana"], people["noa"]
    shared, private = gal_content.shared_post_id, gal_content.private_post_id

    # noa posts as gal: refused by the WITH CHECK of posts_write
    with as_user(engine, noa) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, _INSERT_POST, a=gal.id, t=gal_content.title_ids[0])
    assert_rls_refused(exc, "posts")

    # dana (approved follower, can SEE the shared post) still cannot change or delete it
    with as_user(engine, dana) as conn:
        for sql in (
            "UPDATE app.posts SET opinion = 'hacked', rating = 1 WHERE id = :p",
            "DELETE FROM app.posts WHERE id = :p",
        ):
            for post_id in (shared, private):
                assert run(conn, sql, p=post_id).rowcount == 0, (sql, post_id)
    with as_user(engine, gal) as conn:
        rows = run(conn, "SELECT opinion, rating FROM app.posts ORDER BY id").all()
        assert [tuple(r) for r in rows] == [(GAL_SHARED_OPINION, 9.0), (GAL_PRIVATE_OPINION, 4.5)]

    # dana files a wishlist item under gal's name
    with as_user(engine, dana) as conn, pytest.raises(ProgrammingError) as exc:
        run(
            conn,
            "INSERT INTO app.wishlist_items (owner_id, title_id, source) VALUES (:o, :t, 'search')",
            o=gal.id,
            t=gal_content.title_ids[0],
        )
    assert_rls_refused(exc, "wishlist_items")

    # same for genre prefs and events
    with as_user(engine, dana) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, "INSERT INTO app.user_genre_prefs (user_id, genre_id) VALUES (:o, 28)", o=gal.id)
    assert_rls_refused(exc, "user_genre_prefs")
    with as_user(engine, dana) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, "INSERT INTO app.events (user_id, event_type) VALUES (:o, 'saved')", o=gal.id)
    assert_rls_refused(exc, "events")


def test_events_are_append_only(people, gal_content, engine):
    gal = people["gal"]
    for sql in ("UPDATE app.events SET event_type = 'x'", "DELETE FROM app.events"):
        with as_user(engine, gal) as conn, pytest.raises(ProgrammingError) as exc:
            run(conn, sql)
        assert_permission_denied(exc, "events")


@pytest.mark.parametrize(
    ("table", "sql"),
    [
        ("events", "INSERT INTO app.events (user_id, event_type, id) VALUES (:a, 'x', 999999)"),
        (
            "events",
            "INSERT INTO app.events (user_id, event_type, created_at)"
            " VALUES (:a, 'x', now() - interval '1 year')",
        ),
        (
            "wishlist_items",
            "INSERT INTO app.wishlist_items (owner_id, title_id, source, added_at)"
            " VALUES (:a, :t, 'search', now() - interval '1 year')",
        ),
        (
            "wishlist_items",
            "INSERT INTO app.wishlist_items (owner_id, title_id, source, watched_at)"
            " VALUES (:a, :t, 'search', now())",
        ),
    ],
)
def test_server_owned_insert_columns_are_denied(table, sql, people, gal_content, engine):
    with as_user(engine, people["dana"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, sql, a=people["dana"].id, t=gal_content.title_ids[0])
    assert_permission_denied(exc, table)


def test_post_ownership_and_timestamps_are_not_writable(people, gal_content, engine):
    for column, value in (
        ("author_id", "(SELECT id FROM app.profiles WHERE username = 'noa')"),
        ("title_id", "1"),
        ("created_at", "now()"),
    ):
        with as_user(engine, people["gal"]) as conn, pytest.raises(ProgrammingError) as exc:
            run(
                conn,
                f"UPDATE app.posts SET {column} = {value} WHERE id = :p",
                p=gal_content.shared_post_id,
            )
        assert_permission_denied(exc, "posts")


def test_owner_can_manage_own_content(people, gal_content, engine):
    gal = people["gal"]
    first, second = gal_content.title_ids
    with as_user(engine, gal) as conn:
        # delete + re-create through the sequence, then edit within the granted columns
        mine = run(conn, "DELETE FROM app.posts WHERE id = :p", p=gal_content.private_post_id)
        assert mine.rowcount == 1
        new_id = scalar(
            conn,
            "INSERT INTO app.posts (author_id, title_id, rating, opinion, is_shared)"
            " VALUES (:a, :t, 8, 'again', false) RETURNING id",
            a=gal.id,
            t=second,
        )
        assert new_id > gal_content.private_post_id
        updated = run(
            conn,
            "UPDATE app.posts SET rating = 6.5, is_shared = true WHERE id = :p",
            p=new_id,
        )
        assert updated.rowcount == 1
        assert scalar(conn, "SELECT rating FROM app.posts WHERE id = :p", p=new_id) == 6.5

        # wishlist, genre prefs and events
        assert (
            run(
                conn,
                "UPDATE app.wishlist_items SET status = 'watched'"
                " WHERE owner_id = :a AND title_id = :t",
                a=gal.id,
                t=second,
            ).rowcount
            == 1
        )
        run(
            conn,
            "INSERT INTO app.wishlist_items (owner_id, title_id, source, source_post_id)"
            " VALUES (:a, :t, 'post', :p)",
            a=gal.id,
            t=first,
            p=gal_content.shared_post_id,
        )
        wishes = run(conn, "DELETE FROM app.wishlist_items WHERE owner_id = :a", a=gal.id)
        assert wishes.rowcount == 2
        prefs = run(conn, "DELETE FROM app.user_genre_prefs WHERE user_id = :a", a=gal.id)
        assert prefs.rowcount == 1
        event_id = scalar(
            conn,
            "INSERT INTO app.events (user_id, event_type, props) VALUES (:a, 'saved', '{}')"
            " RETURNING id",
            a=gal.id,
        )
        assert event_id is not None
        assert scalar(conn, "SELECT count(*) FROM app.events") == 2
