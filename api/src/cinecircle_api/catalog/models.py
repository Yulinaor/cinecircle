"""Response bodies for the /titles endpoints, and the row → body mapping (he/en text choice)."""

from datetime import date, datetime

from pydantic import BaseModel

from cinecircle_api.catalog.parse import Locale, MediaType, SearchResult, pick_text
from cinecircle_api.catalog.service import CachedTitle

POSTER_BASE = "https://image.tmdb.org/t/p/w342"


def poster_url(path: str | None) -> str | None:
    return f"{POSTER_BASE}{path}" if path else None


class TitleSearchItem(BaseModel):
    tmdb_id: int
    media_type: MediaType
    name: str
    year: int | None
    poster_url: str | None


class SearchResponse(BaseModel):
    results: list[TitleSearchItem]


class Genre(BaseModel):
    id: int
    name: str


class ImdbRating(BaseModel):
    rating: float
    votes: int | None


class Ratings(BaseModel):
    imdb: ImdbRating | None
    rotten_tomatoes: int | None
    metacritic: int | None
    tmdb: float | None


class Season(BaseModel):
    season_number: int
    name: str | None
    overview: str | None
    air_date: date | None
    episode_count: int | None
    poster_url: str | None


class TitleDetail(BaseModel):
    id: int
    tmdb_id: int
    media_type: MediaType
    imdb_id: str | None
    name: str | None
    name_lang: Locale | None
    overview: str | None
    overview_lang: Locale | None
    year_start: int | None
    year_end: int | None
    runtime_min: int | None
    season_count: int | None
    poster_url: str | None
    genres: list[Genre]
    ratings: Ratings
    seasons: list[Season]
    stale: bool
    fetched_at: datetime


def search_response(results: list[SearchResult]) -> SearchResponse:
    return SearchResponse(
        results=[
            TitleSearchItem(
                tmdb_id=r.tmdb_id,
                media_type=r.media_type,
                name=r.name,
                year=r.year,
                poster_url=poster_url(r.poster_path),
            )
            for r in results
        ]
    )


def title_detail(cached: CachedTitle, lang: Locale) -> TitleDetail:
    row = cached.row
    name, name_lang = pick_text(row.name_he, row.name_en, lang)
    overview, overview_lang = pick_text(row.overview_he, row.overview_en, lang)
    imdb = (
        ImdbRating(rating=float(row.imdb_rating), votes=row.imdb_votes)
        if row.imdb_rating is not None
        else None
    )
    return TitleDetail(
        id=row.id,
        tmdb_id=row.tmdb_id,
        media_type=row.media_type,
        imdb_id=row.imdb_id,
        name=name,
        name_lang=name_lang,
        overview=overview,
        overview_lang=overview_lang,
        year_start=row.year_start,
        year_end=row.year_end,
        runtime_min=row.runtime_min,
        season_count=row.season_count,
        poster_url=poster_url(row.poster_path),
        genres=[
            Genre(id=g.id, name=(g.name_he if lang == "he" and g.name_he else g.name_en))
            for g in row.genres
        ],
        ratings=Ratings(
            imdb=imdb,
            rotten_tomatoes=row.rt_score,
            metacritic=row.metacritic,
            tmdb=float(row.tmdb_rating) if row.tmdb_rating is not None else None,
        ),
        seasons=[
            Season(
                season_number=s.season_number,
                name=pick_text(s.name_he, s.name_en, lang)[0],
                overview=pick_text(s.overview_he, s.overview_en, lang)[0],
                air_date=s.air_date,
                episode_count=s.episode_count,
                poster_url=poster_url(s.poster_path),
            )
            for s in row.seasons
        ],
        stale=cached.stale,
        fetched_at=row.fetched_at,
    )
