import math

import pytest
from pytest import approx

from cinecircle_api.taste.score import (
    GenreStat,
    TasteProfile,
    affinity,
    agreement,
    feed_fit,
    genre_fit,
    mean_of,
    quality,
    round_half_up,
    signal,
    strong_genres,
    title_fit,
)

TOL = 5e-4

# The Task 2 dataset: Dana, 20 rated titles, mean_all 0.70, no picks.
DANA = TasteProfile(
    rated=20,
    mean_all=0.70,
    picked=frozenset(),
    genres={
        28: GenreStat(2, 1.0),
        12: GenreStat(2, 0.9),
        18: GenreStat(4, 0.7),
        9648: GenreStat(1, 0.9),
        878: GenreStat(2, 0.95),
    },
)


def test_feed_example_from_spec():  # 03 section 4 "Feed"
    g = mean_of([0.82, 0.78, 0.70])
    assert g == approx(0.767, abs=TOL)
    a = agreement(8, 1.5)
    assert a == approx(0.742, abs=TOL)
    s = signal(a, 9.0)
    assert s == approx(0.694, abs=TOL)
    assert quality(8.5, None) == 0.85
    assert feed_fit(g, s, 0.85) == 76
    assert round_half_up(a * 100) == 74


def test_title_example_from_spec():  # 03 section 4 "Discover": Severance
    assert title_fit(mean_of([0.70, 0.75, 0.80]), quality(8.7, None)) == 79


def test_affinities_from_ratings():
    got = [affinity(DANA, g) for g in (28, 12, 18, 9648, 878)]
    assert got == approx([0.82, 0.78, 0.70, 0.75, 0.80], abs=TOL)
    assert affinity(DANA, 35) == approx(0.70)  # never rated: the prior
    assert strong_genres(DANA, [18, 12, 28]) == [28, 12]  # Drama 0.70 is third


def test_strong_genres_order_and_threshold():
    p = TasteProfile(
        rated=10,
        mean_all=0.5,
        picked=frozenset({1}),
        genres={1: GenreStat(1, 0.5), 2: GenreStat(10, 0.9), 3: GenreStat(10, 0.9)},
    )
    # 2 and 3 tie on affinity: the lower genre id comes first
    assert strong_genres(p, [3, 2, 1]) == [2, 3]
    assert strong_genres(p, [1]) == []  # 0.5 + 0.1 is below 0.70
    assert strong_genres(p, []) == []


def test_pick_bonus_and_cap():
    p = TasteProfile(
        rated=10, mean_all=0.95, picked=frozenset({28}), genres={28: GenreStat(5, 1.0)}
    )
    assert affinity(p, 28) == 1.0  # min(1, (5 + 2.85) / 8 + 0.1)
    q = TasteProfile(
        rated=10, mean_all=0.70, picked=frozenset({28}), genres={28: GenreStat(2, 1.0)}
    )
    assert affinity(q, 28) == approx(0.92)  # 0.82 + 0.10
    assert affinity(q, 35) == approx(0.70)  # not picked: no bonus


def test_cold_start_example():  # P2: picks {28}; rated 2 (Action-only 9, Comedy 6)
    p = TasteProfile(
        rated=2,
        mean_all=0.75,
        picked=frozenset({28}),
        genres={28: GenreStat(1, 0.9), 35: GenreStat(1, 0.6)},
    )
    assert p.state == "cold"
    assert affinity(p, 28) == approx(0.825) and affinity(p, 18) == 0.5
    assert feed_fit(genre_fit(p, [28, 18]), signal(0.5, 8.0), quality(7.0, None)) == 62


def test_states():
    locked = TasteProfile(rated=0, mean_all=None, picked=frozenset(), genres={})
    assert locked.state == "locked"
    picks_only = TasteProfile(rated=0, mean_all=None, picked=frozenset({28}), genres={})
    assert picks_only.state == "cold"
    assert affinity(picks_only, 28) == approx(0.8)
    assert affinity(picks_only, 35) == 0.5
    four = TasteProfile(rated=4, mean_all=0.7, picked=frozenset(), genres={})
    assert four.state == "cold"
    five = TasteProfile(rated=5, mean_all=0.7, picked=frozenset(), genres={})
    assert five.state == "full"
    assert affinity(five, 35) == approx(0.7)  # full: mean_all prior
    assert affinity(four, 35) == 0.5  # cold: 0.5 prior
    assert affinity(locked, 35) == 0.5  # locked: callers never ask; same as cold


def test_quality_fallbacks():
    assert quality(None, 7.9) == approx(0.79)
    assert quality(None, None) == 0.6
    assert quality(8.5, 7.0) == 0.85  # IMDb wins


def test_agreement_edges():
    assert agreement(0, None) == 0.5
    assert agreement(0, 2.0) == 0.5
    assert agreement(3, 0.0) == 0.75
    assert agreement(3, None) == 0.5
    assert agreement(9, 9.0) == approx(0.125)  # total disagreement stays above 0


def test_signal():
    assert signal(0.5, 3.0) == approx(0.5)  # neutral agreement ignores the author
    assert signal(1.0, 9.0) == approx(0.9)
    assert signal(0.0, 9.0) == approx(0.1)


def test_rounding():
    assert round_half_up(78.5) == 79
    assert round_half_up(0.5) == 1
    assert round_half_up(78.49) == 78
    assert round_half_up(76.15) == 76
    assert round_half_up(100 * (0.5 * 0.57 + 0.3 * 0.5 + 0.2 * 0.57)) == 55  # 54.9
    assert round_half_up(-3) == 0
    assert round_half_up(100.4) == 100
    assert round_half_up(250) == 100


def test_no_genres():
    # a title with no genres: the prior of an unpicked, unrated genre
    assert genre_fit(DANA, []) == approx(0.70)
    cold = TasteProfile(rated=2, mean_all=0.75, picked=frozenset({28}), genres={})
    assert genre_fit(cold, []) == 0.5


def test_genre_fit_is_mean_of_affinities():
    assert genre_fit(DANA, [28, 12, 18]) == approx(0.767, abs=TOL)


def test_mean_of_empty_raises():
    with pytest.raises(ValueError):
        mean_of([])


def test_fits_are_ints_in_range():
    for g in (0.0, 0.5, 1.0):
        for s in (0.0, 1.0):
            assert 0 <= feed_fit(g, s, 1.0) <= 100
    assert title_fit(1.0, 1.0) == 100
    assert not math.isnan(title_fit(0.0, 0.0))
    assert title_fit(0.0, 0.0) == 0
