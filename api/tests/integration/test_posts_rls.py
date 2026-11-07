"""Posts rules in SQL: the season trigger, `updated_at`, who may change a post, new indexes.

Gal = owner, Dana = approved follower who can see his shared post, Noa = stranger (see conftest).
"""

import psycopg.errors
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, ProgrammingError

from cinecircle_api.db import act_as
from tests.integration.conftest import GAL, as_user, claims_for, insert_series
from tests.integration.test_people_rls import assert_permission_denied, run, scalar

pytestmark = pytest.mark.integration

_INSERT = (
    "INSERT INTO app.posts (author_id, title_id, season_number, rating)"
    " VALUES (auth.uid(), :t, :s, 8)"
)


def _is_season_violation(conn: sa.Connection, title_id: int, season: int) -> bool:
    """Try the insert in a savepoint; True when refused by the `posts_season_valid` rule."""
    try:
        with conn.begin_nested():
            run(conn, _INSERT, t=title_id, s=season)
    except IntegrityError as exc:
        assert isinstance(exc.orig, psycopg.errors.CheckViolation)
        assert exc.orig.diag.constraint_name == "posts_season_valid"
        return True
    return False


def test_season_trigger(people, clean_catalog, engine):
    with engine.begin() as conn:  # as postgres
        movie = conn.scalar(
            sa.text(
                "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
                " VALUES (1, 'movie', 'A movie', '{}') RETURNING id"
            )
        )
        series = insert_series(conn, 2, (1, 2))
    with as_user(engine, people["gal"]) as conn:
        assert _is_season_violation(conn, movie, 1) is True  # a movie has no seasons
        assert _is_season_violation(conn, series, 3) is True  # the series stops at 2
        assert _is_season_violation(conn, series, -1) is True
        assert _is_season_violation(conn, movie, -1) is True
        assert _is_season_violation(conn, series, 1) is False
        assert _is_season_violation(conn, series, 0) is False  # whole series beside season 1
        assert _is_season_violation(conn, movie, 0) is False
        assert scalar(conn, "SELECT count(*) FROM app.posts") == 3


def test_season_trigger_rechecks_when_season_changes(people, clean_catalog, engine):
    """The trigger also fires when season_number / title_id change (service-role path)."""
    with engine.begin() as conn:
        series = insert_series(conn, 3, (1,))
        post = conn.scalar(
            sa.text(
                "INSERT INTO app.posts (author_id, title_id, season_number, rating)"
                " VALUES (:a, :t, 1, 8) RETURNING id"
            ),
            {"a": GAL.id, "t": series},
        )
    with engine.connect() as conn, pytest.raises(IntegrityError) as exc:  # as postgres
        run(conn, "UPDATE app.posts SET season_number = 9 WHERE id = :p", p=post)
    assert exc.value.orig.diag.constraint_name == "posts_season_valid"


def test_updated_at_moves_only_on_real_change(people, gal_content, engine):
    post = gal_content.shared_post_id
    # Separate committed transactions: within one, now() would not move.
    with engine.begin() as conn:
        act_as(conn, claims_for(GAL))
        run(conn, "UPDATE app.posts SET rating = 8.5 WHERE id = :p", p=post)
    with engine.connect() as conn:
        created, updated = run(
            conn, "SELECT created_at, updated_at FROM app.posts WHERE id = :p", p=post
        ).one()
    assert updated > created

    with engine.begin() as conn:
        act_as(conn, claims_for(GAL))
        run(
            conn,
            "UPDATE app.posts SET rating = rating, is_shared = is_shared WHERE id = :p",
            p=post,
        )
    with engine.connect() as conn:
        again = scalar(conn, "SELECT updated_at FROM app.posts WHERE id = :p", p=post)
    assert again == updated  # a save that changes nothing does not mark the post edited


def test_cannot_set_updated_at(people, gal_content, engine):
    with as_user(engine, people["gal"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(
            conn,
            "UPDATE app.posts SET updated_at = '2000-01-01' WHERE id = :p",
            p=gal_content.shared_post_id,
        )
    assert_permission_denied(exc, "posts")


def test_only_author_updates_or_deletes(people, gal_content, engine):
    shared = gal_content.shared_post_id
    for key in ("dana", "noa"):  # Dana can see the post; Noa cannot
        with as_user(engine, people[key]) as conn:
            update = run(conn, "UPDATE app.posts SET rating = 1 WHERE id = :p", p=shared)
            assert update.rowcount == 0, key
            assert run(conn, "DELETE FROM app.posts WHERE id = :p", p=shared).rowcount == 0, key
    with as_user(engine, people["gal"]) as conn:
        assert scalar(conn, "SELECT rating FROM app.posts WHERE id = :p", p=shared) == 9.0


def test_new_indexes_exist(engine):
    wanted = {
        "notifications_recipient_created_idx",
        "follows_followee_idx",
        "posts_title_created_idx",
    }
    with engine.connect() as conn:
        found = run(
            conn,
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'app' AND indexname = ANY(:names)",
            names=sorted(wanted),
        ).scalars()
        assert set(found) == wanted
