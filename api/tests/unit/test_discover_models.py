from cinecircle_api.catalog.parse import ListItem
from cinecircle_api.discover.models import item_name


def _item(name: str | None) -> ListItem:
    return ListItem(1, "movie", name, None, 2020, (), None)


def test_hebrew_name_is_kept():
    assert item_name(_item("האודיסאה"), {1: "The Odyssey"}, "he") == ("האודיסאה", "he")


def test_mixed_name_with_a_hebrew_letter_is_hebrew():
    assert item_name(_item("מלחמת הכוכבים 2"), {}, "he") == ("מלחמת הכוכבים 2", "he")


def test_name_without_hebrew_falls_back_to_english():
    assert item_name(_item("Dune"), {1: "Dune: Part Two"}, "he") == ("Dune: Part Two", "en")


def test_no_english_name_uses_the_original_one_labelled_english():
    assert item_name(_item("Dune"), {}, "he") == ("Dune", "en")
    assert item_name(_item("Dune"), {1: None}, "he") == ("Dune", "en")


def test_english_lists_are_english():
    assert item_name(_item("Dune"), {1: "ignored"}, "en") == ("Dune", "en")


def test_no_name_at_all():
    assert item_name(_item(None), {}, "he") == (None, None)
    assert item_name(_item(None), {}, "en") == (None, None)
