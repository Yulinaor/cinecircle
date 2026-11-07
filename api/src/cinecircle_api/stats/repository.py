"""My Stats (plan P1, P2). Every function takes the request's `UserDb` connection and runs as the
signed-in user: the statements filter `author_id = auth.uid()` or lean on RLS, and none takes the
viewer's id as a parameter. The caller owns the transaction (never commit or roll back here)."""

from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa
from sqlalchemy import Connection

from cinecircle_api.catalog.parse import Locale, pick_text
from cinecircle_api.stats.models import (
    IMDB_BUCKET_KEYS,
    AgreementRow,
    GenreStat,
    ImdbBucket,
    ImdbStats,
    MyStats,
    RatingBucket,
    bucket_of,
    imdb_bucket,
)
from cinecircle_api.taste.repository import load_agreements
from cinecircle_api.taste.score import AGREE_MIN_COMMON, agreement, round_half_up

_MAX_GENRES = 5
_MAX_AGREEMENT = 5

# One rating per title (03 section 2: the whole-series rating when there is one, else the average
# of the season ratings), on the 1-10 scale. Each statement below starts with it.
MY_CTE = (
    "WITH my AS ("
    " SELECT title_id,"
    "  COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) AS r"
    " FROM app.posts WHERE author_id = auth.uid() GROUP BY title_id)"
)

# Each rated title with the exact (numeric) gap to the catalogue's IMDb rating, when it has one.
_RATED = sa.text(
    MY_CTE + " SELECT my.r, t.imdb_rating IS NOT NULL AS has_imdb, my.r - t.imdb_rating AS gap"
    " FROM my JOIN app.titles t ON t.id = my.title_id"
)

# The five genres with the most rated titles; ties go to the higher mean, then the lower id.
_GENRES = sa.text(
    MY_CTE + " SELECT g.id, g.name_en, g.name_he, count(*) AS n, round(avg(my.r), 1) AS mean"
    " FROM my JOIN app.title_genres tg ON tg.title_id = my.title_id"
    " JOIN app.genres g ON g.id = tg.genre_id"
    " GROUP BY g.id ORDER BY n DESC, avg(my.r) DESC, g.id LIMIT :limit"
)

# Cards are readable by every signed-in user (R5), so this adds nothing RLS would hide.
_CARDS = sa.text(
    "SELECT id, username, display_name, avatar_url FROM app.profiles WHERE id IN :ids"
).bindparams(sa.bindparam("ids", expanding=True))


def _distribution_and_imdb(conn: Connection) -> tuple[int, list[RatingBucket], ImdbStats]:
    counts = dict.fromkeys(range(1, 11), 0)
    gaps: list[Decimal] = []
    rated = 0
    for row in conn.execute(_RATED):
        rated += 1
        counts[bucket_of(float(row.r))] += 1
        if row.has_imdb:
            gaps.append(row.gap)
    by_key = dict.fromkeys(IMDB_BUCKET_KEYS, 0)
    for gap in gaps:
        by_key[imdb_bucket(float(gap))] += 1
    mean_gap = None
    if gaps:
        mean_gap = float((sum(gaps) / len(gaps)).quantize(Decimal("0.1"), ROUND_HALF_UP))
    return (
        rated,
        [RatingBucket(rating=n, count=count) for n, count in counts.items()],
        ImdbStats(
            compared=len(gaps),
            mean_gap=mean_gap,
            buckets=[ImdbBucket(key=key, count=count) for key, count in by_key.items()],
        ),
    )


def _genres(conn: Connection, lang: Locale) -> list[GenreStat]:
    return [
        GenreStat(
            id=row.id,
            name=pick_text(row.name_he, row.name_en, lang)[0] or row.name_en,
            count=row.n,
            mean=float(row.mean),
        )
        for row in conn.execute(_GENRES, {"limit": _MAX_GENRES})
    ]


def _agreement(conn: Connection) -> list[AgreementRow]:
    """The followed accounts the caller shares at least AGREE_MIN_COMMON rated titles with, best
    agreement first (the feed's number, 03 section 3); ties go to more common titles, then the
    username. `load_agreements` only sees shared posts RLS lets the caller read."""
    shared = {
        author_id: (common, round_half_up(100 * agreement(common, gap)))
        for author_id, (common, gap) in load_agreements(conn).items()
        if common >= AGREE_MIN_COMMON
    }
    if not shared:
        return []
    rows = [
        AgreementRow(
            username=card.username,
            display_name=card.display_name,
            avatar_url=card.avatar_url,
            agreement=shared[card.id][1],
            common=shared[card.id][0],
        )
        for card in conn.execute(_CARDS, {"ids": list(shared)})
    ]
    rows.sort(key=lambda row: (-row.agreement, -row.common, row.username))
    return rows[:_MAX_AGREEMENT]


def my_stats(conn: Connection, lang: Locale) -> MyStats:
    rated, distribution, imdb = _distribution_and_imdb(conn)
    return MyStats(
        rated=rated,
        distribution=distribution,
        genres=_genres(conn, lang),
        imdb=imdb,
        agreement=_agreement(conn),
    )
