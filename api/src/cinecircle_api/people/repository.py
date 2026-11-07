"""Hand-written SQL for profiles and cards. Every function takes the request's `UserDb`
connection: it runs as the signed-in user, so RLS decides what comes back and `auth.uid()` is
the viewer. The caller owns the transaction (never commit or roll back here)."""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.people.models import FollowState, MyProfile, UserCard

_PROFILE_PKEY = "profiles_pkey"
_USERNAME_UNIQUE = "profiles_username_key"


class ProfileExists(Exception):
    """The signed-in user already has a profile."""


class UsernameTaken(Exception):
    """Another user already has this username."""


class _Unset:
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _Unset()  # "leave this field alone", as opposed to None = "clear it"


@dataclass(frozen=True)
class CardRow:
    id: UUID
    username: str
    display_name: str
    avatar_url: str | None
    follow_state: FollowState

    def card(self) -> UserCard:
        return UserCard(
            username=self.username,
            display_name=self.display_name,
            avatar_url=self.avatar_url,
            follow_state=self.follow_state,
        )


# ===== My profile ================================================================================

_MY_PROFILE = sa.text(
    "SELECT p.username, p.display_name, p.avatar_url, d.bio, COALESCE(s.locale, 'he') AS locale"
    " FROM app.profiles p"
    " LEFT JOIN app.profile_details d ON d.user_id = p.id"
    " LEFT JOIN app.user_settings s ON s.user_id = p.id"
    " WHERE p.id = auth.uid()"
)
_INSERT_PROFILE = sa.text(
    "INSERT INTO app.profiles (id, username, display_name, avatar_url)"
    " VALUES (auth.uid(), :username, :display_name, :avatar_url)"
)
_INSERT_DETAILS = sa.text(
    "INSERT INTO app.profile_details (user_id, bio) VALUES (auth.uid(), NULL)"
)
_INSERT_SETTINGS = sa.text(
    "INSERT INTO app.user_settings (user_id, locale) VALUES (auth.uid(), :locale)"
)
_SET_DISPLAY_NAME = sa.text("UPDATE app.profiles SET display_name = :value WHERE id = auth.uid()")
_SET_BIO = sa.text("UPDATE app.profile_details SET bio = :value WHERE user_id = auth.uid()")
_SET_LOCALE = sa.text("UPDATE app.user_settings SET locale = :value WHERE user_id = auth.uid()")


def get_my_profile(conn: Connection) -> MyProfile | None:
    row = conn.execute(_MY_PROFILE).one_or_none()
    return MyProfile.model_validate(row._asdict()) if row else None


def create_profile(
    conn: Connection, username: str, display_name: str, avatar_url: str | None, locale: Locale
) -> None:
    """Insert profile, details and settings together; the savepoint keeps a unique violation
    from poisoning the request transaction."""
    try:
        with conn.begin_nested():
            conn.execute(
                _INSERT_PROFILE,
                {"username": username, "display_name": display_name, "avatar_url": avatar_url},
            )
            conn.execute(_INSERT_DETAILS)
            conn.execute(_INSERT_SETTINGS, {"locale": locale})
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == _PROFILE_PKEY:
            raise ProfileExists from None
        if constraint == _USERNAME_UNIQUE:
            raise UsernameTaken from None
        raise


def update_my_profile(
    conn: Connection,
    *,
    display_name: str | _Unset = UNSET,
    bio: str | None | _Unset = UNSET,
    locale: Locale | _Unset = UNSET,
) -> None:
    """Change only the fields passed. The username is not here: it never changes."""
    if not isinstance(display_name, _Unset):
        conn.execute(_SET_DISPLAY_NAME, {"value": display_name})
    if not isinstance(bio, _Unset):
        conn.execute(_SET_BIO, {"value": bio})
    if not isinstance(locale, _Unset):
        conn.execute(_SET_LOCALE, {"value": locale})


# ===== Other people ==============================================================================


def follow_state_sql(person: str) -> str:
    """The viewer's follow state towards `person` (a profiles alias), read from the row `f`
    that `card_join_follow(person)` joins."""
    return (
        f"CASE WHEN {person}.id = auth.uid() THEN 'self'"
        "      WHEN f.status = 'accepted' THEN 'following'"
        "      WHEN f.status = 'pending' THEN 'requested'"
        "      ELSE 'none' END"
    )


def card_join_follow(person: str) -> str:
    """The viewer's own follow row (`f`) towards `person` (a profiles alias)."""
    return f" LEFT JOIN app.follows f ON f.follower_id = auth.uid() AND f.followee_id = {person}.id"


# Pieces of a card query, shared with the follow and notification lists: they all join onto
# `p` (the person on the card) and read `follow_state` from the viewer's own row towards `p`.
CARD_COLUMNS = (
    "p.id, p.username, p.display_name, p.avatar_url, " + follow_state_sql("p") + " AS follow_state"
)
CARD_JOIN_FOLLOW = card_join_follow("p")
CARD_FROM = " FROM app.profiles p" + CARD_JOIN_FOLLOW
_CARD_SELECT = "SELECT " + CARD_COLUMNS + CARD_FROM
# Raw strings: the SQL escape character is one backslash.
_SEARCH = sa.text(
    _CARD_SELECT
    + r" WHERE (p.username ILIKE :contains ESCAPE '\' OR p.display_name ILIKE :contains ESCAPE '\')"
    + r" ORDER BY (p.username ILIKE :prefix ESCAPE '\') DESC, p.username"
    + " LIMIT :limit"
)
_CARD = sa.text(_CARD_SELECT + " WHERE p.username = :username")
# Driven from profile_details so a row RLS hides yields no result at all (not a null bio).
_DETAILS = sa.text(
    "SELECT d.bio, (SELECT count(*) FROM app.posts po"
    "               WHERE po.author_id = d.user_id AND po.is_shared) AS post_count"
    " FROM app.profile_details d WHERE d.user_id = :user_id"
)
_FOLLOW_COUNTS = sa.text(
    "SELECT count(*) FILTER (WHERE followee_id = auth.uid()) AS followers,"
    "       count(*) FILTER (WHERE follower_id = auth.uid()) AS following"
    " FROM app.follows"
    " WHERE status = 'accepted' AND (followee_id = auth.uid() OR follower_id = auth.uid())"
)
_CAN_SEE = sa.text("SELECT (:user_id = auth.uid()) OR app.follows_approved(:user_id)")


def _like_escape(text: str) -> str:
    """Make `text` match literally inside a LIKE pattern that uses ESCAPE '\\'."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_cards(conn: Connection, q: str, limit: int = 20) -> list[CardRow]:
    escaped = _like_escape(q)
    rows = conn.execute(
        _SEARCH, {"contains": f"%{escaped}%", "prefix": f"{escaped}%", "limit": limit}
    )
    return [CardRow(**row._asdict()) for row in rows]


def get_card(conn: Connection, username: str) -> CardRow | None:
    row = conn.execute(_CARD, {"username": username}).one_or_none()
    return CardRow(**row._asdict()) if row else None


def get_details(conn: Connection, user_id: UUID) -> tuple[str | None, int] | None:
    """(bio, number of shared posts), or None when RLS hides this person's details."""
    row = conn.execute(_DETAILS, {"user_id": user_id}).one_or_none()
    return (row.bio, row.post_count) if row else None


def follow_counts(conn: Connection) -> tuple[int, int]:
    """(accepted followers, accepted followees) of the caller."""
    row = conn.execute(_FOLLOW_COUNTS).one()
    return row.followers, row.following


def can_see_content(conn: Connection, user_id: UUID) -> bool:
    return bool(conn.scalar(_CAN_SEE, {"user_id": user_id}))
