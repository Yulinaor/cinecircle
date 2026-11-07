"""The two spec 03 section 6 loaders plus a title lookup. Every function takes the request's
`UserDb` connection: it runs as the signed-in user, so `auth.uid()` is the viewer and RLS hides
other people's private ratings and everyone the viewer may not see (plan P5). The caller owns the
transaction (never commit or roll back here)."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Connection

from cinecircle_api.catalog.parse import GenreRow
from cinecircle_api.posts.repository import genre_rows
from cinecircle_api.taste.score import GenreStat, TasteProfile

# The viewer's profile in one statement, over one rating per title (03 section 2: the
# whole-series rating when there is one, else the average of the season ratings): how many
# titles, their mean, each genre's count and mean, and the genres picked in onboarding.
_PROFILE = sa.text(
    "WITH my AS ("
    " SELECT title_id,"
    "  COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) / 10.0 AS r"
    " FROM app.posts WHERE author_id = auth.uid() GROUP BY title_id),"
    " per_genre AS ("
    "  SELECT tg.genre_id, count(*) AS n, avg(my.r) AS mean"
    "  FROM my JOIN app.title_genres tg ON tg.title_id = my.title_id"
    "  GROUP BY tg.genre_id)"
    " SELECT (SELECT count(*) FROM my) AS rated,"
    " (SELECT avg(r) FROM my) AS mean_all,"
    " COALESCE((SELECT json_agg(json_build_array(genre_id, n, mean)) FROM per_genre), '[]')"
    "  AS genres,"
    " COALESCE((SELECT json_agg(genre_id) FROM app.user_genre_prefs WHERE user_id = auth.uid()),"
    "  '[]') AS picked"
)

# Agreement with each author the viewer can see (03 section 6): mine = all my ratings, theirs =
# other people's shared ratings (RLS leaves only the ones the viewer may read). The gap is on the
# 1-10 scale; `score.agreement` turns it into a percentage.
_AGREEMENTS = sa.text(
    "WITH mine AS ("
    " SELECT title_id,"
    "  COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) AS r"
    " FROM app.posts WHERE author_id = auth.uid() GROUP BY title_id),"
    " theirs AS ("
    "  SELECT author_id, title_id,"
    "   COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) AS r"
    "  FROM app.posts WHERE author_id <> auth.uid() AND is_shared"
    "  GROUP BY author_id, title_id)"
    " SELECT t.author_id, count(*) AS common_titles, avg(abs(m.r - t.r)) AS mean_gap"
    " FROM mine m JOIN theirs t USING (title_id)"
    " GROUP BY t.author_id"
)

_TITLE_INPUTS = sa.text(
    "SELECT t.imdb_rating, t.tmdb_rating,"
    " COALESCE((SELECT json_agg(json_build_array(g.id, g.name_en, g.name_he) ORDER BY g.id)"
    "           FROM app.title_genres tg JOIN app.genres g ON g.id = tg.genre_id"
    "           WHERE tg.title_id = t.id), '[]') AS genres"
    " FROM app.titles t WHERE t.id = :id"
)


@dataclass(frozen=True)
class TitleInputs:
    """What the title formula needs from the catalogue."""

    genres: tuple[GenreRow, ...]
    imdb_rating: Decimal | None
    tmdb_rating: Decimal | None


def load_profile(conn: Connection) -> TasteProfile:
    """The caller's genre statistics over one rating per title, plus their genre picks."""
    row = conn.execute(_PROFILE).one()
    # The query groups by genre, so each genre id appears once.
    genres = {genre_id: GenreStat(n=n, mean=float(mean)) for genre_id, n, mean in row.genres}
    mean_all = float(row.mean_all) if row.mean_all is not None else None
    return TasteProfile(
        rated=row.rated, mean_all=mean_all, genres=genres, picked=frozenset(row.picked)
    )


def load_agreements(conn: Connection) -> dict[UUID, tuple[int, float]]:
    """Author id -> (titles both rated, mean rating gap) for every author whose shared ratings
    the caller can see and who share at least one rated title with them."""
    return {
        row.author_id: (row.common_titles, float(row.mean_gap)) for row in conn.execute(_AGREEMENTS)
    }


def title_inputs(conn: Connection, title_id: int) -> TitleInputs | None:
    """The title's genres and catalogue ratings, or None when it is not cached."""
    row = conn.execute(_TITLE_INPUTS, {"id": title_id}).one_or_none()
    if row is None:
        return None
    return TitleInputs(
        genres=genre_rows(row.genres), imdb_rating=row.imdb_rating, tmdb_rating=row.tmdb_rating
    )
