import pytest

from cinecircle_api.people.usernames import normalize_username


def test_normalize_username():
    assert normalize_username(" Gal.B_1 ") == "gal.b_1"
    for raw in ("ab", "x" * 31, "gal!", "גל", "", "gal b", "gal\nx"):
        with pytest.raises(ValueError, match="^invalid$"):
            normalize_username(raw)
    for raw in ("ME", "search", " Me "):
        with pytest.raises(ValueError, match="^reserved$"):
            normalize_username(raw)


def test_username_length_bounds_are_accepted():
    assert normalize_username("abc") == "abc"
    assert normalize_username("x" * 30) == "x" * 30
