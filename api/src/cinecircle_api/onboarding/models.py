"""The taste quiz (plan P6-P8): the fixed genre chips and quiz pool, what the web sends and what it
gets back. Chip names live in the web's i18n; the API only knows keys and TMDB genre ids."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from cinecircle_api.catalog.parse import MediaType
from cinecircle_api.pagination import BIGINT_MAX
from cinecircle_api.posts.models import Rating

# Each chip maps to its TMDB movie and TV genre ids (TV lists merge some genres, P7). Order is
# the order the quiz shows them in.
GENRE_CHIPS: dict[str, tuple[int, ...]] = {
    "action": (28, 10759),
    "adventure": (12, 10759),
    "animation": (16,),
    "comedy": (35,),
    "crime": (80,),
    "documentary": (99,),
    "drama": (18,),
    "family": (10751, 10762),
    "fantasy": (14, 10765),
    "history": (36,),
    "horror": (27,),
    "music": (10402,),
    "mystery": (9648,),
    "romance": (10749,),
    "scifi": (878, 10765),
    "thriller": (53,),
    "war": (10752, 10768),
    "western": (37,),
}

# Widely seen titles the web offers to rate (P8): movies first, then series.
QUIZ_POOL: tuple[tuple[MediaType, int], ...] = (
    ("movie", 278),  # The Shawshank Redemption
    ("movie", 155),  # The Dark Knight
    ("movie", 27205),  # Inception
    ("movie", 597),  # Titanic
    ("movie", 13),  # Forrest Gump
    ("movie", 671),  # Harry Potter and the Philosopher's Stone
    ("series", 1668),  # Friends
    ("series", 1396),  # Breaking Bad
    ("series", 1399),  # Game of Thrones
    ("series", 66732),  # Stranger Things
)

GenreKey = Literal[
    "action",
    "adventure",
    "animation",
    "comedy",
    "crime",
    "documentary",
    "drama",
    "family",
    "fantasy",
    "history",
    "horror",
    "music",
    "mystery",
    "romance",
    "scifi",
    "thriller",
    "war",
    "western",
]


class GenreChip(BaseModel):
    key: GenreKey
    picked: bool  # every genre id of the chip is among the caller's picks


class QuizTitle(BaseModel):
    media_type: MediaType
    tmdb_id: int
    my_rating: float | None  # the caller's own season-0 rating, when the title is cached and posted


class OnboardingState(BaseModel):
    done: bool  # the caller has genre picks
    genres: list[GenreChip]
    quiz: list[QuizTitle]


def _unique(values: list) -> list:
    if len(set(values)) != len(values):
        raise ValueError("values must be unique")
    return values


class QuizRating(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_id: Annotated[int, Field(ge=1, le=BIGINT_MAX)]
    rating: Rating


class OnboardingAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genres: Annotated[list[GenreKey], Field(min_length=3, max_length=5), AfterValidator(_unique)]
    ratings: Annotated[list[QuizRating], Field(max_length=10)]

    @field_validator("ratings")
    @classmethod
    def _one_rating_per_title(cls, ratings: list[QuizRating]) -> list[QuizRating]:
        _unique([r.title_id for r in ratings])
        return ratings

    @property
    def genre_ids(self) -> set[int]:
        return {genre_id for key in self.genres for genre_id in GENRE_CHIPS[key]}
