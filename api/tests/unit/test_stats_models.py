import pytest

from cinecircle_api.stats.models import bucket_of, imdb_bucket


@pytest.mark.parametrize(
    ("rating", "bucket"), [(1.0, 1), (1.5, 1), (7.5, 7), (9.5, 9), (9.99, 9), (10.0, 10)]
)
def test_bucket_of(rating, bucket):
    assert bucket_of(rating) == bucket


def test_bucket_of_stays_in_range():
    assert bucket_of(0.5) == 1  # not a stored rating, but the chart has no bucket 0
    assert bucket_of(10.4) == 10


@pytest.mark.parametrize(
    ("gap", "key"),
    [
        (-9.0, "much_lower"),
        (-2.5, "much_lower"),
        (-2.0, "much_lower"),
        (-1.99, "lower"),
        (-0.5, "lower"),
        (-0.49, "same"),
        (0.0, "same"),
        (0.49, "same"),
        (0.5, "higher"),
        (1.99, "higher"),
        (2.0, "much_higher"),
        (9.0, "much_higher"),
    ],
)
def test_imdb_bucket_edges(gap, key):
    assert imdb_bucket(gap) == key
