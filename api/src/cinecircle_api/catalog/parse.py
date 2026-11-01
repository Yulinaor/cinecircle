"""Pure functions: raw TMDB/OMDb JSON → records. No I/O."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

MediaType = Literal["movie", "series"]
Locale = Literal["he", "en"]
TypeFilter = Literal["movie", "series", "all"]

_TMDB_TO_MEDIA: dict[str, MediaType] = {"movie": "movie", "tv": "series"}
_ENDED = {"Ended", "Canceled"}


@dataclass(frozen=True)
class SearchResult:
    tmdb_id: int
    media_type: MediaType
    name: str
    year: int | None
    poster_path: str | None


@dataclass(frozen=True)
class SeasonRecord:
    season_number: int
    name_en: str | None
    overview_en: str | None
    poster_path: str | None
    air_date: date | None
    episode_count: int | None


@dataclass(frozen=True)
class TitleRecord:
    tmdb_id: int
    media_type: MediaType
    imdb_id: str | None
    name_en: str
    name_he: str | None
    overview_en: str | None
    overview_he: str | None
    year_start: int | None
    year_end: int | None
    runtime_min: int | None
    season_count: int | None
    poster_path: str | None
    tmdb_rating: Decimal | None
    raw_tmdb: dict
    genre_ids: tuple[int, ...]
    seasons: tuple[SeasonRecord, ...]


@dataclass(frozen=True)
class OmdbRatings:
    imdb_rating: Decimal | None
    imdb_votes: int | None
    rt_score: int | None
    metacritic: int | None


@dataclass(frozen=True)
class GenreRow:
    id: int
    name_en: str
    name_he: str | None


def _text(value: object) -> str | None:
    """Empty strings from TMDB count as missing."""
    if isinstance(value, str):
        return value.strip() or None
    return None


def _year(value: object) -> int | None:
    text = _text(value)
    return int(text[:4]) if text and text[:4].isdigit() else None


def _date(value: object) -> date | None:
    text = _text(value)
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def parse_search(raw: dict, type_filter: TypeFilter) -> list[SearchResult]:
    results: list[SearchResult] = []
    for item in raw.get("results") or []:
        media_type = _TMDB_TO_MEDIA.get(item.get("media_type", ""))
        if media_type is None or (type_filter != "all" and media_type != type_filter):
            continue
        is_movie = media_type == "movie"
        name = _text(item.get("title" if is_movie else "name"))
        if name is None:
            continue
        year = _year(item.get("release_date" if is_movie else "first_air_date"))
        results.append(
            SearchResult(item["id"], media_type, name, year, _text(item.get("poster_path")))
        )
    return results


def _hebrew_translation(raw: dict) -> dict:
    for entry in (raw.get("translations") or {}).get("translations") or []:
        if entry.get("iso_639_1") == "he":
            return entry.get("data") or {}
    return {}


def _season(raw: dict) -> SeasonRecord:
    return SeasonRecord(
        season_number=raw["season_number"],
        name_en=_text(raw.get("name")),
        overview_en=_text(raw.get("overview")),
        poster_path=_text(raw.get("poster_path")),
        air_date=_date(raw.get("air_date")),
        episode_count=raw.get("episode_count"),
    )


def parse_title(raw: dict, media_type: MediaType) -> TitleRecord:
    is_movie = media_type == "movie"
    name_key = "title" if is_movie else "name"
    he = _hebrew_translation(raw)
    if is_movie:
        runtime = raw.get("runtime") or None  # TMDB sends 0 for "unknown"
        year_end = None
    else:
        runtimes = raw.get("episode_run_time") or []
        runtime = runtimes[0] if runtimes else None
        ended = raw.get("status") in _ENDED
        year_end = _year(raw.get("last_air_date")) if ended else None
    vote_count = raw.get("vote_count") or 0
    vote_average = raw.get("vote_average")
    tmdb_rating = (
        Decimal(str(round(vote_average, 1))) if vote_count and vote_average is not None else None
    )
    seasons = tuple(
        _season(s) for s in raw.get("seasons") or [] if (s.get("season_number") or 0) >= 1
    )
    return TitleRecord(
        tmdb_id=raw["id"],
        media_type=media_type,
        imdb_id=_text((raw.get("external_ids") or {}).get("imdb_id")),
        name_en=_text(raw.get(name_key)) or _text(raw.get(f"original_{name_key}")) or "",
        name_he=_text(he.get(name_key)),
        overview_en=_text(raw.get("overview")),
        overview_he=_text(he.get("overview")),
        year_start=_year(raw.get("release_date" if is_movie else "first_air_date")),
        year_end=year_end,
        runtime_min=runtime,
        season_count=None if is_movie else raw.get("number_of_seasons"),
        poster_path=_text(raw.get("poster_path")),
        tmdb_rating=tmdb_rating,
        raw_tmdb=raw,
        genre_ids=tuple(g["id"] for g in raw.get("genres") or []),
        seasons=seasons,
    )


def _omdb_value(raw: dict, key: str) -> str | None:
    value = _text(raw.get(key))
    return None if value in (None, "N/A") else value


def _omdb_rating(raw: dict, source: str) -> str | None:
    for rating in raw.get("Ratings") or []:
        if rating.get("Source") == source:
            value = _text(rating.get("Value"))
            return None if value in (None, "N/A") else value
    return None


def _int(text: str | None) -> int | None:
    if text is None:
        return None
    digits = text.replace(",", "")
    return int(digits) if digits.isdigit() else None


def parse_omdb(raw: dict | None) -> OmdbRatings:
    if not raw:
        return OmdbRatings(None, None, None, None)
    rating_text = _omdb_value(raw, "imdbRating")
    try:
        imdb_rating = Decimal(rating_text) if rating_text else None
    except InvalidOperation:
        imdb_rating = None
    rt = _omdb_rating(raw, "Rotten Tomatoes")
    mc = _omdb_rating(raw, "Metacritic")
    return OmdbRatings(
        imdb_rating=imdb_rating,
        imdb_votes=_int(_omdb_value(raw, "imdbVotes")),
        rt_score=_int(rt.rstrip("%")) if rt else None,
        metacritic=_int(mc.split("/")[0]) if mc else None,
    )


def merge_genre_lists(en: list[dict], he: list[dict]) -> list[GenreRow]:
    """Combine TMDB genre lists (movie + tv) by id. A Hebrew name equal to English is missing."""
    names_en = {g["id"]: _text(g.get("name")) for g in en}
    names_he = {g["id"]: _text(g.get("name")) for g in he}
    rows: list[GenreRow] = []
    for genre_id in sorted(names_en.keys() | names_he.keys()):
        name_en = names_en.get(genre_id) or names_he.get(genre_id) or str(genre_id)
        name_he = names_he.get(genre_id)
        rows.append(GenreRow(genre_id, name_en, None if name_he == name_en else name_he))
    return rows


def pick_text(he: str | None, en: str | None, lang: Locale) -> tuple[str | None, Locale | None]:
    """The text in `lang` when present, else the other one; plus the language it is in."""
    first, second = ((he, "he"), (en, "en")) if lang == "he" else ((en, "en"), (he, "he"))
    for text, text_lang in (first, second):
        if text:
            return text, text_lang
    return None, None
