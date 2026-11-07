"""Discover's two tables: reviews are catalogue data any signed-in user may read, the list
cache is service-only, and nobody but the service writes either (plan P3, P7)."""

import psycopg.errors
import pytest
from sqlalchemy.exc import DBAPIError, ProgrammingError

from tests.integration.conftest import as_user
from tests.integration.test_people_rls import assert_permission_denied, run, scalar

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]

_INSERT_TITLE = (
    "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
    " VALUES (603, 'movie', 'The Matrix', '{}') RETURNING id"
)
_INSERT_REVIEW = (
    "INSERT INTO app.external_reviews"
    " (title_id, source_review_id, author_name, excerpt, url, author_rating)"
    " VALUES (:t, :rid, 'NeoBrowser', 'Great', 'https://www.themoviedb.org/review/1', 9.5)"
)


@pytest.fixture
def matrix_title(engine) -> int:
    with engine.begin() as conn:
        title_id = scalar(conn, _INSERT_TITLE)
        run(conn, _INSERT_REVIEW, t=title_id, rid="r1")
        run(
            conn,
            "INSERT INTO app.discover_cache (list_key, locale, payload)"
            " VALUES ('trending:movie:week', 'he', '[]')",
        )
    yield title_id
    with engine.begin() as conn:
        run(conn, "DELETE FROM app.discover_cache")


def test_reviews_are_readable_cache_is_not(people, matrix_title, engine):
    with as_user(engine, people["dana"]) as conn:
        assert scalar(conn, "SELECT count(*) FROM app.external_reviews") == 1
        assert scalar(conn, "SELECT reviews_fetched_at IS NULL FROM app.titles") is True
    with as_user(engine, people["dana"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, "SELECT * FROM app.discover_cache")
    assert_permission_denied(exc, "discover_cache")


@pytest.mark.parametrize(
    ("table", "sql"),
    [
        ("external_reviews", _INSERT_REVIEW),
        (
            "discover_cache",
            "INSERT INTO app.discover_cache (list_key, locale, payload) VALUES ('x', 'he', '[]')",
        ),
    ],
)
def test_users_cannot_write_catalogue_tables(people, matrix_title, engine, table, sql):
    with as_user(engine, people["dana"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, sql, t=matrix_title, rid="r2")
    assert_permission_denied(exc, table)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE app.external_reviews SET excerpt = 'x'",
        "DELETE FROM app.external_reviews",
        "UPDATE app.titles SET reviews_fetched_at = now()",
        "UPDATE app.discover_cache SET payload = '[]'",
        "DELETE FROM app.discover_cache",
    ],
)
def test_users_cannot_change_or_delete_either(people, matrix_title, engine, sql):
    with as_user(engine, people["noa"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, sql)
    assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege)


@pytest.mark.parametrize("table", ["external_reviews", "discover_cache"])
def test_table_privileges_are_exact(engine, table):
    with engine.connect() as conn:

        def has(role: str, priv: str) -> bool:
            return scalar(
                conn,
                "SELECT has_table_privilege(:r, CAST(:t AS regclass), :p)",
                r=role,
                t=f"app.{table}",
                p=priv,
            )

        for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            assert has("authenticated", priv) is False, priv
        assert has("authenticated", "SELECT") is (table == "external_reviews")
        for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):  # one at a time: a list means ANY
            assert has("service_role", priv) is True, priv
        for priv in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            assert has("anon", priv) is False, priv
        assert scalar(
            conn,
            "SELECT relrowsecurity FROM pg_class WHERE oid = CAST(:t AS regclass)",
            t=f"app.{table}",
        )


def test_anon_reads_neither(engine, matrix_title):
    for table in ("external_reviews", "discover_cache"):
        with engine.connect() as conn, pytest.raises(ProgrammingError) as exc:
            run(conn, "SET LOCAL ROLE anon")
            run(conn, f"SELECT * FROM app.{table}")
        assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege), table


def test_service_session_writes_both_and_the_ddl_holds(engine, matrix_title):
    with engine.begin() as conn:
        run(conn, "SET LOCAL ROLE service_role")
        run(conn, _INSERT_REVIEW, t=matrix_title, rid="r2")
        run(conn, "UPDATE app.titles SET reviews_fetched_at = now() WHERE id = :t", t=matrix_title)
        run(
            conn,
            "INSERT INTO app.discover_cache (list_key, locale, payload)"
            " VALUES ('recs:movie:603', 'en', '[{\"tmdb_id\": 1}]')",
        )
        assert scalar(conn, "SELECT count(*) FROM app.external_reviews") == 2
        assert (
            scalar(conn, "SELECT source FROM app.external_reviews WHERE source_review_id='r2'")
            == "tmdb"
        )
        assert scalar(conn, "SELECT fetched_at IS NOT NULL FROM app.discover_cache LIMIT 1")
        assert scalar(conn, "SELECT reviews_fetched_at IS NOT NULL FROM app.titles") is True


def test_review_rules(engine, matrix_title):
    with engine.connect() as conn:
        conn.begin()
        with pytest.raises(DBAPIError) as long_excerpt:  # char_length(excerpt) <= 300
            run(
                conn,
                "INSERT INTO app.external_reviews (title_id, source_review_id, author_name,"
                " excerpt, url) VALUES (:t, 'long', 'a', repeat('x', 301), 'https://x.test')",
                t=matrix_title,
            )
        assert isinstance(long_excerpt.value.orig, psycopg.errors.CheckViolation)
        conn.rollback()
        conn.begin()
        with pytest.raises(DBAPIError) as dup:  # UNIQUE (source, source_review_id)
            run(conn, _INSERT_REVIEW, t=matrix_title, rid="r1")
        assert isinstance(dup.value.orig, psycopg.errors.UniqueViolation)


def test_reviews_follow_their_title_and_have_a_title_index(engine, matrix_title):
    with engine.connect() as conn:
        index_cols = (
            run(
                conn,
                "SELECT pg_get_indexdef(indexrelid) FROM pg_index"
                " WHERE indrelid = 'app.external_reviews'::regclass",
            )
            .scalars()
            .all()
        )
    assert any("(title_id)" in d for d in index_cols), index_cols
    with engine.begin() as conn:
        run(conn, "DELETE FROM app.titles WHERE id = :t", t=matrix_title)
        assert scalar(conn, "SELECT count(*) FROM app.external_reviews") == 0
