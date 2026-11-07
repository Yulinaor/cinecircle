"""Hand-written SQL for the taste quiz. Every function takes the request's `UserDb` connection
(`auth.uid()` is the caller) and the caller owns the transaction (never commit or roll back)."""

from collections.abc import Iterable
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from cinecircle_api.onboarding.models import (
    GENRE_CHIPS,
    QUIZ_POOL,
    GenreChip,
    OnboardingState,
    QuizRating,
    QuizTitle,
)
from cinecircle_api.posts.repository import TitleMissing

_TITLE_FKEY = "posts_title_id_fkey"
_PICKS = sa.text("SELECT genre_id FROM app.user_genre_prefs WHERE user_id = auth.uid()")
# The caller's own season-0 rating on each cached pool title, private or shared. The two arrays
# only prefilter; the (media_type, tmdb_id) pairs are matched exactly in `state`.
_MY_QUIZ_RATINGS = sa.text(
    "SELECT t.media_type, t.tmdb_id, p.rating"
    " FROM app.posts p JOIN app.titles t ON t.id = p.title_id"
    " WHERE p.author_id = auth.uid() AND p.season_number = 0"
    "   AND t.media_type = ANY(:media_types) AND t.tmdb_id = ANY(:tmdb_ids)"
)
_DELETE_PICKS = sa.text("DELETE FROM app.user_genre_prefs WHERE user_id = auth.uid()")
# Two submits at once can both insert the same pick: the second finds it there and adds nothing.
_INSERT_PICK = sa.text(
    "INSERT INTO app.user_genre_prefs (user_id, genre_id) VALUES (auth.uid(), :genre_id)"
    " ON CONFLICT DO NOTHING"
)
# A title the caller already posted on (season 0) keeps its post: the conflict inserts nothing.
_INSERT_PRIVATE = sa.text(
    "INSERT INTO app.posts (author_id, title_id, season_number, rating, is_shared)"
    " VALUES (auth.uid(), :title_id, 0, :rating, false)"
    " ON CONFLICT (author_id, title_id, season_number) DO NOTHING"
    " RETURNING id"
)


def state(conn: Connection) -> OnboardingState:
    picks = set(conn.execute(_PICKS).scalars())
    params = {
        "media_types": sorted({media_type for media_type, _ in QUIZ_POOL}),
        "tmdb_ids": [tmdb_id for _, tmdb_id in QUIZ_POOL],
    }
    mine = {
        (row.media_type, row.tmdb_id): float(row.rating)
        for row in conn.execute(_MY_QUIZ_RATINGS, params)
    }
    return OnboardingState(
        done=bool(picks),
        genres=[
            GenreChip(key=key, picked=picks.issuperset(ids))  # type: ignore[arg-type]
            for key, ids in GENRE_CHIPS.items()
        ],
        quiz=[
            QuizTitle(
                media_type=media_type, tmdb_id=tmdb_id, my_rating=mine.get((media_type, tmdb_id))
            )
            for media_type, tmdb_id in QUIZ_POOL
        ],
    )


def replace_picks(conn: Connection, genre_ids: set[int]) -> None:
    """The caller's genre picks become exactly `genre_ids` (which must exist in app.genres)."""
    conn.execute(_DELETE_PICKS)
    if genre_ids:
        conn.execute(_INSERT_PICK, [{"genre_id": genre_id} for genre_id in sorted(genre_ids)])


def add_private_ratings(conn: Connection, ratings: Iterable[QuizRating]) -> list[tuple[int, int]]:
    """Insert each rating as the caller's private season-0 post. Returns (title_id, post_id) of
    the posts that are new; a title the caller already posted on is skipped. An unknown title
    raises `TitleMissing`."""
    created: list[tuple[int, int]] = []
    for rating in ratings:
        params = {"title_id": rating.title_id, "rating": Decimal(str(rating.rating))}
        try:
            with conn.begin_nested():  # an expected violation must not poison the transaction
                post_id = conn.execute(_INSERT_PRIVATE, params).scalar_one_or_none()
        except IntegrityError as exc:
            if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == _TITLE_FKEY:
                raise TitleMissing from None
            raise
        if post_id is not None:
            created.append((rating.title_id, post_id))
    return created
