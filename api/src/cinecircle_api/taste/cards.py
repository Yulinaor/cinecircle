"""Post cards and title pages with the viewer's Taste Match attached (plan P3).

A route that returns cards calls `post_cards`: the viewer's taste data is loaded once, and only
when at least one card is someone else's post (the viewer's own carry no score).
"""

from collections.abc import Sequence

from sqlalchemy import Connection

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.posts.models import PostCard, post_card
from cinecircle_api.posts.repository import PostRow
from cinecircle_api.taste.context import TasteContext
from cinecircle_api.taste.models import Taste
from cinecircle_api.taste.repository import title_inputs


def post_cards(
    conn: Connection, rows: Sequence[PostRow], lang: Locale, ctx: TasteContext | None = None
) -> list[PostCard]:
    """The rows as cards. Pass `ctx` when the caller already loaded one for this request."""
    if ctx is None and any(row.author.follow_state != "self" for row in rows):
        ctx = TasteContext.load(conn)
    return [post_card(row, lang, ctx.for_post(row, lang) if ctx else None) for row in rows]


def title_taste(conn: Connection, ctx: TasteContext, title_id: int, lang: Locale) -> Taste | None:
    """The Discover formula for one cached title; None when the viewer is locked."""
    if not ctx.unlocked:
        return None
    inputs = title_inputs(conn, title_id)
    if inputs is None:
        return None
    return ctx.for_title(inputs.genres, inputs.imdb_rating, inputs.tmdb_rating, lang)
