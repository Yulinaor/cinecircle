"""Wishlist rules in SQL: the source check, the `watched_at` clock, who may write which column.

Gal = owner of the shared post (title 1) and the private rating (title 2), Dana = approved
follower who can see his shared post, Noa = stranger (see conftest).
"""

import psycopg.errors
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, ProgrammingError

from cinecircle_api.db import act_as
from tests.integration.conftest import as_user, claims_for
from tests.integration.test_people_rls import assert_permission_denied, run, scalar

pytestmark = pytest.mark.integration

_INSERT = (
    "INSERT INTO app.wishlist_items (owner_id, title_id, source, source_post_id, status)"
    " VALUES (auth.uid(), :t, :src, :p, :st)"
)


def _try_insert(conn: sa.Connection, title_id, source, post_id=None, status="want"):
    """Insert in a savepoint; the IntegrityError when refused, else None."""
    try:
        with conn.begin_nested():
            run(conn, _INSERT, t=title_id, src=source, p=post_id, st=status)
    except IntegrityError as exc:
        return exc
    return None


def _assert_source_violation(exc: IntegrityError | None) -> None:
    assert exc is not None
    assert isinstance(exc.orig, psycopg.errors.CheckViolation)
    assert exc.orig.diag.constraint_name == "wishlist_source_valid"


def test_source_post_must_be_visible_on_the_same_title(people, gal_content, engine):
    first, second = gal_content.title_ids
    shared, private = gal_content.shared_post_id, gal_content.private_post_id
    with as_user(engine, people["dana"]) as conn:
        _assert_source_violation(_try_insert(conn, second, "post", shared))  # wrong title
        _assert_source_violation(_try_insert(conn, second, "post", private))  # cannot see it
        _assert_source_violation(_try_insert(conn, first, "post", private))  # nor on its title
        _assert_source_violation(_try_insert(conn, first, "post", None))  # post without a post
        # a post id on any other source is refused too (trigger or the table CHECK)
        _assert_source_violation(_try_insert(conn, first, "search", shared))
        assert _try_insert(conn, first, "post", shared) is None
        assert scalar(conn, "SELECT count(*) FROM app.wishlist_items") == 1


def test_source_post_hidden_and_missing_fail_alike(people, gal_content, engine):
    """Noa cannot see Gal's shared post: it must look exactly like a post that does not exist."""
    title = gal_content.title_ids[0]
    with as_user(engine, people["noa"]) as conn:
        hidden = _try_insert(conn, title, "post", gal_content.shared_post_id)
        missing = _try_insert(conn, title, "post", 999999999)
    _assert_source_violation(hidden)
    _assert_source_violation(missing)
    assert hidden.orig.diag.constraint_name == missing.orig.diag.constraint_name
    assert hidden.orig.diag.message_primary == missing.orig.diag.message_primary
    assert str(gal_content.shared_post_id) not in hidden.orig.diag.message_primary


def _watched_at(conn: sa.Connection, owner, title):
    return scalar(
        conn,
        "SELECT watched_at FROM app.wishlist_items WHERE owner_id = :o AND title_id = :t",
        o=owner.id,
        t=title,
    )


def test_watched_at_follows_status(people, gal_content, engine):
    gal = people["gal"]
    first, second = gal_content.title_ids  # Gal's item is on `second`, status 'want'

    def update_status(status: str):
        # Separate committed transactions: within one, now() would not move.
        with engine.begin() as conn:
            act_as(conn, claims_for(gal))
            run(
                conn,
                "UPDATE app.wishlist_items SET status = :s WHERE title_id = :t",
                s=status,
                t=second,
            )
            return _watched_at(conn, gal, second)

    with as_user(engine, gal) as conn:
        assert _watched_at(conn, gal, second) is None

    stamped = update_status("watched")
    assert stamped is not None
    assert update_status("watched") == stamped  # saving "watched" again does not move the clock
    assert update_status("want") is None  # taking it back clears it

    with engine.begin() as conn:  # inserted as already watched
        act_as(conn, claims_for(gal))
        run(conn, _INSERT, t=first, src="search", p=None, st="watched")
        assert _watched_at(conn, gal, first) is not None


def test_cannot_set_watched_at(people, gal_content, engine):
    with as_user(engine, people["gal"]) as conn, pytest.raises(ProgrammingError) as exc:
        run(conn, "UPDATE app.wishlist_items SET watched_at = now()")
    assert_permission_denied(exc, "wishlist_items")


def test_via_join_hides_with_the_post(people, gal_content, engine):
    """Dana keeps her item when she loses sight of Gal's post; the post just stops joining."""
    dana, gal = people["dana"], people["gal"]
    first = gal_content.title_ids[0]
    with engine.begin() as conn:
        act_as(conn, claims_for(dana))
        run(conn, _INSERT, t=first, src="post", p=gal_content.shared_post_id, st="want")
    via = (
        "SELECT w.title_id, p.id FROM app.wishlist_items w"
        " LEFT JOIN app.posts p ON p.id = w.source_post_id WHERE w.owner_id = auth.uid()"
    )
    with as_user(engine, dana) as conn:
        assert [tuple(r) for r in run(conn, via)] == [(first, gal_content.shared_post_id)]
    with engine.begin() as conn:  # as postgres: Dana stops following Gal
        run(
            conn,
            "DELETE FROM app.follows WHERE follower_id = :d AND followee_id = :g",
            d=dana.id,
            g=gal.id,
        )
    with as_user(engine, dana) as conn:
        assert [tuple(r) for r in run(conn, via)] == [(first, None)]
        assert scalar(conn, "SELECT source_post_id FROM app.wishlist_items") == (
            gal_content.shared_post_id
        )
