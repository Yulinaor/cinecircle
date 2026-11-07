import pytest
from pydantic import ValidationError

from cinecircle_api.onboarding.models import GENRE_CHIPS, QUIZ_POOL, OnboardingAnswers


def _answers(**fields) -> OnboardingAnswers:
    return OnboardingAnswers.model_validate(
        {"genres": ["action", "drama", "comedy"], "ratings": [], **fields}
    )


def test_onboarding_validation():
    keys = list(GENRE_CHIPS)
    assert _answers(genres=keys[:3]).genres == keys[:3]
    assert _answers(genres=keys[:5]).genres == keys[:5]
    for genres in (keys[:2], keys[:6], [*keys[:2], "nonsense"], ["action", "action", "drama"], []):
        with pytest.raises(ValidationError):
            _answers(genres=genres)

    ten = [{"title_id": n, "rating": 8} for n in range(1, 11)]
    assert len(_answers(ratings=ten).ratings) == 10
    assert _answers(ratings=[{"title_id": 1, "rating": 1}, {"title_id": 2, "rating": 10}])
    bad_ratings = (
        [*ten, {"title_id": 11, "rating": 8}],  # 11 ratings
        [{"title_id": 1, "rating": 8}, {"title_id": 1, "rating": 9}],  # repeated title
        [{"title_id": 1, "rating": 0}],
        [{"title_id": 1, "rating": 10.5}],
        [{"title_id": 1, "rating": "9"}],
        [{"title_id": 0, "rating": 8}],
        [{"title_id": 2**63, "rating": 8}],
        [{"title_id": 1, "rating": 8, "extra": 1}],
    )
    for ratings in bad_ratings:
        with pytest.raises(ValidationError):
            _answers(ratings=ratings)
    with pytest.raises(ValidationError):
        _answers(extra="no")


def test_chips_and_pool_are_the_plan_lists():
    assert list(GENRE_CHIPS.items()) == [
        ("action", (28, 10759)),
        ("adventure", (12, 10759)),
        ("animation", (16,)),
        ("comedy", (35,)),
        ("crime", (80,)),
        ("documentary", (99,)),
        ("drama", (18,)),
        ("family", (10751, 10762)),
        ("fantasy", (14, 10765)),
        ("history", (36,)),
        ("horror", (27,)),
        ("music", (10402,)),
        ("mystery", (9648,)),
        ("romance", (10749,)),
        ("scifi", (878, 10765)),
        ("thriller", (53,)),
        ("war", (10752, 10768)),
        ("western", (37,)),
    ]
    assert QUIZ_POOL == (
        ("movie", 278),
        ("movie", 155),
        ("movie", 27205),
        ("movie", 597),
        ("movie", 13),
        ("movie", 671),
        ("series", 1668),
        ("series", 1396),
        ("series", 1399),
        ("series", 66732),
    )
