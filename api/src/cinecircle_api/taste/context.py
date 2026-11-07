"""A viewer's Taste Match, scored from data loaded once per request (plan P2, P4).

The profile is loaded up front; the agreements with other people only when a post by someone
else is first scored, and then once.
"""

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Connection

from cinecircle_api.catalog.parse import GenreRow, Locale
from cinecircle_api.posts.repository import PostRow
from cinecircle_api.taste import score
from cinecircle_api.taste.models import Taste
from cinecircle_api.taste.repository import load_agreements, load_profile
from cinecircle_api.taste.score import TasteProfile


def _float(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None


def _name(genre: GenreRow, lang: Locale) -> str:
    return genre.name_he if lang == "he" and genre.name_he else genre.name_en


def _unique(genres: Sequence[GenreRow]) -> list[GenreRow]:
    """The genres once each, in order: the score functions do not de-duplicate."""
    return list({genre.id: genre for genre in genres}.values())


class TasteContext:
    def __init__(self, conn: Connection, profile: TasteProfile) -> None:
        self._conn = conn
        self._profile = profile
        self._agreements: dict[UUID, tuple[int, float]] | None = None

    @classmethod
    def load(cls, conn: Connection) -> "TasteContext":
        return cls(conn, load_profile(conn))

    @property
    def unlocked(self) -> bool:
        return self._profile.state != "locked"

    def _agreement_with(self, author_id: UUID) -> tuple[int, float | None]:
        if self._agreements is None:
            self._agreements = load_agreements(self._conn)
        common, gap = self._agreements.get(author_id, (0, None))
        return common, gap

    def _reason_genres(self, genres: Sequence[GenreRow], lang: Locale) -> list[str]:
        by_id = {genre.id: genre for genre in genres}
        strong = score.strong_genres(self._profile, list(by_id))
        return [_name(by_id[genre_id], lang) for genre_id in strong]

    def for_post(self, row: PostRow, lang: Locale) -> Taste | None:
        """The feed formula for someone else's post; None for the viewer's own or when locked."""
        if row.author.follow_state == "self" or not self.unlocked:
            return None
        genres = _unique(row.genres)
        g = score.genre_fit(self._profile, [genre.id for genre in genres])
        q = score.quality(_float(row.imdb_rating), _float(row.tmdb_rating))
        agree, shown = 0.5, None
        if self._profile.state == "full":
            common, gap = self._agreement_with(row.author.id)
            agree = score.agreement(common, gap)
            if common >= score.AGREE_MIN_COMMON:
                shown = score.round_half_up(agree * 100)
        s = score.signal(agree, float(row.rating))
        return Taste(
            fit=score.feed_fit(g, s, q),
            genres=self._reason_genres(genres, lang),
            agreement=shown,
        )

    def for_title(
        self,
        genres: Sequence[GenreRow],
        imdb_rating: Decimal | float | None,
        tmdb_rating: Decimal | float | None,
        lang: Locale,
    ) -> Taste | None:
        """The Discover formula for a title with no user content; None when locked."""
        if not self.unlocked:
            return None
        unique = _unique(genres)
        g = score.genre_fit(self._profile, [genre.id for genre in unique])
        q = score.quality(_float(imdb_rating), _float(tmdb_rating))
        return Taste(
            fit=score.title_fit(g, q),
            genres=self._reason_genres(unique, lang),
            agreement=None,
        )
