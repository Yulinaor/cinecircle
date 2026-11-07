from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from cinecircle_api.catalog.parse import GenreRow
from cinecircle_api.people.repository import CardRow
from cinecircle_api.posts.models import CreatePost, UpdatePost, post_card
from cinecircle_api.posts.repository import PostRow
from cinecircle_api.taste.models import Taste


def _create(**fields) -> CreatePost:
    return CreatePost.model_validate({"title_id": 1, "rating": 9, **fields})


def test_rating_must_be_half_steps():
    for rating in (1, 10, 9.5, 9, 1.5):
        assert _create(rating=rating).rating == rating
        assert UpdatePost.model_validate({"rating": rating}).rating == rating
    for rating in (0.5, 10.5, 9.25, 0, -1, "9.5", True, None, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            _create(rating=rating)
        with pytest.raises(ValidationError):
            UpdatePost.model_validate({"rating": rating})
    with pytest.raises(ValidationError):
        CreatePost.model_validate({"title_id": 1})  # rating is required


def test_opinion_length_counts_characters():
    emoji = "👍🏽" * 250  # 500 code points, 1000 UTF-16 units
    assert _create(opinion=emoji).opinion == emoji
    assert _create(opinion="  שלום  ").opinion == "שלום"
    assert _create(opinion="א" * 500).opinion == "א" * 500
    with pytest.raises(ValidationError):
        _create(opinion="א" * 501)
    assert _create(opinion="   ").opinion is None
    assert _create(opinion="").opinion is None
    assert UpdatePost.model_validate({"opinion": "  "}).opinion is None
    assert UpdatePost.model_validate({"opinion": None}).opinion is None
    with pytest.raises(ValidationError):
        UpdatePost.model_validate({"opinion": "👍" * 501})


def test_create_defaults_and_bounds():
    post = _create()
    assert (post.season_number, post.opinion, post.contains_spoilers, post.is_shared) == (
        0,
        None,
        False,
        True,
    )
    for fields in ({"title_id": 0}, {"season_number": -1}, {"season_number": 1001}):
        with pytest.raises(ValidationError):
            _create(**fields)


def test_update_forbids_title_and_season():
    with pytest.raises(ValidationError):
        UpdatePost.model_validate({"title_id": 2})
    with pytest.raises(ValidationError):
        UpdatePost.model_validate({"season_number": 1})
    for field in ("rating", "contains_spoilers", "is_shared"):
        with pytest.raises(ValidationError):
            UpdatePost.model_validate({field: None})
    assert UpdatePost.model_validate({}).model_dump(exclude_unset=True) == {}
    assert UpdatePost.model_validate({"opinion": None}).model_dump(exclude_unset=True) == {
        "opinion": None
    }


_CREATED = datetime(2026, 11, 7, 10, tzinfo=UTC)


def _row(**fields) -> PostRow:
    values = dict(
        id=5,
        title_id=3,
        season_number=0,
        rating=Decimal("9.5"),
        opinion="Epic",
        contains_spoilers=False,
        is_shared=True,
        created_at=_CREATED,
        updated_at=_CREATED,
        author=CardRow(
            id=UUID("00000000-0000-4000-8000-000000000001"),
            username="gal",
            display_name="Gal",
            avatar_url=None,
            follow_state="self",
        ),
        media_type="series",
        name_he="נפרדים",
        name_en="Severance",
        overview_he=None,
        overview_en="Office drama.",
        poster_path="/s.jpg",
        year_start=2022,
        runtime_min=None,
        imdb_rating=Decimal("8.7"),
        tmdb_rating=None,
        genres=(GenreRow(18, "Drama", "דרמה"), GenreRow(9648, "Mystery", None)),
        in_wishlist=False,
        season_name_he=None,
        season_name_en="Season 1",
        season_overview_he=None,
        season_overview_en=None,
        season_poster_path=None,
    )
    return PostRow(**{**values, **fields})


def test_post_card_shape():
    card = post_card(_row(), "he")
    assert card.author.username == "gal" and card.author.follow_state == "self"
    assert (card.title.name, card.title.name_lang) == ("נפרדים", "he")
    assert (card.title.overview, card.title.overview_lang) == ("Office drama.", "en")
    assert card.title.genres == ["דרמה", "Mystery"]
    assert card.title.poster_url == "https://image.tmdb.org/t/p/w342/s.jpg"
    assert (card.title.imdb_rating, card.title.tmdb_rating) == (8.7, None)
    assert card.rating == 9.5 and isinstance(card.rating, float)
    assert card.season is None
    assert card.edited is False
    assert card.in_wishlist is False
    assert post_card(_row(in_wishlist=True), "he").in_wishlist is True
    assert card.taste is None
    taste = Taste(fit=76, genres=["Drama"], agreement=None)
    assert post_card(_row(), "he", taste).taste == taste
    assert post_card(_row(), "en").title.genres == ["Drama", "Mystery"]


def test_post_card_season_and_edited():
    card = post_card(_row(season_number=1, updated_at=_CREATED + timedelta(seconds=1)), "he")
    assert card.season is not None
    assert (card.season.number, card.season.name, card.season.name_lang) == (1, "Season 1", "en")
    assert card.season.poster_url is None
    assert card.edited is True
