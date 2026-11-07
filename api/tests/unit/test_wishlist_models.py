import pytest
from pydantic import TypeAdapter, ValidationError

from cinecircle_api.wishlist.models import SaveTitle, UpdateWishlist, WishlistSort


def _save(**fields) -> SaveTitle:
    return SaveTitle.model_validate({"title_id": 1, "source": "search", **fields})


def test_save_title_source_rules():
    assert _save(source="post", source_post_id=7).source_post_id == 7
    for source in ("search", "discover"):
        assert _save(source=source).source_post_id is None
        assert _save(source=source, source_post_id=None).source_post_id is None

    bad = [
        {"source": "post"},  # a post source needs its post
        {"source": "post", "source_post_id": None},
        {"source": "search", "source_post_id": 7},
        {"source": "discover", "source_post_id": 7},
        {"source": "x"},
        {"source": "search", "fit_at_save": 80},  # the server fills the fit, never the client
        {"title_id": 0},
        {"title_id": 2**63},
        {"source": "post", "source_post_id": 0},
        {"source": "post", "source_post_id": 2**63},
    ]
    for fields in bad:
        with pytest.raises(ValidationError):
            _save(**fields)
    with pytest.raises(ValidationError):
        SaveTitle.model_validate({"source": "search"})  # title_id is required
    with pytest.raises(ValidationError):
        SaveTitle.model_validate({"title_id": 1})  # source is required


def test_update_status_values():
    for status in ("want", "watched"):
        assert UpdateWishlist.model_validate({"status": status}).status == status
    bad = ({"status": "dropped"}, {"status": "x"}, {}, {"status": None}, {"status": "want", "x": 1})
    for body in bad:
        with pytest.raises(ValidationError):
            UpdateWishlist.model_validate(body)


def test_wishlist_sort_values():
    sort = TypeAdapter(WishlistSort)
    assert sort.validate_python("recent") == "recent"
    assert sort.validate_python("fit") == "fit"
    for bad in ("x", "", "Fit", None, 1):
        with pytest.raises(ValidationError):
            sort.validate_python(bad)
